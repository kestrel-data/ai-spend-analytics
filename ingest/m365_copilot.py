"""Microsoft 365 Copilot usage report: one CSV per day, per user and app.

Users are identified by their HR employee id, not their email, because the
tenant exports with concealed user names.
"""

import datetime as dt

from ingest.common import read_landed_csv, replace_day


def load(day: dt.date) -> None:
    rows = read_landed_csv(f"m365_copilot/usage_{day.isoformat()}.csv")
    replace_day("m365_copilot_usage", "day", day, rows)
