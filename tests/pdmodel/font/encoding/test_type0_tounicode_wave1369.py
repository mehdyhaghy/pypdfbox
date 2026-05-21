"""PDType0Font ToUnicode CMap construction matrix.

Wave 1369 round-out — exercises the /Encoding entry handling on
PDType0Font: Identity-H, Identity-V, and predefined Adobe CMaps. Also
covers the predefined-UCS2 fallback via :meth:`get_cmap_ucs2`.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.fontbox.cmap.cmap_manager import CMapManager
from pypdfbox.pdmodel.font.pd_type0_font import (
    IDENTITY_H,
    IDENTITY_V,
    PDType0Font,
)


@pytest.fixture(autouse=True)
def _clear_cmap_cache() -> None:
    """Avoid cross-test cache leakage when these tests check cache behavior."""
    CMapManager.clear_cache()
    yield
    CMapManager.clear_cache()


def _build_type0_dict(
    encoding_name: str,
    registry: str = "Adobe",
    ordering: str = "Identity",
    supplement: int = 0,
    descendant_sub_type: str = "CIDFontType2",
) -> COSDictionary:
    """Assemble a minimal Type 0 font dictionary for unit testing."""
    descendant = COSDictionary()
    descendant.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    descendant.set_item(
        COSName.SUBTYPE, COSName.get_pdf_name(descendant_sub_type)
    )
    descendant.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("X"))

    info = COSDictionary()
    info.set_item(COSName.get_pdf_name("Registry"), COSName.get_pdf_name(registry))
    info.set_item(COSName.get_pdf_name("Ordering"), COSName.get_pdf_name(ordering))
    from pypdfbox.cos import COSInteger

    info.set_item(
        COSName.get_pdf_name("Supplement"), COSInteger.get(supplement)
    )
    descendant.set_item(COSName.get_pdf_name("CIDSystemInfo"), info)

    arr = COSArray()
    arr.add(descendant)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type0"))
    font_dict.set_item(COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("X"))
    font_dict.set_item(COSName.get_pdf_name("DescendantFonts"), arr)
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"), COSName.get_pdf_name(encoding_name)
    )
    return font_dict


def test_identity_h_cmap_loaded_from_encoding_name() -> None:
    font = PDType0Font(_build_type0_dict(IDENTITY_H))
    cmap = font.get_cmap()
    assert cmap is not None
    assert cmap.get_name() == "Identity-H"
    assert cmap.get_w_mode() == 0


def test_identity_v_cmap_loaded_from_encoding_name() -> None:
    font = PDType0Font(_build_type0_dict(IDENTITY_V))
    cmap = font.get_cmap()
    assert cmap is not None
    assert cmap.get_name() == "Identity-V"
    assert cmap.get_w_mode() == 1


def test_identity_constants_match_pdf_spec_names() -> None:
    # PDF 32000-1 §9.7.5.2 Table 118 names — surfaced as module-level
    # constants so callers don't stringly-type them.
    assert IDENTITY_H == "Identity-H"
    assert IDENTITY_V == "Identity-V"


@pytest.mark.parametrize(
    "ordering,expected_ucs2_name",
    [
        ("GB1", "Adobe-GB1-UCS2"),
        ("CNS1", "Adobe-CNS1-UCS2"),
        ("Japan1", "Adobe-Japan1-UCS2"),
        ("Korea1", "Adobe-Korea1-UCS2"),
    ],
)
def test_cmap_ucs2_is_loaded_for_each_cjk_collection(
    ordering: str, expected_ucs2_name: str
) -> None:
    font = PDType0Font(
        _build_type0_dict(IDENTITY_H, registry="Adobe", ordering=ordering)
    )
    ucs2 = font.get_cmap_ucs2()
    assert ucs2 is not None
    # The UCS2 CMap's own name matches the registry-keyed lookup. (The
    # CMap's internal /CIDSystemInfo /Ordering uses the suffixed form
    # "Adobe_<Collection>_UCS2" — distinct from the descendant's ordering.)
    assert ucs2.get_name() == expected_ucs2_name


def test_cmap_ucs2_is_none_for_identity_collection() -> None:
    # Adobe-Identity is the catch-all for opaque CIDs — no UCS2 fallback.
    font = PDType0Font(
        _build_type0_dict(IDENTITY_H, registry="Adobe", ordering="Identity")
    )
    assert font.get_cmap_ucs2() is None


def test_cmap_ucs2_is_none_for_non_adobe_registry() -> None:
    # Custom registries (rare but possible) have no Adobe-supplied UCS2.
    font = PDType0Font(
        _build_type0_dict(IDENTITY_H, registry="Custom", ordering="Japan1")
    )
    assert font.get_cmap_ucs2() is None


def test_cmap_ucs2_caches_result() -> None:
    font = PDType0Font(
        _build_type0_dict(IDENTITY_H, registry="Adobe", ordering="Japan1")
    )
    a = font.get_cmap_ucs2()
    b = font.get_cmap_ucs2()
    # Same instance — cached on first call.
    assert a is b


def test_get_c_map_ucs2_alias() -> None:
    # Upstream has a ``getCMapUCS2`` getter; the literal camelCase → snake
    # alias is ``get_c_map_ucs2``. Both forms should resolve identically.
    font = PDType0Font(
        _build_type0_dict(IDENTITY_H, registry="Adobe", ordering="GB1")
    )
    assert font.get_c_map_ucs2() is font.get_cmap_ucs2()


def test_get_c_map_alias() -> None:
    font = PDType0Font(_build_type0_dict(IDENTITY_H))
    assert font.get_c_map() is font.get_cmap()


def test_read_encoding_primes_caches() -> None:
    font = PDType0Font(
        _build_type0_dict(IDENTITY_H, registry="Adobe", ordering="Japan1")
    )
    # Before: lazy attributes are unset (False).
    assert font._cmap_loaded is False
    assert font._cmap_ucs2_loaded is False
    font.read_encoding()
    # After: both lazy caches are primed.
    assert font._cmap_loaded is True
    assert font._cmap_ucs2_loaded is True


def test_fetch_c_map_ucs2_primes_only_ucs2_cache() -> None:
    font = PDType0Font(
        _build_type0_dict(IDENTITY_H, registry="Adobe", ordering="GB1")
    )
    font.fetch_c_map_ucs2()
    # UCS2 cache is primed.
    assert font._cmap_ucs2_loaded is True
