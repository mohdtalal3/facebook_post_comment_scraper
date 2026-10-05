"""Central runtime configuration shared by all scraper modules.

The web app (or a CLI script) sets the session once via `set_session()`
and every scraper module reads the same values — no more per-module
globals scattered across files.
"""
import os
import re

from dotenv import load_dotenv

from . import proxy_utils

load_dotenv()

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"

# Session state (set at runtime by the web app / CLI)
COOKIES = {}
FB_DTSG = ""
PROXIES = None


def set_session(cookies=None, fb_dtsg=None, proxies=None):
    """Set the active session. `cookies` is a dict, `proxies` a requests proxy dict."""
    global COOKIES, FB_DTSG, PROXIES
    COOKIES = cookies or {}
    FB_DTSG = fb_dtsg or ""
    PROXIES = proxies


def apply_proxy(has_cookies: bool, log=None):
    """Pick the right proxy mode (static for cookie sessions, rotating otherwise)."""
    global PROXIES
    proxies = proxy_utils.select_proxy(has_cookies)
    PROXIES = proxies
    if log:
        if proxies:
            url = proxies.get("http", "")
            if has_cookies:
                m = re.search(r":(\d+)$", url)
                log(f"Proxy: STATIC (cookie session) — port {m.group(1) if m else '?'}")
            else:
                log(f"Proxy: ROTATING — {url}")
        else:
            log("No proxy configured — requests will go out directly")
    return proxies


def user_id():
    return COOKIES.get("c_user", "0")
