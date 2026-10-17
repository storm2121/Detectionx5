"""Exercise HTTP handling and real multi-image voting without model downloads."""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api
from plate_reader import Detection, PlateReading, parse_plate
from plate_reader import pipeline
from plate_reader.ocr import EasyOCRBackend


@pytest.fixture
def photo():
    buffer = BytesIO()
    Image.new("RGB", (32, 16), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def service(monkeypatch):
    detector = Mock()
    detector.detect.return_value = []
    backend = Mock(spec=EasyOCRBackend)
    detector_factory = Mock(return_value=detector)
    backend_factory = Mock(return_value=backend)
    read_images = Mock(wraps=api.read_images)
    monkeypatch.setattr(api, "PlateDetector", detector_factory)
    monkeypatch.setattr(api, "EasyOCRBackend", backend_factory)
    monkeypatch.setattr(api, "read_images", read_images)

    app = api.create_app()
    detector_factory.assert_not_called()
    backend_factory.assert_not_called()
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client, detector=detector, backend=backend,
            detector_factory=detector_factory, backend_factory=backend_factory,
            read_images=read_images,
        )
    assert not hasattr(app.state, "detector")
    assert not hasattr(app.state, "backend")


def upload(photo, name="car.png"):
    return ("files", (name, photo, "image/png"))


def reading(text, score):
    plate = parse_plate(text)
    assert plate is not None
    return PlateReading(
        plate=plate,
        detection=Detection((0, 0, 32, 16), 0.9, np.zeros((16, 32, 3), dtype=np.uint8)),
        votes={plate.text: score},
    )


def test_health_and_models_loaded_once_at_startup(service, photo):
    service.detector_factory.assert_called_once_with()
    service.backend_factory.assert_called_once_with()
    service.backend.load_models.assert_called_once_with()
    assert service.client.get("/health").json() == {"status": "ok"}

    for _ in range(2):
        assert service.client.post("/read", files=[upload(photo)]).status_code == 200

    service.detector_factory.assert_called_once_with()
    service.backend_factory.assert_called_once_with()
    service.backend.load_models.assert_called_once_with()
    for call in service.read_images.call_args_list:
        assert call.kwargs["detector"] is service.detector
        assert call.kwargs["backend"] is service.backend


def test_multiple_photos_vote_and_count_each_photo_once(service, photo, monkeypatch):
    readings = [
        reading("24830-ب-1", 4.0),
        reading("24830-ب-1", 3.0),
        reading("24830-ب-1", 1.0),
        reading("12345-أ-2", 2.0),
    ]
    service.detector.detect.side_effect = [
        [readings[0].detection],
        [readings[1].detection, readings[2].detection],
        [readings[3].detection],
    ]
    monkeypatch.setattr(pipeline, "read_detection", Mock(side_effect=readings))

    def detect(paths, **kwargs):
        assert len(set(paths)) == 3
        assert all(path.read_bytes() == photo for path in paths)
        return pipeline.read_images(paths, **kwargs)

    service.read_images.side_effect = detect
    response = service.client.post(
        "/read", files=[upload(photo, "../../car.png")] * 3,
    )

    assert response.status_code == 200
    assert response.json() == {
        "plate": "24830-ب-1",
        "fields": {"digits": "24830", "letter": "ب", "region": "1"},
        "confidence": 0.8,
        "images_agreeing": 2,
        "images_processed": 3,
    }
    paths = service.read_images.call_args.args[0]
    assert all(not path.parent.exists() for path in paths)


def test_temporary_plate_fields(service, photo, monkeypatch):
    result = reading("72173 WW", 2.0)
    service.detector.detect.return_value = [result.detection]
    monkeypatch.setattr(pipeline, "read_detection", Mock(return_value=result))

    response = service.client.post("/read", files=[upload(photo)])
    assert response.status_code == 200
    assert response.json() == {
        "plate": "72173 WW",
        "fields": {"digits": "72173", "letter": None, "region": None},
        "confidence": 1.0,
        "images_agreeing": 1,
        "images_processed": 1,
    }


def test_no_readable_plate(service, photo):
    response = service.client.post("/read", files=[upload(photo), upload(photo)])
    assert response.status_code == 200
    assert response.json() == {
        "plate": None, "fields": None, "confidence": 0.0,
        "images_agreeing": 0, "images_processed": 2,
    }


def test_missing_photos(service):
    assert service.client.post("/read").status_code == 422
    service.read_images.assert_not_called()


@pytest.mark.parametrize("data", [b"", b"this is not a photo"])
def test_invalid_photos_rejected_before_inference(service, photo, data):
    response = service.client.post("/read", files=[upload(photo), upload(data)])
    assert response.status_code == 400
    service.read_images.assert_not_called()


def test_unsupported_image_format(service):
    buffer = BytesIO()
    Image.new("RGB", (32, 16)).save(buffer, format="GIF")
    assert service.client.post("/read", files=[upload(buffer.getvalue())]).status_code == 415
    service.read_images.assert_not_called()


def test_photo_count_limit(service, photo):
    response = service.client.post("/read", files=[upload(photo)] * (api.MAX_PHOTOS + 1))
    assert response.status_code == 413
    service.read_images.assert_not_called()


def test_photo_size_limit(service, photo, monkeypatch):
    monkeypatch.setattr(api, "MAX_PHOTO_BYTES", len(photo) - 1)
    assert service.client.post("/read", files=[upload(photo)]).status_code == 413
    service.read_images.assert_not_called()


def test_temp_photos_removed_after_inference_error(service, photo):
    service.read_images.side_effect = RuntimeError("inference failed")
    with pytest.raises(RuntimeError, match="inference failed"):
        service.client.post("/read", files=[upload(photo)])
    assert all(not path.parent.exists() for path in service.read_images.call_args.args[0])


def test_startup_fails_if_ocr_models_cannot_load(service):
    service.backend.load_models.side_effect = RuntimeError("missing OCR weights")
    with pytest.raises(RuntimeError, match="missing OCR weights"):
        with TestClient(api.create_app()):
            pytest.fail("The server must not become ready without OCR models.")


def test_ocr_warmup_reuses_all_readers(monkeypatch):
    factory = Mock(side_effect=lambda languages: object())
    backend = EasyOCRBackend()
    monkeypatch.setattr(backend, "_reader", factory)

    backend.load_models()
    backend.load_models()
    assert [call.args[0] for call in factory.call_args_list] == [["en"], ["ar"], ["ar", "en"]]
