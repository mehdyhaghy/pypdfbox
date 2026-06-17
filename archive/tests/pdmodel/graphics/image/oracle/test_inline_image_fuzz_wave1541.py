"""Differential fuzz of the ``PDInlineImage`` OBJECT API surface against the
live Apache PDFBox 3.0.7 oracle (wave 1541).

The existing inline probes work at the BI/ID/EI *tokenizer* level
(``InlineImageFuzzProbe`` / ``InlineImageDictProbe`` / ``InlineEiScanProbe``)
or pin a single facet (``InlineImageKeyResolveProbe`` = key precedence,
``InlineCsResolveProbe`` = resolved colour-space class). This module fuzzes the
*getter projection* of ``PDInlineImage`` directly — constructing the object
over 44 malformed/edge-case parameter dictionaries and asserting, per case, a
COMBINED tuple of every scalar getter plus the colour-space identity, filter
list, decode array and suffix:

* ``get_width`` / ``get_height`` (abbrev ``/W /H`` vs full ``/Width /Height``;
  missing / zero / negative / non-int / float / null values)
* ``get_bits_per_component`` (missing / 0 / negative / non-int; stencil forces 1)
* ``is_stencil`` / ``get_interpolate``
* ``get_color_space`` name + class (``/G /RGB /CMYK`` abbreviations, ``[/I ...]``
  indexed abbreviation, named-resource colour space, unknown name, absent CS)
* ``get_filters`` (``/AHx /A85 /Fl /RL /LZW`` single + array, full ``/Filter``,
  unknown filter)
* ``get_decode`` (correct/wrong arity, non-array)
* ``get_suffix`` (png / jpg / tiff)

The expected literals were captured from Apache PDFBox 3.0.7 via
``oracle/probes/InlineImageApiFuzzProbe.java`` and are asserted oracle-free
here; the ``@requires_oracle`` test re-runs the Java probe and confirms the
projection still matches byte-for-byte (modulo the one documented divergence
below).

DOCUMENTED DIVERGENCE — ``f_ccf_suffix``
----------------------------------------
The constructor eagerly decodes the filter chain. With *empty* raw data and a
``CCITTFaxDecode`` (``/CCF``) filter, Apache PDFBox's ``CCITTFaxFilter`` throws
out of the constructor (``THROW``), whereas pypdfbox's CCITT filter tolerates
empty input (zero-fills to the declared dimensions) and constructs
successfully. This difference lives in the *filter* module's empty-input
tolerance, not in ``PDInlineImage`` itself, so it is pinned here as an honest
divergence rather than reproduced. (DCT/``/F /DCT`` with empty data throws on
*both* sides, so ``f_dct_suffix`` is a matched ``THROW``.)
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


def _resources_with_rgb_alias() -> PDResources:
    res = PDResources()
    cs_dict = COSDictionary()
    cs_dict.set_item(_n("CS0"), _n("DeviceRGB"))
    res.get_cos_object().set_item(_n("ColorSpace"), cs_dict)
    return res


# --------------------------------------------------------------------------
# Case builders — each returns (label, parameters_dict, resources_or_None).
# Order MUST match oracle/probes/InlineImageApiFuzzProbe.java exactly so the
# differential comparison is positional.
# --------------------------------------------------------------------------
def _cases() -> list[tuple[str, COSDictionary, PDResources | None]]:
    cases: list[tuple[str, COSDictionary, PDResources | None]] = []

    def add(label: str, d: COSDictionary, res: PDResources | None = None) -> None:
        cases.append((label, d, res))

    # abbreviated vs full keys
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(4))
    d.set_item(_n("H"), COSInteger.get(3))
    d.set_item(_n("BPC"), COSInteger.get(8))
    d.set_item(_n("CS"), _n("G"))
    add("abbrev_gray", d)

    d = COSDictionary()
    d.set_item(_n("Width"), COSInteger.get(4))
    d.set_item(_n("Height"), COSInteger.get(3))
    d.set_item(_n("BitsPerComponent"), COSInteger.get(8))
    d.set_item(_n("ColorSpace"), _n("DeviceGray"))
    add("full_gray", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(5))
    d.set_item(_n("Width"), COSInteger.get(50))
    d.set_item(_n("H"), COSInteger.get(6))
    d.set_item(_n("Height"), COSInteger.get(60))
    add("short_wins", d)

    # /CS abbreviations + device names + Pattern + unknown
    for label, cs in (
        ("cs_G", "G"),
        ("cs_RGB", "RGB"),
        ("cs_CMYK", "CMYK"),
        ("cs_DeviceGray", "DeviceGray"),
        ("cs_DeviceRGB", "DeviceRGB"),
        ("cs_DeviceCMYK", "DeviceCMYK"),
        ("cs_Pattern", "Pattern"),
        ("cs_unknown", "Bogus"),
    ):
        d = COSDictionary()
        d.set_item(_n("W"), COSInteger.get(2))
        d.set_item(_n("H"), COSInteger.get(2))
        d.set_item(_n("BPC"), COSInteger.get(8))
        d.set_item(_n("CS"), _n(cs))
        add(label, d)

    # /CS [/I /RGB 1 <palette>] indexed abbreviation
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("BPC"), COSInteger.get(8))
    idx = COSArray()
    idx.add(_n("I"))
    idx.add(_n("RGB"))
    idx.add(COSInteger.get(1))
    idx.add(COSString(bytes([0, 0, 0, 255, 255, 255])))
    d.set_item(_n("CS"), idx)
    add("cs_indexed_I_RGB", d)

    # /CS [/Indexed /DeviceRGB 1 <palette>] full form
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("BPC"), COSInteger.get(8))
    idx2 = COSArray()
    idx2.add(_n("Indexed"))
    idx2.add(_n("DeviceRGB"))
    idx2.add(COSInteger.get(1))
    idx2.add(COSString(bytes([0, 0, 0, 255, 255, 255])))
    d.set_item(_n("CS"), idx2)
    add("cs_indexed_full", d)

    # named resource colour space + missing name
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(8))
    d.set_item(_n("CS"), _n("CS0"))
    add("cs_named_resource", d, _resources_with_rgb_alias())

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(8))
    d.set_item(_n("CS"), _n("Missing"))
    add("cs_named_missing", d, _resources_with_rgb_alias())

    # no CS, not stencil -> get_color_space throws
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(8))
    add("cs_absent_nonstencil", d)

    # /F abbreviations single
    for label, f in (
        ("f_AHx", "AHx"),
        ("f_A85", "A85"),
        ("f_Fl", "Fl"),
        ("f_RL", "RL"),
        ("f_LZW", "LZW"),
    ):
        d = COSDictionary()
        d.set_item(_n("W"), COSInteger.get(0))
        d.set_item(_n("H"), COSInteger.get(0))
        d.set_item(_n("F"), _n(f))
        add(label, d)

    # /F array
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(0))
    d.set_item(_n("H"), COSInteger.get(0))
    fa = COSArray()
    fa.add(_n("A85"))
    fa.add(_n("Fl"))
    d.set_item(_n("F"), fa)
    add("f_array_A85_Fl", d)

    # /Filter full key
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(0))
    d.set_item(_n("H"), COSInteger.get(0))
    d.set_item(_n("Filter"), _n("FlateDecode"))
    add("filter_full_flate", d)

    # unknown filter -> construction throw
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(0))
    d.set_item(_n("H"), COSInteger.get(0))
    d.set_item(_n("F"), _n("Bogus"))
    add("f_unknown", d)

    # DCT with empty data -> construction throw on both sides
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(1))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("BPC"), COSInteger.get(8))
    d.set_item(_n("CS"), _n("RGB"))
    d.set_item(_n("F"), _n("DCT"))
    add("f_dct_suffix", d)

    # CCF with empty data -> Java throws, pypdfbox tolerates (documented divergence)
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(8))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("IM"), COSBoolean.TRUE)
    d.set_item(_n("F"), _n("CCF"))
    add("f_ccf_suffix", d)

    # /BPC edge cases
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("CS"), _n("G"))
    add("bpc_missing", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(0))
    d.set_item(_n("CS"), _n("G"))
    add("bpc_zero", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(-3))
    d.set_item(_n("CS"), _n("G"))
    add("bpc_negative", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), _n("NotANumber"))
    d.set_item(_n("CS"), _n("G"))
    add("bpc_nonint", d)

    # /W /H edge cases
    d = COSDictionary()
    d.set_item(_n("H"), COSInteger.get(2))
    add("w_missing", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(0))
    d.set_item(_n("H"), COSInteger.get(0))
    add("wh_zero", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(-5))
    d.set_item(_n("H"), COSInteger.get(-7))
    add("wh_negative", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSFloat(3.9))
    d.set_item(_n("H"), COSFloat(2.1))
    add("wh_float", d)

    d = COSDictionary()
    d.set_item(_n("W"), _n("Wide"))
    d.set_item(_n("H"), COSString(bytes([0])))
    add("wh_nonint", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSNull.NULL)
    d.set_item(_n("H"), COSNull.NULL)
    add("wh_null", d)

    # /IM stencil edge cases
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(8))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("IM"), COSBoolean.TRUE)
    add("stencil_no_bpc", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(8))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("IM"), COSBoolean.TRUE)
    d.set_item(_n("BPC"), COSInteger.get(8))
    add("stencil_bpc8_mismatch", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(8))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("IM"), COSBoolean.TRUE)
    d.set_item(_n("CS"), _n("RGB"))
    add("stencil_with_rgb", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(8))
    d.set_item(_n("H"), COSInteger.get(1))
    d.set_item(_n("ImageMask"), COSBoolean.TRUE)
    add("imagemask_full", d)

    # /Decode arity
    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(8))
    d.set_item(_n("CS"), _n("G"))
    dec = COSArray()
    dec.add(COSInteger.get(1))
    dec.add(COSInteger.get(0))
    d.set_item(_n("D"), dec)
    add("decode_gray_inverted", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(8))
    d.set_item(_n("CS"), _n("RGB"))
    dec3 = COSArray()
    dec3.add(COSInteger.get(0))
    dec3.add(COSInteger.get(1))
    dec3.add(COSInteger.get(0))
    d.set_item(_n("Decode"), dec3)
    add("decode_wrong_arity", d)

    d = COSDictionary()
    d.set_item(_n("W"), COSInteger.get(2))
    d.set_item(_n("H"), COSInteger.get(2))
    d.set_item(_n("BPC"), COSInteger.get(8))
    d.set_item(_n("CS"), _n("G"))
    d.set_item(_n("D"), COSInteger.get(7))
    add("decode_not_array", d)

    add("empty_dict", COSDictionary())

    return cases


# --------------------------------------------------------------------------
# Python projection — mirrors InlineImageApiFuzzProbe.project() exactly.
# --------------------------------------------------------------------------
def _safe_int(thunk) -> str:
    try:
        return str(int(thunk()))
    except Exception:
        return "<throw>"


def _safe_bool(thunk) -> str:
    try:
        return "true" if thunk() else "false"
    except Exception:
        return "<throw>"


def _safe_str(thunk) -> str:
    try:
        return str(thunk())
    except Exception:
        return "<throw>"


def _cs_name(image: PDInlineImage) -> str:
    try:
        return image.get_color_space().get_name()
    except Exception:
        return "<throw>"


def _cs_class(image: PDInlineImage) -> str:
    try:
        return type(image.get_color_space()).__name__
    except Exception:
        return "<throw>"


def _filters(image: PDInlineImage) -> str:
    return "[" + ",".join(image.get_filters()) + "]"


def _decode(image: PDInlineImage) -> str:
    arr = image.get_decode()
    if arr is None:
        return "null"
    parts: list[str] = []
    for v in arr:
        if isinstance(v, COSInteger):
            parts.append(str(int(v.value)))
        elif isinstance(v, COSFloat):
            parts.append(str(float(v.value)))
        else:
            parts.append(type(v).__name__)
    return "[" + ",".join(parts) + "]"


def _project(image: PDInlineImage) -> str:
    return (
        f"w={_safe_int(image.get_width)} "
        f"h={_safe_int(image.get_height)} "
        f"bpc={_safe_int(image.get_bits_per_component)} "
        f"stencil={_safe_bool(image.is_stencil)} "
        f"interp={_safe_bool(image.get_interpolate)} "
        f"cs={_cs_name(image)} "
        f"csclass={_cs_class(image)} "
        f"filters={_filters(image)} "
        f"decode={_decode(image)} "
        f"suffix={_safe_str(image.get_suffix)}"
    )


def _pypdfbox_lines() -> list[str]:
    out: list[str] = []
    for label, params, res in _cases():
        try:
            image = PDInlineImage(params, b"", res)
            out.append(f"{label}|{_project(image)}")
        except Exception:
            out.append(f"{label}|THROW")
    return out


# Expected projection — captured from Apache PDFBox 3.0.7 via
# oracle/probes/InlineImageApiFuzzProbe.java. Stored as compact per-field
# tuples (w, h, bpc, stencil, interp, cs, csclass, filters, decode, suffix)
# and expanded to the probe's pipe-line format below, so wide literals never
# trip E501. ``"THROW"`` marks a whole-line construction throw.
_T = "<throw>"
_DG = ("DeviceGray", "PDDeviceGray")
_DR = ("DeviceRGB", "PDDeviceRGB")
_DC = ("DeviceCMYK", "PDDeviceCMYK")
_IX = ("Indexed", "PDIndexed")
_NO = (_T, _T)  # colour space throws

_EXPECTED_FIELDS: dict[str, object] = {
    "abbrev_gray": (4, 3, 8, False, False, _DG, "[]", "null", "png"),
    "full_gray": (4, 3, 8, False, False, _DG, "[]", "null", "png"),
    "short_wins": (5, 6, -1, False, False, _NO, "[]", "null", "png"),
    "cs_G": (2, 2, 8, False, False, _DG, "[]", "null", "png"),
    "cs_RGB": (2, 2, 8, False, False, _DR, "[]", "null", "png"),
    "cs_CMYK": (2, 2, 8, False, False, _DC, "[]", "null", "png"),
    "cs_DeviceGray": (2, 2, 8, False, False, _DG, "[]", "null", "png"),
    "cs_DeviceRGB": (2, 2, 8, False, False, _DR, "[]", "null", "png"),
    "cs_DeviceCMYK": (2, 2, 8, False, False, _DC, "[]", "null", "png"),
    "cs_Pattern": (2, 2, 8, False, False, ("Pattern", "PDPattern"), "[]", "null", "png"),
    "cs_unknown": (2, 2, 8, False, False, _NO, "[]", "null", "png"),
    "cs_indexed_I_RGB": (2, 1, 8, False, False, _IX, "[]", "null", "png"),
    "cs_indexed_full": (2, 1, 8, False, False, _IX, "[]", "null", "png"),
    "cs_named_resource": (2, 2, 8, False, False, _DR, "[]", "null", "png"),
    "cs_named_missing": (2, 2, 8, False, False, _NO, "[]", "null", "png"),
    "cs_absent_nonstencil": (2, 2, 8, False, False, _NO, "[]", "null", "png"),
    "f_AHx": (0, 0, -1, False, False, _NO, "[AHx]", "null", "png"),
    "f_A85": (0, 0, -1, False, False, _NO, "[A85]", "null", "png"),
    "f_Fl": (0, 0, -1, False, False, _NO, "[Fl]", "null", "png"),
    "f_RL": (0, 0, -1, False, False, _NO, "[RL]", "null", "png"),
    "f_LZW": (0, 0, -1, False, False, _NO, "[LZW]", "null", "png"),
    "f_array_A85_Fl": (0, 0, -1, False, False, _NO, "[A85,Fl]", "null", "png"),
    "filter_full_flate": (0, 0, -1, False, False, _NO, "[FlateDecode]", "null", "png"),
    "f_unknown": "THROW",
    "f_dct_suffix": "THROW",
    # f_ccf_suffix: see DOCUMENTED DIVERGENCE in the module docstring. Java
    # throws ("THROW"); pypdfbox tolerates empty CCITT data and constructs.
    "f_ccf_suffix": (8, 1, 1, True, False, _DG, "[CCF]", "null", "tiff"),
    "bpc_missing": (2, 2, -1, False, False, _DG, "[]", "null", "png"),
    "bpc_zero": (2, 2, 0, False, False, _DG, "[]", "null", "png"),
    "bpc_negative": (2, 2, -3, False, False, _DG, "[]", "null", "png"),
    "bpc_nonint": (2, 2, -1, False, False, _DG, "[]", "null", "png"),
    "w_missing": (-1, 2, -1, False, False, _NO, "[]", "null", "png"),
    "wh_zero": (0, 0, -1, False, False, _NO, "[]", "null", "png"),
    "wh_negative": (-5, -7, -1, False, False, _NO, "[]", "null", "png"),
    "wh_float": (3, 2, -1, False, False, _NO, "[]", "null", "png"),
    "wh_nonint": (-1, -1, -1, False, False, _NO, "[]", "null", "png"),
    "wh_null": (-1, -1, -1, False, False, _NO, "[]", "null", "png"),
    "stencil_no_bpc": (8, 1, 1, True, False, _DG, "[]", "null", "png"),
    "stencil_bpc8_mismatch": (8, 1, 1, True, False, _DG, "[]", "null", "png"),
    "stencil_with_rgb": (8, 1, 1, True, False, _DR, "[]", "null", "png"),
    "imagemask_full": (8, 1, 1, True, False, _DG, "[]", "null", "png"),
    "decode_gray_inverted": (2, 2, 8, False, False, _DG, "[]", "[1,0]", "png"),
    "decode_wrong_arity": (2, 2, 8, False, False, _DR, "[]", "[0,1,0]", "png"),
    "decode_not_array": (2, 2, 8, False, False, _DG, "[]", "null", "png"),
    "empty_dict": (-1, -1, -1, False, False, _NO, "[]", "null", "png"),
}


def _expand(fields: object) -> str:
    if fields == "THROW":
        return "THROW"
    w, h, bpc, stencil, interp, cs, filters, decode, suffix = fields  # type: ignore[misc]
    cs_name, cs_class = cs
    return (
        f"w={w} h={h} bpc={bpc} "
        f"stencil={'true' if stencil else 'false'} "
        f"interp={'true' if interp else 'false'} "
        f"cs={cs_name} csclass={cs_class} "
        f"filters={filters} decode={decode} suffix={suffix}"
    )


_EXPECTED: dict[str, str] = {
    label: _expand(fields) for label, fields in _EXPECTED_FIELDS.items()
}

# Labels where pypdfbox intentionally diverges from the Java oracle (filter
# module empty-input tolerance, not a PDInlineImage facet). The oracle test
# skips the byte-comparison on these; the value-based test still pins the
# pypdfbox side via _EXPECTED above.
_DIVERGENT_LABELS = {"f_ccf_suffix"}


def test_inline_image_api_projection_value_based() -> None:
    """Oracle-free: every case's getter projection matches the
    PDFBox-3.0.7-derived literal (pypdfbox side, including the documented
    f_ccf_suffix divergence)."""
    got = dict(
        ln.split("|", 1) for ln in _pypdfbox_lines()
    )
    assert got == _EXPECTED


def test_inline_image_api_case_count() -> None:
    """Guard against accidentally dropping a fuzz case."""
    assert len(_cases()) == 44
    assert len(_EXPECTED) == 44


@requires_oracle
def test_inline_image_api_matches_pdfbox() -> None:
    """Differential: re-run the Java probe and confirm the pypdfbox getter
    projection matches Apache PDFBox 3.0.7 line-for-line, except the single
    documented filter-module divergence (f_ccf_suffix)."""
    text = run_probe_text("InlineImageApiFuzzProbe")
    java = dict(
        ln.split("|", 1) for ln in text.splitlines() if ln.strip()
    )
    py = dict(ln.split("|", 1) for ln in _pypdfbox_lines())

    assert set(java) == set(py)
    for label in java:
        if label in _DIVERGENT_LABELS:
            # Documented: Java throws on empty CCITT, pypdfbox tolerates it.
            assert java[label] == "THROW"
            assert py[label] != "THROW"
            continue
        assert py[label] == java[label], f"divergence on {label}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
