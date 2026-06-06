"""Compare two OpenEdge database schemas and produce a delta .df file.

The comparison uses ``prodict/dump_inc.p`` via its persistent-handle API
(the only supported way to call it non-interactively on OE 12.x).

Connection convention used by dump_inc.p
-----------------------------------------
* ``DICTDB``  – the **desired** schema (what you want it to become)
* ``DICTDB2`` – the **current** database (what you have now)

The generated ``.df`` contains the statements needed to bring *DICTDB2* (current)
in line with *DICTDB* (desired).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .._oe import OERunner, _ABL_DUMP_INC
from ..exceptions import OEDBNotFoundError


def make_delta(
    current_db: str | Path,
    desired_db: str | Path,
    output_file: str | Path,
    *,
    tables: str = "ALL",
    codepage: str = "",
    dlc: Optional[str] = None,
    timeout: int = 300,
) -> Path:
    """Generate an incremental ``.df`` that transforms *current_db* into *desired_db*.

    Connects both databases in single-user mode and runs
    ``prodict/dump_inc.p`` to compute the delta.  The resulting file
    contains only the ``ADD``, ``UPDATE``, ``DELETE``, and ``RENAME``
    statements required – it does not re-declare unchanged objects.

    Parameters
    ----------
    current_db:
        The database whose schema will be altered (DICTDB).
    desired_db:
        The database that defines the target schema (DICTDB2).
    output_file:
        Where to write the resulting delta ``.df``.
    tables:
        Comma-separated list of table names to include, or ``"ALL"``
        (default) to compare every user table.
    codepage:
        Output codepage (e.g. ``"UTF-8"``).  Defaults to the ``-cpstream``
        value in ``$DLC/startup.pf``.
    dlc:
        OpenEdge installation directory.
    timeout:
        Maximum seconds for the batch process.

    Returns
    -------
    Path
        Path to the written delta ``.df`` file.  The file may be empty if
        no schema differences were detected.

    Raises
    ------
    OEDBNotFoundError
        If either database ``.db`` file does not exist.
    OERuntimeError
        If the OpenEdge batch process exits non-zero.
    """
    current_db = Path(current_db).with_suffix("")
    desired_db = Path(desired_db).with_suffix("")

    for db in (current_db, desired_db):
        if not db.with_suffix(".db").exists():
            raise OEDBNotFoundError(f"Database not found: {db}.db")

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    runner = OERunner(dlc=dlc)
    if not codepage:
        codepage = runner.cpstream
    # dump_inc.p convention: DICTDB=desired (command-line -db), DICTDB2=current (CONNECT inside ABL).
    # The delta contains changes to apply to DICTDB2 (current) to make it look like DICTDB (desired).
    param = f"{current_db}|{output_file}|{codepage}"
    runner.run_abl(
        _ABL_DUMP_INC,
        db_paths=[desired_db],
        param=param,
        timeout=timeout,
    )

    # Ensure the file exists even when schemas are identical
    if not output_file.exists():
        output_file.touch()

    return output_file
