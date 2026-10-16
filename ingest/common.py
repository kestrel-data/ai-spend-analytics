"""Shared ingest helpers for loading daily usage data into BigQuery raw tables."""

import uuid
from typing import Iterable, Mapping

from google.cloud import bigquery

PROJECT = "kestrel-data-vihaan"


def replace_day(client: bigquery.Client, raw_table: str, day: str, rows: Iterable[Mapping]) -> str:
    """Atomically replace one day's rows in a raw table.

    Previously this deleted the day from the raw table and then appended
    the new rows in a separate load job. Two overlapping runs for the
    same day could both pass the DELETE before either's rows landed,
    leaving two _load_ids for that day (the cause of DATA-106, the
    doubled Sept 17 Azure OpenAI load).

    Now the new rows are loaded into a per-load staging table first, and
    the delete of the old day plus the insert of the staged rows run as
    a single BigQuery multi-statement transaction. A concurrent run for
    the same day either runs entirely before or entirely after this one;
    it can never see, or produce, a half-replaced day.

    Returns the _load_id used for this load.
    """
    load_id = str(uuid.uuid4())
    staging_table = f"{PROJECT}.scratch_employee.replace_day_stage_{load_id.replace('-', '_')}"

    rows_to_load = []
    for row in rows:
        row = dict(row)
        row["_load_id"] = load_id
        rows_to_load.append(row)

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    load_job = client.load_table_from_json(rows_to_load, staging_table, job_config=job_config)
    load_job.result()

    transaction_sql = f"""
    BEGIN
      BEGIN TRANSACTION;
      DELETE FROM `{raw_table}` WHERE usage_date = @day;
      INSERT INTO `{raw_table}`
      SELECT *, CURRENT_TIMESTAMP() AS _loaded_at
      FROM `{staging_table}`;
      COMMIT TRANSACTION;
    EXCEPTION WHEN ERROR THEN
      ROLLBACK TRANSACTION;
      RAISE USING MESSAGE = @@error.message;
    END;
    """
    query_job = client.query(
        transaction_sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("day", "DATE", day)]
        ),
    )
    query_job.result()

    client.delete_table(staging_table, not_found_ok=True)

    return load_id
