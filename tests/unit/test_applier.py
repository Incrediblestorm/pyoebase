"""Unit tests for schema/applier.py – subprocess calls are mocked."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pyoe.exceptions import OEDBNotFoundError, OESchemaError
from pyoe.schema.applier import apply_df, sync_schema


class TestApplyDf:
    def test_raises_if_db_missing(self, tmp_path, sample_df_file):
        with pytest.raises(OEDBNotFoundError):
            apply_df(tmp_path / "nonexistent", sample_df_file)

    def test_raises_if_df_missing(self, tmp_path):
        (tmp_path / "mydb.db").touch()
        with pytest.raises(OESchemaError):
            apply_df(tmp_path / "mydb", tmp_path / "missing.df")

    def test_skips_empty_df(self, tmp_path, empty_df_file):
        (tmp_path / "mydb.db").touch()
        with patch("pyoe.schema.applier.OERunner") as MockRunner:
            apply_df(tmp_path / "mydb", empty_df_file)
            MockRunner.return_value.run_abl.assert_not_called()

    def test_calls_run_abl(self, tmp_path, sample_df_file):
        (tmp_path / "mydb.db").touch()
        with patch("pyoe.schema.applier.OERunner") as MockRunner:
            instance = MockRunner.return_value
            apply_df(tmp_path / "mydb", sample_df_file)
            instance.run_abl.assert_called_once()

    def test_df_path_passed_as_param(self, tmp_path, sample_df_file):
        (tmp_path / "mydb.db").touch()
        with patch("pyoe.schema.applier.OERunner") as MockRunner:
            instance = MockRunner.return_value
            apply_df(tmp_path / "mydb", sample_df_file)
            call_args = instance.run_abl.call_args
            param = call_args[1].get("param", call_args[0][2] if len(call_args[0]) > 2 else "")
            assert str(sample_df_file) in param


class TestSyncSchema:
    def _patch_all(self):
        """Return a context manager that patches all OE I/O."""
        patches = [
            patch("pyoe.schema.applier.create_empty_db"),
            patch("pyoe.schema.applier.apply_df"),
            patch("pyoe.schema.applier.make_delta"),
        ]
        return patches

    def test_raises_if_target_db_missing(self, tmp_path, sample_df_file):
        with pytest.raises(OEDBNotFoundError):
            sync_schema(tmp_path / "nonexistent", sample_df_file)

    def test_raises_if_schema_df_missing(self, tmp_path):
        (tmp_path / "mydb.db").touch()
        with pytest.raises(OESchemaError):
            sync_schema(tmp_path / "mydb", tmp_path / "missing.df")

    def test_full_workflow_order(self, tmp_path, sample_df_file):
        (tmp_path / "mydb.db").touch()

        call_order = []

        def fake_create_empty_db(path, **kw):
            call_order.append("create_empty_db")
            # Simulate creation so apply_df doesn't raise DBNotFound
            Path(path).with_suffix(".db").touch()

        def fake_apply_df(db, df, **kw):
            call_order.append("apply_df")

        def fake_make_delta(cur, des, out, **kw):
            call_order.append("make_delta")
            # Write a non-empty delta so apply_df is called
            Path(out).write_text("ADD TABLE \"NewTable\"\n")
            return Path(out)

        with patch("pyoe.schema.applier.create_empty_db", side_effect=fake_create_empty_db), \
             patch("pyoe.schema.applier.apply_df", side_effect=fake_apply_df), \
             patch("pyoe.schema.applier.make_delta", side_effect=fake_make_delta):
            sync_schema(tmp_path / "mydb", sample_df_file)

        assert call_order == ["create_empty_db", "apply_df", "make_delta", "apply_df"]

    def test_no_apply_when_delta_empty(self, tmp_path, sample_df_file):
        (tmp_path / "mydb.db").touch()

        def fake_create(path, **kw):
            Path(path).with_suffix(".db").touch()

        with patch("pyoe.schema.applier.create_empty_db", side_effect=fake_create), \
             patch("pyoe.schema.applier.make_delta") as mock_delta, \
             patch("pyoe.schema.applier.apply_df") as mock_apply:

            # Delta file is empty
            def make_empty_delta(cur, des, out, **kw):
                Path(out).write_text("")
                return Path(out)

            mock_delta.side_effect = make_empty_delta
            sync_schema(tmp_path / "mydb", sample_df_file)

            # apply_df called once (loading schema into temp DB), not twice
            assert mock_apply.call_count == 1
