import io
from hashlib import sha256


def test_preview_does_not_write_to_store(migration_client):
    response = migration_client.post(
        "/api/migrations/preview", data={"sample": "dirty"}
    )
    assert response.status_code == 200
    assert response.json["balance"]["balanced"]
    assert migration_client.get("/api/migrations/runs").json == {"items": []}


def test_run_endpoints_round_trip(migration_client):
    created = migration_client.post("/api/migrations/runs", data={"sample": "clean"}).json
    fetched = migration_client.get("/api/migrations/runs/" + created["id"]).json
    assert fetched["id"] == created["id"] and fetched["status"] == "PENDING"
    listing = migration_client.get("/api/migrations/runs").json["items"]
    assert [item["id"] for item in listing] == [created["id"]]


def test_upload_matches_sample_content_addressing(migration_client, migration_clean):
    uploaded = migration_client.post(
        "/api/migrations/runs",
        data={"file": (io.BytesIO(migration_clean), "migration.csv")},
    ).json
    sampled = migration_client.post(
        "/api/migrations/runs", data={"sample": "clean"}
    ).json
    assert uploaded["id"] == sampled["id"]


def test_unknown_sample_and_missing_run(migration_client):
    assert (
        migration_client.post(
            "/api/migrations/preview", data={"sample": "nope"}
        ).status_code
        == 404
    )
    assert migration_client.get("/api/migrations/runs/missing").status_code == 404


def test_bad_header_is_rejected_without_persisting(migration_client):
    response = migration_client.post(
        "/api/migrations/runs",
        data={"file": (io.BytesIO(b"wrong,header\n"), "bad.csv")},
    )
    assert response.status_code == 422 and response.json["code"] == "HEADER_MISMATCH"
    assert migration_client.get("/api/migrations/runs").json == {"items": []}


def test_unbalanced_approval_returns_409(migration_client):
    run = migration_client.post(
        "/api/migrations/runs", data={"sample": "dirty"}
    ).json
    response = migration_client.patch(
        "/api/migrations/runs/" + run["id"],
        json=dict(revision=0, status="APPROVED", note="尝试强行签发"),
    )
    assert response.status_code == 409 and response.json["code"] == "MIGRATION_NOT_BALANCED"
    fetched = migration_client.get("/api/migrations/runs/" + run["id"]).json
    assert fetched["status"] == "PENDING" and fetched["revision"] == 0


def test_evidence_download_preserves_basis_and_checksum(migration_client, migration_clean):
    run = migration_client.post(
        "/api/migrations/runs", data={"sample": "clean"}
    ).json
    response = migration_client.get("/api/migrations/runs/" + run["id"] + "/evidence")
    assert response.status_code == 200 and "attachment" in response.headers["Content-Disposition"]
    packet = response.json
    assert packet["schema"] == "migration-evidence/1"
    assert packet["manifest"]["sha256"] == sha256(migration_clean).hexdigest()
    pending = packet["pending"][0]
    assert pending["basis"]["old_refs"] == ["C-OLD-1"]
    assert packet["ledger"] == {"C-NEW-1": 140, "C-NEW-2": 225}


def test_evidence_is_deterministic_for_revision(migration_client):
    run = migration_client.post(
        "/api/migrations/runs", data={"sample": "clean"}
    ).json
    first = migration_client.get(
        "/api/migrations/runs/" + run["id"] + "/evidence"
    ).data
    second = migration_client.get(
        "/api/migrations/runs/" + run["id"] + "/evidence"
    ).data
    assert first == second


def test_intake_guards_apply_to_migration_files(migration_client):
    oversized = b"x" * (256 * 1024 + 1)
    response = migration_client.post(
        "/api/migrations/runs",
        data={"file": (io.BytesIO(oversized), "big.csv")},
    )
    assert response.status_code == 413 and response.json["code"] == "FILE_TOO_LARGE"


def test_migration_store_is_separate_from_dimension_runs(migration_client):
    migration_client.post("/api/migrations/runs", data={"sample": "clean"})
    migration_client.post("/api/runs", data={"sample": "clean"})
    assert len(migration_client.get("/api/migrations/runs").json["items"]) == 1
    assert len(migration_client.get("/api/runs").json["items"]) == 1
