"""Live PDFBox differential parity for the caching + type-leniency edges of
:class:`PDFontDescriptor` that ``test_font_desc_flags_oracle.py`` (wave 1468)
does not cover.

Three behaviours pinned here were *divergences* against Apache PDFBox 3.0.7
before wave 1486 and are now fixed in production:

1. ``get_cap_height`` / ``get_x_height`` lazily cache the ``abs()`` of the dict
   value on first read into an instance field (sentinel
   ``Float.NEGATIVE_INFINITY``); the setter overwrites that cache with the
   *raw* value. So ``set_cap_height(-100)`` after a prior read returns ``-100``
   (the abs() workaround for PDFBOX-429 only fires on the cache-miss dict read).
2. ``get_flags`` lazily caches the dict int on first read (sentinel ``-1``);
   the setter overwrites it. A *direct* mutation of ``/Flags`` on the underlying
   dict after the first read is NOT observed (stale cache) — callers must use
   ``set_flags``.
3. ``get_font_bounding_box`` returns a (zero-padded) :class:`PDRectangle` for a
   malformed short ``/FontBBox`` array, mirroring upstream's
   ``new PDRectangle(rect)`` → ``Arrays.copyOf(toFloatArray(), 4)``. Previously
   pypdfbox dropped a <4-entry array (returned ``None``).

Plus the (already-at-parity) type-leniency surface: ``/FontFamily`` /
``/CharSet`` resolve via ``getString`` (COSName → null); ``/FontStretch`` /
``/FontName`` via ``getNameAsString`` (COSString tolerated).

Oracle: ``oracle/probes/FontDescCacheLenientProbe.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from tests.oracle.harness import requires_oracle, run_probe_text

_CAP_HEIGHT = COSName.get_pdf_name("CapHeight")
_X_HEIGHT = COSName.get_pdf_name("XHeight")
_FLAGS = COSName.get_pdf_name("Flags")
_FONT_BBOX = COSName.get_pdf_name("FontBBox")
_FONT_FAMILY = COSName.get_pdf_name("FontFamily")
_FONT_STRETCH = COSName.get_pdf_name("FontStretch")
_CHAR_SET = COSName.get_pdf_name("CharSet")
_FONT_NAME = COSName.get_pdf_name("FontName")


# ---------------------------------------------------------------------------
# Plain (non-oracle) pins — run everywhere, encode the oracle-confirmed values.
# ---------------------------------------------------------------------------


def test_cap_height_setter_caches_raw_negative_after_read() -> None:
    """First read caches abs(662)=662; setter caches raw -100; re-read = -100."""
    d = COSDictionary()
    d.set_float(_CAP_HEIGHT, 662.0)
    fd = PDFontDescriptor(d)
    assert fd.get_cap_height() == 662.0
    fd.set_cap_height(-100.0)
    assert fd.get_cap_height() == -100.0  # cached raw, NOT abs()
    assert d.get_float(_CAP_HEIGHT, 0.0) == -100.0


def test_x_height_setter_caches_raw_negative_after_read() -> None:
    d = COSDictionary()
    d.set_float(_X_HEIGHT, 450.0)
    fd = PDFontDescriptor(d)
    assert fd.get_x_height() == 450.0
    fd.set_x_height(-50.0)
    assert fd.get_x_height() == -50.0
    assert d.get_float(_X_HEIGHT, 0.0) == -50.0


def test_cap_height_negative_in_dict_returns_abs_on_first_read() -> None:
    """PDFBOX-429 abs() workaround still fires on the cache-miss dict read."""
    d = COSDictionary()
    d.set_float(_CAP_HEIGHT, -662.0)
    assert PDFontDescriptor(d).get_cap_height() == 662.0


def test_x_height_negative_in_dict_returns_abs_on_first_read() -> None:
    d = COSDictionary()
    d.set_float(_X_HEIGHT, -450.0)
    assert PDFontDescriptor(d).get_x_height() == 450.0


def test_flags_cache_is_stale_after_direct_dict_mutation() -> None:
    """get_flags caches on first read; a later direct dict write is not seen."""
    d = COSDictionary()
    d.set_int(_FLAGS, 4)  # Symbolic
    fd = PDFontDescriptor(d)
    assert fd.get_flags() == 4
    d.set_int(_FLAGS, 64)  # direct mutation -> NOT observed
    assert fd.get_flags() == 4  # stale cache
    assert fd.is_symbolic() is True
    assert fd.is_italic() is False


def test_set_flags_updates_cache() -> None:
    d = COSDictionary()
    d.set_int(_FLAGS, 4)
    fd = PDFontDescriptor(d)
    assert fd.get_flags() == 4
    fd.set_flags(64)
    assert fd.get_flags() == 64
    assert fd.is_symbolic() is False
    assert fd.is_italic() is True


def test_font_bounding_box_short_array_is_zero_padded() -> None:
    """A 3-entry /FontBBox is zero-padded to 4 (upstream Arrays.copyOf)."""
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSInteger.get(-200))
    arr.add(COSInteger.get(1000))
    d = COSDictionary()
    d.set_item(_FONT_BBOX, arr)
    r = PDFontDescriptor(d).get_font_bounding_box()
    assert r is not None
    # toFloatArray padded to [0,-200,1000,0]; PDRectangle normalises corners.
    assert r.get_lower_left_x() == 0.0
    assert r.get_lower_left_y() == -200.0
    assert r.get_upper_right_x() == 1000.0
    assert r.get_upper_right_y() == 0.0


def test_font_bounding_box_missing_is_none() -> None:
    assert PDFontDescriptor(COSDictionary()).get_font_bounding_box() is None


def test_flags_as_string_decodes_to_zero() -> None:
    """A /Flags stored as a COSString is not a COSNumber -> getInt default 0."""
    d = COSDictionary()
    d.set_item(_FLAGS, COSString("64"))
    fd = PDFontDescriptor(d)
    assert fd.get_flags() == 0
    assert fd.is_italic() is False


def test_cap_height_as_integer() -> None:
    d = COSDictionary()
    d.set_item(_CAP_HEIGHT, COSInteger.get(662))
    assert PDFontDescriptor(d).get_cap_height() == 662.0


def test_font_family_as_name_returns_none() -> None:
    """/FontFamily via getString — a COSName value is NOT coerced (null)."""
    d = COSDictionary()
    d.set_item(_FONT_FAMILY, COSName.get_pdf_name("Times"))
    assert PDFontDescriptor(d).get_font_family() is None


def test_font_family_as_string_returns_text() -> None:
    d = COSDictionary()
    d.set_item(_FONT_FAMILY, COSString("Times"))
    assert PDFontDescriptor(d).get_font_family() == "Times"


def test_font_stretch_as_string_is_tolerated() -> None:
    """/FontStretch via getNameAsString — a COSString value IS resolved."""
    d = COSDictionary()
    d.set_item(_FONT_STRETCH, COSString("Condensed"))
    assert PDFontDescriptor(d).get_font_stretch() == "Condensed"


def test_char_set_as_name_returns_none() -> None:
    d = COSDictionary()
    d.set_item(_CHAR_SET, COSName.get_pdf_name("StandardEncoding"))
    assert PDFontDescriptor(d).get_char_set() is None


def test_char_set_as_string_returns_text() -> None:
    d = COSDictionary()
    d.set_item(_CHAR_SET, COSString("/a/b/c"))
    assert PDFontDescriptor(d).get_char_set() == "/a/b/c"


def test_font_name_as_string_is_tolerated() -> None:
    """/FontName via getNameAsString — a COSString value IS resolved."""
    d = COSDictionary()
    d.set_item(_FONT_NAME, COSString("ABCDEF+Helvetica"))
    assert PDFontDescriptor(d).get_font_name() == "ABCDEF+Helvetica"


def test_set_font_bounding_box_null_removes_key() -> None:
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    fd = PDFontDescriptor()
    fd.set_font_bounding_box(PDRectangle(0, -200, 1000, 900))
    assert _FONT_BBOX in fd.get_cos_object()
    fd.set_font_bounding_box(None)
    assert _FONT_BBOX not in fd.get_cos_object()


# ---------------------------------------------------------------------------
# Optional differential — only when the live oracle JAR is present.
# ---------------------------------------------------------------------------


_ORACLE_CASES = [
    "capheight_setraw_after_read",
    "xheight_setraw_after_read",
    "capheight_negative_first_read",
    "flags_cache_after_directmutate",
    "flags_as_string",
    "capheight_as_integer",
    "fontfamily_as_name",
    "fontfamily_as_string",
    "fontstretch_as_string",
    "charset_as_name",
    "charset_as_string",
    "fontname_as_string",
    "bbox_three_entries",
    "bbox_missing",
    "setbbox_null_removes",
]


def _fmt(v: float) -> str:
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _py_block(case: str) -> str:
    if case == "capheight_setraw_after_read":
        d = COSDictionary()
        d.set_float(_CAP_HEIGHT, 662.0)
        fd = PDFontDescriptor(d)
        line1 = "read1\t" + _fmt(fd.get_cap_height())
        fd.set_cap_height(-100.0)
        line2 = "read2\t" + _fmt(fd.get_cap_height())
        line3 = "dict\t" + _fmt(d.get_float(_CAP_HEIGHT, 0.0))
        return f"{line1}\n{line2}\n{line3}\n"
    if case == "xheight_setraw_after_read":
        d = COSDictionary()
        d.set_float(_X_HEIGHT, 450.0)
        fd = PDFontDescriptor(d)
        line1 = "read1\t" + _fmt(fd.get_x_height())
        fd.set_x_height(-50.0)
        line2 = "read2\t" + _fmt(fd.get_x_height())
        line3 = "dict\t" + _fmt(d.get_float(_X_HEIGHT, 0.0))
        return f"{line1}\n{line2}\n{line3}\n"
    if case == "capheight_negative_first_read":
        d = COSDictionary()
        d.set_float(_CAP_HEIGHT, -662.0)
        return "read\t" + _fmt(PDFontDescriptor(d).get_cap_height()) + "\n"
    if case == "flags_cache_after_directmutate":
        d = COSDictionary()
        d.set_int(_FLAGS, 4)
        fd = PDFontDescriptor(d)
        l1 = "read1\t" + str(fd.get_flags())
        d.set_int(_FLAGS, 64)
        l2 = "read2\t" + str(fd.get_flags())
        l3 = "symbolic\t" + str(int(fd.is_symbolic()))
        l4 = "italic\t" + str(int(fd.is_italic()))
        return f"{l1}\n{l2}\n{l3}\n{l4}\n"
    if case == "flags_as_string":
        d = COSDictionary()
        d.set_item(_FLAGS, COSString("64"))
        fd = PDFontDescriptor(d)
        return f"flags\t{fd.get_flags()}\nitalic\t{int(fd.is_italic())}\n"
    if case == "capheight_as_integer":
        d = COSDictionary()
        d.set_item(_CAP_HEIGHT, COSInteger.get(662))
        return "capHeight\t" + _fmt(PDFontDescriptor(d).get_cap_height()) + "\n"
    if case == "fontfamily_as_name":
        d = COSDictionary()
        d.set_item(_FONT_FAMILY, COSName.get_pdf_name("Times"))
        v = PDFontDescriptor(d).get_font_family()
        return "fontFamily\t" + ("<null>" if v is None else v) + "\n"
    if case == "fontfamily_as_string":
        d = COSDictionary()
        d.set_item(_FONT_FAMILY, COSString("Times"))
        v = PDFontDescriptor(d).get_font_family()
        return "fontFamily\t" + ("<null>" if v is None else v) + "\n"
    if case == "fontstretch_as_string":
        d = COSDictionary()
        d.set_item(_FONT_STRETCH, COSString("Condensed"))
        v = PDFontDescriptor(d).get_font_stretch()
        return "fontStretch\t" + ("<null>" if v is None else v) + "\n"
    if case == "charset_as_name":
        d = COSDictionary()
        d.set_item(_CHAR_SET, COSName.get_pdf_name("StandardEncoding"))
        v = PDFontDescriptor(d).get_char_set()
        return "charSet\t" + ("<null>" if v is None else v) + "\n"
    if case == "charset_as_string":
        d = COSDictionary()
        d.set_item(_CHAR_SET, COSString("/a/b/c"))
        v = PDFontDescriptor(d).get_char_set()
        return "charSet\t" + ("<null>" if v is None else v) + "\n"
    if case == "fontname_as_string":
        d = COSDictionary()
        d.set_item(_FONT_NAME, COSString("ABCDEF+Helvetica"))
        v = PDFontDescriptor(d).get_font_name()
        return "fontName\t" + ("<null>" if v is None else v) + "\n"
    if case == "bbox_three_entries":
        arr = COSArray()
        arr.add(COSInteger.get(0))
        arr.add(COSInteger.get(-200))
        arr.add(COSInteger.get(1000))
        d = COSDictionary()
        d.set_item(_FONT_BBOX, arr)
        r = PDFontDescriptor(d).get_font_bounding_box()
        if r is None:
            return "bbox\t<null>\n"
        return (
            "bbox\t"
            + _fmt(r.get_lower_left_x())
            + ","
            + _fmt(r.get_lower_left_y())
            + ","
            + _fmt(r.get_upper_right_x())
            + ","
            + _fmt(r.get_upper_right_y())
            + "\n"
        )
    if case == "bbox_missing":
        r = PDFontDescriptor(COSDictionary()).get_font_bounding_box()
        return "bbox\t" + ("<null>" if r is None else "notnull") + "\n"
    if case == "setbbox_null_removes":
        from pypdfbox.pdmodel.pd_rectangle import PDRectangle

        fd = PDFontDescriptor()
        fd.set_font_bounding_box(PDRectangle(0, -200, 1000, 900))
        l1 = "present1\t" + str(int(_FONT_BBOX in fd.get_cos_object()))
        fd.set_font_bounding_box(None)
        l2 = "present2\t" + str(int(_FONT_BBOX in fd.get_cos_object()))
        return f"{l1}\n{l2}\n"
    raise AssertionError(f"unknown case {case}")


@requires_oracle
@pytest.mark.parametrize("case", _ORACLE_CASES)
def test_cache_lenient_matches_pdfbox(case: str) -> None:
    java = run_probe_text("FontDescCacheLenientProbe", case)
    py = _py_block(case)
    assert java.splitlines() == py.splitlines(), (
        f"case={case}\n java={java!r}\n   py={py!r}"
    )
