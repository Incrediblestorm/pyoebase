"""Dump an OpenEdge database schema to a .df file."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .._oe import OERunner, _ABL_DUMP_DF
from ..exceptions import OEDBNotFoundError


def dump_schema(
    db_path: str | Path,
    output_file: str | Path,
    *,
    tables: str = "ALL",
    codepage: str = "",
    dlc: Optional[str] = None,
    timeout: int = 120,
) -> Path:
    """Dump the schema of an OpenEdge database to a ``.df`` file.

    Parameters
    ----------
    db_path:
        Path to the database (with or without ``.db`` extension).
    output_file:
        Destination ``.df`` file.  Parent directories are created if they
        do not exist.
    tables:
        Comma-separated list of table names to dump, or ``"ALL"`` (default)
        to dump every user table.
    codepage:
        Output codepage (e.g. ``"UTF-8"``).  Defaults to the database's
        native codepage.
    dlc:
        OpenEdge installation directory.
    timeout:
        Maximum seconds to wait for the batch process.

    Returns
    -------
    Path
        The path to the written ``.df`` file.

    Raises
    ------
    OEDBNotFoundError
        If the database ``.db`` file does not exist.
    OERuntimeError
        If the OpenEdge batch process exits with a non-zero return code.
    """
    db_path = Path(db_path).with_suffix("")
    if not db_path.with_suffix(".db").exists():
        raise OEDBNotFoundError(f"Database not found: {db_path}.db")

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    runner = OERunner(dlc=dlc)
    param = f"{tables}|{output_file}|{codepage}"
    runner.run_abl(
        _ABL_DUMP_DF,
        db_paths=[db_path],
        param=param,
        timeout=timeout,
    )

    return output_file
