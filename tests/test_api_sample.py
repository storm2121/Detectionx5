"""Opt-in API regression test with the real detector, OCR, and sample photo."""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api import create_app

pytestmark = pytest.mark.skipif(
    os.getenv("PLATE_TEST_MODELS") != "1",
    reason="set PLATE_TEST_MODELS=1 to load real detector and OCR models",
)


def test_sample_plate_over_api():
    """Pin the expected text so a detector crop change cannot silently regress OCR."""
    sample = ROOT / "samples" / "car.jpg"
    with TestClient(create_app()) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        # Repeated copies test the multipart contract and model reuse; they do
        # not provide the independent evidence that different photos would.
        for count in (1, 2):
            with ExitStack() as stack:
                files = [
                    ("files", (sample.name, stack.enter_context(sample.open("rb")), "image/jpeg"))
                    for _ in range(count)
                ]
                response = client.post("/read", files=files)

            assert response.status_code == 200
            body = response.json()
            assert body["plate"] == "24830-ب-1"
            assert body["fields"] == {"digits": "24830", "letter": "ب", "region": "1"}
            assert 0 < body["confidence"] <= 1
            assert body["images_agreeing"] == count
            assert body["images_processed"] == count
