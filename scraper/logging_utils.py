"""Thread-aware logging for scrapers.

Scraper modules call `log()` instead of `print()`. When a job runs inside
the web app, the worker thread installs a sink so every message is streamed
to the browser. Outside of a job (CLI use), messages go to stdout.
"""
import sys
import threading

_local = threading.local()


def set_sink(sink):
    """Install a log sink for the current thread. sink(message: str)."""
    _local.sink = sink


def clear_sink():
    _local.sink = None


def get_sink():
    return getattr(_local, "sink", None)


def log(message=""):
    sink = get_sink()
    if sink is not None:
        try:
            sink(message)
            return
        except Exception:
            pass
    print(message)
