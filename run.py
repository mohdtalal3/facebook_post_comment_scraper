#!/usr/bin/env python3
"""Facebook Scraper — Flask web GUI.

Usage:
    python run.py            # http://127.0.0.1:5001
    python run.py --port 8080
"""
import argparse
import threading
import webbrowser

from web import create_app
from scraper.config import APP_VERSION

app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facebook Scraper web GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    frozen = getattr(__import__("sys"), "frozen", False)
    debug = args.debug and not frozen

    url = f"http://{args.host}:{args.port}"
    print(f"\n  Facebook Scraper v{APP_VERSION} running →  {url}\n")

    if frozen:
        # Packaged app: open the browser automatically, no reloader
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
        app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    else:
        app.run(host=args.host, port=args.port, debug=debug, threaded=True)
