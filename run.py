#!/usr/bin/env python3
"""Facebook Scraper — Flask web GUI.

Usage:
    python run.py            # http://127.0.0.1:5001
    python run.py --port 8080
"""
import argparse
import socket
import threading
import webbrowser

from web import create_app
from scraper.config import APP_VERSION

app = create_app()


def find_free_port(start, tries=10):
    """If the preferred port is taken, move to the next one instead of dying."""
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facebook Scraper web GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    frozen = getattr(__import__("sys"), "frozen", False)
    debug = args.debug and not frozen

    if frozen:
        # Packaged app: never die on a busy port, open the browser automatically
        args.port = find_free_port(args.port)
        url = f"http://{args.host}:{args.port}"
        print(f"\n  Facebook Scraper v{APP_VERSION} running →  {url}\n")
        threading.Timer(1.5, webbrowser.open, args=(url,)).start()
        app.run(host=args.host, port=args.port, debug=False, use_reloader=False)
    else:
        url = f"http://{args.host}:{args.port}"
        print(f"\n  Facebook Scraper v{APP_VERSION} running →  {url}\n")
        app.run(host=args.host, port=args.port, debug=debug, threaded=True)
