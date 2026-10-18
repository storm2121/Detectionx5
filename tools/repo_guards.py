"""Repository guards run by pre-commit and by the CI test suite.

``names``  fails when a file (or a commit message) mentions a forbidden token: the
           hosting service and the name of the detector's original training dataset.
           The tokens are stored only as SHA-256 digests of their normalised spelling,
           so this file can be committed without containing what it forbids.
``data``   fails when an image, a video, an archive or a CSV with more than 50 rows
           is staged under ``data/``, which must stay a placeholder until the final step.

Normalisation lower-cases the text (after NFKD), keeps only ``[a-z0-9]`` and joins
everything, so spacing, punctuation, casing, hyphenation and full-width forms do not
evade the check. Every window of each token's length is hashed and compared.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ForbiddenToken:
    length: int
    sha256: str
    label: str  # a neutral description, never the token itself


FORBIDDEN: tuple[ForbiddenToken, ...] = (
    ForbiddenToken(
        8, "a929cdacf5a9095cb27dc5992210dabc0d51159dbe757076d0ff084efa414bdb", "dataset host"
    ),
    ForbiddenToken(
        29, "98b326aa81ffcf72b50a78ae3fa516efc083f9331265594fd93601dfa43fc625", "dataset name"
    ),
    ForbiddenToken(
        10, "e26b9d1f0f9b001d849f659dcbd16a22afd843743ab541d1c717313e69abc09f", "dataset workspace"
    ),
)

BINARY_SUFFIXES = frozenset(
    {
        ".pt",
        ".pth",
        ".onnx",
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
        ".gif",
        ".tif",
        ".tiff",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".zip",
        ".gz",
        ".tar",
        ".7z",
        ".npz",
        ".npy",
        ".pkl",
        ".ico",
        ".pdf",
        ".db",
        ".sqlite",
    }
)
IMAGE_OR_MEDIA_SUFFIXES = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".webp",
        ".gif",
        ".tif",
        ".tiff",
        ".heic",
        ".mp4",
        ".avi",
        ".mov",
        ".mkv",
        ".webm",
        ".zip",
        ".tar",
        ".gz",
        ".7z",
        ".npz",
        ".npy",
    }
)
MAX_CSV_ROWS = 50


def normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).lower()
    return "".join(ch for ch in folded if ("a" <= ch <= "z") or ("0" <= ch <= "9"))


def find_forbidden(text: str, tokens: Sequence[ForbiddenToken] = FORBIDDEN) -> list[ForbiddenToken]:
    """Return every forbidden token whose normalised spelling occurs in ``text``."""
    stream = normalise(text).encode("ascii")
    found: list[ForbiddenToken] = []
    for token in tokens:
        if len(stream) < token.length:
            continue
        windows = {stream[i : i + token.length] for i in range(len(stream) - token.length + 1)}
        if any(hashlib.sha256(w).hexdigest() == token.sha256 for w in windows):
            found.append(token)
    return found


def _is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        with path.open("rb") as handle:
            return b"\0" in handle.read(8192)
    except OSError:
        return True


def repository_files(root: Path = ROOT) -> list[Path]:
    """Tracked files plus untracked files that are not ignored."""
    output = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    names = sorted({name for name in output.decode("utf-8").split("\0") if name})
    return [root / name for name in names if (root / name).is_file()]


def check_names(paths: Iterable[Path], tokens: Sequence[ForbiddenToken] = FORBIDDEN) -> list[str]:
    problems: list[str] = []
    for path in paths:
        if not path.is_file() or _is_binary(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in find_forbidden(text, tokens):
            problems.append(f"{path}: mentions the forbidden {token.label}")
    return problems


def _csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = [line for line in handle if line.strip()]
    return max(0, len(lines) - 1)  # minus the header


def check_data(paths: Iterable[Path], root: Path = ROOT) -> list[str]:
    problems: list[str] = []
    data_root = (root / "data").resolve()
    for path in paths:
        resolved = path.resolve()
        if data_root not in resolved.parents:
            continue
        suffix = resolved.suffix.lower()
        if suffix in IMAGE_OR_MEDIA_SUFFIXES:
            problems.append(
                f"{path}: real images, videos and archives must not be committed under data/"
            )
        elif suffix == ".csv" and resolved.is_file() and _csv_rows(resolved) > MAX_CSV_ROWS:
            problems.append(f"{path}: CSV under data/ has more than {MAX_CSV_ROWS} rows")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="repo_guards", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    names = sub.add_parser("names", help="forbidden dataset-host and dataset-name tokens")
    names.add_argument("files", nargs="*", type=Path)
    names.add_argument("--all", action="store_true", help="scan every repository file")
    names.add_argument(
        "--commit-msg", action="store_true", help="treat the files as commit messages"
    )
    data = sub.add_parser("data", help="no real data under data/")
    data.add_argument("files", nargs="*", type=Path)
    data.add_argument("--all", action="store_true", help="scan every repository file")
    args = parser.parse_args(argv)

    files: list[Path] = repository_files() if args.all else list(args.files)
    problems = check_names(files) if args.command == "names" else check_data(files)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
