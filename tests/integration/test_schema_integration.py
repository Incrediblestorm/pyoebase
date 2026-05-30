"""Integration tests for schema dump / load / compare / sync."""

import pytest
from pathlib import Path

from tests.integration.conftest import skip_no_oe, skip_no_sports, DLC
from pyoe.db.creator import create_empty_db
from pyoe.schema.dumper import dump_schema
from pyoe.schema.loader import parse_df
from pyoe.schema.comparator import make_delta
from pyoe.schema.applier import apply_df, sync_schema


# ---------------------------------------------------------------------------
# Schema dump
# ---------------------------------------------------------------------------

@skip_no_sports
@pytest.mark.integration
class TestDumpSchemaIntegration:
    def test_dump_produces_df_file(self, sports2000_db, tmp_path):
        out = tmp_path / "sports2000.df"
        result = dump_schema(sports2000_db, out, dlc=DLC)
        assert result.exists()
        assert result.stat().st_size > 0

    def test_dump_contains_add_table(self, sports2000_db, tmp_path):
        out = tmp_path / "sports2000.df"
        dump_schema(sports2000_db, out, dlc=DLC)
        content = out.read_text(errors="replace")
        assert "ADD TABLE" in content

    def test_dump_parseable_by_loader(self, sports2000_db, tmp_path):
        out = tmp_path / "sports2000.df"
        dump_schema(sports2000_db, out, dlc=DLC)
        schema = parse_df(out)
        assert len(schema.tables) > 0

    def test_dump_sports2000_has_customer_table(self, sports2000_db, tmp_path):
        out = tmp_path / "sports2000.df"
        dump_schema(sports2000_db, out, dlc=DLC)
        schema = parse_df(out)
        assert "CUSTOMER" in schema.tables


# ---------------------------------------------------------------------------
# Schema load (apply_df)
# ---------------------------------------------------------------------------

@skip_no_oe
@pytest.mark.integration
class TestApplyDfIntegration:
    def test_load_df_into_empty_db(self, tmp_path):
        db = create_empty_db(tmp_path / "target", dlc=DLC).with_suffix("")
        df_content = """\
ADD TABLE "TestTable"
  AREA "Data Area"
  LABEL "Test Table"
  TABLE-TYPE T
  DUMP-NAME "testtable"

ADD FIELD "Id" OF "TestTable" AS integer
  FORMAT ">>>>>>9"
  INITIAL "0"
  ORDER 10
  POSITION 1

ADD INDEX "Id" ON "TestTable"
  AREA "Index Area"
  PRIMARY
  UNIQUE
  ACTIVE
  INDEX-FIELD "Id" ASCENDING
"""
        df_file = tmp_path / "test.df"
        df_file.write_text(df_content)
        apply_df(db, df_file, dlc=DLC)

        # Dump back and verify the table appears
        out = tmp_path / "verify.df"
        dump_schema(db, out, dlc=DLC)
        schema = parse_df(out)
        assert "TESTTABLE" in schema.tables


# ---------------------------------------------------------------------------
# Incremental (delta) dump
# ---------------------------------------------------------------------------

@skip_no_oe
@pytest.mark.integration
class TestMakeDeltaIntegration:
    def test_identical_dbs_produce_empty_delta(self, tmp_path):
        db1 = create_empty_db(tmp_path / "db1", dlc=DLC).with_suffix("")
        db2 = create_empty_db(tmp_path / "db2", dlc=DLC).with_suffix("")
        delta = tmp_path / "delta.df"
        make_delta(db1, db2, delta, dlc=DLC)
        assert delta.exists()
        assert delta.stat().st_size == 0

    def test_delta_reflects_added_table(self, tmp_path):
        db1 = create_empty_db(tmp_path / "db1", dlc=DLC).with_suffix("")
        db2 = create_empty_db(tmp_path / "db2", dlc=DLC).with_suffix("")

        df_file = tmp_path / "new_table.df"
        df_file.write_text(
            'ADD TABLE "NewTable"\n  AREA "Data Area"\n  TABLE-TYPE T\n\n'
            'ADD FIELD "Id" OF "NewTable" AS integer\n  ORDER 10\n\n'
            'ADD INDEX "Id" ON "NewTable"\n  PRIMARY\n  UNIQUE\n  ACTIVE\n'
            '  INDEX-FIELD "Id" ASCENDING\n'
        )
        apply_df(db2, df_file, dlc=DLC)

        delta = tmp_path / "delta.df"
        make_delta(db1, db2, delta, dlc=DLC)
        content = delta.read_text(errors="replace")
        assert "NewTable" in content


# ---------------------------------------------------------------------------
# Full sync_schema workflow
# ---------------------------------------------------------------------------

@skip_no_oe
@pytest.mark.integration
class TestSyncSchemaIntegration:
    def test_sync_adds_missing_table(self, tmp_path):
        target = create_empty_db(tmp_path / "target", dlc=DLC).with_suffix("")

        desired_df = tmp_path / "desired.df"
        desired_df.write_text(
            'ADD TABLE "SyncedTable"\n  AREA "Data Area"\n  TABLE-TYPE T\n\n'
            'ADD FIELD "Id" OF "SyncedTable" AS integer\n  ORDER 10\n\n'
            'ADD INDEX "Id" ON "SyncedTable"\n  PRIMARY\n  UNIQUE\n  ACTIVE\n'
            '  INDEX-FIELD "Id" ASCENDING\n'
        )
        sync_schema(target, desired_df, dlc=DLC)

        out = tmp_path / "verify.df"
        dump_schema(target, out, dlc=DLC)
        schema = parse_df(out)
        assert "SYNCEDTABLE" in schema.tables

    def test_sync_is_idempotent(self, tmp_path):
        target = create_empty_db(tmp_path / "target", dlc=DLC).with_suffix("")
        desired_df = tmp_path / "desired.df"
        desired_df.write_text(
            'ADD TABLE "T"\n  AREA "Data Area"\n  TABLE-TYPE T\n\n'
            'ADD FIELD "Id" OF "T" AS integer\n  ORDER 10\n\n'
            'ADD INDEX "Id" ON "T"\n  PRIMARY\n  UNIQUE\n  ACTIVE\n'
            '  INDEX-FIELD "Id" ASCENDING\n'
        )
        sync_schema(target, desired_df, dlc=DLC)
        # Second run should not raise and should produce empty delta
        sync_schema(target, desired_df, dlc=DLC)
