# pyoe.schema — Schema operations

```python
from pyoe.schema import dump_schema, parse_df, make_delta, apply_df, sync_schema
```

---

## `dump_schema`

```python
def dump_schema(
    db_path: str | Path,
    output_file: str | Path,
    *,
    codepage: str = "",
    dlc: str | None = None,
    timeout: int = 120,
) -> Path
```

Dump the complete schema of a database to a `.df` file.

Internally runs `prodict/dump_df.r` in batch single-user mode. The output contains `ADD TABLE`, `ADD FIELD`, and `ADD INDEX` stanzas for every user table in the database.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | `str \| Path` | — | Source database. |
| `output_file` | `str \| Path` | — | Destination `.df` file. Parent directories are created if missing. |
| `codepage` | `str` | `""` | Output codepage (e.g. `"UTF-8"`). Defaults to the database's native codepage. |
| `dlc` | `str \| None` | `$DLC` | OpenEdge installation directory. |
| `timeout` | `int` | `120` | Process timeout in seconds. |

**Returns** — `Path` to the written `.df` file.

**Raises**

| Exception | When |
|---|---|
| `OEDBNotFoundError` | The database `.db` file does not exist |
| `OERuntimeError` | The batch process exits non-zero |

**Example**

```python
from pyoe.schema import dump_schema

df_path = dump_schema("/var/db/myapp", "/backups/myapp_schema.df")
print(f"Schema written to {df_path}")

# With UTF-8 output encoding
dump_schema("/var/db/myapp", "/backups/myapp_schema.df", codepage="UTF-8")
```

---

## `parse_df`

```python
def parse_df(path: str | Path) -> Schema
```

Parse a `.df` file into a [`Schema`](#schema-1) object. No OpenEdge installation required.

```python
from pyoe.schema import parse_df

schema = parse_df("/backups/myapp_schema.df")

# List all tables
for name in schema.table_names():
    print(name)

# Inspect a specific table
tbl = schema.tables["CUSTOMER"]
for field in tbl.field_list():   # sorted by ORDER attribute
    print(f"  {field.name:30} {field.datatype}")

# Check indexes
for idx in tbl.indexes.values():
    print(f"  INDEX {idx.name}  primary={idx.primary}  unique={idx.unique}")
    for f in idx.index_fields:
        direction = "ASC" if f.ascending else "DESC"
        print(f"    {f.name} {direction}")
```

---

## `make_delta`

```python
def make_delta(
    current_db: str | Path,
    desired_db: str | Path,
    output_file: str | Path,
    *,
    codepage: str = "",
    dlc: str | None = None,
    timeout: int = 300,
) -> Path
```

Generate an incremental `.df` containing the statements needed to transform `current_db`'s schema into `desired_db`'s schema.

Runs `prodict/dump_inc.r` with both databases connected simultaneously — `current_db` as DICTDB (the one to be altered), `desired_db` as DICTDB2 (the target). The output file is empty when the schemas are already identical.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `current_db` | `str \| Path` | — | The database whose schema will be altered (DICTDB). |
| `desired_db` | `str \| Path` | — | The database whose schema defines the target (DICTDB2). |
| `output_file` | `str \| Path` | — | Destination for the delta `.df`. |
| `codepage` | `str` | `""` | Output codepage. |
| `dlc` | `str \| None` | `$DLC` | OpenEdge installation directory. |
| `timeout` | `int` | `300` | Process timeout in seconds. |

**Returns** — `Path` to the delta `.df` (may be empty if no differences exist).

**Raises**

| Exception | When |
|---|---|
| `OEDBNotFoundError` | Either database `.db` file does not exist |
| `OERuntimeError` | The batch process exits non-zero |

**Example**

```python
from pyoe.schema import make_delta

delta = make_delta(
    "/var/db/app_live",
    "/var/db/app_template",
    "/tmp/schema_delta.df",
)

if delta.stat().st_size == 0:
    print("Schemas are identical — nothing to apply")
else:
    print(f"Delta: {delta.stat().st_size} bytes")
    print(delta.read_text())
```

---

## `apply_df`

```python
def apply_df(
    db_path: str | Path,
    df_file: str | Path,
    *,
    dlc: str | None = None,
    timeout: int = 300,
) -> None
```

Load a `.df` file into an existing database using `prodict/load_df_silent.r`.

Handles all stanza types: `ADD`, `UPDATE`, `DELETE`, `RENAME`. Passing an empty `.df` is a no-op.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | `str \| Path` | — | Target database. |
| `df_file` | `str \| Path` | — | The `.df` file to apply. |
| `dlc` | `str \| None` | `$DLC` | OpenEdge installation directory. |
| `timeout` | `int` | `300` | Process timeout in seconds. |

**Raises**

| Exception | When |
|---|---|
| `OEDBNotFoundError` | The database `.db` file does not exist |
| `OESchemaError` | The `.df` file does not exist |
| `OERuntimeError` | The batch process exits non-zero |

**Example**

```python
from pyoe.schema import apply_df

# Load a full schema into a fresh empty database
apply_df("/var/db/newapp", "/schemas/app_v1.df")

# Apply an incremental delta
apply_df("/var/db/app_live", "/tmp/schema_delta.df")
```

---

## `sync_schema`

```python
def sync_schema(
    target_db: str | Path,
    schema_df: str | Path,
    *,
    dlc: str | None = None,
    workdir: str | Path | None = None,
    keep_workdir: bool = False,
    timeout: int = 300,
) -> Path
```

The primary high-level function. Alters `target_db` so its schema matches `schema_df`.

Orchestrates the full four-step workflow (create → load → diff → apply) internally. No changes are made if the schemas are already identical.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `target_db` | `str \| Path` | — | The database to be altered. |
| `schema_df` | `str \| Path` | — | `.df` file defining the desired schema. |
| `dlc` | `str \| None` | `$DLC` | OpenEdge installation directory. |
| `workdir` | `str \| Path \| None` | `None` | Directory for temporary files (temp DB, intermediate `.df`). Uses system temp if unset. |
| `keep_workdir` | `bool` | `False` | Do not delete `workdir` on exit. Useful for debugging. |
| `timeout` | `int` | `300` | Per-step timeout in seconds. |

**Returns** — `Path` to the delta `.df` that was applied, named `<db>_schema_delta.df` next to the target database. The file is empty if no changes were needed.

**Raises**

| Exception | When |
|---|---|
| `OEDBNotFoundError` | `target_db` does not exist |
| `OESchemaError` | `schema_df` does not exist |
| `OERuntimeError` | Any internal OpenEdge step exits non-zero |

**Examples**

```python
from pyoe.schema import sync_schema

# Basic usage
delta = sync_schema("/var/db/myapp", "/schemas/app.df")
print(f"Applied {delta.stat().st_size} bytes of changes")

# Inspect the delta before deciding whether to proceed
delta = sync_schema("/var/db/myapp", "/schemas/app.df", keep_workdir=True)
print(delta.read_text())

# Check whether changes were needed at all
if delta.stat().st_size == 0:
    print("Already up to date")
```

---

## Schema data classes

These are returned by `parse_df` and can be used for programmatic schema inspection.

### `Schema`

```python
@dataclass
class Schema:
    tables: dict[str, SchemaTable]      # keyed by upper-case table name
    sequences: dict[str, SchemaSequence]

    def table(self, name: str) -> SchemaTable  # case-insensitive lookup
    def table_names(self) -> list[str]         # sorted
```

### `SchemaTable`

```python
@dataclass
class SchemaTable:
    name: str
    area: str
    label: str
    description: str
    table_type: str       # "T" for regular table
    dump_name: str        # used by data dump/load utilities
    fields: dict[str, SchemaField]   # keyed by upper-case field name
    indexes: dict[str, SchemaIndex]  # keyed by upper-case index name

    def field_list(self) -> list[SchemaField]  # sorted by ORDER attribute
```

### `SchemaField`

```python
@dataclass
class SchemaField:
    name: str
    table: str
    datatype: str          # "CHARACTER", "INTEGER", "DECIMAL", "LOGICAL", "DATE", …
    format: str
    initial: str
    label: str
    column_label: str
    description: str
    help: str
    mandatory: bool
    extent: int            # array extent; 0 = scalar
    decimals: int
    order: int
    position: int
    max_width: int
    case_sensitive: bool
```

### `SchemaIndex`

```python
@dataclass
class SchemaIndex:
    name: str
    table: str
    area: str
    primary: bool
    unique: bool
    active: bool
    word_index: bool
    description: str
    index_fields: list[IndexField]

@dataclass
class IndexField:
    name: str
    ascending: bool   # False = DESCENDING
```

### `SchemaSequence`

```python
@dataclass
class SchemaSequence:
    name: str
    initial: int
    increment: int
    cycle_on_limit: bool
    min_val: int | None
    max_val: int | None
```

---

## `DFParser`

The parser class backing `parse_df`. Use it directly if you need to parse multiple files or reuse the parser:

```python
from pyoe.schema.loader import DFParser

parser = DFParser()
schema = parser.parse_file("/schemas/app.df")

# Or parse raw text
schema2 = parser.parse_text("""
ADD TABLE "Config"
  AREA "Data Area"
  TABLE-TYPE T

ADD FIELD "Key" OF "Config" AS character
  FORMAT "x(50)"
  ORDER 10
""")
```
