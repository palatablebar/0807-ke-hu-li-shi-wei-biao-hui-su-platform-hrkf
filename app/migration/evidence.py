import json


def artifact(run):
    packet = {
        "schema": "migration-evidence/1",
        "manifest": run["report"]["manifest"],
        "balance": run["report"]["balance"],
        "mappings": run["report"]["mappings"],
        "ledger": run["report"]["ledger"],
        "attributed": run["report"]["attributed"],
        "pending": run["report"]["pending"],
        "intake": run["report"]["intake"],
        "review": {key: run[key] for key in ("status", "revision", "note", "reviewed")},
    }
    return (
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
