"""Send synthetic photos to a running service and print the read (the demo and smoke check).

    uv run python tools/demo_read.py                    # http://localhost:8100
    uv run python tools/demo_read.py --url http://host:port --views 3 --crop

By default it sends a synthetic street scene through the detector; ``--crop`` sends
synthetic plate crops with ``detect=false``. Everything sent is generated, so the printed
read is a synthetic result, which is not real-world accuracy.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import uuid
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plate_reader.synthetic import encode_png, make_scene, make_views  # noqa: E402


def multipart(files: list[tuple[str, bytes]]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for name, data in files:
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{name}"\r\n'
            "Content-Type: image/png\r\n\r\n".encode()
            + data
            + b"\r\n"
        )
    body = b"".join(parts) + f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8100")
    parser.add_argument("--views", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--crop", action="store_true", help="send crops with detect=false")
    args = parser.parse_args(argv)

    with urllib.request.urlopen(f"{args.url}/health", timeout=10) as response:
        print("health:", response.read().decode())
    if args.crop:
        images = [encode_png(v.image) for v in make_views(args.seed, 0, args.views)]
        truth = make_views(args.seed, 0, 1)[0].text
        query = "?detect=false"
    else:
        scene = make_scene(args.seed, 0, empty_fraction=0.0)
        images = [encode_png(scene.image)]
        truth = scene.plates[0][0] if scene.plates else None
        query = ""
    body, content_type = multipart([(f"view{i}.png", data) for i, data in enumerate(images)])
    request = urllib.request.Request(
        f"{args.url}/read{query}", data=body, headers={"Content-Type": content_type}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        read = json.loads(response.read().decode("utf-8"))
    summary = {
        key: read.get(key)
        for key in ("plate", "confidence", "prediction_set", "review", "model_version")
    }
    print("truth (synthetic):", truth)
    print("read:", json.dumps(summary, ensure_ascii=False))
    print("synthetic input: synthetic results are not real-world accuracy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
