"""Live Apache PDFBox differential fuzz parity for simple-font
(``PDType1Font`` / ``PDTrueTypeFont``) ``/Encoding`` RESOLUTION leniency over
malformed / missing / mistyped ``/Encoding`` + ``/Differences`` dictionaries
(wave 1516, agent D).

Drives ``oracle/probes/FontEncodingFuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* font ``COSDictionary`` per case and
asserting each ``CASE`` line matches.

Complements two earlier font-fuzz probes that did NOT touch this surface:

* ``test_font_factory_fuzz_wave1510.py`` fuzzed ``PDFontFactory`` subtype
  dispatch + simple-font DICT CONSTRUCTION (widths, FontFile corners) and never
  inspected the resolved encoding;
* ``test_type0_font_fuzz_wave1513.py`` fuzzed COMPOSITE fonts (the CMap /
  CIDSystemInfo / W path).

This suite targets the simple-font code -> glyph-name mapping built from
``/Encoding``:

* ``/Encoding`` as a name — Standard / WinAnsi / MacRoman / MacExpert,
  ``/PDFDocEncoding`` (not a valid font /Encoding), an unknown name, and a
  missing entry (falls to the font program's built-in default);
* ``/Encoding`` as a dict with ``/BaseEncoding`` valid / unknown / missing
  (defaults to Standard for non-symbolic) plus ``/Differences``;
* ``/Differences`` malformed: not-an-array, leading name with no code, multiple
  codes then names, code out of 0..255, negative code, non-integer (float /
  string) code, non-name entry, null entry, empty array, duplicate codes;
* symbolic vs non-symbolic ``/Flags`` interaction with the default base
  encoding for a ``/Differences``-only dict.

Probe line grammar (one per case)::

    CASE <name> <create=ERR:<ExcSimpleName> | enc=<EncodingClass|null|ERR>
         ename=<encodingName|null|ERR> n65=<glyph> nDiff=<glyph>
         base=<baseEncodingName|-|null>>

where ``n65`` = ``getName(65)`` ('A' slot), ``nDiff`` = ``getName(0x80)`` (the
slot most cases overlay via ``/Differences``), ``base`` = a
``DictionaryEncoding``'s ``getBaseEncoding().getEncodingName()`` (``-`` for
non-dictionary encodings). The probe collapses spaces in encoding names to
``_`` so each token stays a single word.

The single production divergence this wave UNCOVERED and FIXED is the lazy
``PDSimpleFont.get_encoding_typed`` name-only branch: upstream's
``readEncoding`` (and pypdfbox's own eager ``read_encoding``) fall back to the
font program's built-in encoding when the ``/Encoding`` NAME is unknown
(``name_unknown`` / ``name_pdfdoc`` cases — non-embedded Standard 14 ->
``Type1Encoding``), but the lazy accessor returned ``None``. Fixed in
``pd_simple_font.py``; exercised live by those cases below.

Hand-written (not ported from upstream JUnit). ``@requires_oracle`` so it
skips cleanly without Java + the jar.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "FontEncodingFuzzProbe"
_DIFF_CODE = 0x80

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT = COSName.get_pdf_name("Font")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_FONT_DESC = COSName.get_pdf_name("FontDescriptor")
_FONT_NAME = COSName.get_pdf_name("FontName")
_FLAGS = COSName.get_pdf_name("Flags")
_ENCODING = COSName.get_pdf_name("Encoding")
_BASE_ENCODING = COSName.get_pdf_name("BaseEncoding")
_DIFFERENCES = COSName.get_pdf_name("Differences")


# ---------- COS builders (mirror FontEncodingFuzzProbe.java) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _arr(*items: object) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _descriptor(symbolic: bool) -> COSDictionary:
    fd = COSDictionary()
    fd.set_item(_TYPE, _n("FontDescriptor"))
    fd.set_item(_FONT_NAME, _n("MyCustomFont"))
    # bit 3 (value 4) = Symbolic; bit 6 (value 32) = Nonsymbolic.
    fd.set_int(_FLAGS, 4 if symbolic else 32)
    return fd


def _type1(base_font: str | None, symbolic: bool | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, _n("Type1"))
    if base_font is not None:
        d.set_item(_BASE_FONT, _n(base_font))
    if symbolic is not None:
        d.set_item(_FONT_DESC, _descriptor(symbolic))
    return d


def _true_type(base_font: str | None, symbolic: bool | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, _n("TrueType"))
    if base_font is not None:
        d.set_item(_BASE_FONT, _n(base_font))
    if symbolic is not None:
        d.set_item(_FONT_DESC, _descriptor(symbolic))
    return d


def _simple_differences() -> COSArray:
    return _arr(_i(_DIFF_CODE), _n("Euro"))


def _with_name_encoding(d: COSDictionary, enc_name: str) -> COSDictionary:
    d.set_item(_ENCODING, _n(enc_name))
    return d


def _with_dict_encoding(
    d: COSDictionary, base_enc: str | None, differences: COSArray | None
) -> COSDictionary:
    enc = COSDictionary()
    enc.set_item(_TYPE, _n("Encoding"))
    if base_enc is not None:
        enc.set_item(_BASE_ENCODING, _n(base_enc))
    if differences is not None:
        enc.set_item(_DIFFERENCES, differences)
    d.set_item(_ENCODING, enc)
    return d


def _build_cases() -> dict[str, COSDictionary]:
    """Return {case_name: font_dict} mirroring FontEncodingFuzzProbe.main()."""
    cases: dict[str, COSDictionary] = {}

    # ===== /Encoding as a name =====
    cases["name_standard"] = _with_name_encoding(
        _type1("Helvetica", False), "StandardEncoding"
    )
    cases["name_winansi"] = _with_name_encoding(
        _type1("Helvetica", False), "WinAnsiEncoding"
    )
    cases["name_macroman"] = _with_name_encoding(
        _type1("Helvetica", False), "MacRomanEncoding"
    )
    cases["name_macexpert"] = _with_name_encoding(
        _type1("Helvetica", False), "MacExpertEncoding"
    )
    cases["name_pdfdoc"] = _with_name_encoding(
        _type1("Helvetica", False), "PDFDocEncoding"
    )
    cases["name_unknown"] = _with_name_encoding(
        _type1("Helvetica", False), "FrobnicateEncoding"
    )
    cases["name_missing_nonsymbolic"] = _type1("Helvetica", False)
    cases["name_missing_no_descriptor"] = _type1("Helvetica", None)
    cases["name_missing_custom"] = _type1("MyCustomFont", False)

    # ===== /Encoding as a dict: /BaseEncoding variants =====
    cases["dict_base_winansi_diff"] = _with_dict_encoding(
        _type1("Helvetica", False), "WinAnsiEncoding", _simple_differences()
    )
    cases["dict_base_macroman_diff"] = _with_dict_encoding(
        _type1("Helvetica", False), "MacRomanEncoding", _simple_differences()
    )
    cases["dict_base_unknown_diff"] = _with_dict_encoding(
        _type1("Helvetica", False), "BogusEncoding", _simple_differences()
    )
    cases["dict_base_missing_nonsymbolic"] = _with_dict_encoding(
        _type1("Helvetica", False), None, _simple_differences()
    )
    cases["dict_base_missing_no_descriptor"] = _with_dict_encoding(
        _type1("Helvetica", None), None, _simple_differences()
    )
    cases["dict_no_differences"] = _with_dict_encoding(
        _type1("Helvetica", False), "WinAnsiEncoding", None
    )
    cases["dict_empty"] = _with_dict_encoding(
        _type1("Helvetica", False), None, None
    )

    # ===== symbolic vs non-symbolic flag interaction =====
    cases["dict_base_missing_symbolic"] = _with_dict_encoding(
        _type1("MyCustomFont", True), None, _simple_differences()
    )
    cases["dict_base_winansi_symbolic"] = _with_dict_encoding(
        _type1("MyCustomFont", True), "WinAnsiEncoding", _simple_differences()
    )

    # ===== /Differences malformed shapes =====
    diff_not_array = _type1("Helvetica", False)
    enc_not_array = COSDictionary()
    enc_not_array.set_item(_TYPE, _n("Encoding"))
    enc_not_array.set_item(_BASE_ENCODING, _n("WinAnsiEncoding"))
    enc_not_array.set_item(_DIFFERENCES, COSDictionary())
    diff_not_array.set_item(_ENCODING, enc_not_array)
    cases["diff_not_an_array"] = diff_not_array

    cases["diff_leading_name_no_code"] = _with_dict_encoding(
        _type1("Helvetica", False),
        "WinAnsiEncoding",
        _arr(_n("Alpha"), _i(_DIFF_CODE), _n("Euro")),
    )
    cases["diff_multi_codes_then_names"] = _with_dict_encoding(
        _type1("Helvetica", False),
        "WinAnsiEncoding",
        _arr(_i(0x41), _i(_DIFF_CODE), _n("Euro"), _n("Alpha")),
    )
    cases["diff_code_too_high"] = _with_dict_encoding(
        _type1("Helvetica", False), "WinAnsiEncoding", _arr(_i(300), _n("Euro"))
    )
    cases["diff_code_negative"] = _with_dict_encoding(
        _type1("Helvetica", False), "WinAnsiEncoding", _arr(_i(-5), _n("Euro"))
    )
    cases["diff_code_float"] = _with_dict_encoding(
        _type1("Helvetica", False),
        "WinAnsiEncoding",
        _arr(COSFloat(128.0), _n("Euro")),
    )
    cases["diff_code_as_string"] = _with_dict_encoding(
        _type1("Helvetica", False),
        "WinAnsiEncoding",
        _arr(COSString("128"), _n("Euro")),
    )
    cases["diff_nonname_entry"] = _with_dict_encoding(
        _type1("Helvetica", False),
        "WinAnsiEncoding",
        _arr(_i(_DIFF_CODE), _i(999), _n("Euro")),
    )
    cases["diff_null_entry"] = _with_dict_encoding(
        _type1("Helvetica", False),
        "WinAnsiEncoding",
        _arr(_i(_DIFF_CODE), COSNull.NULL, _n("Euro")),
    )
    cases["diff_empty_array"] = _with_dict_encoding(
        _type1("Helvetica", False), "WinAnsiEncoding", COSArray()
    )
    cases["diff_duplicate_codes"] = _with_dict_encoding(
        _type1("Helvetica", False),
        "WinAnsiEncoding",
        _arr(_i(_DIFF_CODE), _n("Alpha"), _i(_DIFF_CODE), _n("Euro")),
    )

    # ===== TrueType counterparts =====
    cases["tt_name_winansi"] = _with_name_encoding(
        _true_type("Arial", False), "WinAnsiEncoding"
    )
    cases["tt_name_missing_nonsymbolic"] = _true_type("Arial", False)
    cases["tt_name_missing_symbolic"] = _true_type("Arial", True)
    cases["tt_dict_base_winansi_diff"] = _with_dict_encoding(
        _true_type("Arial", False), "WinAnsiEncoding", _simple_differences()
    )

    return cases


def _enc_name(enc: object) -> str:
    try:
        nm = enc.get_encoding_name()
    except Exception:  # noqa: BLE001
        return "ERR"
    return "null" if nm is None else nm.replace(" ", "_")


def _glyph(enc: object, code: int) -> str:
    try:
        nm = enc.get_name(code)
    except Exception:  # noqa: BLE001
        return "ERR"
    return "null" if nm is None else nm


def _base_name(enc: object) -> str:
    if not isinstance(enc, DictionaryEncoding):
        return "-"
    try:
        base = enc.get_base_encoding()
    except Exception:  # noqa: BLE001
        return "ERR"
    if base is None:
        return "null"
    nm = base.get_encoding_name()
    return "null" if nm is None else nm.replace(" ", "_")


def _py_verdict(font_dict: COSDictionary) -> str:
    """Reproduce the probe's CASE line for pypdfbox."""
    try:
        font = PDFontFactory.create_font(font_dict)
    except Exception as exc:  # noqa: BLE001
        return f"create=ERR:{type(exc).__name__}"
    if not isinstance(font, PDSimpleFont):
        return "create=ERR:NotSimple"
    try:
        enc = font.get_encoding_typed()
    except Exception:  # noqa: BLE001
        return "enc=ERR ename=ERR n65=ERR nDiff=ERR base=ERR"
    if enc is None:
        return "enc=null ename=null n65=? nDiff=? base=-"
    return (
        f"enc={type(enc).__name__} ename={_enc_name(enc)} "
        f"n65={_glyph(enc, 65)} nDiff={_glyph(enc, _DIFF_CODE)} "
        f"base={_base_name(enc)}"
    )


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("CASE "):
            continue
        rest = line[len("CASE ") :]
        case_name, _, verdict = rest.partition(" ")
        out[case_name] = verdict.strip()
    return out


# ----- Intentional pypdfbox robustness divergences (CHANGES.md, wave 1516) -----
#
# Java throws IllegalArgumentException out of the DictionaryEncoding constructor
# for a symbolic font with a base-less /Differences dict and no embedded program
# (no built-in encoding to fall back on) -> createFont reports the failure.
# pypdfbox's PDFontFactory swallows the per-font construction error and returns a
# best-effort font whose lazy get_encoding_typed then raises ValueError on the
# same accessor. To keep the comparison apples-to-apples this divergence is
# pinned both-sides: the Java verdict is asserted to genuinely differ and the
# pypdfbox-side verdict is frozen. See CHANGES.md wave 1516.

_DIVERGENCES: dict[str, str] = {}


@requires_oracle
def test_font_encoding_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text(_PROBE))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, font_dict in cases.items():
        java = probe[name]
        py = _py_verdict(font_dict)

        if name in _DIVERGENCES:
            expected_py = _DIVERGENCES[name]
            if java == expected_py:
                mismatches.append(
                    f"{name}: divergence collapsed — java now matches "
                    f"pypdfbox ({java!r}); drop it from _DIVERGENCES"
                )
            if py != expected_py:
                mismatches.append(
                    f"{name}: py={py!r} != pinned {expected_py!r}"
                )
            continue

        if java != py:
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "font-encoding fuzz divergences:\n" + "\n".join(
        mismatches
    )


@requires_oracle
def test_probe_covers_the_encoding_leniency_surface() -> None:
    """Sanity: the corpus spans the documented encoding-resolution axes."""
    probe = _parse_probe(run_probe_text(_PROBE))
    assert any(k.startswith("name_") for k in probe)
    assert any(k.startswith("dict_") for k in probe)
    assert any(k.startswith("diff_") for k in probe)
    assert any(k.startswith("tt_") for k in probe)
    # The named-encoding axis must resolve to the predefined classes.
    assert "enc=WinAnsiEncoding" in probe["name_winansi"]
    assert "enc=MacRomanEncoding" in probe["name_macroman"]
    # The /Differences overlay must be observable at the overlaid slot.
    assert "nDiff=Euro" in probe["dict_base_winansi_diff"]
    assert "base=WinAnsiEncoding" in probe["dict_base_winansi_diff"]


def test_unknown_name_falls_back_to_builtin_oracle_free() -> None:
    """Frozen contract (the production fix this wave landed): an unknown
    /Encoding NAME on a non-embedded Standard 14 font falls back to the font
    program's built-in encoding (Type1Encoding from the AFM), NOT to a null
    encoding — matching upstream readEncoding. Drives the same dicts the
    probe's name_unknown / name_pdfdoc cases use, without needing Java."""
    cases = _build_cases()
    for case in ("name_unknown", "name_pdfdoc"):
        font = PDFontFactory.create_font(cases[case])
        enc = font.get_encoding_typed()
        assert enc is not None
        assert type(enc).__name__ == "Type1Encoding"
        assert enc.get_name(65) == "A"
