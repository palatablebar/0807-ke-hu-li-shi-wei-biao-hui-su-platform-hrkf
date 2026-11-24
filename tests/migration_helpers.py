import io

import pytest

from app.migration.schema import HEADER


def mrow(record, old, new, note="映射"):
    return [record, "mapping", old, new, "0", note]


def trow(record, customer, cents, note="交易"):
    return [record, "transaction", customer, "", str(cents), note]


def migration_csv(rows):
    import csv

    stream = io.StringIO(newline="")
    csv.writer(stream).writerows([HEADER, *rows])
    return stream.getvalue().encode()


@pytest.fixture
def migration_dirty():
    from app.config import ROOT

    return (ROOT / "sample_data" / "migration_incoming.csv").read_bytes()


@pytest.fixture
def migration_clean():
    from app.config import ROOT

    return (ROOT / "sample_data" / "migration_ready.csv").read_bytes()


@pytest.fixture
def migration_store(tmp_path):
    from app.migration.store import MigrationStore

    return MigrationStore(tmp_path / "migrations.sqlite3")


@pytest.fixture
def migration_client(tmp_path):
    from app.main import create_app

    return create_app(tmp_path / "runs.db").test_client()
