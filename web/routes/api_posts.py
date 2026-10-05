"""Scraped posts API: list with filters, view, download JSON, download images, delete."""
from flask import Blueprint, Response, jsonify, request

from scraper import storage

posts_bp = Blueprint("api_posts", __name__)


@posts_bp.route("", methods=["GET"])
def list_posts():
    posts = storage.list_posts(
        post_type=request.args.get("type") or None,
        source=request.args.get("source") or None,
        query=request.args.get("q") or None,
        min_comments=request.args.get("min_comments", 0, type=int),
        job_id=request.args.get("job_id") or None,
    )
    return jsonify({"posts": posts, "sources": storage.list_sources()})


@posts_bp.route("/view", methods=["GET"])
def view_post():
    data = storage.load_post(request.args.get("type"),
                             request.args.get("source"),
                             request.args.get("id"))
    if not data:
        return jsonify({"error": "post not found"}), 404
    return jsonify({"post": data})


@posts_bp.route("/download", methods=["GET"])
def download_post():
    data = storage.load_post(request.args.get("type"),
                             request.args.get("source"),
                             request.args.get("id"))
    if not data:
        return jsonify({"error": "post not found"}), 404

    import json as _json
    post_id = request.args.get("id")
    return Response(
        _json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename={post_id}.json"},
    )


@posts_bp.route("/images", methods=["GET"])
def download_images():
    result = storage.images_zip(request.args.get("type"),
                                request.args.get("source"),
                                request.args.get("id"))
    if not result:
        return jsonify({"error": "no images found for this post"}), 404

    zip_bytes, filename = result
    return Response(zip_bytes, mimetype="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@posts_bp.route("/download-all", methods=["GET"])
def download_all():
    result = storage.export_all_zip()
    if not result:
        return jsonify({"error": "no posts to export"}), 404
    zip_bytes, filename = result
    return Response(zip_bytes, mimetype="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@posts_bp.route("/download-selected", methods=["POST"])
def download_selected():
    body = request.get_json(force=True, silent=True) or {}
    keys = [(p.get("type"), p.get("source"), p.get("id"))
            for p in body.get("posts", []) if p.get("id")]
    if not keys:
        return jsonify({"error": "no posts selected"}), 400

    result = storage.posts_zip(keys)
    if not result:
        return jsonify({"error": "no files found for the selected posts"}), 404
    zip_bytes, filename = result
    return Response(zip_bytes, mimetype="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@posts_bp.route("/delete", methods=["POST"])
def delete_post():
    body = request.get_json(force=True, silent=True) or {}
    deleted = storage.delete_post(body.get("type"), body.get("source"), body.get("id"))
    if not deleted:
        return jsonify({"error": "post not found"}), 404
    return jsonify({"ok": True})
