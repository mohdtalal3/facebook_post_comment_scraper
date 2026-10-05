"""Scrape job API: start, status, live logs (SSE + polling), stop."""
import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from ..jobs import manager

scrape_bp = Blueprint("api_scrape", __name__)


@scrape_bp.route("/scrape", methods=["POST"])
def start_scrape():
    body = request.get_json(force=True, silent=True) or {}

    job_type = body.get("type")
    if job_type not in ("simple_post", "page_posts", "group_posts"):
        return jsonify({"error": "type must be simple_post, page_posts or group_posts"}), 400

    urls = [u.strip() for u in body.get("urls", []) if u and u.strip()]
    if not urls:
        return jsonify({"error": "at least one URL is required"}), 400

    params = {
        "urls": urls,
        "download_images": bool(body.get("download_images", True)),
    }
    if job_type in ("page_posts", "group_posts"):
        params["limit"] = max(1, int(body.get("limit", 10)))
        params["min_comments"] = max(0, int(body.get("min_comments", 0)))
        params["fetch_comments"] = bool(body.get("fetch_comments", True))

        try:
            start_date, end_date = _parse_date_range(body.get("start_date"), body.get("end_date"))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

    try:
        job = manager.start(job_type, params)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409

    return jsonify({"job": job.to_dict()}), 202


def _parse_date_range(start_date, end_date):
    """Convert 'YYYY-MM-DD' strings to epoch seconds.

    start_date → beginning of that day, end_date → end of that day (inclusive).
    """
    from datetime import datetime, timedelta

    def parse(value, offset_days):
        if not value:
            return None
        try:
            d = datetime.strptime(value.strip(), "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"invalid date '{value}', expected YYYY-MM-DD")
        if offset_days:
            d += timedelta(days=1) - timedelta(seconds=1)  # end of day
        return int(d.timestamp())

    return parse(start_date, False), parse(end_date, True)

@scrape_bp.route("/job", methods=["GET"])
def job_status():
    after = request.args.get("after", 0, type=int)
    job = manager.last
    if not job:
        return jsonify({"status": "idle", "logs": []})
    data = job.to_dict()
    data["logs"] = job.get_logs(after)
    return jsonify(data)


@scrape_bp.route("/job/logs/stream")
def job_logs_stream():
    """SSE stream of live logs for the current/last job."""
    def generate():
        after = 0
        last_id = None
        while True:
            job = manager.last
            if not job:
                yield _sse("idle", {})
                break
            if job.id != last_id:
                last_id = job.id
                after = 0
            logs = job.wait_for_logs(after, timeout=1.0)
            if logs:
                after += len(logs)
                yield _sse("log", {"logs": logs, "after": after})
            if job.status != "running" and job.log_count() <= after:
                yield _sse("end", {"status": job.status})
                break

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@scrape_bp.route("/job/stop", methods=["POST"])
def stop_job():
    job = manager.last
    if not job or job.status != "running":
        return jsonify({"error": "no running job"}), 400
    job.stop()
    return jsonify({"ok": True})
