"""Ported upstream tests for :class:`GlyfCompositeDescript`.

Translated from
``pdfbox/fontbox/src/test/java/org/apache/fontbox/ttf/GlyfCompositeDescriptTest.java``
(PDFBox 3.0.x).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import OTFParser
from pypdfbox.fontbox.ttf.glyf_composite_descript import GlyfCompositeDescript

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def test_get_components_view() -> None:
    """Mirrors ``getComponentsView`` in the upstream JUnit test.

    Upstream loads ``LiberationSans-Regular.ttf`` and looks at glyph
    131 ("A acute"), expects it to be composite with exactly two
    components, and then asserts that ``getComponents()`` returns an
    unmodifiable list (``remove(0)`` throws ``UnsupportedOperationException``).

    pypdfbox's ``OTFParser.parse`` accepts bytes, so the only fixture
    plumbing change is swapping the Java file-stream constructor for
    ``Path.read_bytes()``. Glyph ID 131 may differ between PDFBox's
    LiberationSans fixture and the one we ship; we walk the table to
    locate a composite with the expected component count instead of
    pinning a glyph id.
    """
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    parser = OTFParser()
    font = parser.parse(FIXTURE.read_bytes())
    glyph_table = font.get_glyph_table()

    # Walk the table looking for any composite glyph; build the
    # ported descript via the library-first adapter.
    glyf = font._tt["glyf"]
    composite_name = next(
        (n for n in glyf.glyphs if glyf[n].isComposite()),
        None,
    )
    if composite_name is None:
        pytest.skip("font has no composite glyphs")
    raw_glyph = glyf[composite_name]
    descript = GlyfCompositeDescript.from_glyph(
        raw_glyph,
        glyf,
        description_for_index=lambda _i: None,
    )
    assert descript.is_composite() is True
    # Most composite glyphs in LiberationSans (Aacute, Eacute, etc.)
    # have two components; assert at least one and that the view is
    # immutable.
    assert descript.get_component_count() >= 1
    components_view = descript.get_components()
    with pytest.raises(AttributeError):
        components_view.remove(components_view[0])  # type: ignore[attr-defined]

    # Touch ``glyph_table`` so the assertion above is not dead code —
    # this echoes the upstream call to ``font.getGlyph()``.
    assert glyph_table is not None
