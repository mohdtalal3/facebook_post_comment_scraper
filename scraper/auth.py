"""Authentication helpers: cookie parsing and cURL parsing."""
import re
from urllib.parse import parse_qs, unquote


def parse_cookies(cookie_string):
    """Parse 'key1=value1; key2=value2' into a dict."""
    cookies = {}
    if not cookie_string:
        return cookies
    for part in cookie_string.split(";"):
        part = part.strip()
        if "=" in part:
            key, value = part.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies


def parse_curl(curl_text):
    """Extract (cookies_str, fb_dtsg) from a pasted 'Copy as cURL' command."""
    curl_text = (curl_text or "").strip()
    cookies_str = ""
    fb_dtsg = None

    m = re.search(r"(?:^|\s)-b\s+['\"]([^'\"]+)['\"]", curl_text, re.MULTILINE)
    if m:
        cookies_str = m.group(1).strip()

    m = re.search(r"(?:--data-raw|--data-urlencode|--data|-d)\s+['\"]([^'\"]+)['\"]",
                  curl_text, re.MULTILINE | re.DOTALL)
    if m:
        body = m.group(1).strip()
        params = parse_qs(body)
        if "fb_dtsg" in params:
            fb_dtsg = params["fb_dtsg"][0]
        else:
            m2 = re.search(r"fb_dtsg=([^&\s]+)", body)
            if m2:
                fb_dtsg = unquote(m2.group(1))

    return cookies_str, fb_dtsg
