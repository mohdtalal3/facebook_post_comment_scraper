"""Resolve Facebook URLs into the IDs the scrapers need."""
import base64
import re
from html import unescape

import requests

from .config import COOKIES, PROXIES
from .logging_utils import log

_UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_html(url):
    r = requests.get(url, headers=_UA_HEADERS, cookies=COOKIES,
                     proxies=PROXIES, timeout=20)
    return r.text


def extract_user_id_from_url(url):
    """Extract a page/profile ID from a URL (direct pattern first, HTML fallback)."""
    for pattern in (r'profile\.php\?id=(\d+)', r'/profile/(\d+)', r'id=(\d+)'):
        m = re.search(pattern, url)
        if m:
            log(f"  Found user ID in URL: {m.group(1)}")
            return m.group(1)

    try:
        log(f"  No ID in URL, fetching page: {url}")
        html = _fetch_html(url)
        for pattern in (r'fb://profile/(\d+)', r'"profile_owner":"(\d+)"',
                        r'"userID":"(\d+)"', r'owner_id=(\d+)'):
            m = re.search(pattern, html)
            if m:
                log(f"  Found user ID: {m.group(1)}")
                return m.group(1)
        log("  User ID not found (profile may be private or login-walled)")
    except Exception as e:
        log(f"  Error fetching URL: {e}")
    return None


def extract_group_id_from_url(url):
    """Extract a group ID from a group URL."""
    for pattern in (r'/groups/(\d+)', r'group_id=(\d+)', r'gid=(\d+)'):
        m = re.search(pattern, url)
        if m:
            log(f"  Found group ID in URL: {m.group(1)}")
            return m.group(1)

    try:
        log(f"  No ID in URL, fetching group page: {url}")
        html = _fetch_html(url)
        for pattern in (r'fb://group/(\d+)', r'fb://group/\?id=(\d+)',
                        r'"group_id":"(\d+)"', r'"groupID":"(\d+)"'):
            m = re.search(pattern, html)
            if m:
                log(f"  Found group ID: {m.group(1)}")
                return m.group(1)
        log("  Group ID not found (group may be private or login-walled)")
    except Exception as e:
        log(f"  Error fetching URL: {e}")
    return None


def extract_post_id_from_url(url):
    """Extract a post ID from a post URL."""
    for pattern in (r'/groups/[^/]+/posts/(\d+)', r'/posts/(\d+)'):
        m = re.search(pattern, url)
        if m:
            log(f"  Found post ID in URL: {m.group(1)}")
            return m.group(1)

    try:
        log(f"  No direct ID in URL, fetching post: {url}")
        html = _fetch_html(url)

        if COOKIES:
            m = re.search(r'"storyID":"([^"]+)"', html)
            if m:
                try:
                    decoded = base64.b64decode(m.group(1)).decode("utf-8")
                    parts = decoded.split(":")
                    if len(parts) >= 2:
                        log(f"  Found post ID from storyID: {parts[-1]}")
                        return parts[-1]
                except Exception as e:
                    log(f"  Could not decode storyID: {e}")

        m = re.search(r'<meta property="og:url" content="([^"]+)"', html)
        if m:
            og_url = unescape(m.group(1))
            m2 = re.search(r'/posts/(?:[^/]+/)?(\d+)', og_url) or re.search(r'story_fbid=(\d+)', og_url)
            if m2:
                log(f"  Found post ID from og:url: {m2.group(1)}")
                return m2.group(1)

        log("  Post ID not found in URL")
    except Exception as e:
        log(f"  Error fetching URL: {e}")
    return None


def convert_post_id_to_feedback_id(post_id):
    return base64.b64encode(f"feedback:{post_id}".encode()).decode()
