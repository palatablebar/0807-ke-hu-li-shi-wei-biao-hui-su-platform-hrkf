from flask import Blueprint, Response, current_app, jsonify, request

from app.migration.evidence import artifact
from app.migration.inputs import read_migration_input
from app.migration.migrate import run
from app.migration.review import execute, review

blueprint = Blueprint("migration", __name__, url_prefix="/api/migrations")


@blueprint.post("/preview")
def preview():
    # 阶段预览不入库：返回完整迁移报告，但不写入任何批次。
    return jsonify(run(read_migration_input()))


@blueprint.route("/runs", methods=["GET", "POST"])
def runs():
    store = current_app.extensions["migration_runs"]
    if request.method == "GET":
        return jsonify(items=store.list())
    return jsonify(execute(store, read_migration_input()))


@blueprint.route("/runs/<run_id>", methods=["GET", "PATCH"])
def batch(run_id):
    store = current_app.extensions["migration_runs"]
    if request.method == "GET":
        return jsonify(store.load(run_id))
    return jsonify(review(store, run_id, request.get_json(silent=True)))


@blueprint.get("/runs/<run_id>/evidence")
def export(run_id):
    report = current_app.extensions["migration_runs"].load(run_id)
    return Response(
        artifact(report),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="migration-{report["id"][:12]}.json"',
            "Cache-Control": "no-store",
        },
    )
