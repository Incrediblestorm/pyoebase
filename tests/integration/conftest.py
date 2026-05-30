"""Integration test fixtures – require a live OpenEdge installation."""

import os
import shutil
from pathlib import Path

import pytest

DLC = os.environ.get("DLC", "/usr/dlc")
SPORTS2000_SRC = Path(DLC) / "sports2000"

# Glob pattern for all sports2000 extent files
_SPORTS_GLOBS = ["sports2000.db", "sports2000.b1", "sports2000*.d*"]


def _oe_available() -> bool:
    """Return True if the OpenEdge runtime is accessible."""
    return (Path(DLC) / "bin" / "_progres").exists()


def _sports2000_available() -> bool:
    return _oe_available() and SPORTS2000_SRC.with_suffix(".db").exists()


skip_no_oe = pytest.mark.skipif(not _oe_available(), reason="OpenEdge runtime not found")
skip_no_sports = pytest.mark.skipif(
    not _sports2000_available(), reason="sports2000 database not found"
)


@pytest.fixture(scope="session")
def sports2000_db(tmp_path_factory):
    """Copy sports2000 to a session-scoped temp dir and return the DB path."""
    dest = tmp_path_factory.mktemp("sports2000")
    src = SPORTS2000_SRC.parent
    for pattern in _SPORTS_GLOBS:
        for f in src.glob(pattern):
            shutil.copy2(f, dest / f.name)
    return dest / "sports2000"


@pytest.fixture
def fresh_db(tmp_path):
    """Create a fresh empty database for each test."""
    from pyoe.db.creator import create_empty_db
    return create_empty_db(tmp_path / "testdb", dlc=DLC)
