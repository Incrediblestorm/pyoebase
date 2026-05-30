"""Parallel schema synchronisation across multiple OpenEdge databases.

Usage::

    from pyoe.sync import sync_many, print_progress

    jobs = [
        ("/var/db/app1", "/schemas/app.df"),
        ("/var/db/app2", "/schemas/app.df"),
        ("/var/db/tenant_001", "/schemas/tenant.df"),
        ("/var/db/tenant_002", "/schemas/tenant.df"),
    ]

    results = sync_many(jobs, max_workers=4, on_progress=print_progress)

    failed = [r for r in results if not r.success]
    if failed:
        raise SystemExit(f"{len(failed)} database(s) failed to sync")
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

from .schema.applier import sync_schema


@dataclass
class SyncResult:
    """Outcome of a single :func:`sync_schema` call."""

    db_path: Path
    schema_df: Path
    started_at: float          # time.monotonic() at start
    finished_at: float         # time.monotonic() at end
    delta_bytes: int = 0       # size of the applied delta; 0 means no changes
    error: Optional[Exception] = None

    # ------------------------------------------------------------------

    @property
    def duration(self) -> float:
        """Wall-clock seconds taken."""
        return self.finished_at - self.started_at

    @property
    def changed(self) -> bool:
        """True if the schema was actually altered (delta was non-empty)."""
        return self.delta_bytes > 0

    @property
    def success(self) -> bool:
        return self.error is None

    def __str__(self) -> str:
        status = "OK" if self.success else "FAIL"
        change = f"{self.delta_bytes}B delta" if self.changed else "no changes"
        return (
            f"[{status}] {self.db_path.name:<30}  "
            f"{self.duration:6.1f}s  {change}"
            + (f"  ERROR: {self.error}" if self.error else "")
        )


# ---------------------------------------------------------------------------
# Built-in progress callback
# ---------------------------------------------------------------------------

_print_lock = threading.Lock()


def print_progress(result: SyncResult) -> None:
    """Ready-made *on_progress* callback that prints one line per completed DB.

    Thread-safe.  Pass it directly to :func:`sync_many`::

        sync_many(jobs, on_progress=print_progress)
    """
    with _print_lock:
        print(result, flush=True)


# ---------------------------------------------------------------------------
# sync_many
# ---------------------------------------------------------------------------

def sync_many(
    jobs: Sequence[tuple[str | Path, str | Path]],
    *,
    max_workers: int = 4,
    dlc: Optional[str] = None,
    timeout: int = 300,
    workdir: Optional[str | Path] = None,
    on_progress: Optional[Callable[[SyncResult], None]] = None,
) -> list[SyncResult]:
    """Synchronise the schema of multiple OpenEdge databases in parallel.

    Each element of *jobs* is a ``(db_path, schema_df)`` pair.  All pairs
    are submitted to a thread pool; up to *max_workers* run concurrently.
    Because the actual work is done by ``_progres`` subprocesses the Python
    GIL is not a bottleneck.

    Parameters
    ----------
    jobs:
        Sequence of ``(db_path, schema_df)`` pairs.  Each item is passed
        directly to :func:`~pyoe.schema.applier.sync_schema`.
    max_workers:
        Maximum number of databases to process simultaneously.
    dlc:
        OpenEdge installation directory.
    timeout:
        Per-database timeout in seconds passed to :func:`sync_schema`.
    workdir:
        Optional base directory for temporary files.  A per-job subdirectory
        is created inside it so that parallel jobs don't collide.  Defaults
        to the system temp directory.
    on_progress:
        Callable invoked (in the completing worker thread) immediately after
        each job finishes – whether it succeeded or failed.  Receives a
        :class:`SyncResult`.  Use :func:`print_progress` for a simple
        console reporter.

    Returns
    -------
    list[SyncResult]
        One :class:`SyncResult` per input job, in the same order as *jobs*.
        Results for failed jobs have ``result.error`` set; they do not raise.

    Examples
    --------
    Run silently, then inspect failures::

        results = sync_many(jobs, max_workers=8)
        for r in results:
            if not r.success:
                print(f"FAILED {r.db_path}: {r.error}")

    Stream progress to stdout as each DB finishes::

        results = sync_many(jobs, on_progress=print_progress)
    """
    if not jobs:
        return []

    # Build a workdir per job to prevent filename collisions between threads
    base_work = Path(workdir) if workdir else None

    # Preserve insertion order while collecting futures keyed by (db, df)
    ordered: list[SyncResult | None] = [None] * len(jobs)

    def _run_one(index: int, db_path: Path, schema_df: Path) -> SyncResult:
        job_workdir: Optional[Path] = None
        if base_work is not None:
            job_workdir = base_work / f"job_{index:04d}_{db_path.stem}"
            job_workdir.mkdir(parents=True, exist_ok=True)

        started = time.monotonic()
        error: Optional[Exception] = None
        delta_bytes = 0

        try:
            delta_file = sync_schema(
                db_path,
                schema_df,
                dlc=dlc,
                workdir=job_workdir,
                timeout=timeout,
            )
            if delta_file.exists():
                delta_bytes = delta_file.stat().st_size
        except Exception as exc:  # noqa: BLE001
            error = exc

        result = SyncResult(
            db_path=db_path,
            schema_df=schema_df,
            started_at=started,
            finished_at=time.monotonic(),
            delta_bytes=delta_bytes,
            error=error,
        )

        if on_progress is not None:
            on_progress(result)

        return result

    normalized = [(Path(db), Path(df)) for db, df in jobs]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_index = {
            pool.submit(_run_one, i, db, df): i
            for i, (db, df) in enumerate(normalized)
        }
        for future in as_completed(future_to_index):
            i = future_to_index[future]
            ordered[i] = future.result()

    return ordered  # type: ignore[return-value]  # all slots filled above
