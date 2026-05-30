# pyoe.sync — Parallel multi-database sync

```python
from pyoe.sync import sync_many, print_progress, SyncResult
```

---

## `sync_many`

```python
def sync_many(
    jobs: Sequence[tuple[str | Path, str | Path]],
    *,
    max_workers: int = 4,
    dlc: str | None = None,
    timeout: int = 300,
    workdir: str | Path | None = None,
    on_progress: Callable[[SyncResult], None] | None = None,
) -> list[SyncResult]
```

Synchronise the schema of multiple OpenEdge databases in parallel.

Each job calls [`sync_schema`](schema.md#sync_schema) in its own thread. Because the actual work is done by `_progres` subprocesses, threads do not compete for the Python GIL — true parallelism is achieved up to the limit set by `max_workers`.

Results are returned in the **same order as the input jobs** regardless of which database finishes first.

**Errors are captured, not raised.** A failed job sets `result.error` and processing of the remaining databases continues. Check `result.success` after the call returns.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `jobs` | `Sequence[tuple[db, df]]` | — | Each tuple is `(db_path, schema_df)` passed to `sync_schema`. |
| `max_workers` | `int` | `4` | Maximum number of databases processed simultaneously. |
| `dlc` | `str \| None` | `$DLC` | OpenEdge installation directory, applied to all jobs. |
| `timeout` | `int` | `300` | Per-database timeout in seconds. |
| `workdir` | `str \| Path \| None` | `None` | Base directory for temp files. A subdirectory is created per job to avoid collisions. Uses system temp if unset. |
| `on_progress` | `Callable \| None` | `None` | Called in the completing worker thread immediately after each job finishes. Receives a [`SyncResult`](#syncresult). |

**Returns** — `list[SyncResult]`, one entry per input job, in input order.

**Never raises** — all exceptions are captured in `SyncResult.error`.

**Examples**

```python
from pyoe.sync import sync_many, print_progress

jobs = [
    ("/var/db/tenant_001", "/schemas/app.df"),
    ("/var/db/tenant_002", "/schemas/app.df"),
    ("/var/db/tenant_003", "/schemas/app.df"),
]

# Stream progress as each database completes
results = sync_many(jobs, max_workers=4, on_progress=print_progress)

# Example output (order depends on which DB finishes first):
# [OK] tenant_001                          3.2s  1248B delta
# [OK] tenant_003                          3.5s  no changes
# [OK] tenant_002                          4.1s  512B delta
```

```python
# Check for failures after the run
failed = [r for r in results if not r.success]
if failed:
    for r in failed:
        print(f"FAILED {r.db_path.name}: {r.error}")
    raise SystemExit(f"{len(failed)} database(s) failed")
```

```python
# Collect timing statistics
total_changed = sum(1 for r in results if r.changed)
total_time    = sum(r.duration for r in results)
slowest       = max(results, key=lambda r: r.duration)

print(f"{total_changed}/{len(results)} databases had schema changes")
print(f"Slowest: {slowest.db_path.name} ({slowest.duration:.1f}s)")
```

```python
# Use a custom callback to write a log file
import csv, sys

def csv_logger(result, writer=csv.writer(sys.stdout)):
    writer.writerow([
        result.db_path.name,
        f"{result.duration:.2f}",
        "changed" if result.changed else "unchanged",
        str(result.error) if result.error else "",
    ])

sync_many(jobs, on_progress=csv_logger)
```

---

## `SyncResult`

```python
@dataclass
class SyncResult:
    db_path:     Path
    schema_df:   Path
    started_at:  float   # time.monotonic()
    finished_at: float   # time.monotonic()
    delta_bytes: int
    error:       Exception | None
```

**Computed properties**

| Property | Type | Description |
|---|---|---|
| `duration` | `float` | Wall-clock seconds: `finished_at - started_at` |
| `changed` | `bool` | `True` if a non-empty delta was applied |
| `success` | `bool` | `True` if `error is None` |

**`__str__`** returns a single formatted line suitable for logging:

```
[OK]   tenant_001                          3.2s  1248B delta
[FAIL] tenant_002                          0.1s  no changes  ERROR: Database not found: …
```

---

## `print_progress`

```python
def print_progress(result: SyncResult) -> None
```

A ready-made `on_progress` callback that prints one line per completed database to stdout. Thread-safe — uses a lock to prevent interleaved output from concurrent workers.

```python
results = sync_many(jobs, on_progress=print_progress)
```

Pass `None` (the default) to run silently and inspect `results` after the fact.
