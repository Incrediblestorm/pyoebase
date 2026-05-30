"""Unit tests for pyoe/sync.py – no OE runtime required."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from pyoe.sync import SyncResult, print_progress, sync_many


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    db_name="mydb",
    duration=1.5,
    delta_bytes=0,
    error=None,
):
    now = time.monotonic()
    return SyncResult(
        db_path=Path(f"/db/{db_name}"),
        schema_df=Path("/schemas/app.df"),
        started_at=now - duration,
        finished_at=now,
        delta_bytes=delta_bytes,
        error=error,
    )


def _fake_sync_schema_factory(delta_content: str = "", raise_for: set = frozenset()):
    """Return a sync_schema replacement that writes a delta file."""

    def _fake(db_path, schema_df, *, dlc=None, workdir=None, timeout=300, **kw):
        db_path = Path(db_path).with_suffix("")
        if db_path in raise_for or str(db_path) in raise_for:
            raise RuntimeError(f"Simulated failure for {db_path}")
        # Write delta next to the db
        delta = db_path.parent / f"{db_path.name}_schema_delta.df"
        delta.write_text(delta_content)
        return delta

    return _fake


# ---------------------------------------------------------------------------
# SyncResult
# ---------------------------------------------------------------------------

class TestSyncResult:
    def test_duration(self):
        r = _make_result(duration=3.7)
        assert abs(r.duration - 3.7) < 0.05

    def test_changed_true_when_delta_nonempty(self):
        r = _make_result(delta_bytes=512)
        assert r.changed is True

    def test_changed_false_when_delta_empty(self):
        r = _make_result(delta_bytes=0)
        assert r.changed is False

    def test_success_true_when_no_error(self):
        r = _make_result()
        assert r.success is True

    def test_success_false_when_error(self):
        r = _make_result(error=RuntimeError("boom"))
        assert r.success is False

    def test_str_ok_no_changes(self):
        r = _make_result()
        s = str(r)
        assert "[OK]" in s
        assert "no changes" in s

    def test_str_ok_with_changes(self):
        r = _make_result(delta_bytes=1024)
        s = str(r)
        assert "[OK]" in s
        assert "delta" in s

    def test_str_fail(self):
        r = _make_result(error=RuntimeError("oops"))
        s = str(r)
        assert "[FAIL]" in s
        assert "oops" in s


# ---------------------------------------------------------------------------
# sync_many – empty input
# ---------------------------------------------------------------------------

class TestSyncManyEmpty:
    def test_empty_jobs_returns_empty_list(self):
        assert sync_many([]) == []


# ---------------------------------------------------------------------------
# sync_many – result ordering
# ---------------------------------------------------------------------------

class TestSyncManyOrdering:
    def test_results_in_input_order(self, tmp_path):
        dbs = [tmp_path / f"db{i}" for i in range(5)]
        for db in dbs:
            db.with_suffix(".db").touch()

        schema_df = tmp_path / "schema.df"
        schema_df.write_text("ADD TABLE \"T\"\n")

        call_order = []

        def fake_sync(db, df, **kw):
            db = Path(db).with_suffix("")
            call_order.append(db.name)
            delta = db.parent / f"{db.name}_schema_delta.df"
            delta.write_text("")
            return delta

        with patch("pyoe.sync.sync_schema", side_effect=fake_sync):
            results = sync_many(
                [(db, schema_df) for db in dbs],
                max_workers=3,
            )

        assert [r.db_path for r in results] == dbs
        assert len(results) == 5


# ---------------------------------------------------------------------------
# sync_many – success path
# ---------------------------------------------------------------------------

class TestSyncManySuccess:
    def test_all_success_when_no_errors(self, tmp_path):
        dbs = [tmp_path / f"db{i}" for i in range(3)]
        for db in dbs:
            db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("")):
            results = sync_many([(db, schema_df) for db in dbs])

        assert all(r.success for r in results)
        assert all(r.error is None for r in results)

    def test_changed_flag_reflects_delta_content(self, tmp_path):
        db = tmp_path / "mydb"
        db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("ADD TABLE \"T\"\n")):
            results = sync_many([(db, schema_df)])

        assert results[0].changed is True
        assert results[0].delta_bytes > 0

    def test_no_change_when_delta_empty(self, tmp_path):
        db = tmp_path / "mydb"
        db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("")):
            results = sync_many([(db, schema_df)])

        assert results[0].changed is False
        assert results[0].delta_bytes == 0

    def test_duration_is_positive(self, tmp_path):
        db = tmp_path / "mydb"
        db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("")):
            results = sync_many([(db, schema_df)])

        assert results[0].duration >= 0


# ---------------------------------------------------------------------------
# sync_many – error isolation
# ---------------------------------------------------------------------------

class TestSyncManyErrorIsolation:
    def test_one_failure_does_not_cancel_others(self, tmp_path):
        dbs = [tmp_path / f"db{i}" for i in range(4)]
        for db in dbs:
            db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        # Only db1 fails
        fail_db = dbs[1].with_suffix("")

        with patch(
            "pyoe.sync.sync_schema",
            side_effect=_fake_sync_schema_factory("", raise_for={fail_db}),
        ):
            results = sync_many([(db, schema_df) for db in dbs])

        assert not results[1].success
        assert isinstance(results[1].error, RuntimeError)
        # Others succeeded
        for i in (0, 2, 3):
            assert results[i].success, f"db{i} should have succeeded"

    def test_error_stored_on_result(self, tmp_path):
        db = tmp_path / "mydb"
        db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=RuntimeError("injected")):
            results = sync_many([(db, schema_df)])

        assert results[0].error is not None
        assert "injected" in str(results[0].error)

    def test_does_not_raise_on_failure(self, tmp_path):
        db = tmp_path / "mydb"
        db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=RuntimeError("oops")):
            results = sync_many([(db, schema_df)])  # must not raise

        assert len(results) == 1


# ---------------------------------------------------------------------------
# sync_many – on_progress callback
# ---------------------------------------------------------------------------

class TestSyncManyCallback:
    def test_callback_called_once_per_job(self, tmp_path):
        n = 5
        dbs = [tmp_path / f"db{i}" for i in range(n)]
        for db in dbs:
            db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        called_with = []

        def cb(result):
            called_with.append(result)

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("")):
            sync_many([(db, schema_df) for db in dbs], on_progress=cb)

        assert len(called_with) == n

    def test_callback_receives_sync_result(self, tmp_path):
        db = tmp_path / "mydb"
        db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        received = []

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("")):
            sync_many([(db, schema_df)], on_progress=received.append)

        assert isinstance(received[0], SyncResult)

    def test_callback_called_even_on_error(self, tmp_path):
        db = tmp_path / "mydb"
        db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        received = []
        with patch("pyoe.sync.sync_schema", side_effect=RuntimeError("bang")):
            sync_many([(db, schema_df)], on_progress=received.append)

        assert len(received) == 1
        assert not received[0].success


# ---------------------------------------------------------------------------
# sync_many – max_workers
# ---------------------------------------------------------------------------

class TestSyncManyWorkers:
    def test_more_workers_than_jobs_is_fine(self, tmp_path):
        dbs = [tmp_path / f"db{i}" for i in range(2)]
        for db in dbs:
            db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("")):
            results = sync_many([(db, schema_df) for db in dbs], max_workers=20)

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_single_worker_runs_sequentially(self, tmp_path):
        dbs = [tmp_path / f"db{i}" for i in range(3)]
        for db in dbs:
            db.with_suffix(".db").touch()
        schema_df = tmp_path / "s.df"
        schema_df.write_text("")

        with patch("pyoe.sync.sync_schema", side_effect=_fake_sync_schema_factory("")):
            results = sync_many([(db, schema_df) for db in dbs], max_workers=1)

        assert all(r.success for r in results)


# ---------------------------------------------------------------------------
# print_progress (smoke test)
# ---------------------------------------------------------------------------

class TestPrintProgress:
    def test_print_progress_does_not_raise(self, capsys):
        r = _make_result(delta_bytes=256)
        print_progress(r)
        out = capsys.readouterr().out
        assert "OK" in out

    def test_print_progress_shows_fail(self, capsys):
        r = _make_result(error=RuntimeError("problem"))
        print_progress(r)
        out = capsys.readouterr().out
        assert "FAIL" in out
