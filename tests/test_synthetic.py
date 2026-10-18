"""Hypothesis invariants of the synthetic generator (ARCHITECTURE §6)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from plate_reader import grammar
from plate_reader.data.validate import (
    ValidationReport,
    validate_data,
    validate_ocr_csv,
)
from plate_reader.synthetic import (
    DEFAULT,
    encode_png,
    make_crop,
    make_pseudo_real,
    make_scene,
    make_views,
    render_plate,
    sample_style,
    write_crops,
    write_scenes,
    write_views,
)
from plate_reader.synthetic import augment as aug
from plate_reader.synthetic.fonts import FONT_DIR, FONTS, load_font
from plate_reader.synthetic.generate import MAX_SIZE, MIN_SIZE
from plate_reader.synthetic.splits import SPLIT_SEEDS

seeds = st.integers(0, 2**31 - 1)
indices = st.integers(0, 10**6)
fast = settings(max_examples=40)


def _within_bounds(image: np.ndarray) -> bool:
    h, w = image.shape[:2]
    return MIN_SIZE[0] <= h <= MAX_SIZE[0] and MIN_SIZE[1] <= w <= MAX_SIZE[1]


@fast
@given(seeds, indices)
def test_crop_labels_are_grammar_valid_and_sizes_bounded(seed: int, index: int) -> None:
    sample = make_crop(seed, index)
    assert grammar.accepts(sample.tokens)
    assert grammar.parse(sample.text) is not None
    assert grammar.parse(sample.text).tokens == sample.tokens  # type: ignore[union-attr]
    assert sample.image.dtype == np.uint8
    assert sample.image.ndim == 3
    assert sample.image.shape[2] == 3
    assert _within_bounds(sample.image)
    assert sample.format in grammar.FORMAT_NAMES


@fast
@given(seeds, indices)
def test_a_seed_reproduces_identical_png_bytes(seed: int, index: int) -> None:
    first, second = make_crop(seed, index), make_crop(seed, index)
    assert encode_png(first.image) == encode_png(second.image)
    assert first.tokens == second.tokens
    assert first.meta == second.meta


@fast
@given(seeds, indices)
def test_pseudo_real_is_valid_bounded_and_deterministic(seed: int, index: int) -> None:
    sample = make_pseudo_real(seed, index)
    assert grammar.accepts(sample.tokens)
    assert _within_bounds(sample.image)
    assert sample.meta["kind"] == "pseudo_real"
    assert sample.meta["strength"] >= 0.75
    assert encode_png(sample.image) == encode_png(make_pseudo_real(seed, index).image)


@settings(max_examples=15)
@given(seeds, indices, st.integers(1, 5))
def test_views_share_one_label_and_differ_in_pixels(seed: int, index: int, k: int) -> None:
    views = make_views(seed, index, k)
    assert len(views) == k
    assert len({v.tokens for v in views}) == 1
    assert all(_within_bounds(v.image) for v in views)
    assert [v.meta["view"] for v in views] == list(range(1, k + 1))
    if k > 1:
        assert len({encode_png(v.image) for v in views}) == k


@settings(max_examples=10)
@given(seeds, indices)
def test_scene_boxes_lie_inside_the_image(seed: int, index: int) -> None:
    sample = make_scene(seed, index)
    h, w = sample.image.shape[:2]
    for tokens, (x1, y1, x2, y2) in sample.plates:
        assert grammar.accepts(tokens)
        assert 0 <= x1 < x2 <= w
        assert 0 <= y1 < y2 <= h
    assert encode_png(sample.image) == encode_png(make_scene(seed, index).image)


def test_different_indices_and_seeds_give_different_crops() -> None:
    images = {encode_png(make_crop(1, i).image) for i in range(20)}
    assert len(images) == 20
    assert encode_png(make_crop(1, 0).image) != encode_png(make_crop(2, 0).image)


def test_both_formats_and_all_letters_are_generated() -> None:
    samples = [make_crop(SPLIT_SEEDS["test"], i) for i in range(300)]
    formats = {s.format for s in samples}
    assert formats == {"standard", "temporary"}
    letters = {p.letter for s in samples if (p := grammar.Plate.from_tokens(s.tokens)) and p.letter}
    assert letters == set(grammar.LETTERS)


def test_split_seeds_are_distinct() -> None:
    assert len(set(SPLIT_SEEDS.values())) == len(SPLIT_SEEDS)


def test_render_plate_draws_every_glyph_and_rejects_invalid_text() -> None:
    rng = np.random.default_rng(0)
    style = sample_style(rng)
    rendered = render_plate("24830-ب-1", style)
    assert [symbol for symbol, _ in rendered.boxes] == list("24830-ب-1")
    assert rendered.image.shape == (style.height, style.width, 3)
    temporary = render_plate("72173-WW", style)
    assert [symbol for symbol, _ in temporary.boxes] == list("72173WW")
    with pytest.raises(ValueError):
        render_plate("nope", style)
    assert style.as_dict()["width"] == style.width


def test_long_plates_are_condensed_to_fit() -> None:
    style = sample_style(np.random.default_rng(3))
    narrow = type(style)(**{**style.as_dict(), "width": 300})
    rendered = render_plate("12345-أ-67", narrow)
    assert all(x2 <= narrow.width for _, (_, _, x2, _) in rendered.boxes)


def test_strength_zero_leaves_photometry_unchanged() -> None:
    image = np.random.default_rng(1).integers(0, 256, size=(32, 96, 3), dtype=np.uint8)
    rng = np.random.default_rng(2)
    out, params = aug.photometric(image, rng, 0.0, DEFAULT)
    assert np.array_equal(out, image)
    assert params["contrast"] == 1.0
    for op in (aug.shadow, aug.dirt, aug.glare, aug.blur, aug.resolution, aug.noise):
        result, _ = op(image, rng, 0.0, DEFAULT)
        assert np.array_equal(result, image)


def test_strong_augmentations_change_the_image() -> None:
    image = np.full((48, 160, 3), 200, dtype=np.uint8)
    strong = aug.AugmentConfig(
        shadow_prob=1.0, dirt_prob=1.0, glare_prob=1.0, occlusion_prob=1.0, downscale=0.3
    )
    for op in (aug.shadow, aug.dirt, aug.glare, aug.noise):
        rng = np.random.default_rng(5)
        result, params = op(image, rng, 1.0, strong)
        assert not np.array_equal(result, image), op.__name__
        assert any(v for v in params.values())
    occluded, params = aug.occlusion(image, np.random.default_rng(5), 1.0, strong, (10, 5, 150, 40))
    assert params["occlusion"] > 0
    assert not np.array_equal(occluded, image)
    textured = np.random.default_rng(9).integers(0, 256, size=(48, 160, 3), dtype=np.uint8)
    blurred = [aug.blur(textured, np.random.default_rng(s), 1.0, strong)[1] for s in range(20)]
    assert any(p["motion_px"] > 0 for p in blurred)
    assert any(p["sigma"] > 0 for p in blurred)
    lowres = [aug.resolution(textured, np.random.default_rng(s), 1.0, strong)[1] for s in range(5)]
    assert any(p["resolution"] < 1 for p in lowres)
    jpegs = [aug.jpeg(textured, np.random.default_rng(s), 1.0, strong)[1] for s in range(10)]
    assert any(p["jpeg_quality"] < 100 for p in jpegs)
    assert aug.sharpness(textured) > aug.sharpness(np.full_like(textured, 7))


def test_fonts_are_bundled_with_their_licences() -> None:
    listing = (FONT_DIR / "FONTS.md").read_text(encoding="utf-8")
    for spec in FONTS:
        path = FONT_DIR / spec.path
        assert path.is_file(), spec.path
        assert (path.parent / "OFL.txt").is_file()
        assert "SIL Open Font License" in (path.parent / "OFL.txt").read_text(encoding="utf-8")
        assert path.name in listing
        assert spec.licence == "OFL-1.1"
        weight = spec.weights[0] if spec.weights else None
        assert load_font(spec.key, 32, weight).getbbox("1")[2] > 0


def test_written_sets_are_deterministic_and_pass_the_real_data_validator(tmp_path: Path) -> None:
    first = write_crops(tmp_path / "a", 12, seed=3)
    second = write_crops(tmp_path / "b", 12, seed=3)
    assert first.digest == second.digest
    for name in ("labels.csv", "meta.jsonl", "manifest.json", "crops/000011.png"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    report = ValidationReport(root=tmp_path / "a")
    validate_ocr_csv(report, tmp_path / "a" / "labels.csv", "crops")
    assert report.errors == []
    assert report.warnings == []
    assert report.counts["crops"] == 12

    pseudo = write_crops(tmp_path / "p", 6, seed=3, pseudo_real=True)
    assert pseudo.kind == "pseudo_real"
    assert '"set_kind": "pseudo_real"' in (tmp_path / "p" / "manifest.json").read_text("utf-8")

    scenes = write_scenes(tmp_path / "s", 10, seed=4)
    assert scenes.n == 10
    scene_report = validate_data(tmp_path / "s")
    assert scene_report.errors == []
    assert scene_report.counts["detector_val_images"] == 2
    assert scene_report.counts["eval_images"] >= 1

    views = write_views(tmp_path / "v", 4, 3, seed=5)
    lines = (tmp_path / "v" / "views.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 + 4 * 3
    assert views.as_dict()["kind"] == "views"


def test_synth_cli_writes_every_kind(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from plate_reader.cli import app

    runner = CliRunner()
    for kind, extra in (
        ("crops", []),
        ("pseudo-real", []),
        ("views", ["--k", "2"]),
        ("scenes", []),
    ):
        out = tmp_path / kind
        result = runner.invoke(
            app, ["synth", kind, "--out", str(out), "--n", "3", "--seed", "1", *extra]
        )
        assert result.exit_code == 0, result.output
        assert "synthetic results are not real-world accuracy" in result.output
        assert (out / "manifest.json").exists()
