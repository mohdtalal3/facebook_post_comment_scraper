"""Central runtime configuration shared by all scraper modules.

The web app (or a CLI script) sets the session once via `set_session()`
and every scraper module reads the same values — no more per-module
globals scattered across files.
"""
import json
import os
import re
import sys

from . import proxy_utils

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"


def app_root():
    """Writable base directory: next to the executable when frozen (exe/dmg),
    otherwise the project root."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundle_root():
    """Read-only bundled assets root (PyInstaller extracts to _MEIPASS)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return app_root()


# App version: stamped into _version.py by the build workflow
try:
    from _version import __version__
except ImportError:
    __version__ = "dev"

APP_VERSION = __version__

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


# ---- proxy configuration (data/settings.json persistence) ----
SETTINGS_FILE = os.path.join(app_root(), "data", "settings.json")

# In-memory proxy state, loaded from settings.json at startup
PROXY_SETTINGS = {"rotating": "", "static": ""}


def mask_proxy(url):
    """Mask the password in a proxy URL: http://user:***@host:port"""
    if not url:
        return ""
    return re.sub(r"(://[^:@/]+:)[^@/]+(@)", r"\1***\2", url)


def load_proxy_settings():
    """Load saved proxy settings (data/settings.json).

    Called once at app startup so proxies saved via the UI survive restarts.
    """
    global PROXY_SETTINGS
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            settings = json.load(f)
    except Exception:
        return
    PROXY_SETTINGS = {
        "rotating": settings.get("rotating_proxy", "") or "",
        "static": settings.get("static_proxy", "") or "",
    }


def save_proxy_settings(rotating=None, static=None):
    """Persist proxy URLs to data/settings.json and apply them immediately.

    Passing an empty string clears that proxy.
    """
    global PROXY_SETTINGS
    if rotating is not None:
        PROXY_SETTINGS["rotating"] = rotating.strip()
    if static is not None:
        PROXY_SETTINGS["static"] = static.strip()

    settings = {
        "rotating_proxy": PROXY_SETTINGS["rotating"],
        "static_proxy": PROXY_SETTINGS["static"],
    }
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
