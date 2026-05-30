# Guide: Parallel Schema Sync

When the same schema change needs to be applied to many databases — such as a fleet of tenant databases — `sync_many` runs them all concurrently and gives you structured timing and error information for each.

---

## Basic usage

```python
from pyoe.sync import sync_many, print_progress

jobs = [
    ("/var/db/tenant_001", "/schemas/app.df"),
    ("/var/db/tenant_002", "/schemas/app.df"),
    ("/var/db/tenant_003", "/schemas/app.df"),
]

results = sync_many(jobs, max_workers=4, on_progress=print_progress)
```

Output as databases complete (order varies):

```
[OK] tenant_001                          3.1s  1248B delta
[OK] tenant_003                          3.4s  no changes
[OK] tenant_002                          4.0s  512B delta
```

---

## Choosing `max_workers`

Each worker runs one `_progres` subprocess. Because the work is I/O-bound (disk reads/writes and the OE runtime), you can typically run more workers than CPU cores without contention.

Practical guidelines:

| Scenario | Suggested `max_workers` |
|---|---|
| Local disk, same machine | `4` – `8` |
| Network/SAN storage | `2` – `4` (watch for I/O saturation) |
| Very fast NVMe, many small DBs | `8` – `16` |
| Single DB (for consistency with the API) | `1` |

Start conservatively and increase based on observed wall-clock time.

---

## Building the jobs list dynamically

```python
from pathlib import Path
from pyoe.sync import sync_many, print_progress

SCHEMA = Path("/schemas/app.df")
DB_ROOT = Path("/var/db/tenants")

# All subdirectories containing a .db file
jobs = [
    (db_dir / db_dir.name, SCHEMA)
    for db_dir in sorted(DB_ROOT.iterdir())
    if (db_dir / (db_dir.name + ".db")).exists()
]

print(f"Syncing {len(jobs)} databases...")
results = sync_many(jobs, max_workers=6, on_progress=print_progress)
```

---

## Handling failures

Failures are captured in `result.error` — they never interrupt the other databases.

```python
results = sync_many(jobs, max_workers=4)

succeeded = [r for r in results if r.success]
failed    = [r for r in results if not r.success]

print(f"{len(succeeded)} succeeded, {len(failed)} failed")

for r in failed:
    print(f"  FAILED {r.db_path.name}: {r.error}")

if failed:
    raise SystemExit(1)
```

---

## Timing and reporting

`SyncResult` carries precise wall-clock timing for each database:

```python
results = sync_many(jobs, max_workers=4)

changed   = [r for r in results if r.changed]
unchanged = [r for r in results if r.success and not r.changed]

print(f"\nSummary:")
print(f"  Changed:   {len(changed)}")
print(f"  Unchanged: {len(unchanged)}")
print(f"  Failed:    {sum(1 for r in results if not r.success)}")
print(f"  Total wall time: {max(r.finished_at for r in results) - min(r.started_at for r in results):.1f}s")

if changed:
    print(f"\nDatabases that changed:")
    for r in sorted(changed, key=lambda r: -r.delta_bytes):
        print(f"  {r.db_path.name:<30}  {r.delta_bytes:>6} bytes  {r.duration:.1f}s")
```

---

## Writing a run log

```python
import csv
import sys
from datetime import datetime
from pyoe.sync import sync_many

log_file = open(f"/var/log/schema_sync_{datetime.now():%Y%m%d_%H%M%S}.csv", "w", newline="")
writer = csv.writer(log_file)
writer.writerow(["database", "duration_s", "delta_bytes", "status", "error"])

def log_result(result):
    writer.writerow([
        result.db_path.name,
        f"{result.duration:.2f}",
        result.delta_bytes,
        "ok" if result.success else "fail",
        str(result.error) if result.error else "",
    ])
    log_file.flush()
    # Also print to terminal
    print(result)

results = sync_many(jobs, max_workers=4, on_progress=log_result)
log_file.close()
```

---

## Stopping early on first failure

`sync_many` always runs all jobs to completion. If you want to abort on the first failure, run jobs in batches:

```python
BATCH = 4

for i in range(0, len(jobs), BATCH):
    batch = jobs[i : i + BATCH]
    results = sync_many(batch, max_workers=BATCH, on_progress=print_progress)
    if any(not r.success for r in results):
        print("Batch failed — stopping.")
        raise SystemExit(1)
```

---

## Debugging a failed job

Pass `workdir` to preserve the intermediate files (temp database, intermediate `.df` files) for inspection:

```python
import tempfile

with tempfile.TemporaryDirectory(delete=False) as debug_dir:
    results = sync_many(
        [("/var/db/problem_tenant", "/schemas/app.df")],
        workdir=debug_dir,
    )

print(f"Workdir preserved at: {debug_dir}")
# Inspect: {debug_dir}/job_0000_problem_tenant/delta.df
#          {debug_dir}/job_0000_problem_tenant/desired.db  etc.
```
