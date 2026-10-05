"""Scrape job history API."""
from flask import Blueprint, jsonify

from scraper import storage

jobs_bp = Blueprint("api_jobs", __name__)


@jobs_bp.route("", methods=["GET"])
def list_jobs():
    return jsonify({"jobs": storage.list_jobs()})
