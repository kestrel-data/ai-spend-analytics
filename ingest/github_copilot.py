"""GitHub Copilot usage and seats: called directly against the vendor API
(no landed file), since both usage and seat assignment come from the same
org-wide endpoints.

Seats has no history endpoint, so each day's load takes a fresh snapshot of
the *current* seat list and stores it dated to that load day in
raw.github_copilot_seats. On a backfill this means every day gets the same
snapshot under a different `as_of`. `created_at` lets staging exclude a seat
from days before it was assigned, but a seat removed before the load ran
drops out of every backfilled day, including days it was actually billed.
Flagged in the PR; there's no way around it without a seat-history endpoint.
"""

import datetime as dt
import os
import time

import requests

from ingest.common import replace_day

BASE_URL = "https://kestrel-copilot-api.paddoxtechnologies.com"
TOKEN = os.environ.get("COPILOT_API_TOKEN")
MAX_RETRIES = 6


def _headers() -> dict:
    return {"Authorization": f"Bearer {TOKEN}"}


def _get(path: str, params: dict) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        resp = requests.get(f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=30)
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", "5")))
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"{path} still rate limited after {MAX_RETRIES} attempts")


def _stringify(row: dict) -> dict:
    # replace_day's type inference expects CSV-style string values, with ""
    # standing in for a missing value, same as every other source.
    return {k: ("" if v is None else str(v)) for k, v in row.items()}


def _usage_rows(day: dt.date) -> list[dict]:
    rows = []
    page = 1
    while True:
        resp = _get(
            "/orgs/kestrel/copilot/usage",
            {"since": day.isoformat(), "until": day.isoformat(), "page": page},
        )
        rows.extend(resp.json()["usage"])
        if 'rel="next"' not in resp.headers.get("Link", ""):
            break
        page += 1
    return [_stringify(r) for r in rows]


def _seat_rows(day: dt.date) -> list[dict]:
    resp = _get("/orgs/kestrel/copilot/seats", {})
    rows = resp.json()["seats"]
    for row in rows:
        row["as_of"] = day.isoformat()
    return [_stringify(r) for r in rows]


def load(day: dt.date) -> None:
    replace_day("github_copilot_usage", "day", day, _usage_rows(day))
    replace_day("github_copilot_seats", "as_of", day, _seat_rows(day))
