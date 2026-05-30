"""Apply a .df schema file to an OpenEdge database.

Also provides the high-level :func:`sync_schema` function that orchestrates
the full "make a database's schema match a .df file" workflow.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from .._oe import OERunner, _ABL_LOAD_DF
from ..db.creator import create_empty_db
from ..exceptions import OEDBNotFoundError, OESchemaError


def apply_df(
    db_path: str | Path,
    df_file: str | Path,
    *,
    dlc: Optional[str] = None,
    timeout: int = 300,
) -> None:
    """Apply a ``.df`` schema file to an existing OpenEdge database.

    Runs ``prodict/load_df_silent.r`` in batch single-user mode.  This is
    the standard OpenEdge mechanism for loading schema changes and handles
    all statement types (``ADD``, ``UPDATE``, ``DELETE``, ``RENAME``).

    Parameters
    ----------
    db_path:
        Target database (with or without ``.db`` extension).
    df_file:
        Path to the ``.df`` file to load.
    dlc:
        OpenEdge installation directory.
    timeout:
        Maximum seconds for the batch process.

    Raises
    ------
    OEDBNotFoundError
        If the database ``.db`` file does not exist.
    OESchemaError
        If the ``.df`` file does not exist or is empty.
    OERuntimeError
        If the OpenEdge batch process exits non-zero.
    """
    db_path = Path(db_path).with_suffix("")
    if not db_path.with_suffix(".db").exists():
        raise OEDBNotFoundError(f"Database not found: {db_path}.db")

    df_file = Path(df_file)
    if not df_file.exists():
        raise OESchemaError(f".df file not found: {df_file}")
    if df_file.stat().st_size == 0:
        return  # nothing to do

    runner = OERunner(dlc=dlc)
    runner.run_abl(
        _ABL_LOAD_DF,
        db_paths=[db_path],
        param=str(df_file),
        timeout=timeout,
    )


def sync_schema(
    target_db: str | Path,
    schema_df: str | Path,
    *,
    dlc: Optional[str] = None,
    workdir: Optional[str | Path] = None,
    keep_workdir: bool = False,
    timeout: int = 300,
) -> Path:
    """Alter *target_db* so its schema matches the definitions in *schema_df*.

    This is the primary high-level entry point for schema synchronisation.
    The workflow is:

    1. Create a temporary empty database.
    2. Load *schema_df* into it (this becomes the "desired" schema DB).
    3. Run ``prodict/dump_inc.r`` connected to both *target_db* and the
       temporary DB to generate a delta ``.df``.
    4. Apply the delta to *target_db*.

    No changes are made to *target_db* if the schemas are already identical
    (the delta will be empty).

    Parameters
    ----------
    target_db:
        The database to be altered.
    schema_df:
        A ``.df`` file that defines the desired schema.
    dlc:
        OpenEdge installation directory.
    workdir:
        Directory in which to create temporary files.  A system temp
        directory is used if not specified.
    keep_workdir:
        When True, the temporary directory is not deleted on exit.
        Useful for debugging failed syncs.
    timeout:
        Per-step timeout in seconds.

    Returns
    -------
    Path
        Path to the delta ``.df`` file that was applied (may be empty if no
        changes were needed).

    Raises
    ------
    OEDBNotFoundError
        If *target_db* or the OE empty template does not exist.
    OESchemaError
        If *schema_df* does not exist.
    OERuntimeError
        If any OpenEdge batch process exits non-zero.
    """
    # Deferred import to avoid circular dependency
    from .comparator import make_delta

    target_db = Path(target_db).with_suffix("")
    if not target_db.with_suffix(".db").exists():
        raise OEDBNotFoundError(f"Target database not found: {target_db}.db")

    schema_df = Path(schema_df)
    if not schema_df.exists():
        raise OESchemaError(f"Schema .df file not found: {schema_df}")

    # Always produce a delta file that outlives the temp workdir.
    # Named after the target DB so callers can correlate it.
    delta_out = target_db.parent / f"{target_db.name}_schema_delta.df"

    use_temp = workdir is None and not keep_workdir
    work_path = Path(tempfile.mkdtemp()) if use_temp else Path(workdir or target_db.parent / f"{target_db.name}_sync_work")
    work_path.mkdir(parents=True, exist_ok=True)

    try:
        desired_db = work_path / "desired"
        create_empty_db(desired_db, dlc=dlc)
        apply_df(desired_db, schema_df, dlc=dlc, timeout=timeout)

        delta_file = work_path / "delta.df"
        make_delta(target_db, desired_db, delta_file, dlc=dlc, timeout=timeout)

        if delta_file.stat().st_size > 0:
            apply_df(target_db, delta_file, dlc=dlc, timeout=timeout)

        shutil.copy2(delta_file, delta_out)
        return delta_out
    finally:
        if use_temp:
            shutil.rmtree(work_path, ignore_errors=True)

