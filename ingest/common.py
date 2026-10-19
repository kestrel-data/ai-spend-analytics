"""Shared load logic for every source.

A load replaces whole days in a raw table: it loads the file's rows into a
throwaway table, then swaps them into the day with one atomic multi-statement
transaction (delete the day, insert the new rows, commit). Two loads for the
same day can therefore never both land: whichever transaction commits second
sees the first one's rows, deletes them, and inserts only its own. Columns
the file adds are added to the raw table rather than dropped, so a vendor
renaming a column shows up as a new column, and the cleaned models decide
what to do with it.
"""

import csv
import datetime as dt
import io
import os
import random
import time
import uuid

from google.api_core.exceptions import Conflict, NotFound
from google.cloud import bigquery, storage

PROJECT = os.environ["GCP_PROJECT"]
BUCKET = os.environ["LANDING_BUCKET"]

TYPES = {"INTEGER": int, "INT64": int, "FLOAT": float, "FLOAT64": float}


def days(start: dt.date, end: dt.date):
    while start <= end:
        yield start
        start += dt.timedelta(days=1)


def read_landed_csv(path: str) -> list[dict]:
    blob = storage.Client(project=PROJECT).bucket(BUCKET).blob(path)
    if not blob.exists():
        raise FileNotFoundError(f"gs://{BUCKET}/{path} has not landed")
    return list(csv.DictReader(io.StringIO(blob.download_as_text())))


def _date(value: str) -> dt.date:
    if len(value) != 10:
        raise ValueError(value)
    return dt.date.fromisoformat(value)


def _infer(rows: list[dict], column: str) -> str:
    values = [r[column] for r in rows if r[column] != ""]
    for kind, cast in (("INT64", int), ("NUMERIC", float), ("DATE", _date)):
        try:
            for v in values:
                cast(v)
            return kind
        except ValueError:
            continue
    return "STRING"


def _typed(rows: list[dict], schema: list[bigquery.SchemaField]):
    types = {f.name: f.field_type for f in schema}
    out_schema = list(schema)
    for column in rows[0] if rows else []:
        if column not in types:
            types[column] = _infer(rows, column)
            out_schema.append(bigquery.SchemaField(column, types[column]))
    typed = [
        {k: (None if v == "" else TYPES.get(types[k], str)(v)) for k, v in row.items()}
        for row in rows
    ]
    return typed, out_schema


def _run_transaction(client: bigquery.Client, sql: str, job_config, attempts: int = 5) -> None:
    """Run a multi-statement transaction, retrying if BigQuery aborts it
    because another transaction committed against the same table first."""
    for attempt in range(attempts):
        try:
            client.query(sql, job_config=job_config).result()
            return
        except Conflict:
            if attempt == attempts - 1:
                raise
            time.sleep(random.uniform(0.2, 1.0) * (attempt + 1))


def replace_day(table: str, date_column: str, day: dt.date, rows: list[dict]) -> str:
    client = bigquery.Client(project=PROJECT)
    table_id = f"{PROJECT}.raw.{table}"
    load_id = uuid.uuid4().hex
    loaded_at = dt.datetime.now(dt.timezone.utc).isoformat()

    try:
        existing = client.get_table(table_id).schema
        table_exists = True
    except NotFound:
        existing = [
            bigquery.SchemaField("_load_id", "STRING"),
            bigquery.SchemaField("_loaded_at", "TIMESTAMP"),
        ]
        table_exists = False

    if not rows:
        if table_exists:
            _run_transaction(
                client,
                f"DELETE FROM `{table_id}` WHERE {date_column} = @day",
                bigquery.QueryJobConfig(
                    query_parameters=[bigquery.ScalarQueryParameter("day", "DATE", day)]
                ),
            )
        print(f"{table} {day}: 0 rows, load {load_id}")
        return load_id

    typed, schema = _typed(rows, existing)
    for row in typed:
        row["_load_id"] = load_id
        row["_loaded_at"] = loaded_at

    if not table_exists:
        # The very first load for a source creates the table; there is
        # nothing else writing to it yet, so a plain append is safe.
        client.load_table_from_json(
            typed,
            table_id,
            job_config=bigquery.LoadJobConfig(
                schema=schema,
                write_disposition="WRITE_APPEND",
                schema_update_options=["ALLOW_FIELD_ADDITION"],
            ),
        ).result()
        print(f"{table} {day}: {len(rows)} rows, load {load_id}")
        return load_id

    # A vendor file can add columns. Add them to the real table up front so
    # the transaction's INSERT can name every column.
    existing_names = {f.name for f in existing}
    for field in schema:
        if field.name not in existing_names:
            try:
                client.query(
                    f"ALTER TABLE `{table_id}` ADD COLUMN {field.name} {field.field_type}"
                ).result()
            except Conflict:
                pass  # another concurrent load already added it

    tmp_table_id = f"{PROJECT}.raw._tmp_{table}_{load_id}"
    try:
        client.load_table_from_json(
            typed,
            tmp_table_id,
            job_config=bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE"),
        ).result()

        columns = ", ".join(f.name for f in schema)
        _run_transaction(
            client,
            f"""
            BEGIN TRANSACTION;
            DELETE FROM `{table_id}` WHERE {date_column} = @day;
            INSERT INTO `{table_id}` ({columns})
            SELECT {columns} FROM `{tmp_table_id}`;
            COMMIT TRANSACTION;
            """,
            bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("day", "DATE", day)]
            ),
        )
    finally:
        client.delete_table(tmp_table_id, not_found_ok=True)

    print(f"{table} {day}: {len(rows)} rows, load {load_id}")
    return load_id
