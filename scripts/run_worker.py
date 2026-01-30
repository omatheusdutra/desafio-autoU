import os
import sys
from pathlib import Path

from redis import Redis
from rq import Queue
from rq.worker import SimpleWorker
from rq.timeouts import TimerDeathPenalty

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "backend" / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def main() -> None:
    conn = Redis.from_url(REDIS_URL)
    queue = Queue("email-smart-reply", connection=conn)
    worker = SimpleWorker([queue], connection=conn)
    # Windows doesn't support SIGALRM; use a timer-based death penalty instead.
    worker.death_penalty_class = TimerDeathPenalty
    worker.work()


if __name__ == "__main__":
    main()
