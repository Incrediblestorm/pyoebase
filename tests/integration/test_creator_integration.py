"""Integration tests for db/creator.py – requires OpenEdge runtime."""

import pytest
from pathlib import Path

from tests.integration.conftest import skip_no_oe, DLC
from pyoe.db.creator import create_empty_db, db_exists
from pyoe.exceptions import OEDBAlreadyExistsError


@skip_no_oe
@pytest.mark.integration
class TestCreateEmptyDbIntegration:
    def test_creates_db_file(self, tmp_path):
        result = create_empty_db(tmp_path / "newdb", dlc=DLC)
        assert result.exists()
        assert result.suffix == ".db"

    def test_creates_extent_files(self, tmp_path):
        create_empty_db(tmp_path / "newdb", dlc=DLC)
        assert (tmp_path / "newdb.b1").exists()
        assert (tmp_path / "newdb.d1").exists()

    def test_db_is_usable_by_proutil(self, tmp_path):
        """Verify the created DB passes a basic proutil integrity check."""
        import subprocess
        create_empty_db(tmp_path / "newdb", dlc=DLC)
        result = subprocess.run(
            [str(Path(DLC) / "bin" / "proutil"), str(tmp_path / "newdb"), "-C", "dbanalys"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # dbanalys should exit 0 for a healthy database
        assert result.returncode == 0

    def test_raises_on_duplicate_without_overwrite(self, tmp_path):
        create_empty_db(tmp_path / "newdb", dlc=DLC)
        with pytest.raises(OEDBAlreadyExistsError):
            create_empty_db(tmp_path / "newdb", dlc=DLC)

    def test_overwrite_replaces_db(self, tmp_path):
        create_empty_db(tmp_path / "newdb", dlc=DLC)
        result = create_empty_db(tmp_path / "newdb", overwrite=True, dlc=DLC)
        assert result.exists()
