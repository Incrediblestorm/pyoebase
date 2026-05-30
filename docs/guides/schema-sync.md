# Guide: Schema Sync Walkthrough

This guide walks through the complete workflow for bringing a database's schema up to date with a `.df` definition file.

---

## Scenario

You have:
- A running application database at `/var/db/myapp`
- A `.df` file (`/schemas/app_v2.df`) that defines the desired schema after a feature release

You want to:
1. See what will change before committing
2. Apply the changes
3. Verify the result

---

## Step 1 — Inspect the current schema

Dump the current schema so you can see where you're starting from:

```python
from pyoe.schema import dump_schema, parse_df

# Write the current schema to a file
dump_schema("/var/db/myapp", "/tmp/myapp_current.df")

# Parse and inspect it
current = parse_df("/tmp/myapp_current.df")
print(f"Tables: {len(current.tables)}")
for name in current.table_names():
    tbl = current.tables[name]
    print(f"  {name}: {len(tbl.fields)} fields, {len(tbl.indexes)} indexes")
```

---

## Step 2 — Preview the delta

Before changing anything, generate the delta to see exactly what `sync_schema` would apply:

```python
from pyoe.db import create_empty_db
from pyoe.schema import apply_df, make_delta
import tempfile

with tempfile.TemporaryDirectory() as tmp:
    # Load the desired schema into a scratch database
    desired_db = f"{tmp}/desired"
    create_empty_db(desired_db)
    apply_df(desired_db, "/schemas/app_v2.df")

    # Compute the delta
    delta = make_delta("/var/db/myapp", desired_db, f"{tmp}/delta.df")

    if delta.stat().st_size == 0:
        print("No schema changes needed.")
    else:
        print("Proposed changes:")
        print(delta.read_text())
```

Example output:
```
ADD FIELD "PhoneNumber" OF "Customer" AS character
  FORMAT "x(20)"
  ORDER 60
  POSITION 6

UPDATE FIELD "Name" OF "Customer" AS character
  FORMAT "x(50)"

ADD TABLE "AuditLog"
  AREA "Data Area"
  TABLE-TYPE T
  ...
```

---

## Step 3 — Apply the schema

Once you're satisfied with the preview, apply it:

```python
from pyoe.schema import sync_schema

delta = sync_schema("/var/db/myapp", "/schemas/app_v2.df")

if delta.stat().st_size == 0:
    print("Already up to date.")
else:
    print(f"Schema updated. Delta saved to: {delta}")
```

`sync_schema` saves the applied delta as `myapp_schema_delta.df` next to the database file. Keep this for audit purposes.

---

## Step 4 — Verify

Dump the updated schema and confirm it matches your expectations:

```python
from pyoe.schema import dump_schema, parse_df

dump_schema("/var/db/myapp", "/tmp/myapp_after.df")
after = parse_df("/tmp/myapp_after.df")

# Check the new field is present
cust = after.tables["CUSTOMER"]
assert "PHONENUMBER" in cust.fields, "PhoneNumber field missing"
assert "AUDITLOG" in after.tables, "AuditLog table missing"

# Check the format was updated
assert cust.fields["NAME"].format == "x(50)"

print("Verification passed.")
```

---

## Putting it all together

```python
import sys
from pyoe.schema import dump_schema, sync_schema

DB    = "/var/db/myapp"
SCHEMA = "/schemas/app_v2.df"
BACKUP = "/backups/myapp_pre_upgrade.df"

# 1. Backup current schema
dump_schema(DB, BACKUP)
print(f"Schema backed up to {BACKUP}")

# 2. Apply new schema
delta = sync_schema(DB, SCHEMA)

# 3. Report
size = delta.stat().st_size
if size == 0:
    print("Database was already up to date.")
else:
    print(f"Applied {size} bytes of schema changes.")
    print(f"Delta saved to: {delta}")
```

---

## Error handling

```python
from pyoe.exceptions import OEDBNotFoundError, OERuntimeError
from pyoe.schema import sync_schema

try:
    delta = sync_schema("/var/db/myapp", "/schemas/app_v2.df")
except OEDBNotFoundError as e:
    print(f"Database not found: {e}")
    sys.exit(1)
except OERuntimeError as e:
    print(f"OpenEdge error (rc={e.returncode}):")
    print(e.stderr)
    sys.exit(1)
```

---

## Re-running is safe

`sync_schema` is idempotent. Running it twice with the same `.df` file results in an empty delta on the second run — no changes are applied.

```python
sync_schema("/var/db/myapp", "/schemas/app_v2.df")  # applies changes
sync_schema("/var/db/myapp", "/schemas/app_v2.df")  # delta is empty, nothing happens
```
