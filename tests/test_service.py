"""Every endpoint of services/api with a fake recogniser and detector, SQLite and fakeredis."""

from __future__ import annotations

import csv
import json
import math
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cv2
import numpy as np
import pytest
from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from PIL import Image
from rq import Queue

from plate_reader.data.validate import ValidationReport, validate_ocr_csv
from plate_reader.detector import Detection
from plate_reader.hypotheses import Hypothesis, ViewRead
from services.api import jobs as jobs_module
from services.api.config import ServiceSettings
from services.api.engine import Engine
from services.api.main import create_app

CONFIDENT = (60, 60, 60)
AMBIGUOUS = (200, 200, 200)


class FakeRecognizer:
    """Reads the crop's mean brightness: dark crops are a sure plate, light ones ambiguous."""

    name = "fake-crnn"
    version = "fake-1"
    conformal_threshold = 0.6

    def read(self, image: np.ndarray) -> ViewRead:
        if float(image.mean()) < 100:
            hyps = (
                Hypothesis("24830-ب-1", math.log(0.99)),
                Hypothesis("24830-د-1", math.log(0.01)),
            )
        else:
            hyps = (Hypothesis("12-WW", math.log(0.55)), Hypothesis("13-WW", math.log(0.45)))
        return ViewRead(
            hypotheses=hyps,
            prediction=hyps[0].tokens,
            confidence=hyps[0].probability,
            prediction_set=tuple(h.tokens for h in hyps),
            calibrated=True,
        )


class FakeDetector:
    """The plate is whatever is not black; an all-black photo has no plate."""

    model_path = "fake-detector.onnx"

    def detect_image(self, image: np.ndarray) -> list[Detection]:
        mask = image.max(axis=2) > 40 if image.ndim == 3 else image > 40
        ys, xs = np.nonzero(mask)
        if xs.size == 0:
            return []
        x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
        return [Detection((x1, y1, x2, y2), 0.9, image[y1:y2, x1:x2].copy())]


def png(colour: tuple[int, int, int], size: tuple[int, int] = (120, 40)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def files(*payloads: bytes) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (f"p{i}.png", data, "image/png")) for i, data in enumerate(payloads)]


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    settings = ServiceSettings(
        db_url=f"sqlite:///{(tmp_path / 'plates.db').as_posix()}",
        storage_dir=tmp_path / "storage",
        jobs_root=tmp_path / "jobs",
        export_dir=tmp_path / "data" / "ocr" / "train",
        registry_path=tmp_path / "registry.json",
        results_dir=tmp_path / "results",
        review_threshold=0.9,
    )
    engine = Engine(FakeRecognizer(), FakeDetector())
    queue = Queue("plates", is_async=False, connection=FakeRedis())
    monkeypatch.setattr(jobs_module, "ENGINE_FACTORY", lambda _: engine)
    jobs_module._ENGINES.clear()
    app = create_app(settings, engine_factory=lambda _: engine, queue_factory=lambda _: queue)
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, settings=settings, engine=engine, app=app)
    jobs_module._ENGINES.clear()


def test_health_models_and_metrics(service: Any) -> None:
    health = service.client.get("/health").json()
    assert health == {
        "status": "ok",
        "database": "ok",
        "queue": "ok",
        "model_version": "fake-1",
        "detector": True,
    }
    service.settings.registry_path.write_text(
        json.dumps({"models": [{"version": "v1"}], "active": {"crnn": "v1"}})
    )
    models = service.client.get("/models").json()
    assert models["recognizer"]["name"] == "fake-crnn"
    assert models["registry"]["active"] == {"crnn": "v1"}
    assert models["alpha"] == pytest.approx(0.05)
    service.client.post("/read", files=files(png(CONFIDENT)))
    metrics = service.client.get("/metrics").text
    for name in (
        "plate_reads_total",
        "plate_review_queue_size",
        "plate_stage_seconds",
        "plate_read_confidence",
    ):
        assert name in metrics


def test_confident_read_is_accepted_with_a_singleton_set(service: Any) -> None:
    response = service.client.post("/read", files=files(png(CONFIDENT), png(CONFIDENT)))
    assert response.status_code == 200
    body = response.json()
    assert body["plate"] == "24830-ب-1"
    assert body["fields"] == {"digits": "24830", "letter": "ب", "region": "1"}
    assert body["format"] == "standard"
    assert body["calibrated"] is True
    assert body["confidence"] > 0.99
    assert body["prediction_set"] == ["24830-ب-1"]
    assert body["level"] == pytest.approx(0.95)
    assert body["review"] == {"queued": False, "reason": None, "item_id": None}
    assert len(body["views"]) == 2
    assert body["views"][0]["box"] == [0, 0, 120, 40]
    assert [p["symbol"] for p in body["positions"]] == list("24830-ب-1")
    assert body["model_version"] == "fake-1"
    assert service.client.get(f"/reads/{body['id']}").json()["plate"] == "24830-ب-1"


def test_review_round_trip_exports_a_labelled_crop(service: Any) -> None:
    read = service.client.post("/read", files=files(png(AMBIGUOUS))).json()
    assert read["review"]["queued"] is True
    assert read["review"]["reason"] == "set_size"
    assert read["prediction_set"] == ["12 WW", "13 WW"]
    queue = service.client.get("/review/queue").json()
    assert [item["read_id"] for item in queue] == [read["id"]]
    crop = service.client.get(queue[0]["crops"][0])
    assert crop.status_code == 200
    assert crop.headers["content-type"] == "image/png"

    assert (
        service.client.post(f"/review/{queue[0]['id']}", json={"plate": "not a plate"}).status_code
        == 422
    )
    assert service.client.post(f"/review/{queue[0]['id']}", json={}).status_code == 422
    assert service.client.post("/review/nope", json={"plate": "13 WW"}).status_code == 404
    decided = service.client.post(f"/review/{queue[0]['id']}", json={"plate": "13ww"}).json()
    assert decided["status"] == "corrected"
    assert decided["corrected_plate"] == "13 WW"
    assert service.client.get("/review/queue").json() == []
    assert service.client.get(f"/reads/{read['id']}").json()["status"] == "reviewed"

    export = service.client.post("/review/export").json()
    assert export["exported"] == 1
    export_dir = service.settings.export_dir
    crop_file = export_dir / export["files"][0]
    assert crop_file.exists()
    with (export_dir / "labels.csv").open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["crop_path", "plate_text", "format"]
    assert rows[1] == [export["files"][0], "13 WW", "temporary"]
    report = ValidationReport(root=export_dir)
    validate_ocr_csv(report, export_dir / "labels.csv", "exported")
    assert report.errors == []
    # Exported once only.
    assert service.client.post("/review/export").json()["exported"] == 0


def test_confirming_a_read_and_unreadable_photos(service: Any) -> None:
    low = service.client.post("/read", files=files(png(AMBIGUOUS))).json()
    item = service.client.get("/review/queue").json()[0]
    confirmed = service.client.post(f"/review/{item['id']}", json={"confirm": True}).json()
    assert confirmed["corrected_plate"] == low["plate"]
    blank = service.client.post("/read", files=files(png((0, 0, 0)))).json()
    assert blank["plate"] is None
    assert blank["review"]["queued"] is False  # nothing was detected, nothing to review
    assert blank["views"][0]["box"] is None


def test_read_log_lists_and_filters(service: Any) -> None:
    for colour in (CONFIDENT, AMBIGUOUS, CONFIDENT):
        service.client.post("/read", files=files(png(colour)))
    page = service.client.get("/reads", params={"limit": 2}).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    queued = service.client.get("/reads", params={"status": "queued"}).json()
    assert queued["total"] == 1
    assert service.client.get("/reads", params={"status": "nope"}).status_code == 422
    assert service.client.get("/reads/missing").status_code == 404
    assert service.client.get("/reads/missing/views/0/crop").status_code == 404


def test_upload_validation(service: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    client = service.client
    assert client.post("/read").status_code == 422
    assert client.post("/read", files=files(b"")).status_code == 400
    assert client.post("/read", files=files(b"not an image")).status_code == 400
    gif = BytesIO()
    Image.new("RGB", (8, 8)).save(gif, format="GIF")
    assert client.post("/read", files=files(gif.getvalue())).status_code == 415
    assert client.post("/read", files=files(*([png(CONFIDENT)] * 11))).status_code == 413
    big = png(CONFIDENT, (2000, 2000))
    monkeypatch.setattr(service.settings, "max_photo_bytes", len(big) - 1)
    assert client.post("/read", files=files(big)).status_code == 413


def test_folder_job_runs_and_streams_progress(service: Any) -> None:
    folder = service.settings.jobs_root / "batch"
    folder.mkdir(parents=True)
    for i, colour in enumerate((CONFIDENT, AMBIGUOUS, CONFIDENT)):
        (folder / f"{i}.png").write_bytes(png(colour))
    (folder / "broken.png").write_bytes(b"x")
    response = service.client.post("/jobs", json={"kind": "folder", "path": "batch"})
    assert response.status_code == 202
    job = service.client.get(f"/jobs/{response.json()['id']}").json()
    assert job["status"] == "finished"
    assert job["progress"] == 1.0
    assert job["result"]["items"] == 4
    plates = [r.get("plate") for r in job["result"]["reads"]]
    assert plates.count("24830-ب-1") == 2
    assert any("error" in r for r in job["result"]["reads"])
    events = service.client.get(f"/jobs/{job['id']}/events").text
    assert "event: progress" in events
    assert "event: done" in events
    assert service.client.get("/reads", params={"limit": 10}).json()["total"] == 3


def _video(path: Path, frames: int = 24) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 8.0, (160, 120))
    for t in range(frames):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)
        x = 20 + t  # the plate drifts right by one pixel per frame
        frame[50:70, x : x + 60] = 80  # a dim plate on black: the fake reads it as confident
        writer.write(frame)
    writer.release()
    return path


def test_video_job_tracks_one_plate_and_fuses_its_views(service: Any) -> None:
    root = service.settings.jobs_root
    root.mkdir(parents=True, exist_ok=True)
    _video(root / "clip.mp4")
    response = service.client.post("/jobs", json={"kind": "video", "path": "clip.mp4"})
    job = service.client.get(f"/jobs/{response.json()['id']}").json()
    assert job["status"] == "finished", job
    tracks = job["result"]["tracks"]
    assert len(tracks) == 1
    assert tracks[0]["plate"] == "24830-ب-1"
    assert len(tracks[0]["frames"]) >= 3
    read = service.client.get(f"/reads/{tracks[0]['read_id']}").json()
    assert read["source"] == "job"
    assert len(read["views"]) == len(tracks[0]["frames"])

    upload = service.client.post(
        "/jobs/upload",
        files=[("video", ("clip.mp4", (root / "clip.mp4").read_bytes(), "video/mp4"))],
    )
    assert upload.status_code == 202
    assert service.client.get(f"/jobs/{upload.json()['id']}").json()["status"] == "finished"
    bad = service.client.post("/jobs/upload", files=[("video", ("clip.txt", b"x", "text/plain"))])
    assert bad.status_code == 415


def test_job_requests_are_validated(service: Any) -> None:
    client = service.client
    service.settings.jobs_root.mkdir(parents=True, exist_ok=True)
    assert client.post("/jobs", json={"kind": "folder", "path": "../outside"}).status_code == 400
    assert client.post("/jobs", json={"kind": "folder", "path": "missing"}).status_code == 404
    assert client.post("/jobs", json={"kind": "video", "path": "missing.mp4"}).status_code == 404
    assert client.post("/jobs", json={"kind": "dvd", "path": "x"}).status_code == 422
    assert client.get("/jobs/missing").status_code == 404
    assert client.get("/jobs/missing/events").status_code == 404


def test_video_without_a_detector_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = ServiceSettings(
        db_url=f"sqlite:///{(tmp_path / 'p.db').as_posix()}",
        storage_dir=tmp_path / "s",
        jobs_root=tmp_path / "jobs",
        export_dir=tmp_path / "e",
    )
    engine = Engine(FakeRecognizer(), detector=None)
    monkeypatch.setattr(jobs_module, "ENGINE_FACTORY", lambda _: engine)
    jobs_module._ENGINES.clear()
    queue = Queue("plates", is_async=False, connection=FakeRedis())
    app = create_app(settings, engine_factory=lambda _: engine, queue_factory=lambda _: queue)
    (tmp_path / "jobs").mkdir()
    _video(tmp_path / "jobs" / "clip.mp4", frames=4)
    with TestClient(app) as client:
        job_id = client.post("/jobs", json={"kind": "video", "path": "clip.mp4"}).json()["id"]
        job = client.get(f"/jobs/{job_id}").json()
        assert job["status"] == "failed"
        assert "detector" in job["error"]
        # Without a detector, photos are read as plate crops.
        assert client.post("/read", files=files(png(CONFIDENT))).json()["plate"] == "24830-ب-1"
    jobs_module._ENGINES.clear()


def test_no_queue_means_503(tmp_path: Path) -> None:
    settings = ServiceSettings(
        db_url=f"sqlite:///{(tmp_path / 'q.db').as_posix()}",
        storage_dir=tmp_path / "s",
        jobs_root=tmp_path / "jobs",
    )
    (tmp_path / "jobs" / "batch").mkdir(parents=True)
    engine = Engine(FakeRecognizer(), FakeDetector())
    app = create_app(settings, engine_factory=lambda _: engine, queue_factory=lambda _: None)
    with TestClient(app) as client:
        assert client.post("/jobs", json={"kind": "folder", "path": "batch"}).status_code == 503
        assert client.get("/health").json()["queue"] == "not configured"


class UncertainRecognizer(FakeRecognizer):
    """A read whose best candidate is too unusual to certify: the set comes back empty."""

    conformal_threshold = 0.001

    def read(self, image: np.ndarray) -> ViewRead:
        hyps = (Hypothesis("24830-ب-1", math.log(0.97)), Hypothesis("24830-د-1", math.log(0.03)))
        return ViewRead(
            hypotheses=hyps, prediction=hyps[0].tokens, confidence=0.97, calibrated=True
        )


@pytest.mark.parametrize(("skip", "queued"), [(False, True), (True, False)])
def test_empty_sets_go_to_review_unless_skipped(tmp_path: Path, skip: bool, queued: bool) -> None:
    settings = ServiceSettings(
        db_url=f"sqlite:///{(tmp_path / 'e.db').as_posix()}",
        storage_dir=tmp_path / "s",
        review_threshold=0.9,
        review_skip_empty_sets=skip,
    )
    engine = Engine(UncertainRecognizer(), FakeDetector(), review_empty_sets=not skip)
    app = create_app(settings, engine_factory=lambda _: engine, queue_factory=lambda _: None)
    with TestClient(app) as client:
        body = client.post("/read", files=files(png(CONFIDENT))).json()
    assert body["prediction_set"] == []
    assert body["review"]["queued"] is queued
    assert body["review"]["reason"] == ("empty_set" if queued else None)


def test_results_are_served_as_committed(service: Any) -> None:
    assert service.client.get("/results").json() == []
    results = service.settings.results_dir
    results.mkdir()
    payload = {
        "schema": "detectionx5.eval/1",
        "label": "synthetic results are not real-world accuracy",
    }
    (results / "eval_synthetic.json").write_text(json.dumps(payload), encoding="utf-8")
    (results / "broken.json").write_text("{", encoding="utf-8")
    (results / "notes.txt").write_text("not served", encoding="utf-8")
    index = service.client.get("/results").json()
    assert index == [{"name": "eval_synthetic", **payload}]
    served = service.client.get("/results/eval_synthetic")
    assert served.status_code == 200
    assert served.headers["content-type"] == "application/json"
    assert served.json() == payload
    assert service.client.get("/results/notes").status_code == 404
    assert service.client.get("/results/missing").status_code == 404
    assert service.client.get("/results/..%2Fsecret").status_code in (404, 422)
    assert service.client.get("/results/Eval-Synthetic").status_code == 422


def test_jobs_are_listed_newest_first(service: Any) -> None:
    folder = service.settings.jobs_root / "batch"
    folder.mkdir(parents=True)
    (folder / "a.png").write_bytes(png(CONFIDENT))
    first = service.client.post("/jobs", json={"kind": "folder", "path": "batch"}).json()
    second = service.client.post("/jobs", json={"kind": "folder", "path": "batch"}).json()
    listed = service.client.get("/jobs").json()
    assert {job["id"] for job in listed} == {first["id"], second["id"]}
    assert all(job["status"] == "finished" for job in listed)
    assert listed[0]["created_at"] >= listed[1]["created_at"]
    assert len(service.client.get("/jobs", params={"limit": 1}).json()) == 1
    assert service.client.get("/jobs", params={"offset": 2}).json() == []
