"""A content-addressed cache of recogniser reads.

The EasyOCR baseline costs about a second per crop, and later milestones re-evaluate the
same deterministic synthetic sets with more recognisers. A read is cached under the hash of
the recogniser's name, version and the exact image bytes, so any change to the image, the
model or the code version that the recogniser reports misses the cache. Only recognisers
that declare ``cacheable = True`` are cached; cached latencies are the ones measured when
the read was first made.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..hypotheses import Hypothesis, ViewRead
from ..imaging import Image


def _encode(read: ViewRead) -> dict[str, Any]:
    payload = asdict(read)
    payload["hypotheses"] = [[h.tokens, h.logp] for h in read.hypotheses]
    payload["votes"] = [list(v) for v in read.votes]
    payload["prediction_set"] = (
        list(read.prediction_set) if read.prediction_set is not None else None
    )
    return payload


def _decode(payload: dict[str, Any]) -> ViewRead:
    return ViewRead(
        hypotheses=tuple(Hypothesis(str(t), float(lp)) for t, lp in payload["hypotheses"]),
        prediction=payload["prediction"],
        confidence=payload["confidence"],
        prediction_set=tuple(payload["prediction_set"])
        if payload["prediction_set"] is not None
        else None,
        votes=tuple((str(t), float(w)) for t, w in payload["votes"]),
        latency_ms=float(payload["latency_ms"]),
        calibrated=bool(payload["calibrated"]),
        extra=dict(payload.get("extra", {})),
    )


class ReadCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(name: str, version: str, image: Image) -> str:
        digest = hashlib.sha256()
        digest.update(f"{name}\0{version}\0{image.shape}\0{image.dtype}\0".encode())
        digest.update(image.tobytes())
        return digest.hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> ViewRead | None:
        path = self._path(key)
        if not path.exists():
            self.misses += 1
            return None
        self.hits += 1
        return _decode(json.loads(path.read_text(encoding="utf-8")))

    def put(self, key: str, read: ViewRead) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_encode(read), ensure_ascii=False), encoding="utf-8")


__all__ = ["ReadCache"]
