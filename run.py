#!/usr/bin/env python3
"""Facebook Scraper — Flask web GUI.

Usage:
    python run.py            # http://127.0.0.1:5001
    python run.py --port 8080
"""
import argparse

from web import create_app

app = create_app()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facebook Scraper web GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"\n  Facebook Scraper running →  http://{args.host}:{args.port}\n")
    #app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    app.run(host=args.host, port=args.port, debug=True, threaded=True)
