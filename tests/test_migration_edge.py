from app.migration.review import execute, review
from migration_helpers import migration_csv, mrow, trow


def test_transaction_without_any_mapping_is_blocked(migration_store):
    report = execute(migration_store, migration_csv([trow("T1", "GHOST", 10)]))["report"]
    assert not report["balance"]["signable"]
    assert report["balance"]["issues"] == {"UNMAPPED_ID": 1}


def test_mapping_without_transactions_is_not_signable(migration_store):
    report = execute(migration_store, migration_csv([mrow("M1", "OLD1", "NEW1")]))["report"]
    assert report["balance"]["balanced"] and not report["balance"]["signable"]


def test_held_then_approve_flow_on_clean_batch(migration_store, migration_clean):
    run = execute(migration_store, migration_clean)
    review(
        migration_store,
        run["id"],
        dict(revision=0, status="HELD", note="先挂起等待审计排期"),
    )
    output = review(
        migration_store,
        run["id"],
        dict(revision=1, status="APPROVED", note="审计完成，准予签发"),
    )
    assert output["status"] == "APPROVED" and output["revision"] == 2


def test_rejected_mapping_keeps_line_number_for_audit(migration_store):
    rows = [
        mrow("S1", "X1", "X1"),
        mrow("OK", "OLD1", "NEW1"),
        trow("T1", "OLD1", 10),
    ]
    report = execute(migration_store, migration_csv(rows))["report"]
    bad = next(row for row in report["isolation"] if row["record"] == "S1")
    assert bad["line"] > 1 and bad["reason"] == "MAPPING_SELF"
