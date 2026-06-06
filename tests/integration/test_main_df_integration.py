"""Integration tests for the full main.df → database → round-trip workflow.

Requires:
  - A live OpenEdge 12.x installation (DLC env var or /usr/dlc)
  - A main.df schema file at /tmp/main.df or /var/db/schema/11.10.0-main.df

Run with:
    pytest -m integration tests/integration/test_main_df_integration.py -v
"""

import pytest
from pathlib import Path

from tests.integration.conftest import skip_no_oe, skip_no_main_df, DLC
from pyoe.db.creator import create_empty_db
from pyoe.schema.applier import apply_df, sync_schema
from pyoe.schema.comparator import make_delta
from pyoe.schema.dumper import dump_schema
from pyoe.schema.loader import parse_df


# ---------------------------------------------------------------------------
# apply_df: load main.df into a fresh database
# ---------------------------------------------------------------------------

@skip_no_main_df
@pytest.mark.integration
class TestApplyMainDf:
    def test_apply_produces_correct_table_count(self, main_schema_db, main_df_path, tmp_path):
        """Every table in main.df should be present after apply_df."""
        desired = parse_df(main_df_path)
        out = tmp_path / "dumped.df"
        dump_schema(main_schema_db, out, dlc=DLC, timeout=180)
        actual = parse_df(out)

        missing = set(desired.tables.keys()) - set(actual.tables.keys())
        assert not missing, f"Tables missing after load: {sorted(missing)[:10]}"

    def test_apply_no_extra_user_tables(self, main_schema_db, main_df_path, tmp_path):
        """No unexpected user tables should appear beyond what the .df defines."""
        desired = parse_df(main_df_path)
        out = tmp_path / "dumped.df"
        dump_schema(main_schema_db, out, dlc=DLC, timeout=180)
        actual = parse_df(out)

        extra = set(actual.tables.keys()) - set(desired.tables.keys())
        assert not extra, f"Unexpected tables after load: {sorted(extra)}"

    def test_apply_preserves_all_fields(self, main_schema_db, main_df_path, tmp_path):
        """Every field defined in main.df should survive the round-trip."""
        desired = parse_df(main_df_path)
        out = tmp_path / "dumped.df"
        dump_schema(main_schema_db, out, dlc=DLC, timeout=180)
        actual = parse_df(out)

        missing_fields = []
        for tname in sorted(desired.tables.keys()):
            if tname not in actual.tables:
                continue
            dt = desired.tables[tname]
            at = actual.tables[tname]
            lost = set(dt.fields.keys()) - set(at.fields.keys())
            if lost:
                missing_fields.append(f"{tname}: {sorted(lost)}")

        assert not missing_fields, (
            f"Fields missing after load ({len(missing_fields)} tables affected):\n"
            + "\n".join(missing_fields[:10])
        )

    def test_apply_preserves_sequences(self, main_schema_db, main_df_path, tmp_path):
        """Sequences defined in main.df should be present after load."""
        desired = parse_df(main_df_path)
        if not desired.sequences:
            pytest.skip("main.df defines no sequences")

        out = tmp_path / "dumped.df"
        dump_schema(main_schema_db, out, dlc=DLC, timeout=180)
        actual = parse_df(out)

        missing = set(desired.sequences.keys()) - set(actual.sequences.keys())
        assert not missing, f"Sequences missing: {sorted(missing)[:10]}"

    def test_apply_field_datatypes_correct(self, main_schema_db, main_df_path, tmp_path):
        """Spot-check: field datatypes should survive the round-trip unchanged."""
        desired = parse_df(main_df_path)
        out = tmp_path / "dumped.df"
        dump_schema(main_schema_db, out, dlc=DLC, timeout=180)
        actual = parse_df(out)

        mismatched = []
        for tname in sorted(desired.tables.keys())[:30]:
            if tname not in actual.tables:
                continue
            for fname, df in desired.tables[tname].fields.items():
                af = actual.tables[tname].fields.get(fname)
                if af and af.datatype != df.datatype:
                    mismatched.append(
                        f"{tname}.{fname}: want {df.datatype}, got {af.datatype}"
                    )

        assert not mismatched, (
            f"Datatype mismatches ({len(mismatched)}):\n" + "\n".join(mismatched[:10])
        )


# ---------------------------------------------------------------------------
# make_delta: incremental comparison
# ---------------------------------------------------------------------------

@skip_no_main_df
@pytest.mark.integration
class TestMainDfDelta:
    def test_delta_self_is_empty(self, main_schema_db, tmp_path):
        """Comparing main_schema_db against itself should produce an empty delta."""
        # Both DICTDB and DICTDB2 point to the same schema → no differences.
        db2 = create_empty_db(tmp_path / "clone", dlc=DLC).with_suffix("")

        # Load same df into db2 to make them identical
        out_df = tmp_path / "current.df"
        dump_schema(main_schema_db, out_df, dlc=DLC, timeout=180)
        apply_df(db2, out_df, dlc=DLC, timeout=600)

        delta = tmp_path / "delta.df"
        make_delta(main_schema_db, db2, delta, dlc=DLC, timeout=300)
        # dump_inc always writes a small file header; an empty schema delta has no ADD/UPDATE/DELETE lines
        content = delta.read_text(errors="replace")
        schema_lines = [l for l in content.splitlines()
                        if l.startswith(("ADD ", "UPDATE ", "DELETE ", "RENAME ", "DROP "))]
        assert not schema_lines, (
            f"Expected empty delta but found schema changes:\n" + "\n".join(schema_lines[:5])
        )

    def test_delta_detects_added_table(self, main_schema_db, tmp_path):
        """Delta should include ADD TABLE when desired DB has an extra table."""
        desired = create_empty_db(tmp_path / "desired", dlc=DLC).with_suffix("")

        # Start desired from the main schema, then add one more table
        current_df = tmp_path / "base.df"
        dump_schema(main_schema_db, current_df, dlc=DLC, timeout=180)
        apply_df(desired, current_df, dlc=DLC, timeout=600)

        extra_df = tmp_path / "extra.df"
        extra_df.write_text(
            'ADD TABLE "ZZZDeltaTest"\n  AREA "Schema Area"\n  DUMP-NAME "zzzdelta"\n\n'
            'ADD FIELD "Id" OF "ZZZDeltaTest" AS integer\n  ORDER 10\n  POSITION 2\n  MAX-WIDTH 4\n\n'
            'ADD INDEX "Id" ON "ZZZDeltaTest"\n  AREA "Schema Area"\n  UNIQUE\n  PRIMARY\n'
            '  INDEX-FIELD "Id" ASCENDING\n'
        )
        apply_df(desired, extra_df, dlc=DLC)

        delta = tmp_path / "delta.df"
        make_delta(main_schema_db, desired, delta, dlc=DLC, timeout=300)
        content = delta.read_text(errors="replace")
        assert "ZZZDeltaTest" in content


# ---------------------------------------------------------------------------
# sync_schema: idempotency with main.df
# ---------------------------------------------------------------------------

@skip_no_main_df
@pytest.mark.integration
class TestSyncMainDf:
    def test_sync_is_idempotent(self, main_df_path, tmp_path):
        """Running sync_schema twice with the same .df must produce an empty second delta."""
        target = create_empty_db(tmp_path / "target", dlc=DLC).with_suffix("")

        delta1 = sync_schema(target, main_df_path, dlc=DLC, timeout=600)
        assert delta1.stat().st_size > 0, "First sync should have applied changes"

        delta2 = sync_schema(target, main_df_path, dlc=DLC, timeout=600)
        content2 = delta2.read_text(errors="replace")
        schema_lines = [l for l in content2.splitlines()
                        if l.startswith(("ADD ", "UPDATE ", "DELETE ", "RENAME ", "DROP "))]
        assert not schema_lines, (
            f"Second sync should be a no-op but produced changes:\n" + "\n".join(schema_lines[:5])
        )

    def test_sync_result_db_matches_desired(self, main_df_path, tmp_path):
        """After sync_schema, the target DB schema must match main.df exactly."""
        target = create_empty_db(tmp_path / "target", dlc=DLC).with_suffix("")
        sync_schema(target, main_df_path, dlc=DLC, timeout=600)

        out = tmp_path / "verify.df"
        dump_schema(target, out, dlc=DLC, timeout=180)

        desired = parse_df(main_df_path)
        actual = parse_df(out)

        missing = set(desired.tables.keys()) - set(actual.tables.keys())
        extra = set(actual.tables.keys()) - set(desired.tables.keys())

        assert not missing, f"Tables missing after sync: {sorted(missing)[:10]}"
        assert not extra, f"Unexpected tables after sync: {sorted(extra)}"
