"""Live Apache PDFBox differential fuzz parity for the ``PDSimpleFont`` code ->
glyph-name -> Unicode resolution chain (``to_unicode(int)``), the
``get_glyph_list()`` flavour pick (AGL vs ZapfDingbats), and the resolved
``get_encoding_typed`` class over malformed / mistyped / glyph-name-edge inputs
(wave 1533, agent D).

Drives ``oracle/probes/PdSimpleFontFuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* font ``COSDictionary`` per case and
asserting each ``CASE`` line matches.

Complements ``test_font_encoding_fuzz_wave1516.py`` (which pinned only the
resolved *encoding class* + ``Encoding.get_name(code)`` — the encoding-resolution
leniency surface and never drove ``to_unicode``) and
``test_to_unicode_simple_font_oracle.py`` (which pinned a single well-formed
Type1+WinAnsi+ToUnicode font). This suite targets the downstream
``PDSimpleFont.to_unicode`` chain on malformed dictionaries:

* ``to_unicode`` where the glyph name is a synthetic ``uniXXXX`` / ``uXXXXXX``
  name (AGL name-to-unicode algorithm), a standard glyph (``Euro``),
  ``.notdef``, an AGL-absent name, a dotted-suffix name (``A.sc``), and a
  malformed ``uniXXXXzz`` name;
* the ``/ToUnicode`` CMap override (a present mapping wins) and fallback
  (a CMap miss falls through to encoding + glyph list);
* ``/ToUnicode`` of the WRONG COS type — a ``COSName`` (upstream loads it as a
  *predefined* CMap, e.g. ``Identity-H`` mapping each code to itself) and a
  ``COSInteger`` (treated as absent);
* ``/ToUnicode`` filling a code the encoding leaves at ``.notdef``;
* the ``get_glyph_list()`` flavour: Standard-14 ``Symbol`` (AGL) and
  ``ZapfDingbats`` (the Zapf list), including a ZapfDingbats with an explicit
  (ignored, non-embedded) name encoding;
* no ``/Encoding`` at all on a non-embedded Standard 14 (font built-in).

Probe line grammar (one per case)::

    CASE <name> create=ERR:<Exc>
    CASE <name> enc=<EncodingClass|null> gl=<AGL|ZAPF>
         c<code>:<glyph>-><U+XXXX...|null> ...

Hand-written (not ported from upstream JUnit). ``@requires_oracle`` so it skips
cleanly without Java + the jar.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_simple_font import PDSimpleFont
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "PdSimpleFontFuzzProbe"

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
_TO_UNICODE = COSName.get_pdf_name("ToUnicode")


# ---------- COS builders (mirror PdSimpleFontFuzzProbe.java) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _arr(*items: object) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _descriptor(symbolic: bool) -> COSDictionary:
    fd = COSDictionary()
    fd.set_item(_TYPE, _n("FontDescriptor"))
    fd.set_item(_FONT_NAME, _n("MyCustomFont"))
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


def _dict_encoding(base_enc: str | None, differences: COSArray | None) -> COSDictionary:
    enc = COSDictionary()
    enc.set_item(_TYPE, _n("Encoding"))
    if base_enc is not None:
        enc.set_item(_BASE_ENCODING, _n(base_enc))
    if differences is not None:
        enc.set_item(_DIFFERENCES, differences)
    return enc


def _to_unicode_stream(pairs: list[tuple[int, str]]) -> COSStream:
    """A /ToUnicode stream mapping each (code -> 4+-hex-unicode) bfchar."""
    parts = [
        "/CIDInit /ProcSet findresource begin\n",
        "12 dict begin\nbegincmap\n",
        "/CMapType 2 def\n",
        "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n",
        f"{len(pairs)} beginbfchar\n",
    ]
    for code, hex_u in pairs:
        parts.append(f"<{code:02X}> <{hex_u}>\n")
    parts.append("endbfchar\nendcmap\n")
    parts.append("CMapName currentdict /CMap defineresource pop\nend\nend\n")
    s = COSStream()
    with s.create_output_stream() as out:
        out.write("".join(parts).encode("ascii"))
    return s


def _build_cases() -> dict[str, tuple[COSDictionary, list[int]]]:
    """Return {case: (font_dict, codes)} mirroring PdSimpleFontFuzzProbe.main()."""
    cases: dict[str, tuple[COSDictionary, list[int]]] = {}
    codes = [65, 0x80, 0x20, 0x01]

    winansi = _type1("Helvetica", False)
    winansi.set_item(_ENCODING, _n("WinAnsiEncoding"))
    cases["name_winansi_tounicode"] = (winansi, codes)

    standard = _type1("Helvetica", False)
    standard.set_item(_ENCODING, _n("StandardEncoding"))
    cases["name_standard_tounicode"] = (standard, codes)

    diff_uni = _type1("Helvetica", False)
    diff_uni.set_item(_ENCODING, _dict_encoding("WinAnsiEncoding", _arr(_i(0x80), _n("uni20AC"))))
    cases["diff_uniXXXX"] = (diff_uni, codes)

    diff_euro = _type1("Helvetica", False)
    diff_euro.set_item(_ENCODING, _dict_encoding("WinAnsiEncoding", _arr(_i(0x80), _n("Euro"))))
    cases["diff_euro"] = (diff_euro, codes)

    diff_unknown = _type1("Helvetica", False)
    diff_unknown.set_item(
        _ENCODING, _dict_encoding("WinAnsiEncoding", _arr(_i(0x80), _n("Frobnicate")))
    )
    cases["diff_unknown_glyph"] = (diff_unknown, codes)

    diff_notdef = _type1("Helvetica", False)
    diff_notdef.set_item(
        _ENCODING, _dict_encoding("WinAnsiEncoding", _arr(_i(0x80), _n(".notdef")))
    )
    cases["diff_notdef"] = (diff_notdef, codes)

    diff_ulong = _type1("Helvetica", False)
    diff_ulong.set_item(
        _ENCODING, _dict_encoding("WinAnsiEncoding", _arr(_i(0x80), _n("u1F600")))
    )
    cases["diff_u_long"] = (diff_ulong, codes)

    tu_override = _type1("Helvetica", False)
    tu_override.set_item(_ENCODING, _n("WinAnsiEncoding"))
    tu_override.set_item(_TO_UNICODE, _to_unicode_stream([(65, "005A")]))
    cases["tounicode_override"] = (tu_override, codes)

    tu_name = _type1("Helvetica", False)
    tu_name.set_item(_ENCODING, _n("WinAnsiEncoding"))
    tu_name.set_item(_TO_UNICODE, _n("Identity-H"))
    cases["tounicode_wrong_type_name"] = (tu_name, codes)

    tu_int = _type1("Helvetica", False)
    tu_int.set_item(_ENCODING, _n("WinAnsiEncoding"))
    tu_int.set_item(_TO_UNICODE, _i(42))
    cases["tounicode_wrong_type_int"] = (tu_int, codes)

    tu_notdef = _type1("Helvetica", False)
    tu_notdef.set_item(_ENCODING, _n("WinAnsiEncoding"))
    tu_notdef.set_item(_TO_UNICODE, _to_unicode_stream([(0x01, "0041")]))
    cases["tounicode_fills_notdef"] = (tu_notdef, codes)

    cases["std14_symbol"] = (_type1("Symbol", None), [65, 0x61, 0x20])
    cases["std14_zapfdingbats"] = (_type1("ZapfDingbats", None), [65, 0x61, 0x20])

    zapf_named = _type1("ZapfDingbats", None)
    zapf_named.set_item(_ENCODING, _n("WinAnsiEncoding"))
    cases["std14_zapf_named_enc"] = (zapf_named, [65, 0x61, 0x20])

    cases["no_encoding_helvetica"] = (_type1("Helvetica", False), [65, 0x80, 0x20])

    diff_bad_uni = _type1("Helvetica", False)
    diff_bad_uni.set_item(
        _ENCODING, _dict_encoding("WinAnsiEncoding", _arr(_i(0x80), _n("uni20ACzz")))
    )
    cases["diff_bad_uni"] = (diff_bad_uni, codes)

    diff_suffix = _type1("Helvetica", False)
    diff_suffix.set_item(
        _ENCODING, _dict_encoding("WinAnsiEncoding", _arr(_i(0x80), _n("A.sc")))
    )
    cases["diff_dotted_suffix"] = (diff_suffix, codes)

    return cases


def _hex_uni(u: str | None) -> str:
    if u is None:
        return "null"
    if u == "":
        return "EMPTY"
    return " ".join(f"U+{ord(ch):04X}" for ch in u)


def _glyph_flavour(font: PDSimpleFont) -> str:
    try:
        gl = font.get_glyph_list()
    except Exception:  # noqa: BLE001
        return "GL_ERR"
    # The AGL has no "a1"; ZapfDingbatsGlyphList maps it to U+2701.
    return "ZAPF" if gl.to_unicode("a1") is not None else "AGL"


def _enc_name(font: PDSimpleFont) -> str:
    try:
        enc = font.get_encoding_typed()
    except Exception:  # noqa: BLE001
        return "ENC_ERR"
    return "null" if enc is None else type(enc).__name__


def _glyph_name(font: PDSimpleFont, code: int) -> str:
    try:
        enc = font.get_encoding_typed()
    except Exception:  # noqa: BLE001
        return "ERR"
    if enc is None:
        return "-"
    try:
        g = enc.get_name(code)
    except Exception:  # noqa: BLE001
        return "ERR"
    return "null" if g is None else g


def _py_verdict(font_dict: COSDictionary, codes: list[int]) -> str:
    try:
        font = PDFontFactory.create_font(font_dict)
    except Exception as exc:  # noqa: BLE001
        return f"create=ERR:{type(exc).__name__}"
    if not isinstance(font, PDSimpleFont):
        return "create=ERR:NotSimple"
    parts = [f"enc={_enc_name(font)}", f"gl={_glyph_flavour(font)}"]
    for code in codes:
        try:
            u = _hex_uni(font.to_unicode(code))
        except Exception:  # noqa: BLE001
            u = "TU_ERR"
        parts.append(f"c{code}:{_glyph_name(font, code)}->{u}")
    return " ".join(parts)


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


# ----- Intentional pypdfbox divergences (none currently) -----
_DIVERGENCES: dict[str, str] = {}


@requires_oracle
def test_pd_simple_font_fuzz_matches_pdfbox() -> None:
    probe = _parse_probe(run_probe_text(_PROBE))
    assert probe, "probe emitted no CASE lines"

    cases = _build_cases()
    assert set(cases) == set(probe), (
        f"case mismatch: only-in-py={set(cases) - set(probe)}, "
        f"only-in-java={set(probe) - set(cases)}"
    )

    mismatches: list[str] = []
    for name, (font_dict, codes) in cases.items():
        java = probe[name]
        py = _py_verdict(font_dict, codes)

        if name in _DIVERGENCES:
            expected_py = _DIVERGENCES[name]
            if java == expected_py:
                mismatches.append(
                    f"{name}: divergence collapsed — java now matches "
                    f"pypdfbox ({java!r}); drop it from _DIVERGENCES"
                )
            if py != expected_py:
                mismatches.append(f"{name}: py={py!r} != pinned {expected_py!r}")
            continue

        if java != py:
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "pd-simple-font fuzz divergences:\n" + "\n".join(mismatches)


@requires_oracle
def test_probe_covers_the_to_unicode_surface() -> None:
    """Sanity: the corpus spans the documented toUnicode resolution axes."""
    probe = _parse_probe(run_probe_text(_PROBE))
    # uniXXXX glyph name resolves to its code point.
    assert "c128:uni20AC->U+20AC" in probe["diff_uniXXXX"]
    # /ToUnicode override wins over the encoding glyph.
    assert "c65:A->U+005A" in probe["tounicode_override"]
    # ZapfDingbats picks the Zapf glyph list.
    assert "gl=ZAPF" in probe["std14_zapfdingbats"]
    assert "gl=ZAPF" in probe["std14_zapf_named_enc"]
    # Symbol picks the AGL (not Zapf).
    assert "gl=AGL" in probe["std14_symbol"]


def test_to_unicode_glyph_name_edges_oracle_free() -> None:
    """Frozen contract: the AGL name-to-unicode algorithm drives ``to_unicode``
    for synthetic glyph names without needing Java.

    * ``uniXXXX`` -> its code point;
    * a malformed ``uniXXXXzz`` -> None;
    * a dotted-suffix ``A.sc`` -> the base glyph's code point;
    * an AGL-absent name (``Frobnicate``) and ``.notdef`` -> None.
    """
    cases = _build_cases()

    font = PDFontFactory.create_font(cases["diff_uniXXXX"][0])
    assert font.to_unicode(0x80) == "€"

    font = PDFontFactory.create_font(cases["diff_bad_uni"][0])
    assert font.to_unicode(0x80) is None

    font = PDFontFactory.create_font(cases["diff_dotted_suffix"][0])
    assert font.to_unicode(0x80) == "A"

    font = PDFontFactory.create_font(cases["diff_unknown_glyph"][0])
    assert font.to_unicode(0x80) is None

    font = PDFontFactory.create_font(cases["diff_notdef"][0])
    assert font.to_unicode(0x80) is None

    # Direct AGL sanity (no font needed).
    assert GlyphList.DEFAULT.to_unicode("uni20AC") == "€"
    assert GlyphList.DEFAULT.to_unicode("uni20ACzz") is None
