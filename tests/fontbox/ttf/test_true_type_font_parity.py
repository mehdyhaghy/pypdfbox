"""Parity tests for the PDFBox-shaped accessors on
:class:`pypdfbox.fontbox.ttf.TrueTypeFont`.

Loads the bundled LiberationSans-Regular fixture (a real OpenFont
Liberation TTF) and asserts each accessor returns the expected type and
a sensible value. Mirrors how upstream's
``org.apache.fontbox.ttf.TrueTypeFontTest`` exercises name / head / post
/ OS/2 lookups against a fixture font.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


# ---------- name-table accessors -----------------------------------------


def test_get_name_returns_postscript_name(liberation_sans: TrueTypeFont) -> None:
    name = liberation_sans.get_name()
    assert name == "LiberationSans"


def test_get_family_name(liberation_sans: TrueTypeFont) -> None:
    family = liberation_sans.get_family_name()
    assert family == "Liberation Sans"


def test_get_full_name(liberation_sans: TrueTypeFont) -> None:
    full = liberation_sans.get_full_name()
    assert full == "Liberation Sans"


def test_get_version(liberation_sans: TrueTypeFont) -> None:
    version = liberation_sans.get_version()
    assert version is not None
    assert version.startswith("Version")


# ---------- head / post / OS/2 scalar accessors --------------------------


def test_get_font_bbox(liberation_sans: TrueTypeFont) -> None:
    bbox = liberation_sans.get_font_bbox()
    assert isinstance(bbox, tuple)
    assert len(bbox) == 4
    x_min, y_min, x_max, y_max = bbox
    # Sanity: the bbox must be non-degenerate.
    assert x_min < x_max
    assert y_min < y_max
    # Liberation Sans on-disk values.
    assert bbox == (-1114, -621, 2666, 2007)


def test_get_italic_angle(liberation_sans: TrueTypeFont) -> None:
    angle = liberation_sans.get_italic_angle()
    assert isinstance(angle, float)
    assert angle == 0.0  # Regular weight, not italic.


def test_get_underline_position(liberation_sans: TrueTypeFont) -> None:
    pos = liberation_sans.get_underline_position()
    assert isinstance(pos, int)
    # Liberation Sans places the underline below the baseline.
    assert pos < 0


def test_get_underline_thickness(liberation_sans: TrueTypeFont) -> None:
    thick = liberation_sans.get_underline_thickness()
    assert isinstance(thick, int)
    assert thick > 0


def test_is_fixed_pitch_for_proportional_font(
    liberation_sans: TrueTypeFont,
) -> None:
    # Liberation Sans is proportional, not monospaced.
    assert liberation_sans.is_fixed_pitch() is False


def test_get_weight(liberation_sans: TrueTypeFont) -> None:
    weight = liberation_sans.get_weight()
    assert isinstance(weight, int)
    # Regular = 400.
    assert weight == 400


def test_get_width(liberation_sans: TrueTypeFont) -> None:
    width = liberation_sans.get_width()
    assert isinstance(width, int)
    # Medium = 5.
    assert width == 5


# ---------- table-presence accessors -------------------------------------


def test_get_capabilities_includes_required_tables(
    liberation_sans: TrueTypeFont,
) -> None:
    caps = liberation_sans.get_capabilities()
    assert isinstance(caps, dict)
    # Every TTF MUST carry these tables.
    for required in ("head", "hhea", "maxp", "hmtx", "cmap", "name", "post"):
        assert required in caps, f"missing required table: {required}"
        assert caps[required] is True


def test_has_table_predicate(liberation_sans: TrueTypeFont) -> None:
    assert liberation_sans.has_table("head") is True
    assert liberation_sans.has_table("OS/2") is True
    # A bogus tag should not be reported as present.
    assert liberation_sans.has_table("ZZZZ") is False
