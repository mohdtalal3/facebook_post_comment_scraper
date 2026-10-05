"""Settings API: cookies / fb_dtsg session config + Chrome login flow."""
from flask import Blueprint, jsonify, request

from scraper import auth
from scraper import config

settings_bp = Blueprint("api_settings", __name__)

_chrome_helper = None


def _session_state():
    return {
        "has_cookies": bool(config.COOKIES),
        "cookie_count": len(config.COOKIES),
        "has_dtsg": bool(config.FB_DTSG),
    }


@settings_bp.route("", methods=["GET"])
def get_settings():
    return jsonify(_session_state())


@settings_bp.route("", methods=["POST"])
def set_settings():
    """Accepts {cookies: "..."} (raw cookie string) and/or {curl: "..."}."""
    body = request.get_json(force=True, silent=True) or {}

    cookies_str = body.get("cookies", "").strip()
    curl_text = body.get("curl", "").strip()

    if curl_text:
        curl_cookies, dtsg = auth.parse_curl(curl_text)
        if curl_cookies:
            cookies_str = curl_cookies
        if dtsg:
            body["fb_dtsg"] = dtsg

    if not cookies_str and not body.get("fb_dtsg"):
        return jsonify({"error": "provide a cookie string or a cURL command"}), 400

    cookies = auth.parse_cookies(cookies_str) if cookies_str else dict(config.COOKIES)
    fb_dtsg = body.get("fb_dtsg") or config.FB_DTSG

    from scraper.config import set_session
    set_session(cookies=cookies, fb_dtsg=fb_dtsg)

    return jsonify(_session_state())


@settings_bp.route("", methods=["DELETE"])
def clear_settings():
    from scraper.config import set_session
    set_session(cookies={}, fb_dtsg="")
    return jsonify(_session_state())


@settings_bp.route("/chrome/start", methods=["POST"])
def chrome_start():
    global _chrome_helper
    if _chrome_helper and _chrome_helper._thread and _chrome_helper._thread.is_alive():
        return jsonify({"error": "Chrome login already in progress"}), 409

    from scraper.logging_utils import log
    _chrome_helper = auth.ChromeLoginHelper(log=log)
    _chrome_helper.start()
    return jsonify({"ok": True}), 202


@settings_bp.route("/chrome/finish", methods=["POST"])
def chrome_finish():
    global _chrome_helper
    if not _chrome_helper:
        return jsonify({"error": "Chrome login was never started"}), 400

    result = _chrome_helper.finish(timeout=180)
    if result.get("error"):
        return jsonify({"error": result["error"]}), 500

    from scraper.config import set_session
    set_session(cookies=auth.parse_cookies(result["cookies"]),
                fb_dtsg=result["fb_dtsg"])
    return jsonify(_session_state())
