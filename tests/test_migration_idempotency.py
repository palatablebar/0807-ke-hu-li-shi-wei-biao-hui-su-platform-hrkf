from app.migration.migrate import run
from app.migration.review import execute
from migration_helpers import migration_csv, mrow, trow


def mappings():
    return [mrow("MP1", "OLD1", "NEW1")]


def test_replay_same_registration_is_counted_but_ingested_once():
    rows = mappings() + [
        trow("T1", "OLD1", 100),
        trow("T1", "OLD1", 100),
        trow("T1", "OLD1", 100),
    ]
    report = run(migration_csv(rows))
    assert report["intake"]["replay"] == 2
    assert report["balance"]["source"]["count"] == 1
    assert len(report["attributed"]) == 1
    assert report["balance"]["line_conservation"]


def test_dual_hit_replay_does_not_duplicate_pending_entry():
    rows = mappings() + [
        trow("T3", "OLD1", 60),
        trow("T3", "NEW1", 60),
        trow("T3", "OLD1", 60),
    ]
    report = run(migration_csv(rows))
    assert len(report["pending"]) == 1
    assert report["balance"]["pending"] == {"count": 1, "cents": 60}


def test_same_customer_conflicting_amounts_isolate_whole_transaction():
    rows = mappings() + [trow("T1", "OLD1", 100), trow("T1", "OLD1", 101)]
    report = run(migration_csv(rows))
    assert report["intake"]["reasons"] == {"DUPLICATE_CONFLICT": 2}
    assert report["balance"]["source"]["count"] == 0


def test_cross_customer_conflicting_amounts_isolate_whole_transaction():
    rows = [mrow("MP1", "OLD1", "NEW1"), mrow("MP2", "OLD2", "NEW2")]
    rows += [trow("T5", "OLD1", 35), trow("T5", "OLD2", 36)]
    report = run(migration_csv(rows))
    assert all(row["reason"] == "DUPLICATE_CONFLICT" for row in report["isolation"])


def test_byte_identical_rerun_returns_same_stored_batch(migration_store, migration_clean):
    first = execute(migration_store, migration_clean)
    second = execute(migration_store, migration_clean)
    assert first == second and len(migration_store.list()) == 1


def test_rerun_preserves_attribution_and_pending_basis(migration_store, migration_clean):
    first = execute(migration_store, migration_clean)
    execute(migration_store, migration_clean)
    loaded = migration_store.load(first["id"])
    assert loaded["report"]["attributed"] == first["report"]["attributed"]
    assert loaded["report"]["pending"] == first["report"]["pending"]


def test_different_source_creates_distinct_batch(
    migration_store, migration_clean, migration_dirty
):
    a = execute(migration_store, migration_clean)
    b = execute(migration_store, migration_dirty)
    assert a["id"] != b["id"] and len(migration_store.list()) == 2


def test_parallel_rerun_commits_single_row(migration_store, migration_clean):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(4)

    def load():
        barrier.wait(3)
        return execute(migration_store, migration_clean)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: load(), range(4)))
    assert all(item == results[0] for item in results)
    assert len(migration_store.list()) == 1
