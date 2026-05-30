"""Unit tests for schema/comparator.py – subprocess calls are mocked."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyoe.exceptions import OEDBNotFoundError
from pyoe.schema.comparator import make_delta


class TestMakeDelta:
    def _setup_dbs(self, tmp_path):
        (tmp_path / "current.db").touch()
        (tmp_path / "desired.db").touch()
        return tmp_path / "current", tmp_path / "desired"

    def test_raises_if_current_missing(self, tmp_path):
        (tmp_path / "desired.db").touch()
        with pytest.raises(OEDBNotFoundError):
            make_delta(tmp_path / "current", tmp_path / "desired", tmp_path / "out.df")

    def test_raises_if_desired_missing(self, tmp_path):
        (tmp_path / "current.db").touch()
        with pytest.raises(OEDBNotFoundError):
            make_delta(tmp_path / "current", tmp_path / "desired", tmp_path / "out.df")

    def test_calls_run_abl_with_two_dbs(self, tmp_path):
        cur, des = self._setup_dbs(tmp_path)

        with patch("pyoe.schema.comparator.OERunner") as MockRunner:
            instance = MockRunner.return_value
            make_delta(cur, des, tmp_path / "delta.df")
            instance.run_abl.assert_called_once()
            call_args = instance.run_abl.call_args
            db_paths = call_args[1].get("db_paths", call_args[0][1])
            assert len(db_paths) == 2
            assert any("current" in str(p) for p in db_paths)
            assert any("desired" in str(p) for p in db_paths)

    def test_current_db_is_first(self, tmp_path):
        cur, des = self._setup_dbs(tmp_path)

        with patch("pyoe.schema.comparator.OERunner") as MockRunner:
            instance = MockRunner.return_value
            make_delta(cur, des, tmp_path / "delta.df")
            call_args = instance.run_abl.call_args
            db_paths = call_args[1].get("db_paths", call_args[0][1])
            assert "current" in str(db_paths[0])

    def test_creates_empty_file_when_run_abl_succeeds(self, tmp_path):
        cur, des = self._setup_dbs(tmp_path)
        out = tmp_path / "delta.df"

        with patch("pyoe.schema.comparator.OERunner") as MockRunner:
            MockRunner.return_value.run_abl = MagicMock()
            result = make_delta(cur, des, out)
            assert out.exists()
            assert result == out

    def test_returns_output_path(self, tmp_path):
        cur, des = self._setup_dbs(tmp_path)
        out = tmp_path / "delta.df"

        with patch("pyoe.schema.comparator.OERunner") as MockRunner:
            MockRunner.return_value.run_abl = MagicMock()
            result = make_delta(cur, des, out)
            assert result == out
