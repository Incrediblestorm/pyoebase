"""Parse OpenEdge .df schema dump files into Python data structures.

The .df format is a plain-text representation of an OpenEdge schema.
Each stanza starts with a verb (``ADD``, ``UPDATE``, ``DELETE``,
``RENAME``) followed by an object type and a series of indented
attribute lines.

Example::

    ADD TABLE "Customer"
      AREA "Data Area"
      LABEL "Customer"
      TABLE-TYPE T

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
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IndexField:
    name: str
    ascending: bool = True


@dataclass
class SchemaIndex:
    name: str
    table: str
    area: str = "Index Area"
    primary: bool = False
    unique: bool = False
    active: bool = True
    word_index: bool = False
    description: str = ""
    index_fields: list[IndexField] = field(default_factory=list)


@dataclass
class SchemaField:
    name: str
    table: str
    datatype: str = "CHARACTER"
    format: str = ""
    initial: str = ""
    label: str = ""
    column_label: str = ""
    description: str = ""
    help: str = ""
    mandatory: bool = False
    extent: int = 0
    decimals: int = 0
    order: int = 0
    position: int = 0
    max_width: int = 0
    case_sensitive: bool = False


@dataclass
class SchemaTable:
    name: str
    area: str = "Data Area"
    label: str = ""
    description: str = ""
    table_type: str = "T"
    dump_name: str = ""
    fields: dict[str, SchemaField] = field(default_factory=dict)
    indexes: dict[str, SchemaIndex] = field(default_factory=dict)

    def field_list(self) -> list[SchemaField]:
        """Fields sorted by their ``order`` attribute."""
        return sorted(self.fields.values(), key=lambda f: f.order)


@dataclass
class SchemaSequence:
    name: str
    initial: int = 1
    increment: int = 1
    cycle_on_limit: bool = False
    min_val: Optional[int] = None
    max_val: Optional[int] = None


@dataclass
class Schema:
    """In-memory representation of an OpenEdge schema."""

    tables: dict[str, SchemaTable] = field(default_factory=dict)
    sequences: dict[str, SchemaSequence] = field(default_factory=dict)

    # The raw stanzas from the .df, keyed by (verb, type, name).
    # Preserved so that round-tripping to .df is lossless.
    _raw_stanzas: list[dict] = field(default_factory=list, repr=False)

    def table(self, name: str) -> SchemaTable:
        """Return a table by case-insensitive name."""
        return self.tables[name.upper()]

    def table_names(self) -> list[str]:
        return sorted(self.tables.keys())


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_QUOTED = re.compile(r'"([^"]*)"')
_VERB_LINE = re.compile(
    r'^(ADD|UPDATE|DELETE|RENAME)\s+(TABLE|FIELD|INDEX|SEQUENCE|DATABASE)\b',
    re.IGNORECASE,
)


def _unquote(s: str) -> str:
    m = _QUOTED.match(s.strip())
    return m.group(1) if m else s.strip().strip('"')


def _parse_bool_attr(line: str) -> bool:
    """Return True; presence of the line implies True."""
    return True


class DFParser:
    """Parse a ``.df`` file or string and return a :class:`Schema`.

    Usage::

        schema = DFParser().parse_file("/path/to/schema.df")
        # or
        schema = DFParser().parse_text(df_text)
    """

    def parse_file(self, path: str | Path) -> Schema:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        return self.parse_text(text)

    def parse_text(self, text: str) -> Schema:
        stanzas = self._split_stanzas(text)
        schema = Schema()
        for stanza in stanzas:
            schema._raw_stanzas.append(stanza)
            self._apply_stanza(schema, stanza)
        return schema

    # ------------------------------------------------------------------

    def _split_stanzas(self, text: str) -> list[dict]:
        """Split raw .df text into a list of stanza dicts."""
        stanzas: list[dict] = []
        current_lines: list[str] = []

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if _VERB_LINE.match(line):
                if current_lines:
                    stanzas.append({"raw": current_lines})
                current_lines = [line]
            elif current_lines:
                current_lines.append(line)

        if current_lines:
            stanzas.append({"raw": current_lines})

        return stanzas

    def _apply_stanza(self, schema: Schema, stanza: dict) -> None:
        lines = stanza["raw"]
        if not lines:
            return
        header = lines[0].strip()
        attrs = [l.strip() for l in lines[1:] if l.strip()]

        m = _VERB_LINE.match(header)
        if not m:
            return

        verb = m.group(1).upper()
        obj_type = m.group(2).upper()
        rest = header[m.end():].strip()

        if obj_type == "TABLE":
            self._handle_table(schema, verb, rest, attrs)
        elif obj_type == "FIELD":
            self._handle_field(schema, verb, rest, attrs)
        elif obj_type == "INDEX":
            self._handle_index(schema, verb, rest, attrs)
        elif obj_type == "SEQUENCE":
            self._handle_sequence(schema, verb, rest, attrs)

    # ------------------------------------------------------------------
    # Table
    # ------------------------------------------------------------------

    def _handle_table(self, schema: Schema, verb: str, rest: str, attrs: list[str]) -> None:
        name = _unquote(rest).upper()

        if verb == "DELETE":
            schema.tables.pop(name, None)
            return

        if verb == "RENAME":
            # RENAME TABLE "old" TO "new"
            parts = rest.upper().split(" TO ")
            old = _unquote(parts[0]).upper()
            new = _unquote(parts[1]).upper() if len(parts) > 1 else old
            tbl = schema.tables.pop(old, SchemaTable(name=new))
            tbl.name = new
            schema.tables[new] = tbl
            return

        tbl = schema.tables.get(name) if verb == "UPDATE" else SchemaTable(name=name)
        if tbl is None:
            tbl = SchemaTable(name=name)

        for attr in attrs:
            ku = attr.upper()
            if ku.startswith("AREA "):
                tbl.area = _unquote(attr[5:])
            elif ku.startswith("LABEL "):
                tbl.label = _unquote(attr[6:])
            elif ku.startswith("DESCRIPTION "):
                tbl.description = _unquote(attr[12:])
            elif ku.startswith("TABLE-TYPE "):
                tbl.table_type = attr[11:].strip()
            elif ku.startswith("DUMP-NAME "):
                tbl.dump_name = _unquote(attr[10:])

        schema.tables[name] = tbl

    # ------------------------------------------------------------------
    # Field
    # ------------------------------------------------------------------

    def _handle_field(self, schema: Schema, verb: str, rest: str, attrs: list[str]) -> None:
        # "FieldName" OF "TableName" AS datatype
        m = re.match(r'"?([^"]+)"?\s+OF\s+"?([^"]+)"?\s+AS\s+(\S+)', rest, re.IGNORECASE)
        if not m:
            return
        fname = m.group(1)
        tname = m.group(2).upper()
        dtype = m.group(3).upper()

        if verb == "DELETE":
            tbl = schema.tables.get(tname)
            if tbl:
                tbl.fields.pop(fname.upper(), None)
            return

        if verb == "RENAME":
            # RENAME FIELD "old" OF "table" TO "new"
            rm = re.match(r'"?([^"]+)"?\s+OF\s+"?([^"]+)"?\s+TO\s+"?([^"]+)"?', rest, re.IGNORECASE)
            if rm:
                old_name = rm.group(1)
                tname2 = rm.group(2).upper()
                new_name = rm.group(3)
                tbl = schema.tables.get(tname2)
                if tbl:
                    fld = tbl.fields.pop(old_name.upper(), None)
                    if fld:
                        fld.name = new_name
                        tbl.fields[new_name.upper()] = fld
            return

        tbl = schema.tables.setdefault(tname, SchemaTable(name=tname))
        fkey = fname.upper()
        fld = tbl.fields.get(fkey) if verb == "UPDATE" else SchemaField(name=fname, table=tname, datatype=dtype)
        if fld is None:
            fld = SchemaField(name=fname, table=tname, datatype=dtype)
        else:
            fld.datatype = dtype

        for attr in attrs:
            ku = attr.upper()
            if ku.startswith("FORMAT "):
                fld.format = _unquote(attr[7:])
            elif ku.startswith("INITIAL "):
                fld.initial = _unquote(attr[8:])
            elif ku.startswith("LABEL "):
                fld.label = _unquote(attr[6:])
            elif ku.startswith("COLUMN-LABEL "):
                fld.column_label = _unquote(attr[13:])
            elif ku.startswith("DESCRIPTION "):
                fld.description = _unquote(attr[12:])
            elif ku.startswith("HELP "):
                fld.help = _unquote(attr[5:])
            elif ku.startswith("ORDER "):
                try:
                    fld.order = int(attr[6:].strip())
                except ValueError:
                    pass
            elif ku.startswith("POSITION "):
                try:
                    fld.position = int(attr[9:].strip())
                except ValueError:
                    pass
            elif ku.startswith("MAX-WIDTH "):
                try:
                    fld.max_width = int(attr[10:].strip())
                except ValueError:
                    pass
            elif ku.startswith("DECIMALS "):
                try:
                    fld.decimals = int(attr[9:].strip())
                except ValueError:
                    pass
            elif ku.startswith("EXTENT "):
                try:
                    fld.extent = int(attr[7:].strip())
                except ValueError:
                    pass
            elif ku == "MANDATORY":
                fld.mandatory = True
            elif ku == "CASE-SENSITIVE":
                fld.case_sensitive = True

        tbl.fields[fkey] = fld

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _handle_index(self, schema: Schema, verb: str, rest: str, attrs: list[str]) -> None:
        # "IndexName" ON "TableName"
        m = re.match(r'"?([^"]+)"?\s+ON\s+"?([^"]+)"?', rest, re.IGNORECASE)
        if not m:
            return
        iname = m.group(1)
        tname = m.group(2).upper()

        if verb == "DELETE":
            tbl = schema.tables.get(tname)
            if tbl:
                tbl.indexes.pop(iname.upper(), None)
            return

        if verb == "RENAME":
            rm = re.match(r'"?([^"]+)"?\s+ON\s+"?([^"]+)"?\s+TO\s+"?([^"]+)"?', rest, re.IGNORECASE)
            if rm:
                old_name = rm.group(1)
                tname2 = rm.group(2).upper()
                new_name = rm.group(3)
                tbl = schema.tables.get(tname2)
                if tbl:
                    idx = tbl.indexes.pop(old_name.upper(), None)
                    if idx:
                        idx.name = new_name
                        tbl.indexes[new_name.upper()] = idx
            return

        tbl = schema.tables.setdefault(tname, SchemaTable(name=tname))
        ikey = iname.upper()
        idx = tbl.indexes.get(ikey) if verb == "UPDATE" else SchemaIndex(name=iname, table=tname)
        if idx is None:
            idx = SchemaIndex(name=iname, table=tname)

        for attr in attrs:
            ku = attr.upper()
            if ku.startswith("AREA "):
                idx.area = _unquote(attr[5:])
            elif ku == "PRIMARY":
                idx.primary = True
            elif ku == "UNIQUE":
                idx.unique = True
            elif ku == "ACTIVE":
                idx.active = True
            elif ku == "INACTIVE":
                idx.active = False
            elif ku == "WORD-INDEX":
                idx.word_index = True
            elif ku.startswith("DESCRIPTION "):
                idx.description = _unquote(attr[12:])
            elif ku.startswith("INDEX-FIELD "):
                parts = attr[12:].split()
                if parts:
                    field_name = _unquote(parts[0])
                    ascending = len(parts) < 2 or parts[1].upper() != "DESCENDING"
                    idx.index_fields.append(IndexField(name=field_name, ascending=ascending))

        tbl.indexes[ikey] = idx

    # ------------------------------------------------------------------
    # Sequence
    # ------------------------------------------------------------------

    def _handle_sequence(self, schema: Schema, verb: str, rest: str, attrs: list[str]) -> None:
        name = _unquote(rest)

        if verb == "DELETE":
            schema.sequences.pop(name.upper(), None)
            return

        skey = name.upper()
        seq = schema.sequences.get(skey) if verb == "UPDATE" else SchemaSequence(name=name)
        if seq is None:
            seq = SchemaSequence(name=name)

        for attr in attrs:
            ku = attr.upper()
            if ku.startswith("INITIAL "):
                try:
                    seq.initial = int(attr[8:].strip())
                except ValueError:
                    pass
            elif ku.startswith("INCREMENT "):
                try:
                    seq.increment = int(attr[10:].strip())
                except ValueError:
                    pass
            elif ku == "CYCLE-ON-LIMIT":
                seq.cycle_on_limit = True
            elif ku.startswith("MIN-VAL "):
                try:
                    seq.min_val = int(attr[8:].strip())
                except ValueError:
                    pass
            elif ku.startswith("MAX-VAL "):
                try:
                    seq.max_val = int(attr[8:].strip())
                except ValueError:
                    pass

        schema.sequences[skey] = seq


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def parse_df(path: str | Path) -> Schema:
    """Parse a ``.df`` file and return a :class:`Schema`.

    Shorthand for ``DFParser().parse_file(path)``.
    """
    return DFParser().parse_file(path)
