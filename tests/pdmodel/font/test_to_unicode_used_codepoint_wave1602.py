"""PDFBOX-6210 — ToUnicode must prefer the code point used in the document.

Upstream 3.0.8 (commit 74458715) fixed wrong CJK text extraction for
embedded subsets: when several code points map to one glyph, the
ToUnicode CMap used to record ``cmapLookup.getCharCodes(gid).get(0)``
(the lowest code point sharing the glyph, often an unexpected
compatibility character). It now prefers the code point actually used
in the document, first occurrence wins, falling back to the cmap's
first entry for glyphs with no recorded input.

The upstream regression tests use ``NotoSansCJKkr-VF.ttf`` (glyph shared
by 食 U+98DF and ⻝ U+2EDD), a fixture downloaded by maven and not
bundled here. The bundled Liberation/DejaVu fonts have *no* glyph shared
between two code points, so these tests construct the scenario
synthetically: the Liberation Sans cmap is patched in-memory so U+0100
maps to the same glyph as U+0041 ("A").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fontTools.ttLib import TTFont

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common import PDStream
from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
    PDCIDFontType2Embedder,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument

_LIB_SANS = (
    Path(__file__).parent.parent.parent.parent
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

#: Synthetic second code point mapped onto the "A" glyph — like upstream's
#: radical/ideograph pair, sorted *after* the original (0x41 < 0x100), so
#: the old ``codes[0]`` behavior always resolved the glyph to U+0041.
_SHARED_CP = 0x0100


@pytest.fixture(scope="module", autouse=True)
def _install_missing_cos_name_constants() -> None:
    """Inject COSName constants the embedder needs but the package omits."""
    for attr, raw in (
        ("BASE_FONT", "BaseFont"),
        ("FONT", "Font"),
        ("FONT_DESC", "FontDescriptor"),
        ("IDENTITY", "Identity"),
        ("ENCODING", "Encoding"),
    ):
        if not hasattr(COSName, attr):
            setattr(COSName, attr, COSName.get_pdf_name(raw))


def _load_shared_glyph_ttf() -> tuple[TTFont, int]:
    """Liberation Sans with U+0041 and U+0100 sharing the "A" glyph.

    Returns the font and the glyph id both code points resolve to.
    """
    if not _LIB_SANS.exists():
        pytest.skip(f"Bundled font missing: {_LIB_SANS}")
    ttf = TTFont(str(_LIB_SANS))
    glyph_name = ttf["cmap"].getBestCmap()[0x41]
    for table in ttf["cmap"].tables:
        if table.isUnicode():
            table.cmap[_SHARED_CP] = glyph_name
    gid = int(ttf.getGlyphID(glyph_name))
    assert gid > 0
    return ttf, gid


def _new_embedder() -> tuple[PDCIDFontType2Embedder, COSDictionary, int]:
    ttf, gid = _load_shared_glyph_ttf()
    dict_ = COSDictionary()
    embedder = PDCIDFontType2Embedder(
        PDDocument(),
        dict_,
        ttf,
        embed_subset=True,
        parent=PDType0Font(),
        vertical=False,
    )
    return embedder, dict_, gid


def _to_unicode_text(dict_: COSDictionary) -> str:
    stream: Any = dict_.get_item(COSName.get_pdf_name("ToUnicode"))
    assert stream is not None
    return PDStream(stream).to_byte_array().decode("ascii")


def _bf_entry(cid: int, code_point: int) -> str:
    return f"<{cid:04X}> <{cid:04X}> <{code_point:04X}>"


# ---------- shared glyph: used code point wins -----------------------------


def test_to_unicode_prefers_code_point_used_in_document() -> None:
    """The document typed U+0100; the shared glyph must NOT extract as U+0041."""
    embedder, dict_, gid = _new_embedder()
    embedder.add_to_subset(_SHARED_CP)
    embedder.build_to_unicode_c_map({gid: gid})
    assert _bf_entry(gid, _SHARED_CP) in _to_unicode_text(dict_)


def test_to_unicode_first_occurrence_wins_for_shared_glyph() -> None:
    """Both code points used: the one typed first wins (putIfAbsent)."""
    embedder, dict_, gid = _new_embedder()
    embedder.add_to_subset(_SHARED_CP)
    embedder.add_to_subset(0x41)  # later occurrence of the same glyph
    embedder.build_to_unicode_c_map({gid: gid})
    assert _bf_entry(gid, _SHARED_CP) in _to_unicode_text(dict_)


def test_to_unicode_keeps_lowest_code_point_when_it_was_typed_first() -> None:
    embedder, dict_, gid = _new_embedder()
    embedder.add_to_subset(0x41)
    embedder.add_to_subset(_SHARED_CP)
    embedder.build_to_unicode_c_map({gid: gid})
    assert _bf_entry(gid, 0x41) in _to_unicode_text(dict_)


def test_to_unicode_falls_back_to_lowest_code_point_without_usage() -> None:
    """No recorded input for the glyph -> pre-6210 ``codes[0]`` fallback."""
    embedder, dict_, gid = _new_embedder()
    embedder.build_to_unicode_c_map({gid: gid})
    assert _bf_entry(gid, 0x41) in _to_unicode_text(dict_)


def test_to_unicode_used_code_point_applies_after_gid_renumber() -> None:
    """Subset path: new gid 1 maps back to the old cid the glyph had."""
    embedder, dict_, gid = _new_embedder()
    embedder.add_to_subset(_SHARED_CP)
    embedder.build_to_unicode_c_map({1: gid})
    assert _bf_entry(gid, _SHARED_CP) in _to_unicode_text(dict_)


# ---------- subset code points: insertion order + accessor -----------------


def test_subset_code_points_preserve_insertion_order() -> None:
    embedder, _dict, _gid = _new_embedder()
    for cp in (0x5A, 0x41, _SHARED_CP, 0x42):
        embedder.add_to_subset(cp)
    assert list(embedder.get_subset_code_points()) == [0x5A, 0x41, _SHARED_CP, 0x42]


def test_subset_code_points_deduplicate_keeping_first_position() -> None:
    embedder, _dict, _gid = _new_embedder()
    for cp in (0x43, 0x41, 0x43, 0x42, 0x41):
        embedder.add_to_subset(cp)
    assert list(embedder.get_subset_code_points()) == [0x43, 0x41, 0x42]


def test_get_subset_code_points_exposes_added_code_points() -> None:
    embedder, _dict, _gid = _new_embedder()
    assert list(embedder.get_subset_code_points()) == []
    embedder.add_to_subset(0x48)
    embedder.add_to_subset(0x69)
    points = embedder.get_subset_code_points()
    assert 0x48 in points
    assert 0x69 in points
    assert len(points) == 2
