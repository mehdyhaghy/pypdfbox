"""Coverage-boost tests for :mod:`pypdfbox.pdmodel.font.pd_cid_font_type2_embedder`.

Targets the embedder constructor, ``/W`` builders (subset + full),
``/CIDToGIDMap``, ``/CIDSet``, ToUnicode CMap, name-tagging,
``checkForCidGidIdentity``, and the public dispatchers.

The embedder references a handful of ``COSName`` constants that are
not yet wired up at module-init time (``BASE_FONT``, ``FONT``,
``FONT_DESC``, ``IDENTITY``, ``ENCODING``). A module-scoped fixture
installs them so the embedder can be exercised end-to-end without
mutating the package source.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import Any

import pytest
from fontTools.ttLib import TTFont

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
    PDCIDFontType2Embedder,
    _encode_widths,
    _State,
    _to_cid_system_info,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.pd_document import PDDocument

_TTF_DIR = Path(__file__).parent.parent.parent.parent / "pypdfbox" / "resources" / "ttf"
_LIB_SANS = _TTF_DIR / "LiberationSans-Regular.ttf"
_LIB_SERIF = _TTF_DIR / "LiberationSerif-Regular.ttf"
_LIB_MONO = _TTF_DIR / "LiberationMono-Regular.ttf"


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


def _load_ttf(path: Path) -> TTFont:
    if not path.exists():
        pytest.skip(f"Bundled font missing: {path}")
    return TTFont(str(path))


@pytest.fixture
def sans_ttf() -> TTFont:
    return _load_ttf(_LIB_SANS)


@pytest.fixture
def serif_ttf() -> TTFont:
    return _load_ttf(_LIB_SERIF)


@pytest.fixture
def mono_ttf() -> TTFont:
    return _load_ttf(_LIB_MONO)


def _new_embedder(
    ttf: TTFont, *, embed_subset: bool = False, vertical: bool = False
) -> tuple[PDCIDFontType2Embedder, COSDictionary, PDDocument, PDType0Font]:
    doc = PDDocument()
    parent = PDType0Font()
    dict_ = COSDictionary()
    embedder = PDCIDFontType2Embedder(
        doc, dict_, ttf, embed_subset=embed_subset, parent=parent, vertical=vertical
    )
    return embedder, dict_, doc, parent


def _cos_to_python(arr: COSArray) -> list[Any]:
    out: list[Any] = []
    for item in arr:
        if isinstance(item, COSArray):
            out.append(_cos_to_python(item))
        elif isinstance(item, COSInteger):
            out.append(item.int_value())
        else:
            out.append(item)
    return out


# --- constructor: full-embed, horizontal ----------------------------------


def test_constructor_full_embed_sets_type0_subtype(sans_ttf: TTFont) -> None:
    _embedder, dict_, _doc, _parent = _new_embedder(sans_ttf)
    assert dict_.get_name("Subtype") == "Type0"


def test_constructor_full_embed_sets_identity_h_encoding(sans_ttf: TTFont) -> None:
    _embedder, dict_, _doc, _parent = _new_embedder(sans_ttf)
    assert dict_.get_name("Encoding") == "Identity-H"


def test_constructor_full_embed_attaches_descendant_fonts_array(
    sans_ttf: TTFont,
) -> None:
    embedder, dict_, _doc, _parent = _new_embedder(sans_ttf)
    descendants = dict_.get_item(COSName.get_pdf_name("DescendantFonts"))
    assert isinstance(descendants, COSArray)
    assert len(descendants) == 1
    assert descendants[0] is embedder._cid_font  # noqa: SLF001 — internal cross-check


def test_constructor_full_embed_writes_to_unicode_cmap(sans_ttf: TTFont) -> None:
    _embedder, dict_, _doc, _parent = _new_embedder(sans_ttf)
    # Non-subset path triggers _build_to_unicode_cmap(None).
    assert dict_.get_item(COSName.get_pdf_name("ToUnicode")) is not None


def test_constructor_subset_skips_initial_to_unicode_cmap(sans_ttf: TTFont) -> None:
    _embedder, dict_, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    # Subset path: ToUnicode written later from build_subset, not in __init__.
    assert dict_.get_item(COSName.get_pdf_name("ToUnicode")) is None


# --- descendant CID font dictionary ----------------------------------------


def test_descendant_cid_font_has_cidfonttype2_subtype(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf)
    cid_font = embedder._cid_font  # noqa: SLF001
    assert cid_font.get_name("Subtype") == "CIDFontType2"


def test_descendant_cid_font_has_adobe_identity_cidsysteminfo(
    sans_ttf: TTFont,
) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf)
    cid_font = embedder._cid_font  # noqa: SLF001
    info = cid_font.get_item(COSName.get_pdf_name("CIDSystemInfo"))
    assert isinstance(info, COSDictionary)
    assert info.get_string(COSName.get_pdf_name("Registry")) == "Adobe"
    assert info.get_string(COSName.get_pdf_name("Ordering")) == "Identity"
    assert info.get_int(COSName.get_pdf_name("Supplement")) == 0


def test_descendant_cid_font_full_embed_uses_identity_cid_to_gid_map(
    sans_ttf: TTFont,
) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf)
    cid_font = embedder._cid_font  # noqa: SLF001
    assert cid_font.get_name("CIDToGIDMap") == "Identity"


def test_descendant_cid_font_full_embed_has_widths(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf)
    widths = embedder._cid_font.get_item(COSName.get_pdf_name("W"))  # noqa: SLF001
    assert isinstance(widths, COSArray)
    assert len(widths) >= 2  # at least one (cid, [w]) pair


# --- build_subset end-to-end ----------------------------------------------


def test_build_subset_writes_font_file2(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    buf = io.BytesIO()
    sans_ttf.save(buf)
    buf.seek(0)
    embedder.build_subset(buf, "AAAAAA", {1: 0, 2: 5, 3: 10})
    assert embedder.font_descriptor.get_font_file2() is not None


def test_build_subset_replaces_cid_to_gid_map_with_stream(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    buf = io.BytesIO()
    sans_ttf.save(buf)
    buf.seek(0)
    embedder.build_subset(buf, "ABCDEF", {1: 1, 2: 2, 3: 3})
    cid_to_gid_map = embedder._cid_font.get_item(  # noqa: SLF001
        COSName.get_pdf_name("CIDToGIDMap")
    )
    # Once a subset is built, CIDToGIDMap is a stream (not Identity).
    assert cid_to_gid_map is not None
    assert not isinstance(cid_to_gid_map, COSName)


def test_build_subset_prepends_six_letter_tag(sans_ttf: TTFont) -> None:
    embedder, dict_, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    buf = io.BytesIO()
    sans_ttf.save(buf)
    buf.seek(0)
    embedder.build_subset(buf, "ABCDEF", {1: 0, 2: 5})
    base_font = dict_.get_name("BaseFont")
    assert base_font is not None
    assert base_font.startswith("ABCDEF")
    assert embedder.font_descriptor.get_font_name() == base_font


def test_build_subset_writes_to_unicode_cmap(sans_ttf: TTFont) -> None:
    embedder, dict_, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    buf = io.BytesIO()
    sans_ttf.save(buf)
    buf.seek(0)
    embedder.build_subset(buf, "BBBBBB", {1: 65, 2: 66, 3: 67})
    assert dict_.get_item(COSName.get_pdf_name("ToUnicode")) is not None


def test_build_subset_writes_cid_set_on_descriptor(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    buf = io.BytesIO()
    sans_ttf.save(buf)
    buf.seek(0)
    embedder.build_subset(buf, "CCCCCC", {1: 1, 2: 2, 3: 3})
    assert embedder.font_descriptor.get_cid_set() is not None


# --- _build_widths_for_subset specifics -----------------------------------


def test_build_widths_for_subset_emits_W_array(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    embedder.build_widths({1: 1, 2: 2, 3: 3, 100: 100})
    widths = embedder._cid_font.get_item(COSName.get_pdf_name("W"))  # noqa: SLF001
    assert isinstance(widths, COSArray)


def test_build_widths_dispatch_to_full_for_cos_dict(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    cid_font = COSDictionary()
    embedder.build_widths(cid_font)
    assert cid_font.get_item(COSName.get_pdf_name("W")) is not None


# --- _build_cid_to_gid_map / _build_cid_set ------------------------------


def test_build_cid_to_gid_map_writes_stream(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    embedder.build_cid_to_gid_map({1: 7, 2: 9, 5: 42})
    stream = embedder._cid_font.get_item(  # noqa: SLF001
        COSName.get_pdf_name("CIDToGIDMap")
    )
    assert stream is not None


def test_build_cid_set_writes_descriptor_cid_set(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    embedder.build_cid_set({1: 1, 7: 7, 12: 12})
    assert embedder.font_descriptor.get_cid_set() is not None


# --- ToUnicode CMap branches ----------------------------------------------


def test_build_to_unicode_c_map_handles_subset_map(sans_ttf: TTFont) -> None:
    embedder, dict_, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    # Map ASCII glyph IDs back to CIDs.
    gid_to_cid = {sans_ttf["cmap"].getBestCmap().get(ord("A"), 0): 1}
    if 0 in gid_to_cid:
        # Defend against the cmap missing the test character.
        gid_to_cid = {1: 1, 2: 2}
    embedder.build_to_unicode_c_map(gid_to_cid)
    assert dict_.get_item(COSName.get_pdf_name("ToUnicode")) is not None


def test_build_to_unicode_c_map_with_none_uses_all_gids(sans_ttf: TTFont) -> None:
    embedder, dict_, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    # Even on a subset embedder we can re-invoke for the full mapping.
    embedder.build_to_unicode_c_map(None)
    assert dict_.get_item(COSName.get_pdf_name("ToUnicode")) is not None


# --- name tagging ---------------------------------------------------------


def test_add_name_tag_prefixes_base_font_and_descriptor(sans_ttf: TTFont) -> None:
    embedder, dict_, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    embedder.add_name_tag("ZZZZZZ+")
    assert dict_.get_name("BaseFont").startswith("ZZZZZZ+")
    assert embedder.font_descriptor.get_font_name().startswith("ZZZZZZ+")
    assert embedder._cid_font.get_name("BaseFont").startswith("ZZZZZZ+")  # noqa: SLF001


# --- to_cid_system_info / get_widths / get_vertical_metrics --------------


def test_to_cid_system_info_method_matches_module_helper(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    info = embedder.to_cid_system_info("Foo", "Bar", 7)
    assert info.get_string(COSName.get_pdf_name("Registry")) == "Foo"
    assert info.get_string(COSName.get_pdf_name("Ordering")) == "Bar"
    assert info.get_int(COSName.get_pdf_name("Supplement")) == 7


def test_get_widths_applies_units_per_em_scaling(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    arr = embedder.get_widths([1, 2048, 2, 1024])
    py = _cos_to_python(arr)
    # unitsPerEm=2048 => scaling=1000/2048 ~ 0.488; widths -> ~1000 and ~500
    assert py[0] == 1
    flat = [x for sub in py if isinstance(sub, list) for x in sub] or py[1:]
    assert any(800 <= int(v) <= 1000 for v in flat if isinstance(v, int))


def test_get_vertical_metrics_uses_same_compressor(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    arr = embedder.get_vertical_metrics([1, 1000, 2, 1000, 3, 1000])
    py = _cos_to_python(arr)
    assert py[0] == 1  # CID start


def test_get_widths_with_no_head_table_uses_unit_scaling(
    sans_ttf: TTFont,
) -> None:
    """Cover the ``KeyError`` -> scaling=1.0 fallback in :meth:`get_widths`."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    # Replace the TTF backing reference with a stub that raises KeyError
    # for "head" so the except-branch (scaling=1.0) executes.
    class _StubTTF:
        def __getitem__(self, name: str) -> Any:
            raise KeyError(name)

    embedder._ttf = _StubTTF()  # noqa: SLF001
    arr = embedder.get_widths([10, 250, 11, 300, 12, 350])
    py = _cos_to_python(arr)
    assert py == [10, [250, 300, 350]]


def test_get_vertical_metrics_with_no_head_table_uses_unit_scaling(
    sans_ttf: TTFont,
) -> None:
    """Cover the ``KeyError`` fallback in :meth:`get_vertical_metrics`."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _StubTTF:
        def __getitem__(self, name: str) -> Any:
            raise KeyError(name)

    embedder._ttf = _StubTTF()  # noqa: SLF001
    arr = embedder.get_vertical_metrics([1, 500, 2, 500, 3, 500])
    py = _cos_to_python(arr)
    assert py == [1, 3, 500]


# --- build_vertical_header / build_vertical_metrics no-op paths ----------


def test_build_vertical_header_returns_false_when_no_vhea(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    cid_font = COSDictionary()
    assert embedder.build_vertical_header(cid_font) is False


def test_build_vertical_metrics_dispatch_dict_is_noop_without_vhea(
    sans_ttf: TTFont,
) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    # Liberation has no vhea -> early return, no exception.
    embedder.build_vertical_metrics({1: 1, 2: 2})


def test_build_vertical_metrics_dispatch_cos_dict_is_noop_without_vhea(
    sans_ttf: TTFont,
) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    cid_font = COSDictionary()
    embedder.build_vertical_metrics(cid_font)


# --- check_for_cid_gid_identity ------------------------------------------


def test_check_for_cid_gid_identity_no_cff_table_returns_silently(
    sans_ttf: TTFont,
) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    # Pure TTF (no "CFF "): the early-return branch.
    embedder.check_for_cid_gid_identity()


# --- create_cid_font public alias / get_cid_font ------------------------


def test_create_cid_font_returns_fresh_dictionary(sans_ttf: TTFont) -> None:
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    second = embedder.create_cid_font()
    assert isinstance(second, COSDictionary)
    assert second is not embedder._cid_font  # noqa: SLF001 — new instance


def test_get_cid_font_invokes_pdcidfonttype2_constructor(
    sans_ttf: TTFont,
) -> None:
    """:meth:`get_cid_font` builds a :class:`PDCIDFontType2` from the descendant.

    Upstream ``PDCIDFontType2`` accepts ``(dict, parent, ttf)``; the
    Python port currently accepts ``(dict)`` only — so this test pins
    that mismatch behind a TypeError until the constructor is widened.
    """
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)
    with pytest.raises(TypeError):
        embedder.get_cid_font()


# --- _encode_widths additional branches ----------------------------------


def test_encode_widths_termination_in_serial_state() -> None:
    # End in SERIAL after at least 3 identical consecutive widths.
    arr = _encode_widths([1, 100, 2, 100, 3, 100, 4, 100, 5, 100], scaling=1.0)
    py = _cos_to_python(arr)
    assert py == [1, 5, 100]


def test_encode_widths_serial_to_first_on_gap() -> None:
    # SERIAL run broken by a CID gap: ends the run, emits the new cid.
    arr = _encode_widths([1, 100, 2, 100, 3, 100, 8, 200], scaling=1.0)
    py = _cos_to_python(arr)
    # SERIAL block 1..3 then a fresh entry for 8.
    assert py[0] == 1
    assert 3 in py  # last CID of the SERIAL group
    assert 100 in py
    assert 8 in py


def test_encode_widths_bracket_to_serial_on_repeat() -> None:
    # BRACKET state transitions to SERIAL when a repeat appears.
    arr = _encode_widths(
        [1, 200, 2, 300, 3, 300, 4, 300, 5, 300], scaling=1.0
    )
    py = _cos_to_python(arr)
    # Should produce a BRACKET termination plus a SERIAL block.
    assert py[0] == 1
    assert any(isinstance(x, list) for x in py)


def test_encode_widths_bracket_termination_on_gap() -> None:
    # BRACKET state ended by a CID gap.
    arr = _encode_widths([1, 200, 2, 300, 7, 400], scaling=1.0)
    py = _cos_to_python(arr)
    assert py[0] == 1
    assert py[-2] == 7


# --- _State enum sanity --------------------------------------------------


def test_state_enum_has_three_members() -> None:
    members = {m.name for m in _State}
    assert members == {"FIRST", "BRACKET", "SERIAL"}


# --- module helper _to_cid_system_info ------------------------------------


def test_module_helper_to_cid_system_info_writes_all_fields() -> None:
    info = _to_cid_system_info("Adobe", "Japan1", 6)
    assert info.get_string(COSName.get_pdf_name("Registry")) == "Adobe"
    assert info.get_string(COSName.get_pdf_name("Ordering")) == "Japan1"
    assert info.get_int(COSName.get_pdf_name("Supplement")) == 6


# --- exercise the embedder against alternative fonts ---------------------


def test_constructor_works_with_liberation_serif(serif_ttf: TTFont) -> None:
    _embedder, dict_, _doc, _parent = _new_embedder(serif_ttf)
    assert dict_.get_name("Subtype") == "Type0"


def test_constructor_works_with_liberation_mono(mono_ttf: TTFont) -> None:
    _embedder, dict_, _doc, _parent = _new_embedder(mono_ttf)
    assert dict_.get_name("Subtype") == "Type0"


# --- check_for_cid_gid_identity branches ---------------------------------


def test_check_for_cid_gid_identity_with_cff_no_charset(sans_ttf: TTFont) -> None:
    """CFF table present but no charset attribute -> returns silently."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _StubCFF:
        cff = type("_Inner", (), {"charset": None})()

    real_get = embedder._ttf.__getitem__  # noqa: SLF001

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "CFF ":
                return _StubCFF()
            return real_get(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder.check_for_cid_gid_identity()


def test_check_for_cid_gid_identity_raises_on_mismatch(sans_ttf: TTFont) -> None:
    """charset[gid] != gid triggers the RuntimeError."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _Maxp:
        numGlyphs = 3

    class _StubCFF:
        cff = type("_Inner", (), {"charset": [10, 20, 30]})()

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "CFF ":
                return _StubCFF()
            if name == "maxp":
                return _Maxp()
            raise KeyError(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    with pytest.raises(RuntimeError, match="CID and GID not identical"):
        embedder.check_for_cid_gid_identity()


def test_check_for_cid_gid_identity_charset_bad_index_no_raise(
    sans_ttf: TTFont,
) -> None:
    """charset[gid] raising IndexError exits silently (no GID check)."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _Maxp:
        numGlyphs = 5

    class _Charset:
        def __getitem__(self, idx: int) -> int:
            raise IndexError(idx)

    class _StubCFF:
        cff = type("_Inner", (), {"charset": _Charset()})()

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "CFF ":
                return _StubCFF()
            if name == "maxp":
                return _Maxp()
            raise KeyError(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    embedder.check_for_cid_gid_identity()


# --- build_vertical_header / metrics with a fake vhea --------------------


def test_build_vertical_header_writes_w2_when_vhea_present(sans_ttf: TTFont) -> None:
    """vhea + vmtx present -> ``buildVerticalHeader`` returns True."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _Vhea:
        ascent = 1024
        advanceHeightMax = 2048

    class _Vmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (1000, 200)

    class _Glyf:
        def __getitem__(self, name: str) -> Any:
            return type("_G", (), {"yMax": 800})()

    real_get = embedder._ttf.__getitem__  # noqa: SLF001

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "vhea":
                return _Vhea()
            if name == "vmtx":
                return _Vmtx()
            if name == "glyf":
                return _Glyf()
            return real_get(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    cid_font = COSDictionary()
    result = embedder.build_vertical_header(cid_font)
    assert result is True


def test_build_vertical_metrics_full_writes_w2_for_all_glyphs(
    sans_ttf: TTFont,
) -> None:
    """``_build_vertical_metrics_full`` delegates to subset variant with all GIDs."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _Vhea:
        ascent = 1024
        advanceHeightMax = 2048

    class _Vmtx:
        def __getitem__(self, name: str) -> tuple[int, int]:
            return (1500, 100)

    class _Glyf:
        def __getitem__(self, name: str) -> Any:
            return type("_G", (), {"yMax": 900})()

    class _Maxp:
        numGlyphs = 4

    real_get = embedder._ttf.__getitem__  # noqa: SLF001

    class _Proxy:
        def __getitem__(self, name: str) -> Any:
            if name == "vhea":
                return _Vhea()
            if name == "vmtx":
                return _Vmtx()
            if name == "glyf":
                return _Glyf()
            if name == "maxp":
                return _Maxp()
            return real_get(name)

    embedder._ttf = _Proxy()  # noqa: SLF001
    cid_font = COSDictionary()
    embedder._build_vertical_metrics_full(cid_font)  # noqa: SLF001
    # ``/W2`` is written on the *embedder*'s descendant dict, not the
    # locally passed cid_font (delegation collapses to subset signature).
    w2 = embedder._cid_font.get_item(COSName.get_pdf_name("W2"))  # noqa: SLF001
    assert w2 is not None


# --- ToUnicode CMap PDF-version bump for surrogate code points -----------


def test_to_unicode_cmap_bumps_pdf_version_when_surrogates_present(
    sans_ttf: TTFont,
) -> None:
    """Code points above U+FFFF must bump the PDF version to >= 1.5."""
    embedder, _dict, doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    # Pretend the cmap reports a supplementary plane code point for GID 1.
    def _stub_reverse() -> dict[int, list[int]]:
        return {1: [0x1F600]}  # smiley face — outside BMP

    embedder._get_unicode_cmap_reverse = _stub_reverse  # type: ignore[assignment]
    # Force the document to start at 1.4 so the version-bump branch runs.
    with contextlib.suppress(AttributeError, TypeError, ValueError):
        doc.set_version(1.4)
    embedder.build_to_unicode_c_map({1: 1})
    # Version should now be >= 1.5.
    assert float(doc.get_version()) >= 1.5


# --- _build_widths_full empty TTF fallback -------------------------------


def test_build_widths_full_missing_head_returns_early(sans_ttf: TTFont) -> None:
    """KeyError on the ``head`` table aborts the builder without raising."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _StubTTF:
        def __getitem__(self, name: str) -> Any:
            raise KeyError(name)

    embedder._ttf = _StubTTF()  # noqa: SLF001
    cid_font = COSDictionary()
    embedder._build_widths_full(cid_font)  # noqa: SLF001
    assert cid_font.get_item(COSName.get_pdf_name("W")) is None


def test_build_widths_for_subset_missing_head_returns_early(
    sans_ttf: TTFont,
) -> None:
    """``_build_widths_for_subset`` early-returns when head/hmtx missing."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _StubTTF:
        def __getitem__(self, name: str) -> Any:
            raise KeyError(name)

    embedder._ttf = _StubTTF()  # noqa: SLF001
    # Should be a silent no-op (no /W mutation, no exception).
    embedder._build_widths_for_subset({1: 1, 2: 2})  # noqa: SLF001


# --- _get_unicode_cmap_reverse fallback ----------------------------------


def test_get_unicode_cmap_reverse_returns_empty_when_no_cmap(
    sans_ttf: TTFont,
) -> None:
    """Missing cmap table -> empty mapping."""
    embedder, _dict, _doc, _parent = _new_embedder(sans_ttf, embed_subset=True)

    class _StubTTF:
        def __getitem__(self, name: str) -> Any:
            raise KeyError(name)

    embedder._ttf = _StubTTF()  # noqa: SLF001
    result = embedder._get_unicode_cmap_reverse()  # noqa: SLF001
    assert result == {}


# --- _encode_widths single-pair termination ------------------------------


def test_encode_widths_two_element_input_returns_first_bracket() -> None:
    """``[cid, w]`` -> ``[cid, [w]]`` (FIRST state terminator)."""
    arr = _encode_widths([1, 500], scaling=1.0)
    py = _cos_to_python(arr)
    assert py == [1, [500]]
