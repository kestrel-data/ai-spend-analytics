"""Covers DATA-109: two loads racing on the same day used to both land,
because replace_day deleted and appended as two separate, non-atomic
BigQuery jobs. This checks the retry wrapper that makes the swap atomic.
"""

import os
import sys
from unittest import mock

import pytest
from google.api_core.exceptions import Conflict

os.environ.setdefault("GCP_PROJECT", "test-project")
os.environ.setdefault("LANDING_BUCKET", "test-bucket")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ingest import common  # noqa: E402


def test_run_transaction_retries_on_conflict_then_succeeds():
    """If a second load's transaction gets aborted because a first one
    committed to the same table first (BigQuery's Conflict), we retry
    instead of giving up with half the rows missing or doubled."""
    client = mock.Mock()
    failing_then_ok = mock.Mock()
    failing_then_ok.result.side_effect = [Conflict("aborted"), None]
    client.query.return_value = failing_then_ok

    with mock.patch.object(common.time, "sleep"):
        common._run_transaction(client, "SELECT 1", job_config=None, attempts=3)

    assert client.query.call_count == 2


def test_run_transaction_raises_after_exhausting_attempts():
    """A transaction that keeps losing the race surfaces the error instead
    of silently leaving the day half-written."""
    client = mock.Mock()
    always_fails = mock.Mock()
    always_fails.result.side_effect = Conflict("aborted")
    client.query.return_value = always_fails

    with mock.patch.object(common.time, "sleep"):
        with pytest.raises(Conflict):
            common._run_transaction(client, "SELECT 1", job_config=None, attempts=3)

    assert client.query.call_count == 3
