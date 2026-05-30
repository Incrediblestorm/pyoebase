# pyoe.db — Database creation

```python
from pyoe.db import create_empty_db, db_exists
```

---

## `create_empty_db`

```python
def create_empty_db(
    db_path: str | Path,
    *,
    overwrite: bool = False,
    dlc: str | None = None,
    structure_file: str | Path | None = None,
) -> Path
```

Create a new empty OpenEdge database by copying the `$DLC/empty` template.

The resulting database has no user tables — it contains only the system schema. Load a `.df` file into it afterwards with [`apply_df`](schema.md#apply_df) to add your schema.

**Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `db_path` | `str \| Path` | — | Destination path. The `.db` extension is optional and stripped automatically. |
| `overwrite` | `bool` | `False` | If `True`, remove any existing database files at `db_path` before creating. |
| `dlc` | `str \| None` | `$DLC` env var | OpenEdge installation directory. |
| `structure_file` | `str \| Path \| None` | `None` | Optional `.st` structure file to add extra extents via `prostrct add`. |

**Returns** — `Path` to the `.db` control file of the new database.

**Raises**

| Exception | When |
|---|---|
| `OEDBAlreadyExistsError` | The database exists and `overwrite=False` |
| `OEDBNotFoundError` | The `$DLC/empty` template is missing |
| `OERuntimeError` | `procopy` or `prostrct` exits non-zero |

**Examples**

```python
from pyoe.db import create_empty_db

# Minimal — create with default single-extent structure
db = create_empty_db("/var/db/myapp")
print(db)   # /var/db/myapp.db

# Replace an existing database
create_empty_db("/var/db/myapp", overwrite=True)

# Create with a custom structure file (multiple extents, specific area sizes)
create_empty_db(
    "/var/db/myapp",
    structure_file="/schemas/myapp.st",
)

# Explicit DLC path
create_empty_db("/var/db/myapp", dlc="/opt/dlc-12.2.13")
```

---

## `db_exists`

```python
def db_exists(db_path: str | Path) -> bool
```

Return `True` if the `.db` control file for `db_path` exists on disk.

```python
from pyoe.db import db_exists

if not db_exists("/var/db/myapp"):
    create_empty_db("/var/db/myapp")
```

---

## Structure files

A `.st` (structure) file controls how database extents are laid out on disk. The format is documented in the OpenEdge Database Administration guide. A simple two-extent example:

```
#  Data Area
d "Data Area":50,8;64 /var/db/myapp/data.d1

#  Index Area
d "Index Area":50,8;64 /var/db/myapp/idx.d1

b before-image:/var/db/myapp/myapp.bi:4096:50000:auto-expand
```

When `structure_file` is provided, `create_empty_db` runs `prostrct add` to attach the extents after the initial database is created from the template.
