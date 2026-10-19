"""Wait until the stack answers, then print where the console is (the `just demo` step).

    uv run python tools/wait_ready.py                 # API on :8100, console on :5174
    uv run python tools/wait_ready.py --wait 300

It sends no photo and generates nothing: it polls the service's ``/health`` and the
console's front page, so `just demo` ends with the stack ready for a person's own photos.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections.abc import Sequence


def wait_healthy(url: str, seconds: float) -> dict[str, object]:
    """Poll ``/health`` until it answers ``ok`` or the time runs out."""
    deadline = time.monotonic() + seconds
    last: Exception | None = None
    while True:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=5) as response:
                health = json.loads(response.read().decode())
                if health.get("status") == "ok":
                    return dict(health)
        except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError) as exc:
            last = exc
        if time.monotonic() >= deadline:
            raise SystemExit(f"the service at {url} did not become healthy: {last}")
        time.sleep(2)


def wait_page(url: str, seconds: float) -> None:
    """Poll a page until it answers 200, so the printed address works when it is printed."""
    deadline = time.monotonic() + seconds
    last: Exception | None = None
    while True:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last = exc
        if time.monotonic() >= deadline:
            raise SystemExit(f"the console at {url} did not answer: {last}")
        time.sleep(2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8100")
    parser.add_argument("--console", default="http://localhost:5174")
    parser.add_argument("--wait", type=float, default=180.0, help="seconds to wait for each")
    args = parser.parse_args(argv)

    health = wait_healthy(args.api, args.wait)
    wait_page(f"{args.console}/read", args.wait)
    detector = "with the detector" if health.get("detector") else "without a detector"
    print(f"service: ready at {args.api}, model {health.get('model_version')}, {detector}")
    print(f"console: {args.console}")
    print("  Read: drop one to ten photos of the same car and press Read plate.")
    print("  Review queue, Jobs, Evaluation, Models and Methods are one click away.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
