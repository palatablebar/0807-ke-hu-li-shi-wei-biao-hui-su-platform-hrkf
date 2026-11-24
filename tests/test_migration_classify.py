from app.migration.migrate import (
    AMBIGUOUS,
    MIGRATED,
    NEW_DIRECT,
    PENDING_REVIEW,
    UNMAPPED,
    run,
)
from migration_helpers import migration_csv, mrow, trow


def by_record(rows):
    return {row["record"]: row for row in rows}


def base_mappings():
    return [mrow("MP1", "OLD1", "NEW1"), mrow("MP2", "OLD2", "NEW2")]


def test_old_only_transaction_is_re_attributed_to_new_customer():
    report = run(migration_csv(base_mappings() + [trow("T1", "OLD1", 100)]))
    item = by_record(report["attributed"])["T1"]
    assert item["status"] == MIGRATED
    assert item["old_customer"] == "OLD1" and item["new_customer"] == "NEW1"


def test_new_only_transaction_keeps_new_customer():
    report = run(migration_csv(base_mappings() + [trow("T2", "NEW1", 40)]))
    item = by_record(report["attributed"])["T2"]
    assert item["status"] == NEW_DIRECT and item["new_customer"] == "NEW1"
    assert item["old_customer"] is None


def test_dual_hit_transaction_is_held_pending_with_basis_not_re_attached():
    rows = base_mappings() + [trow("T3", "OLD1", 60), trow("T3", "NEW1", 60)]
    report = run(migration_csv(rows))
    assert report["attributed"] == []
    pending = report["pending"]
    assert len(pending) == 1 and pending[0]["record"] == "T3"
    item = pending[0]
    assert item["status"] == PENDING_REVIEW and item["new_customer"] == "NEW1"
    # 待核依据必须保留原签约客户，供审计追溯。
    assert item["basis"]["old_refs"] == ["OLD1"]
    assert item["basis"]["new_refs"] == ["NEW1"]
    assert item["basis"]["mapping"] == {"OLD1": "NEW1"}
    assert set(item["basis"]["hit_lines"]) == {"OLD1", "NEW1"}


def test_pending_transaction_is_excluded_from_new_customer_ledger():
    rows = base_mappings() + [
        trow("T1", "OLD1", 100),
        trow("T3", "OLD1", 60),
        trow("T3", "NEW1", 60),
    ]
    report = run(migration_csv(rows))
    assert report["ledger"] == {"NEW1": 100}


def test_unknown_customer_is_blocked_and_keeps_received_amount():
    report = run(migration_csv(base_mappings() + [trow("T9", "GHOST", 88)]))
    reason = {row["record"]: row["reason"] for row in report["isolation"]}
    assert reason["T9"] == UNMAPPED
    assert report["balance"]["blocked"] == {"count": 1, "cents": 88}
    assert by_record(report["attributed"]).get("T9") is None


def test_one_transaction_hitting_two_distinct_customers_is_ambiguous():
    rows = base_mappings() + [trow("T5", "NEW1", 35), trow("T5", "NEW2", 35)]
    report = run(migration_csv(rows))
    reason = {row["record"]: row["reason"] for row in report["isolation"]}
    assert reason["T5"] == AMBIGUOUS


def test_ledger_sums_per_new_customer_and_omits_pending():
    rows = base_mappings() + [
        trow("A", "OLD1", 100),
        trow("B", "NEW1", 40),
        trow("C", "OLD2", 200),
        trow("D", "NEW2", 25),
        trow("E", "OLD1", 60),
        trow("E", "NEW1", 60),
    ]
    report = run(migration_csv(rows))
    assert report["ledger"] == {"NEW1": 140, "NEW2": 225}
    assert report["balance"]["attributed"] == {"count": 4, "cents": 365}
    assert report["balance"]["pending"] == {"count": 1, "cents": 60}


def test_self_mapping_and_mapping_chain_are_rejected():
    rows = [
        mrow("S1", "X1", "X1"),
        mrow("C1", "A1", "B1"),
        mrow("C2", "B1", "D1"),
        trow("T", "A1", 10),
    ]
    report = run(migration_csv(rows))
    reasons = {row["record"]: row["reason"] for row in report["isolation"]}
    assert reasons["S1"] == "MAPPING_SELF"
    assert reasons["C1"] == "MAPPING_CHAIN" and reasons["C2"] == "MAPPING_CHAIN"


def test_transaction_cannot_carry_mapping_target():
    rows = base_mappings() + [["T1", "transaction", "OLD1", "NEW1", "10", "坏行"]]
    report = run(migration_csv(rows))
    assert report["intake"]["reasons"] == {"MAPPING_FIELD_ON_TX": 1}
