import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from app.business import DomainIssue

SCHEMA = """CREATE TABLE IF NOT EXISTS migrations (
    id TEXT PRIMARY KEY, report TEXT NOT NULL, created TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', revision INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '', reviewed TEXT
);"""


class MigrationStore:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=15)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute(SCHEMA)
            yield db

    def register(self, run_id, report):
        with self.connect() as db:
            # 内容寻址 + 冲突不写入：同一来源重跑不会重复入库，也不会改变既有归属。
            db.execute(
                "INSERT INTO migrations(id,report,created) VALUES (?,?,?) "
                "ON CONFLICT(id) DO NOTHING",
                (
                    run_id,
                    json.dumps(report, ensure_ascii=False),
                    report["manifest"]["created"],
                ),
            )
        return self.load(run_id)

    def load(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM migrations WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise DomainIssue("MIGRATION_NOT_FOUND")
        result = dict(row)
        result["report"] = json.loads(result["report"])
        return result

    def list(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,created,status,revision,note FROM migrations "
                    "ORDER BY created DESC,id LIMIT 50"
                )
            ]

    def revise(self, run_id, revision, status, note, now):
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE migrations SET status=?,note=?,reviewed=?,revision=revision+1 "
                "WHERE id=? AND revision=?",
                (status, note, now, run_id, revision),
            )
            if cursor.rowcount != 1:
                raise DomainIssue("STALE_REVIEW")
        return self.load(run_id)
