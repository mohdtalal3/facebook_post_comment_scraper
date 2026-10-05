"""Background job manager.

One scrape job runs at a time (same as the old PyQt version). Each job:
- runs in a worker thread with a thread-local log sink
- keeps an in-memory log buffer (retrievable by index for polling)
- exposes a threading.Event for cooperative stopping
"""
import threading
import time
import uuid

from scraper import storage
from scraper import tasks
from scraper.logging_utils import set_sink, clear_sink


class ScrapeJob:
    def __init__(self, job_type, params):
        self.id = uuid.uuid4().hex[:12]
        self.type = job_type
        self.params = params
        self.status = "running"          # running | done | error | stopped
        self.logs = []
        self.logs_lock = threading.Lock()
        self.log_event = threading.Event()
        self.stop_event = threading.Event()
        self.result = None
        self.error = None
        self.started_at = time.time()
        self.finished_at = None
        self._thread = None

    # ---- logging -------------------------------------------------------
    def _sink(self, message):
        with self.logs_lock:
            self.logs.append(message)
        self.log_event.set()

    def get_logs(self, after=0):
        with self.logs_lock:
            return self.logs[after:]

    def log_count(self):
        with self.logs_lock:
            return len(self.logs)

    def wait_for_logs(self, after, timeout=1.0):
        """Block until new logs exist (or timeout). Used by the SSE stream."""
        if self.log_count() <= after and self.status == "running":
            self.log_event.wait(timeout)
            self.log_event.clear()
        return self.get_logs(after)

    # ---- lifecycle -----------------------------------------------------
    def start(self):
        runner = {
            "simple_post": tasks.run_simple_post,
            "page_posts": tasks.run_page_posts,
            "group_posts": tasks.run_group_posts,
        }.get(self.type)
        if not runner:
            raise ValueError(f"Unknown scrape type: {self.type}")

        # Tag every post saved by this job with the job id
        params = {**self.params, "job_id": self.id}

        def worker():
            set_sink(self._sink)
            try:
                self.result = runner(**params, should_stop=self.stop_event.is_set)
                self.status = "stopped" if self.stop_event.is_set() else "done"
            except Exception as e:
                self.error = str(e)
                self.status = "error"
                self._sink(f"JOB FAILED: {e}")
            finally:
                self.finished_at = time.time()
                storage.update_job_record(self.id,
                                          status=self.status,
                                          finished_at=self.finished_at,
                                          error=self.error)
                clear_sink()

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def stop(self):
        self.stop_event.set()

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "log_count": self.log_count(),
            "error": self.error,
            "result": self.result,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.current = None
        self.last = None

    def start(self, job_type, params):
        with self._lock:
            if self.current and self.current.status == "running":
                raise RuntimeError("A scrape job is already running")
            job = ScrapeJob(job_type, params)

            # Persist the job so posts can be filtered by it later
            storage.save_job_record({
                "id": job.id,
                "type": job_type,
                "params": params,
                "status": "running",
                "started_at": job.started_at,
                "finished_at": None,
                "error": None,
            })

            job.start()
            self.current = job
            self.last = job
            return job

    def status(self):
        job = self.last
        return job.to_dict() if job else {"status": "idle"}


manager = JobManager()
