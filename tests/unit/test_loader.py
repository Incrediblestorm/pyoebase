"""Unit tests for schema/loader.py – no OE runtime required."""

import pytest

from pyoe.schema.loader import (
    DFParser,
    IndexField,
    Schema,
    SchemaField,
    SchemaIndex,
    SchemaTable,
    parse_df,
)
from tests.conftest import SAMPLE_DF, SAMPLE_DF_DELTA


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse(text: str) -> Schema:
    return DFParser().parse_text(text)


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

class TestTableParsing:
    def test_tables_found(self):
        schema = _parse(SAMPLE_DF)
        assert "CUSTOMER" in schema.tables
        assert "ORDER" in schema.tables

    def test_table_attributes(self):
        schema = _parse(SAMPLE_DF)
        tbl = schema.tables["CUSTOMER"]
        assert tbl.area == "Data Area"
        assert tbl.label == "Customer"
        assert tbl.table_type == "T"
        assert tbl.dump_name == "customer"

    def test_table_count(self):
        schema = _parse(SAMPLE_DF)
        assert len(schema.tables) == 2

    def test_delete_table(self):
        schema = _parse(SAMPLE_DF)
        delta = _parse("DELETE TABLE \"Order\"")
        schema.tables.update(delta.tables)
        # A DELETE TABLE stanza that is applied should remove the table.
        # Re-parse with a combined text that includes the delete:
        combined = SAMPLE_DF + "\nDELETE TABLE \"Order\"\n"
        s2 = _parse(combined)
        assert "ORDER" not in s2.tables

    def test_rename_table(self):
        text = 'ADD TABLE "Foo"\n  AREA "Data Area"\n\nRENAME TABLE "Foo" TO "Bar"\n'
        schema = _parse(text)
        assert "BAR" in schema.tables
        assert "FOO" not in schema.tables


# ---------------------------------------------------------------------------
# Field parsing
# ---------------------------------------------------------------------------

class TestFieldParsing:
    def test_fields_found(self):
        schema = _parse(SAMPLE_DF)
        tbl = schema.tables["CUSTOMER"]
        assert "CUSTNUM" in tbl.fields
        assert "NAME" in tbl.fields
        assert "ACTIVE" in tbl.fields

    def test_field_datatype(self):
        schema = _parse(SAMPLE_DF)
        assert schema.tables["CUSTOMER"].fields["CUSTNUM"].datatype == "INTEGER"
        assert schema.tables["CUSTOMER"].fields["NAME"].datatype == "CHARACTER"
        assert schema.tables["CUSTOMER"].fields["ACTIVE"].datatype == "LOGICAL"

    def test_field_attributes(self):
        schema = _parse(SAMPLE_DF)
        f = schema.tables["CUSTOMER"].fields["NAME"]
        assert f.format == "x(30)"
        assert f.label == "Name"
        assert f.max_width == 60
        assert f.order == 20

    def test_field_mandatory_default_false(self):
        schema = _parse(SAMPLE_DF)
        f = schema.tables["CUSTOMER"].fields["CUSTNUM"]
        assert f.mandatory is False

    def test_mandatory_field(self):
        text = (
            'ADD TABLE "T"\n  AREA "Data Area"\n\n'
            'ADD FIELD "F" OF "T" AS character\n  MANDATORY\n'
        )
        schema = _parse(text)
        assert schema.tables["T"].fields["F"].mandatory is True

    def test_field_list_ordering(self):
        schema = _parse(SAMPLE_DF)
        orders = [f.order for f in schema.tables["CUSTOMER"].field_list()]
        assert orders == sorted(orders)

    def test_rename_field(self):
        text = (
            'ADD TABLE "T"\n  AREA "Data Area"\n\n'
            'ADD FIELD "OldName" OF "T" AS character\n  ORDER 10\n\n'
            'RENAME FIELD "OldName" OF "T" TO "NewName"\n'
        )
        schema = _parse(text)
        assert "NEWNAME" in schema.tables["T"].fields
        assert "OLDNAME" not in schema.tables["T"].fields

    def test_delete_field(self):
        text = SAMPLE_DF + '\nDELETE FIELD "Active" OF "Customer"\n'
        schema = _parse(text)
        assert "ACTIVE" not in schema.tables["CUSTOMER"].fields


# ---------------------------------------------------------------------------
# Index parsing
# ---------------------------------------------------------------------------

class TestIndexParsing:
    def test_indexes_found(self):
        schema = _parse(SAMPLE_DF)
        tbl = schema.tables["CUSTOMER"]
        assert "CUSTNUM" in tbl.indexes
        assert "CUSTNAME" in tbl.indexes

    def test_primary_index(self):
        schema = _parse(SAMPLE_DF)
        assert schema.tables["CUSTOMER"].indexes["CUSTNUM"].primary is True
        assert schema.tables["CUSTOMER"].indexes["CUSTNAME"].primary is False

    def test_unique_index(self):
        schema = _parse(SAMPLE_DF)
        assert schema.tables["CUSTOMER"].indexes["CUSTNUM"].unique is True

    def test_index_fields(self):
        schema = _parse(SAMPLE_DF)
        idx = schema.tables["CUSTOMER"].indexes["CUSTNAME"]
        assert len(idx.index_fields) == 2
        assert idx.index_fields[0].name == "Name"
        assert idx.index_fields[0].ascending is True
        assert idx.index_fields[1].name == "CustNum"

    def test_descending_field(self):
        text = (
            'ADD TABLE "T"\n  AREA "Data Area"\n\n'
            'ADD FIELD "F" OF "T" AS integer\n\n'
            'ADD INDEX "I" ON "T"\n  INDEX-FIELD "F" DESCENDING\n'
        )
        schema = _parse(text)
        idx = schema.tables["T"].indexes["I"]
        assert idx.index_fields[0].ascending is False

    def test_delete_index(self):
        text = SAMPLE_DF + '\nDELETE INDEX "CustName" ON "Customer"\n'
        schema = _parse(text)
        assert "CUSTNAME" not in schema.tables["CUSTOMER"].indexes


# ---------------------------------------------------------------------------
# Sequence parsing
# ---------------------------------------------------------------------------

class TestSequenceParsing:
    def test_sequence_found(self):
        schema = _parse(SAMPLE_DF)
        assert "ORDERSEQ" in schema.sequences

    def test_sequence_attributes(self):
        schema = _parse(SAMPLE_DF)
        seq = schema.sequences["ORDERSEQ"]
        assert seq.initial == 1
        assert seq.increment == 1
        assert seq.cycle_on_limit is True


# ---------------------------------------------------------------------------
# Delta / UPDATE stanzas
# ---------------------------------------------------------------------------

class TestDeltaParsing:
    def test_update_field_format(self):
        base = _parse(SAMPLE_DF)
        # Apply update on top
        combined = SAMPLE_DF + '\nUPDATE FIELD "Name" OF "Customer" AS character\n  FORMAT "x(50)"\n'
        schema = _parse(combined)
        assert schema.tables["CUSTOMER"].fields["NAME"].format == "x(50)"

    def test_add_new_table_in_delta(self):
        combined = SAMPLE_DF + SAMPLE_DF_DELTA
        schema = _parse(combined)
        assert "INVOICE" in schema.tables

    def test_delete_table_in_delta(self):
        combined = SAMPLE_DF + SAMPLE_DF_DELTA
        schema = _parse(combined)
        assert "ORDER" not in schema.tables


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

class TestFileIO:
    def test_parse_file(self, sample_df_file):
        schema = parse_df(sample_df_file)
        assert len(schema.tables) == 2

    def test_parse_empty_file(self, empty_df_file):
        schema = parse_df(empty_df_file)
        assert len(schema.tables) == 0
        assert len(schema.sequences) == 0

    def test_table_names_sorted(self, sample_df_file):
        schema = parse_df(sample_df_file)
        names = schema.table_names()
        assert names == sorted(names)
