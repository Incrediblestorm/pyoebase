# Concepts

Understanding a few OpenEdge fundamentals makes the pyoe API much easier to use.

---

## The .df file format

A `.df` (dump file) is OpenEdge's plain-text representation of a database schema. It contains a series of stanzas, each starting with a verb followed by an object type:

```
ADD TABLE "Customer"
  AREA "Data Area"
  LABEL "Customer"
  TABLE-TYPE T
  DUMP-NAME "customer"

ADD FIELD "CustNum" OF "Customer" AS integer
  FORMAT "9999999"
  INITIAL "0"
  ORDER 10

ADD INDEX "CustNum" ON "Customer"
  AREA "Index Area"
  PRIMARY
  UNIQUE
  ACTIVE
  INDEX-FIELD "CustNum" ASCENDING
```

**Verbs:**

| Verb | Meaning |
|---|---|
| `ADD` | Create a new object (table, field, index, sequence) |
| `UPDATE` | Modify an existing object's attributes |
| `DELETE` | Remove an object |
| `RENAME` | Rename an object |

A **full schema dump** contains only `ADD` stanzas — it describes the complete schema from scratch.

A **delta (incremental) dump** contains whatever mix of `ADD`, `UPDATE`, `DELETE`, and `RENAME` statements is needed to transform one schema into another.

---

## DICTDB and DICTDB2

When OpenEdge connects to a database, it assigns it a logical alias. The first database connected becomes `DICTDB` — this is the one that schema tools (the prodict routines) operate on by default.

`pyoe` uses two databases simultaneously for the comparison step:

| Alias | Role in pyoe |
|---|---|
| `DICTDB` | The **current** database — the one whose schema will be altered |
| `DICTDB2` | The **desired** database — the template that defines the target schema |

`prodict/dump_inc.r` connects to both and writes the `.df` statements needed to bring `DICTDB` in line with `DICTDB2`.

---

## Single-user mode (`-1`)

OpenEdge databases can run as multi-user (with a broker server process) or single-user (direct file access). `pyoe` always uses single-user mode (`-1` flag) because:

- Schema operations require exclusive access
- No separate server process needs to be running
- Simpler to set up in scripts and automation

This means **the target database must not have any other connections** when `pyoe` is running against it.

---

## The sync workflow

`sync_schema()` orchestrates four steps internally:

```
schema.df  ──► create_empty_db ──► empty DB
                                        │
                    apply_df(schema.df) ▼
                               desired_schema DB
                                        │
target_db ─────────────────► make_delta ──► delta.df
                                                │
                                    apply_df ──► target_db  (altered)
```

1. **Create** a temporary empty database.
2. **Load** the desired `.df` into it — now it has the schema you want.
3. **Compare** the target database against the desired database using OpenEdge's own incremental dump tool. This produces a delta `.df`.
4. **Apply** the delta to the target database. If the delta is empty (schemas already match), nothing is written.

Using OpenEdge's own comparison tool ensures that nuances like field ordering, area assignments, and codepage handling are respected correctly.

---

## Database file layout

An OpenEdge database is made up of several files with a shared stem:

| File | Description |
|---|---|
| `name.db` | Control file — the "database" as far as OpenEdge is concerned |
| `name.d1` | Primary data extent |
| `name.b1` | Before-image (transaction log) |
| `name.lg` | Log file |

`pyoe` functions accept paths with or without the `.db` extension — both work:

```python
sync_schema("/var/db/myapp",     "/schemas/app.df")   # no extension
sync_schema("/var/db/myapp.db",  "/schemas/app.df")   # .db extension stripped automatically
```
