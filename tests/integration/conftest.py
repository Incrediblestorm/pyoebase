"""Integration test fixtures – require a live OpenEdge installation."""

import os
import shutil
from pathlib import Path

import pytest

DLC = os.environ.get("DLC", "/usr/dlc")
SPORTS2000_SRC = Path(DLC) / "sports2000"

# Schema file locations searched in order when resolving MAIN_DF_SRC.
_MAIN_DF_CANDIDATES = [
    Path("/tmp/main.df"),
    Path("/var/db/schema/11.10.0-main.df"),
    Path("/var/db/schema/10.27.27-main.df"),
]

# Glob pattern for all sports2000 extent files
_SPORTS_GLOBS = ["sports2000.db", "sports2000.b1", "sports2000*.d*"]


def _oe_available() -> bool:
    """Return True if the OpenEdge runtime is accessible."""
    return (Path(DLC) / "bin" / "_progres").exists()


def _sports2000_available() -> bool:
    return _oe_available() and SPORTS2000_SRC.with_suffix(".db").exists()


def _main_df_available() -> bool:
    return _oe_available() and any(p.exists() for p in _MAIN_DF_CANDIDATES)


def _main_df_path() -> Path:
    for p in _MAIN_DF_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("No main.df schema file found")


skip_no_oe = pytest.mark.skipif(not _oe_available(), reason="OpenEdge runtime not found")
skip_no_sports = pytest.mark.skipif(
    not _sports2000_available(), reason="sports2000 database not found"
)
skip_no_main_df = pytest.mark.skipif(
    not _main_df_available(), reason="main.df schema file not found"
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


@pytest.fixture(scope="session")
def main_df_path():
    """Return the path to the main.df schema source file."""
    return _main_df_path()


@pytest.fixture(scope="session")
def main_schema_db(tmp_path_factory, main_df_path):
    """Session-scoped: one empty DB with main.df loaded – shared across tests."""
    from pyoe.db.creator import create_empty_db
    from pyoe.schema.applier import apply_df

    dest = tmp_path_factory.mktemp("main_schema")
    db = create_empty_db(dest / "main", dlc=DLC).with_suffix("")
    apply_df(db, main_df_path, dlc=DLC, timeout=600)
    return db


@pytest.fixture
def fresh_db(tmp_path):
    """Create a fresh empty database for each test."""
    from pyoe.db.creator import create_empty_db
    return create_empty_db(tmp_path / "testdb", dlc=DLC)
