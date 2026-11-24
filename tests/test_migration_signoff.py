import pytest

from app.business import DomainIssue
from app.migration.review import execute, review
from migration_helpers import migration_csv, mrow, trow


def approve(store, run_id, note="切换期归属已复核"):
    return review(
        store, run_id, dict(revision=0, status="APPROVED", note=note)
    )


def test_clean_sample_is_balanced_and_signable(migration_store, migration_clean):
    run = execute(migration_store, migration_clean)
    balance = run["report"]["balance"]
    assert balance["balanced"] and balance["signable"]
    output = approve(migration_store, run["id"])
    assert output["status"] == "APPROVED" and output["revision"] == 1


def test_dirty_sample_is_balanced_but_not_signable(migration_store, migration_dirty):
    run = execute(migration_store, migration_dirty)
    balance = run["report"]["balance"]
    # 数量金额守恒是技术不变量；存在隔离行则业务上不可签发。
    assert balance["balanced"] and not balance["signable"]
    with pytest.raises(DomainIssue, match="MIGRATION_NOT_BALANCED"):
        approve(migration_store, run["id"])


def test_failed_signoff_keeps_legacy_attribution_and_pending_basis(
    migration_store, migration_dirty
):
    run = execute(migration_store, migration_dirty)
    before = migration_store.load(run["id"])
    with pytest.raises(DomainIssue):
        approve(migration_store, run["id"])
    after = migration_store.load(run["id"])
    assert after["revision"] == 0 and after["status"] == "PENDING"
    assert after["report"]["attributed"] == before["report"]["attributed"]
    assert after["report"]["pending"] == before["report"]["pending"]
    assert after["report"]["balance"] == before["report"]["balance"]


def test_held_review_is_allowed_even_when_not_signable(
    migration_store, migration_dirty
):
    run = execute(migration_store, migration_dirty)
    output = review(
        migration_store,
        run["id"],
        dict(revision=0, status="HELD", note="待核交易等待审计确认"),
    )
    assert output["status"] == "HELD" and output["revision"] == 1


def test_approved_migration_is_final(migration_store, migration_clean):
    run = execute(migration_store, migration_clean)
    approve(migration_store, run["id"])
    with pytest.raises(DomainIssue, match="RUN_FINALIZED"):
        review(
            migration_store,
            run["id"],
            dict(revision=1, status="HELD", note="试图撤销签发"),
        )


def test_optimistic_lock_conflict(migration_store, migration_clean):
    run = execute(migration_store, migration_clean)
    payload = dict(revision=0, status="HELD", note="第一次复核")
    review(migration_store, run["id"], payload)
    with pytest.raises(DomainIssue, match="STALE_REVIEW"):
        review(migration_store, run["id"], payload)
    assert migration_store.load(run["id"])["revision"] == 1


def test_note_validation(migration_store, migration_clean):
    run = execute(migration_store, migration_clean)
    with pytest.raises(DomainIssue, match="REVIEW_FIELDS"):
        review(migration_store, run["id"], dict(revision=0, status="APPROVED", note="x"))


def test_pending_only_batch_can_still_be_signed_when_balanced(migration_store):
    # 待核不是隔离：全部对平时，批次仍可签发并由待核依据承担审计追溯。
    rows = [mrow("MP1", "OLD1", "NEW1"), trow("T3", "OLD1", 60), trow("T3", "NEW1", 60)]
    run = execute(migration_store, migration_csv(rows))
    assert run["report"]["balance"]["signable"]
    output = approve(migration_store, run["id"], note="待核依据随证据留档")
    assert output["status"] == "APPROVED"


def test_source_count_and_cents_reconcile_across_three_buckets(migration_store):
    rows = [
        mrow("MP1", "OLD1", "NEW1"),
        trow("A", "OLD1", 100),
        trow("B", "NEW1", 40),
        trow("C", "OLD1", 60),
        trow("C", "NEW1", 60),
        trow("D", "GHOST", 88),
    ]
    balance = execute(migration_store, migration_csv(rows))["report"]["balance"]
    assert balance["source"] == {"count": 4, "cents": 288}
    assert balance["attributed"] == {"count": 2, "cents": 140}
    assert balance["pending"] == {"count": 1, "cents": 60}
    assert balance["blocked"] == {"count": 1, "cents": 88}
    assert balance["count_conservation"] and balance["cents_conservation"]
    assert not balance["signable"]
