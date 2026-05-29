"""Live PDFBox differential parity for the TrueType ``post`` table *header*
fields (``oracle/probes/PostHeaderProbe.java``).

The sibling ``test_post_table_oracle`` pins the glyph-name surface
(``get_format_type`` / ``get_name`` / ``name_to_gid``). This test pins the
remaining scalar header getters that the post table parses before the optional
format-2.0 glyph-name array — the values that feed font metrics and embedding:

* :meth:`PostScriptTable.get_italic_angle` — 16.16 fixed-point degrees (CCW);
  ``0.0`` for upright faces, a negative value for italic/oblique faces.
* :meth:`PostScriptTable.get_underline_position` /
  :meth:`~PostScriptTable.get_underline_thickness` — signed-short FUnits.
* :meth:`PostScriptTable.get_is_fixed_pitch` — the raw 32-bit flag (``0`` for a
  proportional face, non-zero for a monospaced one).
* :meth:`PostScriptTable.get_min_mem_type42` /
  :meth:`~PostScriptTable.get_max_mem_type42` /
  :meth:`~PostScriptTable.get_min_mem_type1` /
  :meth:`~PostScriptTable.get_max_mem_type1` — the Type42/Type1 VM-usage hints.

Fonts chosen to span the interesting cases:
  * ``LiberationSans-Regular`` — upright, proportional (italic angle 0, fixed
    pitch 0).
  * ``LiberationSans-Italic`` — slanted (non-zero italic angle).
  * ``LiberationMono-Regular`` — monospaced (non-zero ``isFixedPitch``).
  * ``DejaVuSans`` — second proportional face, distinct underline metrics.

pypdfbox delegates the byte parse to its own ``TTFDataStream`` but exposes the
FontBox-compatible ``PostScriptTable`` getters; this test verifies every header
field decodes identically to PDFBox 3.0.7. A divergence shows up as a single
differing ``KEY\tVALUE`` line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont
from tests.oracle.harness import requires_oracle, run_probe_text

_TTF_DIR = Path(__file__).resolve().parents[4] / "pypdfbox" / "resources" / "ttf"

_FONTS = [
    "LiberationSans-Regular.ttf",
    "LiberationSans-Italic.ttf",
    "LiberationMono-Regular.ttf",
    "DejaVuSans.ttf",
]


def _java_float(value: float) -> str:
    """Render a float the way Java's ``Float.toString`` does for these fields.

    The post header floats (format type, italic angle) are 16.16 fixed-point
    values whose fractional part is a multiple of ``1/65536``. PDFBox stores
    them as a 32-bit ``float`` and prints them with ``Float.toString``; the
    integer-valued ones (``0.0``, ``-12.0``, ``2.0``) render with a single
    trailing zero, matching Python's ``str(float)``.
    """
    return str(value)


def _pypdfbox_lines(path: Path) -> list[str]:
    """Reproduce the probe's canonical output from pypdfbox.

    Closes the font program in a ``finally`` so the bundled resource handle is
    never left open (Windows would otherwise lock the file).
    """
    ttf = TrueTypeFont.from_bytes(path.read_bytes())
    try:
        post = ttf.get_post_script()
        assert post is not None
        return [
            f"FORMAT\t{_java_float(post.get_format_type())}",
            f"ITALICANGLE\t{_java_float(post.get_italic_angle())}",
            f"UNDERLINEPOSITION\t{post.get_underline_position()}",
            f"UNDERLINETHICKNESS\t{post.get_underline_thickness()}",
            f"ISFIXEDPITCH\t{post.get_is_fixed_pitch()}",
            f"MINMEMTYPE42\t{post.get_min_mem_type42()}",
            f"MAXMEMTYPE42\t{post.get_max_mem_type42()}",
            f"MINMEMTYPE1\t{post.get_min_mem_type1()}",
            f"MAXMEMTYPE1\t{post.get_max_mem_type1()}",
        ]
    finally:
        ttf.close()


@requires_oracle
@pytest.mark.parametrize("font", _FONTS)
def test_post_header_fields_match_pdfbox(font: str) -> None:
    path = _TTF_DIR / font
    java = run_probe_text("PostHeaderProbe", str(path)).splitlines()
    py = _pypdfbox_lines(path)
    assert py == java


@requires_oracle
def test_italic_font_has_nonzero_italic_angle() -> None:
    """Anchor: the italic face must report a non-zero slant on both sides.

    Guards against the parametrised test silently passing if the italic font
    were swapped for an upright one (which would never exercise a non-zero
    16.16-fixed italic angle).
    """
    path = _TTF_DIR / "LiberationSans-Italic.ttf"
    java = dict(
        line.split("\t", 1)
        for line in run_probe_text("PostHeaderProbe", str(path)).splitlines()
    )
    assert float(java["ITALICANGLE"]) != 0.0
    ttf = TrueTypeFont.from_bytes(path.read_bytes())
    try:
        assert ttf.get_post_script().get_italic_angle() != 0.0
    finally:
        ttf.close()


@requires_oracle
def test_mono_font_is_fixed_pitch() -> None:
    """Anchor: the monospaced face must report a non-zero ``isFixedPitch``."""
    path = _TTF_DIR / "LiberationMono-Regular.ttf"
    java = dict(
        line.split("\t", 1)
        for line in run_probe_text("PostHeaderProbe", str(path)).splitlines()
    )
    assert int(java["ISFIXEDPITCH"]) != 0
    ttf = TrueTypeFont.from_bytes(path.read_bytes())
    try:
        assert ttf.get_post_script().get_is_fixed_pitch() != 0
    finally:
        ttf.close()
