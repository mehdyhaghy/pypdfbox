"""Live PDFBox differential fuzz for the simple-font ``/Encoding``
reverse-mapping + ``/Differences`` cursor surface (wave 1548, agent B).

Targets a surface the existing simple-font encoding oracles never drove:

* ``test_font_encoding_fuzz_wave1516`` pinned only the resolved Encoding
  *class*, its base, and ``getName(65)`` / ``getName(0x80)`` — the forward
  code -> name direction at two fixed codes.
* ``test_pd_simple_font_fuzz_wave1533`` pinned ``toUnicode(int)`` and the
  glyph-list flavour.
* ``test_simple_font_widths_oracle`` pinned ``getWidth`` / the ``/Widths``
  array.

NONE drove the **reverse direction** (``get_name_to_code_map()``), the
``/Differences`` cursor semantics for codes **outside 0..255** (negative,
>255) or a **leading name with no preceding integer**, or the resulting
``get_code_to_name_map()`` size.

Upstream ``DictionaryEncoding.applyDifferences`` starts the code cursor at -1
and applies every glyph name at whatever the cursor currently is — there is
**no ``code >= 0`` guard**. So a leading name lands at code -1, a name after a
negative or >255 integer marker lands at that exact out-of-range code, and all
of them stay in both the forward (code -> name) and reverse (name -> code)
maps. Verified live against PDFBox 3.0.7 by ``SimpleFontEncodingFuzzProbe``.

Bug found + fixed by this wave: pypdfbox's ``DictionaryEncoding._apply_
differences`` carried a ``code >= 0`` guard that silently dropped a leading
name (the cursor's initial -1) and any name following a negative integer
marker — so those glyphs collapsed to ``.notdef`` and their reverse mapping
went missing (e.g. ``diff_leading_name`` left ``getName(-1)`` as ``.notdef``
and the ``diff_out_of_range`` code map was 225 entries instead of Java's 226).
The guard is removed; behaviour now mirrors upstream exactly.

The probe builds the font dictionaries entirely in-Java (no fixture); this
sibling rebuilds the identical COS graph and reconstructs the same line format,
so any divergence shows up as a single differing line.
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
from pypdfbox.pdmodel.font.encoding import DictionaryEncoding
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from tests.oracle.harness import requires_oracle, run_probe_text

# Codes / glyph names probed — must match SimpleFontEncodingFuzzProbe exactly.
_CODES = [-5, -1, 0, 65, 128, 129, 130, 200, 255, 256, 300]
_GLYPHS = ["A", "Euro", "Alpha", "Beta", "Gamma", "Delta", "space", ".notdef", "bullet"]


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _arr(*items: object) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


# ---------- dictionary builders (mirror the Java probe) ----------


def _descriptor(symbolic: bool) -> COSDictionary:
    fd = COSDictionary()
    fd.set_item(_n("Type"), _n("FontDescriptor"))
    fd.set_item(_n("FontName"), _n("MyCustomFont"))
    fd.set_int(_n("Flags"), 4 if symbolic else 32)
    return fd


def _type1(base_font: str | None, symbolic: bool | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Font"))
    d.set_item(_n("Subtype"), _n("Type1"))
    if base_font is not None:
        d.set_item(_n("BaseFont"), _n(base_font))
    if symbolic is not None:
        d.set_item(_n("FontDescriptor"), _descriptor(symbolic))
    return d


def _true_type(base_font: str | None, symbolic: bool | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Font"))
    d.set_item(_n("Subtype"), _n("TrueType"))
    if base_font is not None:
        d.set_item(_n("BaseFont"), _n(base_font))
    if symbolic is not None:
        d.set_item(_n("FontDescriptor"), _descriptor(symbolic))
    return d


def _with_dict_encoding(
    d: COSDictionary, base_enc: str | None, differences: COSArray | None
) -> COSDictionary:
    enc = COSDictionary()
    enc.set_item(_n("Type"), _n("Encoding"))
    if base_enc is not None:
        enc.set_item(_n("BaseEncoding"), _n(base_enc))
    if differences is not None:
        enc.set_item(_n("Differences"), differences)
    d.set_item(_n("Encoding"), enc)
    return d


def _with_name_encoding(d: COSDictionary, enc_name: str) -> COSDictionary:
    d.set_item(_n("Encoding"), _n(enc_name))
    return d


def _cases() -> list[tuple[str, COSDictionary]]:
    """Mirror SimpleFontEncodingFuzzProbe.main's corpus exactly, in order."""
    return [
        ("name_standard", _with_name_encoding(_type1("Helvetica", False), "StandardEncoding")),
        ("name_winansi", _with_name_encoding(_type1("Helvetica", False), "WinAnsiEncoding")),
        ("name_macroman", _with_name_encoding(_type1("Helvetica", False), "MacRomanEncoding")),
        ("name_macexpert", _with_name_encoding(_type1("Helvetica", False), "MacExpertEncoding")),
        (
            "diff_out_of_range",
            _with_dict_encoding(
                _type1("Helvetica", False),
                "WinAnsiEncoding",
                _arr(
                    _i(128), _n("Alpha"), _n("Euro"),
                    _i(300), _n("Beta"), _i(-5), _n("Gamma"),
                ),
            ),
        ),
        (
            "diff_leading_name",
            _with_dict_encoding(
                _type1("Helvetica", False),
                "WinAnsiEncoding",
                _arr(_n("Alpha"), _n("Beta"), _i(128), _n("Euro")),
            ),
        ),
        (
            "diff_negative_only",
            _with_dict_encoding(
                _type1("Helvetica", False), "WinAnsiEncoding", _arr(_i(-1), _n("Zeta"))
            ),
        ),
        (
            "diff_high_only",
            _with_dict_encoding(
                _type1("Helvetica", False),
                "WinAnsiEncoding",
                _arr(_i(256), _n("Eta"), _n("Theta"), _i(300), _n("Iota")),
            ),
        ),
        (
            "diff_duplicate_code",
            _with_dict_encoding(
                _type1("Helvetica", False),
                "WinAnsiEncoding",
                _arr(_i(128), _n("Alpha"), _i(128), _n("Euro")),
            ),
        ),
        (
            "diff_remap_base_glyph",
            _with_dict_encoding(
                _type1("Helvetica", False), "WinAnsiEncoding", _arr(_i(200), _n("A"))
            ),
        ),
        (
            "diff_float_marker",
            _with_dict_encoding(
                _type1("Helvetica", False),
                "WinAnsiEncoding",
                _arr(COSFloat(128.7), _n("Alpha")),
            ),
        ),
        (
            "diff_string_marker",
            _with_dict_encoding(
                _type1("Helvetica", False),
                "WinAnsiEncoding",
                _arr(COSString("128"), _n("Alpha")),
            ),
        ),
        (
            "diff_null_entry",
            _with_dict_encoding(
                _type1("Helvetica", False),
                "WinAnsiEncoding",
                _arr(_i(128), COSNull.NULL, _n("Euro")),
            ),
        ),
        (
            "diff_empty",
            _with_dict_encoding(_type1("Helvetica", False), "WinAnsiEncoding", COSArray()),
        ),
        (
            "diff_base_missing_nonsymbolic",
            _with_dict_encoding(
                _type1("Helvetica", False), None, _arr(_i(128), _n("Euro"))
            ),
        ),
        (
            "diff_base_unknown",
            _with_dict_encoding(
                _type1("Helvetica", False), "BogusEncoding", _arr(_i(128), _n("Euro"))
            ),
        ),
        (
            "tt_diff_out_of_range",
            _with_dict_encoding(
                _true_type("Arial", False),
                "WinAnsiEncoding",
                _arr(
                    _i(128), _n("Alpha"), _n("Euro"),
                    _i(300), _n("Beta"), _i(-5), _n("Gamma"),
                ),
            ),
        ),
        ("tt_name_winansi", _with_name_encoding(_true_type("Arial", False), "WinAnsiEncoding")),
    ]


def _collapse(s: str | None) -> str:
    return "null" if s is None else s.replace(" ", "_")


def _forward(enc: object, code: int) -> str:
    try:
        g = enc.get_name(code)
        return "null" if g is None else g
    except Exception:
        return "ERR"


def _reverse(enc: object, glyph: str) -> str:
    try:
        c = enc.get_name_to_code_map().get(glyph)
        return "null" if c is None else str(c)
    except Exception:
        return "ERR"


def _contains_code(enc: object, code: int) -> str:
    try:
        return "true" if enc.contains(code) else "false"
    except Exception:
        return "ERR"


def _contains_name(enc: object, glyph: str) -> str:
    try:
        return "true" if enc.contains(glyph) else "false"
    except Exception:
        return "ERR"


def _py_output() -> str:
    lines: list[str] = []
    for name, dict_ in _cases():
        head = f"CASE {name} "
        try:
            font = PDFontFactory.create_font(dict_)
        except Exception as exc:  # noqa: BLE001
            lines.append(head + "create=ERR:" + type(exc).__name__)
            continue
        try:
            enc = font.get_encoding_typed()
        except Exception:
            lines.append(head + "enc=ERR")
            continue
        if enc is None:
            lines.append(head + "enc=null ename=null base=- size=0")
            continue
        ename = _collapse(enc.get_encoding_name())
        if isinstance(enc, DictionaryEncoding):
            b = enc.get_base_encoding()
            base = "null" if b is None else _collapse(b.get_encoding_name())
        else:
            base = "-"
        try:
            size = len(enc.get_code_to_name_map())
        except Exception:
            size = -1
        lines.append(
            f"CASE {name} enc={type(enc).__name__} ename={ename} base={base} size={size}"
        )
        for code in _CODES:
            lines.append(f"FWD {name} c{code}={_forward(enc, code)}")
        for g in _GLYPHS:
            lines.append(f"REV {name} g{g}={_reverse(enc, g)}")
        for code in _CODES:
            lines.append(f"CONT {name} code{code}={_contains_code(enc, code)}")
        for g in _GLYPHS:
            lines.append(f"CONTN {name} name{g}={_contains_name(enc, g)}")
    return "\n".join(lines) + "\n"


@requires_oracle
def test_simple_font_encoding_reverse_map_matches_pdfbox() -> None:
    """Forward (code->name), reverse (name->code), contains, and code-map size
    for fuzzed simple-font ``/Encoding`` dicts must match Apache PDFBox exactly.

    Pins the no-guard ``/Differences`` cursor: a leading name lands at -1,
    out-of-range (negative / >255) markers keep their entries in both maps, and
    the resulting ``get_code_to_name_map()`` size matches upstream.
    """
    java = run_probe_text("SimpleFontEncodingFuzzProbe").splitlines()
    py = _py_output().splitlines()
    assert len(java) == len(py), (
        f"line-count mismatch: java={len(java)} py={len(py)}\n"
        "java:\n" + "\n".join(java) + "\npy:\n" + "\n".join(py)
    )
    diffs = [
        f"  line {idx}: java={j!r} py={p!r}"
        for idx, (j, p) in enumerate(zip(java, py, strict=True))
        if j != p
    ]
    assert not diffs, "simple-font encoding reverse-map parity broken:\n" + "\n".join(diffs)


def test_leading_name_and_out_of_range_codes_kept() -> None:
    """Regression pin (no oracle needed): a leading ``/Differences`` name lands
    at code -1 and out-of-range integer markers keep their entries — mirroring
    upstream ``applyDifferences`` which has no ``code >= 0`` guard.

    Before the wave-1548 fix pypdfbox silently dropped both, so ``getName(-1)``
    was ``.notdef`` and the reverse map omitted the glyph.
    """
    diffs = _arr(
        _i(128), _n("Alpha"), _n("Euro"),
        _i(300), _n("Beta"), _i(-5), _n("Gamma"),
    )
    d = _with_dict_encoding(_type1("Helvetica", False), "WinAnsiEncoding", diffs)
    enc = PDFontFactory.create_font(d).get_encoding_typed()
    # Out-of-range codes survive in the forward map.
    assert enc.get_name(300) == "Beta"
    assert enc.get_name(-5) == "Gamma"
    # ...and in the reverse map.
    rev = enc.get_name_to_code_map()
    assert rev["Beta"] == 300
    assert rev["Gamma"] == -5
    # Consecutive names increment the cursor: 128->Alpha, 129->Euro.
    assert enc.get_name(128) == "Alpha"
    assert enc.get_name(129) == "Euro"

    # Leading name with no preceding integer lands at the initial cursor -1.
    lead = _arr(_n("Alpha"), _n("Beta"), _i(128), _n("Euro"))
    d2 = _with_dict_encoding(_type1("Helvetica", False), "WinAnsiEncoding", lead)
    enc2 = PDFontFactory.create_font(d2).get_encoding_typed()
    assert enc2.get_name(-1) == "Alpha"
    assert enc2.get_name(0) == "Beta"
    assert enc2.get_name_to_code_map()["Alpha"] == -1
