# pyoe

Python utilities for Progress OpenEdge database schema management.

`pyoe` wraps the OpenEdge batch runtime to provide a clean Python API for schema operations: dumping, parsing, comparing, applying, and parallel-syncing `.df` schema files across multiple databases.

## Quick start

```python
from pyoe.db import create_empty_db
from pyoe.schema import dump_schema, parse_df, sync_schema
from pyoe.sync import sync_many, print_progress

# Create an empty database
create_empty_db("/var/db/myapp")

# Dump its schema to a .df file
dump_schema("/var/db/myapp", "/tmp/myapp.df")

# Inspect the schema
schema = parse_df("/tmp/myapp.df")
for name, tbl in schema.tables.items():
    print(name, [f.name for f in tbl.field_list()])

# Bring a database's schema in line with a .df file
delta = sync_schema("/var/db/myapp", "/schemas/app_v2.df")
print(f"Applied {delta.stat().st_size} bytes of changes")

# Update many databases in parallel
jobs = [("/var/db/tenant_001", "/schemas/app.df"),
        ("/var/db/tenant_002", "/schemas/app.df")]
results = sync_many(jobs, max_workers=4, on_progress=print_progress)
```

## Requirements

- Python 3.9+
- Progress OpenEdge 12.2.x with `$DLC` set to the installation directory

## Installation

```bash
pip install -e ".[dev]"
```

## Documentation

See [`docs/`](docs/index.md) for the full documentation:

- [Installation](docs/installation.md)
- [Concepts](docs/concepts.md)
- [API: db](docs/api/db.md)
- [API: schema](docs/api/schema.md)
- [API: sync](docs/api/sync.md)
- [Guide: Schema Sync Walkthrough](docs/guides/schema-sync.md)
- [Guide: Parallel Sync](docs/guides/parallel-sync.md)
- [Ansible Integration](docs/ansible.md)

## Tests

```bash
pytest tests/unit/ -v                  # unit tests, no OE runtime needed
pytest -m integration -v               # integration tests, requires OpenEdge
pytest -m "not integration" -v         # everything except integration
```
