"""Unit tests for schema/dumper.py – subprocess calls are mocked."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyoe.exceptions import OEDBNotFoundError
from pyoe.schema.dumper import dump_schema


class TestDumpSchema:
    def test_raises_if_db_missing(self, tmp_path):
        with pytest.raises(OEDBNotFoundError):
            dump_schema(tmp_path / "nonexistent", tmp_path / "out.df")

    def test_calls_run_abl(self, tmp_path):
        db = tmp_path / "mydb.db"
        db.touch()
        out = tmp_path / "out.df"

        with patch("pyoe.schema.dumper.OERunner") as MockRunner:
            instance = MockRunner.return_value
            dump_schema(tmp_path / "mydb", out)
            instance.run_abl.assert_called_once()
            _, kwargs = instance.run_abl.call_args
            # db_paths should contain the db stem
            db_paths = instance.run_abl.call_args[1].get(
                "db_paths", instance.run_abl.call_args[0][1]
            )
            assert any("mydb" in str(p) for p in db_paths)

    def test_creates_parent_dirs(self, tmp_path):
        db = tmp_path / "mydb.db"
        db.touch()
        out = tmp_path / "subdir" / "out.df"

        with patch("pyoe.schema.dumper.OERunner") as MockRunner:
            MockRunner.return_value.run_abl = MagicMock()
            dump_schema(tmp_path / "mydb", out)
            assert out.parent.exists()

    def test_returns_output_path(self, tmp_path):
        db = tmp_path / "mydb.db"
        db.touch()
        out = tmp_path / "out.df"

        with patch("pyoe.schema.dumper.OERunner") as MockRunner:
            MockRunner.return_value.run_abl = MagicMock()
            result = dump_schema(tmp_path / "mydb", out)
            assert result == out

    def _get_param(self, mock_instance):
        call_kwargs = mock_instance.run_abl.call_args
        return call_kwargs[1].get("param", call_kwargs[0][2] if len(call_kwargs[0]) > 2 else "")

    def test_default_tables_is_ALL(self, tmp_path):
        db = tmp_path / "mydb.db"
        db.touch()
        out = tmp_path / "out.df"

        with patch("pyoe.schema.dumper.OERunner") as MockRunner:
            instance = MockRunner.return_value
            dump_schema(tmp_path / "mydb", out)
            param = self._get_param(instance)
            assert param.startswith("ALL|")

    def test_custom_tables_in_param(self, tmp_path):
        db = tmp_path / "mydb.db"
        db.touch()
        out = tmp_path / "out.df"

        with patch("pyoe.schema.dumper.OERunner") as MockRunner:
            instance = MockRunner.return_value
            dump_schema(tmp_path / "mydb", out, tables="Customer,Order")
            param = self._get_param(instance)
            assert param.startswith("Customer,Order|")

    def test_codepage_included_in_param(self, tmp_path):
        db = tmp_path / "mydb.db"
        db.touch()
        out = tmp_path / "out.df"

        with patch("pyoe.schema.dumper.OERunner") as MockRunner:
            instance = MockRunner.return_value
            dump_schema(tmp_path / "mydb", out, codepage="UTF-8")
            param = self._get_param(instance)
            assert "UTF-8" in param
