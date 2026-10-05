"""Scrape job history API."""
import os

from flask import Blueprint, Response, jsonify

from scraper import storage

jobs_bp = Blueprint("api_jobs", __name__)


@jobs_bp.route("", methods=["GET"])
def list_jobs():
    return jsonify({"jobs": storage.list_jobs()})


@jobs_bp.route("/<job_id>/logs")
def job_logs(job_id):
    path = os.path.join(storage.DATA_DIR, "logs", f"{job_id}.txt")
    if not os.path.exists(path):
        return jsonify({"error": "logs not found for this job"}), 404
    with open(path, encoding="utf-8") as f:
        return Response(f.read(), mimetype="text/plain")
