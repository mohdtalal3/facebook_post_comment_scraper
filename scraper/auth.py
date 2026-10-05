"""Authentication: cookie parsing, cURL parsing and Chrome login helper."""
import json
import re
import threading
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


class ChromeLoginHelper:
    """Opens Chrome via SeleniumBase, waits for the user to log in, then
    extracts cookies + fb_dtsg from CDP performance logs.

    Usage:
        helper = ChromeLoginHelper()
        helper.start()      # opens Chrome, returns immediately
        ...user logs in...
        helper.finish()     # signals extraction; result lands in helper.result
    """

    def __init__(self, log=None):
        self.log = log or (lambda msg: print(msg))
        self.result = {"cookies": "", "fb_dtsg": "", "error": None}
        self.login_event = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def finish(self, timeout=120):
        """Signal that login is done and wait for extraction to complete."""
        self.login_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        return self.result

    def _run(self):
        try:
            from seleniumbase import SB

            chrome_dir = "/tmp/fb_scraper_chromedata"
            with SB(headless=False, log_cdp_events=True, user_data_dir=chrome_dir) as sb:
                sb.open("https://www.facebook.com/")
                self.log("Chrome opened — please log in, then click 'I've logged in' in the web UI")
                if not self.login_event.wait(timeout=600):
                    self.result["error"] = "Timed out waiting for login"
                    return

                self.log("Extracting cookies and fb_dtsg...")

                fb_dtsg = None
                for entry in sb.driver.get_log("performance"):
                    try:
                        log_entry = json.loads(entry["message"])["message"]
                    except Exception:
                        continue
                    if log_entry.get("method") != "Network.requestWillBeSent":
                        continue
                    request = log_entry.get("params", {}).get("request", {})
                    if "graphql" not in request.get("url", ""):
                        continue
                    post_data = request.get("postData", "")
                    if post_data and not fb_dtsg:
                        params = parse_qs(post_data)
                        if "fb_dtsg" in params:
                            fb_dtsg = params["fb_dtsg"][0]
                            break

                cookies = ["%s=%s" % (c["name"], c["value"]) for c in sb.get_cookies()]
                cookies += ["ps_l=1", "ps_n=1", "dpr=1", "ar_debug=1"]

                self.result["cookies"] = ";".join(cookies)
                self.result["fb_dtsg"] = fb_dtsg or ""
                self.log(f"Extracted {len(cookies)} cookies, fb_dtsg: {'found' if fb_dtsg else 'not found'}")
        except ImportError:
            self.result["error"] = "SeleniumBase is not installed (pip install seleniumbase)"
        except Exception as e:
            self.result["error"] = str(e)
