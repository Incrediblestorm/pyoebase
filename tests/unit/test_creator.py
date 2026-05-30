"""Unit tests for db/creator.py – subprocess calls are mocked."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from pyoe.db.creator import _remove_db_files, create_empty_db, db_exists
from pyoe.exceptions import OEDBAlreadyExistsError, OEDBNotFoundError


# ---------------------------------------------------------------------------
# db_exists
# ---------------------------------------------------------------------------

class TestDbExists:
    def test_true_when_db_file_present(self, tmp_path):
        (tmp_path / "mydb.db").touch()
        assert db_exists(tmp_path / "mydb") is True

    def test_false_when_missing(self, tmp_path):
        assert db_exists(tmp_path / "mydb") is False

    def test_strips_extension(self, tmp_path):
        (tmp_path / "mydb.db").touch()
        assert db_exists(tmp_path / "mydb.db") is True


# ---------------------------------------------------------------------------
# create_empty_db
# ---------------------------------------------------------------------------

class TestCreateEmptyDb:
    def _make_runner(self, tmp_path, dlc_str):
        """Create fake DLC layout and patch OERunner."""
        dlc = Path(dlc_str)
        (dlc / "bin").mkdir(parents=True, exist_ok=True)
        (dlc / "bin" / "_progres").touch()
        (dlc / "bin" / "procopy").touch()
        empty_db = dlc / "empty.db"
        empty_db.touch()

    def test_calls_procopy(self, tmp_path):
        fake_dlc = tmp_path / "dlc"
        self._make_runner(tmp_path, str(fake_dlc))

        with patch("pyoe.db.creator.OERunner") as MockRunner:
            instance = MockRunner.return_value
            create_empty_db(tmp_path / "newdb", dlc=str(fake_dlc))
            instance.run_bin.assert_called_once()
            args = instance.run_bin.call_args
            assert args[0][0] == "procopy"
            assert str(fake_dlc / "empty") in [str(a) for a in args[0][1]]

    def test_raises_if_already_exists(self, tmp_path):
        fake_dlc = tmp_path / "dlc"
        self._make_runner(tmp_path, str(fake_dlc))
        (tmp_path / "existing.db").touch()

        with patch("pyoe.db.creator.OERunner"):
            with pytest.raises(OEDBAlreadyExistsError):
                create_empty_db(tmp_path / "existing", dlc=str(fake_dlc))

    def test_overwrite_removes_existing(self, tmp_path):
        fake_dlc = tmp_path / "dlc"
        self._make_runner(tmp_path, str(fake_dlc))
        existing_db = tmp_path / "mydb.db"
        existing_db.touch()

        with patch("pyoe.db.creator.OERunner") as MockRunner:
            MockRunner.return_value.dlc = fake_dlc
            MockRunner.return_value.run_bin = MagicMock()
            create_empty_db(tmp_path / "mydb", overwrite=True, dlc=str(fake_dlc))
            # The old .db was deleted before procopy ran
            assert not existing_db.exists()

    def test_creates_parent_dirs(self, tmp_path):
        fake_dlc = tmp_path / "dlc"
        self._make_runner(tmp_path, str(fake_dlc))
        deep_path = tmp_path / "a" / "b" / "c" / "newdb"

        with patch("pyoe.db.creator.OERunner") as MockRunner:
            MockRunner.return_value.dlc = fake_dlc
            MockRunner.return_value.run_bin = MagicMock()
            create_empty_db(deep_path, dlc=str(fake_dlc))
            assert deep_path.parent.exists()

    def test_returns_db_path(self, tmp_path):
        fake_dlc = tmp_path / "dlc"
        self._make_runner(tmp_path, str(fake_dlc))

        with patch("pyoe.db.creator.OERunner") as MockRunner:
            MockRunner.return_value.dlc = fake_dlc
            MockRunner.return_value.run_bin = MagicMock()
            result = create_empty_db(tmp_path / "newdb", dlc=str(fake_dlc))
            assert result.suffix == ".db"

    def test_strips_db_extension_from_path(self, tmp_path):
        fake_dlc = tmp_path / "dlc"
        self._make_runner(tmp_path, str(fake_dlc))

        with patch("pyoe.db.creator.OERunner") as MockRunner:
            MockRunner.return_value.dlc = fake_dlc
            MockRunner.return_value.run_bin = MagicMock()
            result = create_empty_db(tmp_path / "newdb.db", dlc=str(fake_dlc))
            assert result == tmp_path / "newdb.db"

    def test_structure_file_calls_prostrct(self, tmp_path):
        fake_dlc = tmp_path / "dlc"
        self._make_runner(tmp_path, str(fake_dlc))
        st_file = tmp_path / "custom.st"
        st_file.touch()

        with patch("pyoe.db.creator.OERunner") as MockRunner:
            instance = MockRunner.return_value
            instance.dlc = fake_dlc
            create_empty_db(tmp_path / "newdb", structure_file=st_file, dlc=str(fake_dlc))
            calls = [c[0][0] for c in instance.run_bin.call_args_list]
            assert "prostrct" in calls


# ---------------------------------------------------------------------------
# _remove_db_files
# ---------------------------------------------------------------------------

class TestRemoveDbFiles:
    def test_removes_standard_extensions(self, tmp_path):
        stem = "testdb"
        for ext in (".db", ".b1", ".d1", ".lg"):
            (tmp_path / (stem + ext)).touch()
        _remove_db_files(tmp_path / stem)
        remaining = list(tmp_path.iterdir())
        assert remaining == []

    def test_removes_numbered_extents(self, tmp_path):
        stem = "testdb"
        (tmp_path / "testdb.db").touch()
        (tmp_path / "testdb_7.d1").touch()
        (tmp_path / "testdb_10.d2").touch()
        _remove_db_files(tmp_path / stem)
        assert list(tmp_path.iterdir()) == []

    def test_leaves_other_files_alone(self, tmp_path):
        (tmp_path / "testdb.db").touch()
        other = tmp_path / "unrelated.txt"
        other.touch()
        _remove_db_files(tmp_path / "testdb")
        assert other.exists()
