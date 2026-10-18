"""``python -m services.api.worker``: an RQ worker for folder and video jobs.

On Linux (the Compose worker) RQ forks a work horse per job. Windows has no ``fork``, so a
``SimpleWorker`` runs jobs in-process with a timer-based timeout instead of ``SIGALRM``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .config import get_service_settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="services.api.worker", description=__doc__)
    parser.add_argument("--burst", action="store_true", help="exit when the queue is empty")
    args = parser.parse_args(argv)

    from redis import Redis
    from rq import Queue, SimpleWorker, Worker

    settings = get_service_settings()
    connection = Redis.from_url(settings.redis_url)
    queue = Queue(settings.queue_name, connection=connection)
    if sys.platform == "win32":
        from rq.timeouts import TimerDeathPenalty

        simple = SimpleWorker([queue], connection=connection)
        simple.death_penalty_class = TimerDeathPenalty
        simple.work(burst=args.burst)
    else:
        Worker([queue], connection=connection).work(burst=args.burst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
