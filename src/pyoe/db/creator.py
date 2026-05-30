"""Create empty OpenEdge databases.

This module is intentionally kept independent of the schema sub-package so
that other tools (schema sync, test fixtures, Ansible modules) can import
and call :func:`create_empty_db` without pulling in schema-related code.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from .._oe import OERunner
from ..exceptions import OEDBAlreadyExistsError, OEDBNotFoundError


def db_exists(db_path: str | Path) -> bool:
    """Return True if the ``.db`` control file for *db_path* exists."""
    return Path(db_path).with_suffix(".db").exists()


def create_empty_db(
    db_path: str | Path,
    *,
    overwrite: bool = False,
    dlc: Optional[str] = None,
    structure_file: Optional[str | Path] = None,
) -> Path:
    """Create a new empty OpenEdge database.

    The database is created by copying the ``$DLC/empty`` template using
    ``procopy``, which produces a properly initialised minimal database.
    Optionally a custom structure file can be applied afterwards with
    ``prostrct`` to add extra extents before the database is used.

    Parameters
    ----------
    db_path:
        Destination path for the new database (without ``.db`` extension,
        or with it – either works).
    overwrite:
        When True, remove any existing database files at *db_path* before
        creating.  Defaults to False.
    dlc:
        OpenEdge installation directory.  Defaults to ``$DLC`` env var or
        ``/usr/dlc``.
    structure_file:
        Optional path to a ``.st`` structure file.  If provided, extra
        extents declared in the file are added with ``prostrct add`` after
        the initial database is created.

    Returns
    -------
    Path
        The path to the ``.db`` control file of the new database.

    Raises
    ------
    OEDBAlreadyExistsError
        If the database already exists and *overwrite* is False.
    OEDBNotFoundError
        If the DLC ``empty`` template is missing.
    OERuntimeError
        If ``procopy`` or ``prostrct`` exits non-zero.
    """
    db_path = Path(db_path).with_suffix("")  # strip .db if present
    runner = OERunner(dlc=dlc)

    empty_template = runner.dlc / "empty"
    if not empty_template.with_suffix(".db").exists():
        raise OEDBNotFoundError(
            f"OpenEdge empty database template not found at {empty_template}. "
            "Check your DLC installation."
        )

    if db_exists(db_path):
        if not overwrite:
            raise OEDBAlreadyExistsError(
                f"Database already exists: {db_path}.db  "
                "Use overwrite=True to replace it."
            )
        _remove_db_files(db_path)

    db_path.parent.mkdir(parents=True, exist_ok=True)

    runner.run_bin("procopy", [str(empty_template), str(db_path)])

    if structure_file is not None:
        _apply_structure(runner, db_path, structure_file)

    return db_path.with_suffix(".db")


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

_DB_SUFFIXES = (".db", ".b1", ".d1", ".lg", ".lk", ".st")


def _remove_db_files(db_path: Path) -> None:
    """Delete all files belonging to the database at *db_path*."""
    stem = db_path.stem
    parent = db_path.parent
    # Remove known fixed-suffix files
    for suffix in _DB_SUFFIXES:
        candidate = parent / (stem + suffix)
        if candidate.exists():
            candidate.unlink()
    # Remove numbered extents: stem_N.d1, stem_N.d2, stem_N.b1 …
    for candidate in parent.glob(f"{stem}_*"):
        if candidate.is_file():
            candidate.unlink()


def _apply_structure(runner: OERunner, db_path: Path, st_file: str | Path) -> None:
    """Run ``prostrct add`` to attach extra extents defined in *st_file*."""
    runner.run_bin("prostrct", ["add", str(db_path), str(st_file)])
