# pyoe

Python utilities for Progress OpenEdge database schema management.

`pyoe` wraps the OpenEdge batch runtime (`_progres`) to provide a clean Python API for schema operations: dumping, parsing, comparing, and applying `.df` schema files, including a parallel runner for updating many databases at once.

---

## Contents

- **[Installation](installation.md)** — Prerequisites, package setup, environment configuration
- **[Concepts](concepts.md)** — `.df` files, DICTDB, single-user mode, the sync workflow
- **API Reference**
  - [db](api/db.md) — Creating and inspecting databases
  - [schema](api/schema.md) — Dump, parse, compare, apply
  - [sync](api/sync.md) — Parallel multi-database sync
- **Guides**
  - [Schema Sync Walkthrough](guides/schema-sync.md) — End-to-end example
  - [Parallel Sync](guides/parallel-sync.md) — Updating many databases at once
- **[Ansible Integration](ansible.md)** — Notes on using pyoe from an Ansible collection

---

## Quick start

```python
from pyoe.db import create_empty_db
from pyoe.schema import dump_schema, parse_df, sync_schema

# Create a new empty database
create_empty_db("/var/db/myapp")

# Dump its schema to a .df file
dump_schema("/var/db/myapp", "/tmp/myapp.df")

# Inspect the schema in Python
schema = parse_df("/tmp/myapp.df")
for name, table in schema.tables.items():
    print(name, [f.name for f in table.field_list()])

# Alter a database to match a .df file
sync_schema("/var/db/myapp", "/schemas/desired.df")
```

```python
# Update many databases in parallel
from pyoe.sync import sync_many, print_progress

jobs = [
    ("/var/db/tenant_001", "/schemas/app.df"),
    ("/var/db/tenant_002", "/schemas/app.df"),
    ("/var/db/tenant_003", "/schemas/app.df"),
]
results = sync_many(jobs, max_workers=4, on_progress=print_progress)
```
