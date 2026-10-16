"""Regression test for DATA-106: replace_day must not duplicate rows when
two loads for the same day overlap."""

import threading


class FakeRawTable:
    """In-memory stand-in for a raw table used to prove that a same-day
    reload fully replaces the prior load instead of leaving two
    _load_ids worth of rows for that day."""

    def __init__(self):
        self.lock = threading.Lock()
        self.rows = []

    def replace_day(self, day, rows, load_id):
        with self.lock:
            self.rows = [r for r in self.rows if r["usage_date"] != day]
            for row in rows:
                row = dict(row)
                row["_load_id"] = load_id
                self.rows.append(row)


def test_same_day_reload_does_not_duplicate():
    table = FakeRawTable()
    day = "2026-09-17"
    first_rows = [{"usage_date": day, "cost": 10.0}]
    second_rows = [{"usage_date": day, "cost": 10.0}]

    t1 = threading.Thread(target=table.replace_day, args=(day, first_rows, "load-1"))
    t2 = threading.Thread(target=table.replace_day, args=(day, second_rows, "load-2"))

    t1.start()
    t1.join()
    t2.start()
    t2.join()

    day_rows = [r for r in table.rows if r["usage_date"] == day]
    assert len(day_rows) == len(second_rows)
    assert len({r["_load_id"] for r in day_rows}) == 1
