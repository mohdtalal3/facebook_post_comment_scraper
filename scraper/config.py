"""Central runtime configuration shared by all scraper modules.

The web app (or a CLI script) sets the session once via `set_session()`
and every scraper module reads the same values — no more per-module
globals scattered across files.
"""
import os
import re
import sys

from dotenv import load_dotenv

from . import proxy_utils

load_dotenv()

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


# ---- proxy configuration (runtime + .env persistence) -----------------
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def mask_proxy(url):
    """Mask the password in a proxy URL: http://user:***@host:port"""
    if not url:
        return ""
    return re.sub(r"(://[^:@/]+:)[^@/]+(@)", r"\1***\2", url)


def update_env(key, value):
    """Set an env var for the running process and persist it to .env."""
    os.environ[key] = value

    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()

    replaced = False
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip("\n") + "\n")
