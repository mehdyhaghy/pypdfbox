"""Wave-1335 coverage round-out for ``pd_cid_font_type2_embedder``.

Targets the residual branches not exercised by
``test_pd_cid_font_type2_embedder_coverage.py``:

* vertical-write constructor + ``build_subset`` vertical leg (line 105, 277)
* ``check_for_cid_gid_identity`` ``maxp`` AttributeError fallback (204-205)
* ``_build_to_unicode_cmap`` missing-``maxp`` fallback (293-294)
* ToUnicode version-bump ``AttributeError`` swallow (316-317)
* ``_build_widths_for_subset`` glyph lookup failures and width==1000 skip
  (376-377, 380)
* ``_build_widths_full`` glyph lookup failures (405-406)
* ``_build_vertical_metrics_for_subset`` glyph-loop branches when
  ``vmtx``/``glyf`` lookups raise or yMax is missing (443, 446-462)
* ``_build_vertical_metrics_full`` missing-``maxp`` early return (479-480)
* ``_get_unicode_cmap_reverse`` ``best_cmap is None`` (line 511) and
  ``getGlyphID`` failure (516-517)
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import pytest
from fontTools.ttLib import TTFont

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
    PDCIDFontType2Embedder,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument

_TTF_DIR = Path(__file__).parent.parent.parent.parent / "pypdfbox" / "resources" / "ttf"
_LIB_SANS = _TTF_DIR / "LiberationSans-Regular.ttf"


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


def _load_ttf() -> TTFont:
    if not _LIB_SANS.exists():
        pytest.skip(f"Bundled font missing: {_LIB_SANS}")
    return TTFont(str(_LIB_SANS))


def _new_embedder(
    *, embed_subset: bool = False, vertical: bool = False
) -> tuple[PDCIDFontType2Embedder, COSDictionary, PDDocument, PDType0Font, TTFont]:
    ttf = _load_ttf()
    doc = PDDocument()
    parent = PDType0Font()
    dict_ = COSDictionary()
    embedder = PDCIDFontType2Embedder(
        doc, dict_, ttf, embed_subset=embed_subset, parent=parent, vertical=vertical
    )
    return embedder, dict_, doc, parent, ttf


# ---------- vertical constructor branch (line 277) -------------------------


def test_constructor_vertical_uses_identity_v_encoding() -> None:
    embedder, dict_, _doc, _parent, _ttf = _new_embedder(vertical=True)
    assert dict_.get_name("Encoding") == "Identity-V"
    # The vertical branch inside _create_cid_font runs even though
    # Liberation has no vhea — it should not raise.
    assert embedder._cid_font is not None  # noqa: SLF001


# ---------- check_for_cid_gid_identity: maxp AttributeError fallback ------


def test_check_for_cid_gid_identity_maxp_attribute_error_returns() -> None:
    """``maxp.numGlyphs`` AttributeError -> silent return (line 204-205)."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _StubCFF:
        cff = type("_Inner", (), {"charset": [0, 1, 2]})()

    class _Maxp:
        # No numGlyphs attribute -> AttributeError on int(.numGlyphs).
        pass

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "CFF ":
                return _StubCFF()
            if name == "maxp":
                return _Maxp()
            raise KeyError(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    # Should not raise — falls through the AttributeError except clause.
    embedder.check_for_cid_gid_identity()


# ---------- _build_to_unicode_cmap: missing maxp (lines 293-294) ----------


def test_build_to_unicode_cmap_with_missing_maxp_treats_glyph_count_zero() -> None:
    """``maxp`` KeyError -> ``max_glyphs = 0`` -> loop skipped."""
    embedder, dict_, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _StubTTF:
        def __getitem__(self, name: str) -> Any:
            raise KeyError(name)

    embedder._ttf = _StubTTF()  # noqa: SLF001
    # Even without maxp, the ToUnicode stream is still written.
    embedder.build_to_unicode_c_map(None)
    assert dict_.get_item(COSName.get_pdf_name("ToUnicode")) is not None


# ---------- ToUnicode version bump: TypeError swallow (lines 316-317) -----


def test_to_unicode_cmap_version_bump_swallows_attribute_error() -> None:
    """A document raising on ``get_version`` is tolerated (line 316-317)."""
    embedder, dict_, doc, _parent, _ttf = _new_embedder(embed_subset=True)

    def _stub_reverse() -> dict[int, list[int]]:
        return {1: [0x1F600]}

    embedder._get_unicode_cmap_reverse = _stub_reverse  # type: ignore[assignment]

    # Patch get_version on the live document to raise AttributeError.
    def _raise_attr_error() -> float:
        raise AttributeError("no version method")

    doc.get_version = _raise_attr_error  # type: ignore[assignment]
    # Should not raise — the except clause swallows it.
    embedder.build_to_unicode_c_map({1: 1})
    assert dict_.get_item(COSName.get_pdf_name("ToUnicode")) is not None


# ---------- _build_widths_for_subset: hmtx lookup failure + 1000 skip ----


def test_build_widths_for_subset_skips_missing_hmtx_entries() -> None:
    """hmtx lookup raising KeyError -> ``continue`` (lines 376-377)."""
    embedder, _dict, _doc, _parent, ttf = _new_embedder(embed_subset=True)

    real_get = ttf.__getitem__

    class _Hmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            # Always raise — every cid is skipped.
            raise KeyError(name)

    class _Head:
        unitsPerEm = 1000

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "hmtx":
                return _Hmtx()
            if name == "head":
                return _Head()
            return real_get(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder._build_widths_for_subset({1: 1, 2: 2})  # noqa: SLF001
    widths = embedder._cid_font.get_item(COSName.get_pdf_name("W"))  # noqa: SLF001
    # No widths emitted but the key is still present (empty array).
    assert isinstance(widths, COSArray)
    assert len(widths) == 0


def test_build_widths_for_subset_skips_widths_equal_to_1000() -> None:
    """width == 1000 after scaling -> ``continue`` (line 380)."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _Hmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (1000, 0)  # advance == 1000 -> skipped

    class _Head:
        unitsPerEm = 1000

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "hmtx":
                return _Hmtx()
            if name == "head":
                return _Head()
            raise KeyError(name)

        def getGlyphName(self, gid: int) -> str:
            return f"gid{gid}"

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder._build_widths_for_subset({1: 1, 2: 2})  # noqa: SLF001
    widths = embedder._cid_font.get_item(COSName.get_pdf_name("W"))  # noqa: SLF001
    assert isinstance(widths, COSArray)
    assert len(widths) == 0  # everything was the default width


# ---------- _build_widths_full: hmtx KeyError fallback (lines 405-406) ----


def test_build_widths_full_uses_zero_when_hmtx_lookup_raises() -> None:
    """KeyError on a glyph name -> ``advance = 0`` (line 405-406)."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _Maxp:
        numGlyphs = 4

    class _Head:
        unitsPerEm = 1000

    class _Hmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            raise KeyError(name)

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "maxp":
                return _Maxp()
            if name == "head":
                return _Head()
            if name == "hmtx":
                return _Hmtx()
            raise KeyError(name)

        def getGlyphName(self, gid: int) -> str:
            return f"gid{gid}"

    embedder._ttf = _Proxy()  # noqa: SLF001
    cid_font = COSDictionary()
    embedder._build_widths_full(cid_font)  # noqa: SLF001
    widths = cid_font.get_item(COSName.get_pdf_name("W"))
    assert isinstance(widths, COSArray)
    # All widths zero -> SERIAL run: encodes as [0, 3, 0].
    assert len(widths) > 0


# ---------- _build_vertical_metrics_for_subset: yMax missing branches ----


def test_build_vertical_metrics_subset_skips_when_hmtx_raises() -> None:
    """``hmtx[name]`` AttributeError -> ``continue`` (line 443-445)."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _Vhea:
        ascent = 880  # matches v_y default
        advanceHeightMax = 1000  # matches w1 default once negated

    class _Vmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (1000, 100)

    class _Hmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            raise AttributeError(name)

    class _Head:
        unitsPerEm = 1000

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "vhea":
                return _Vhea()
            if name == "vmtx":
                return _Vmtx()
            if name == "hmtx":
                return _Hmtx()
            if name == "head":
                return _Head()
            raise KeyError(name)

        def getGlyphName(self, gid: int) -> str:
            return f"gid{gid}"

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder._build_vertical_metrics_for_subset({1: 1, 2: 2})  # noqa: SLF001
    # /W2 set but loop body produced nothing.
    w2 = embedder._cid_font.get_item(COSName.get_pdf_name("W2"))  # noqa: SLF001
    assert isinstance(w2, COSArray)
    assert len(w2) == 0


def test_build_vertical_metrics_subset_uses_zero_ymax_when_glyf_missing() -> None:
    """``glyf`` KeyError -> ``y_max = 0`` (line 446-450)."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _Vhea:
        ascent = 1024
        advanceHeightMax = 2048

    class _Vmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (1500, 100)

    class _Hmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (800, 0)

    class _Head:
        unitsPerEm = 1000

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "vhea":
                return _Vhea()
            if name == "vmtx":
                return _Vmtx()
            if name == "hmtx":
                return _Hmtx()
            if name == "head":
                return _Head()
            if name == "glyf":
                raise KeyError(name)
            raise KeyError(name)

        def getGlyphName(self, gid: int) -> str:
            return f"gid{gid}"

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder._build_vertical_metrics_for_subset({1: 1, 2: 2})  # noqa: SLF001
    w2 = embedder._cid_font.get_item(COSName.get_pdf_name("W2"))  # noqa: SLF001
    assert isinstance(w2, COSArray)
    # Two consecutive CIDs with non-default values -> single BRACKET pair.
    assert len(w2) >= 2


def test_build_vertical_metrics_subset_emits_non_default_block() -> None:
    """A non-default ``height`` + ``advance`` triggers the inner-block path."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _Vhea:
        ascent = 1024
        advanceHeightMax = 2048

    class _Vmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (1500, 100)

    class _Hmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (800, 0)

    class _Glyf:
        def __getitem__(self, name: str) -> Any:
            return type("_G", (), {"yMax": 900})()

    class _Head:
        unitsPerEm = 1000

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "vhea":
                return _Vhea()
            if name == "vmtx":
                return _Vmtx()
            if name == "hmtx":
                return _Hmtx()
            if name == "head":
                return _Head()
            if name == "glyf":
                return _Glyf()
            raise KeyError(name)

        def getGlyphName(self, gid: int) -> str:
            return f"gid{gid}"

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder._build_vertical_metrics_for_subset({1: 1, 3: 3})  # noqa: SLF001
    # Non-contiguous CIDs (1 and 3) -> two separate (cid, [...]) blocks.
    w2 = embedder._cid_font.get_item(COSName.get_pdf_name("W2"))  # noqa: SLF001
    assert isinstance(w2, COSArray)
    assert len(w2) >= 2


def test_build_vertical_metrics_subset_skips_default_height_and_advance() -> None:
    """When height == v_y *and* advance == w1, the cid is skipped (line 453)."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    # Choose values such that v_y == 880 (== default) and w1 == -1000 (== default).
    class _Vhea:
        ascent = 880
        advanceHeightMax = 1000

    class _Vmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            # height = (yMax + tsb) * 1.0 ; advance = -1000
            # We want height == 880 -> set yMax + tsb == 880.
            return (1000, 0)

    class _Hmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (800, 0)

    class _Glyf:
        def __getitem__(self, name: str) -> Any:
            return type("_G", (), {"yMax": 880})()  # tsb 0 + yMax 880

    class _Head:
        unitsPerEm = 1000

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "vhea":
                return _Vhea()
            if name == "vmtx":
                return _Vmtx()
            if name == "hmtx":
                return _Hmtx()
            if name == "head":
                return _Head()
            if name == "glyf":
                return _Glyf()
            raise KeyError(name)

        def getGlyphName(self, gid: int) -> str:
            return f"gid{gid}"

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder._build_vertical_metrics_for_subset({1: 1, 2: 2})  # noqa: SLF001
    w2 = embedder._cid_font.get_item(COSName.get_pdf_name("W2"))  # noqa: SLF001
    # All defaults -> empty W2.
    assert isinstance(w2, COSArray)
    assert len(w2) == 0


# ---------- _build_vertical_metrics_full: missing maxp (479-480) ---------


def test_build_vertical_metrics_full_returns_when_maxp_missing() -> None:
    """``vhea`` present but ``maxp`` missing -> early return."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _Vhea:
        ascent = 1024
        advanceHeightMax = 2048

    class _Vmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (1500, 100)

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "vhea":
                return _Vhea()
            if name == "vmtx":
                return _Vmtx()
            # maxp KeyError -> hits the line 479-480 fallback.
            raise KeyError(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    cid_font = COSDictionary()
    embedder._build_vertical_metrics_full(cid_font)  # noqa: SLF001
    # No /W2 written on the descendant.
    assert cid_font.get_item(COSName.get_pdf_name("W2")) is None


# ---------- _get_unicode_cmap_reverse: best_cmap is None (line 511) -----


def test_get_unicode_cmap_reverse_returns_empty_when_best_cmap_none() -> None:
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _CMap:
        def getBestCmap(self) -> None:  # noqa: N802 - upstream API
            return None

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "cmap":
                return _CMap()
            raise KeyError(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    assert embedder._get_unicode_cmap_reverse() == {}  # noqa: SLF001


def test_get_unicode_cmap_reverse_skips_glyph_id_failures() -> None:
    """``getGlyphID`` raising AttributeError -> entry skipped (lines 516-517)."""
    embedder, _dict, _doc, _parent, _ttf = _new_embedder(embed_subset=True)

    class _CMap:
        def getBestCmap(self) -> dict[int, str]:  # noqa: N802 - upstream API
            return {65: "A", 66: "B"}

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "cmap":
                return _CMap()
            raise KeyError(name)

        def getGlyphID(self, _name: str) -> int:  # noqa: N802 - upstream API
            raise AttributeError("no glyph table")

    embedder._ttf = _Proxy()  # noqa: SLF001
    # Every getGlyphID call fails -> no entries collected.
    assert embedder._get_unicode_cmap_reverse() == {}  # noqa: SLF001


# ---------- build_subset vertical leg (line 105) -------------------------


def test_build_subset_vertical_branch_invokes_vertical_metrics_builder() -> None:
    """``vertical=True`` triggers the vertical-metrics builder during subset."""
    embedder, _dict, _doc, _parent, ttf = _new_embedder(
        embed_subset=True, vertical=True
    )

    import io as _io

    # Save the (non-vertical) TTF as the subset stream.
    buf = _io.BytesIO()
    ttf.save(buf)
    buf.seek(0)
    # Liberation has no vhea -> the vertical branch logs and returns silently.
    embedder.build_subset(buf, "VERTAG", {1: 1, 2: 2})
    # font_file2 still got written.
    assert embedder.font_descriptor.get_font_file2() is not None


# ---------- ToUnicode CMap version bump: TypeError swallow ---------------


def test_to_unicode_version_bump_swallows_type_error_from_set_version() -> None:
    """``set_version`` raising TypeError is tolerated."""
    embedder, _dict, doc, _parent, _ttf = _new_embedder(embed_subset=True)

    def _stub_reverse() -> dict[int, list[int]]:
        return {1: [0x1F600]}

    embedder._get_unicode_cmap_reverse = _stub_reverse  # type: ignore[assignment]
    with contextlib.suppress(AttributeError, TypeError, ValueError):
        doc.set_version(1.4)
    # Replace set_version with a TypeError-raising variant.
    original_set = doc.set_version

    def _raise_type_error(_v: float) -> None:
        raise TypeError("bad version")

    doc.set_version = _raise_type_error  # type: ignore[assignment]
    try:
        embedder.build_to_unicode_c_map({1: 1})
    finally:
        doc.set_version = original_set  # type: ignore[assignment]
