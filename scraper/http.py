"""HTTP helpers: retry logic with proxy rotation and Facebook response parsing."""
import json
import time

import requests

from . import proxy_utils
from .config import GRAPHQL_URL, COOKIES, PROXIES
from .logging_utils import log


def retry_request(url, headers, data, proxies=None, max_retries=5):
    """POST with retry logic. Rotates the static proxy on proxy/IP errors."""
    proxies = proxies if proxies is not None else PROXIES

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, data=data,
                              proxies=proxies, cookies=COOKIES, timeout=30)
            if r.status_code == 200:
                return r
            if proxy_utils.is_proxy_infra_error(status_code=r.status_code):
                log(f"  Attempt {attempt}/{max_retries}: proxy auth failed (HTTP {r.status_code}) — rotating proxy...")
                proxies = proxy_utils.rotate_static_proxy() or proxies
            elif proxy_utils.is_ip_blocked(status_code=r.status_code, response_text=r.text):
                log(f"  Attempt {attempt}/{max_retries}: Facebook blocked this IP (HTTP {r.status_code}) — rotating proxy...")
                proxies = proxy_utils.rotate_static_proxy() or proxies
            else:
                log(f"  Attempt {attempt}/{max_retries}: status {r.status_code}")
        except requests.exceptions.ProxyError:
            log(f"  Attempt {attempt}/{max_retries}: proxy unreachable — rotating proxy...")
            proxies = proxy_utils.rotate_static_proxy() or proxies
        except Exception as e:
            if proxy_utils.is_proxy_infra_error(exc=e):
                log(f"  Attempt {attempt}/{max_retries}: proxy connection error — rotating proxy...")
                proxies = proxy_utils.rotate_static_proxy() or proxies
            else:
                log(f"  Attempt {attempt}/{max_retries}: {e}")

        if attempt < max_retries:
            wait = attempt * 2
            log(f"  Retrying in {wait} seconds...")
            time.sleep(wait)

    raise Exception(f"Request failed after {max_retries} attempts")


def graphql_post(payload, headers=None, proxies=None, max_retries=5):
    """POST a payload to Facebook's GraphQL endpoint with retries."""
    base = {
        "user-agent": "Mozilla/5.0",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.facebook.com",
    }
    if headers:
        base.update(headers)
    return retry_request(GRAPHQL_URL, base, payload, proxies=proxies, max_retries=max_retries)


def fb_json(response_text):
    """Parse `for (;;);{json}` responses into a dict ({} if malformed)."""
    text = response_text.strip()
    if text.startswith("for (;;);"):
        text = text[len("for (;;);"):]
    try:
        parsed = json.loads(text.split("\n")[0].strip())
    except Exception as e:
        log(f"  Could not parse GraphQL response: {e}")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_data_blocks(raw_text):
    """Extract every balanced `{...}` block that follows a "data" key."""
    blocks = []
    i = 0
    n = len(raw_text)
    while True:
        idx = raw_text.find('"data"', i)
        if idx == -1:
            break
        brace_start = raw_text.find('{', idx)
        if brace_start == -1:
            break
        depth = 0
        for j in range(brace_start, n):
            if raw_text[j] == '{':
                depth += 1
            elif raw_text[j] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        blocks.append(json.loads(raw_text[brace_start:j + 1]))
                    except Exception:
                        pass
                    i = j + 1
                    break
        else:
            break
    return blocks


def parse_fb_response(text):
    """Parse a GraphQL response into a list of cleaned data blocks."""
    text = text.replace("for (;;);", "").strip()
    blocks = _extract_data_blocks(text)
    for block in blocks:
        if isinstance(block, dict):
            block.pop("errors", None)
            block.pop("extensions", None)
    return blocks
