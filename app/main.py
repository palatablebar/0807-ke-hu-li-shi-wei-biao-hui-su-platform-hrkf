import os

from flask import Flask, jsonify, render_template, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge

from app.api import api
from app.business import DomainIssue
from app.config import MAX_FILE, ROOT
from app.http_errors import response
from app.migration.api import blueprint as migration_api
from app.migration.store import MigrationStore
from app.review.store import Store
from app.spec import MIGRATION_PROJECT, PROJECT


def create_app(database=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE + 16 * 1024
    app.extensions["runs"] = Store(
        database
        or os.getenv("WORKBENCH_DB", str(ROOT / "instance" / "workbench.sqlite3"))
    )
    app.extensions["migration_runs"] = MigrationStore(
        database
        or os.getenv("WORKBENCH_DB", str(ROOT / "instance" / "workbench.sqlite3"))
    )
    app.register_error_handler(DomainIssue, response)
    app.register_error_handler(
        RequestEntityTooLarge, lambda _: response(DomainIssue("FILE_TOO_LARGE"))
    )
    app.register_blueprint(api)
    app.register_blueprint(migration_api)

    @app.get("/")
    def home():
        return render_template("workbench.html", p=PROJECT)

    @app.get("/migration")
    def migration():
        return render_template("migration.html", p=MIGRATION_PROJECT)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok")

    @app.get("/examples/<profile>")
    def example(profile):
        from app.inputs import SAMPLES

        if profile not in SAMPLES:
            raise DomainIssue("SAMPLE_UNKNOWN")
        return send_from_directory(
            ROOT / "sample_data", SAMPLES[profile], as_attachment=True
        )

    @app.get("/migration/examples/<profile>")
    def migration_example(profile):
        from app.config import MIGRATION_SAMPLES

        if profile not in MIGRATION_SAMPLES:
            raise DomainIssue("SAMPLE_UNKNOWN")
        return send_from_directory(
            ROOT / "sample_data", MIGRATION_SAMPLES[profile], as_attachment=True
        )

    return app


app = create_app()
