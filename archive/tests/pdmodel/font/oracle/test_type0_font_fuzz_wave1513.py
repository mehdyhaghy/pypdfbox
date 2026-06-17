"""Live Apache PDFBox differential fuzz parity for ``PDType0Font`` (composite
font) + its descendant ``PDCIDFontType0`` / ``PDCIDFontType2`` construction
leniency over malformed font dictionaries (wave 1513, agent E).

Drives ``oracle/probes/Type0FontFuzzProbe.java`` (the oracle of record)
against pypdfbox, rebuilding the *identical* malformed / missing / mistyped
Type 0 + descendant ``COSDictionary`` per case and asserting each ``CASE``
line matches.

Complements ``test_font_factory_fuzz_wave1510.py`` (the ``PDFontFactory``
simple-font + subtype-dispatch fuzz, which touched Type 0 only lightly). This
suite goes DEEP into the composite-font path:

* descendant ``/Subtype`` CIDFontType0 vs CIDFontType2 vs unknown vs missing;
* ``/Encoding`` predefined-name vs Identity-H/V vs missing vs unknown vs
  embedded-CMap stream (and its effect on ``code_to_cid``);
* the descendant ``/W`` width array in all its malformed shapes —
  ``c [w...]`` (form 1), ``c1 c2 w`` (form 2), out-of-order ranges,
  non-numeric / null entries, truncated tails, wrong-type;
* ``/DW`` default width missing / float / string / negative;
* ``/CIDToGIDMap`` Identity vs stream vs absent vs odd-name vs wrong-type
  (reported as the raw COS-entry KIND, never resolved through a substitute
  font — keeps the contract font-mapper-free);
* ``/CIDSystemInfo`` missing / partial (any of /Registry, /Ordering,
  /Supplement dropped or mistyped).

Probe line grammar (one per case)::

    CASE <name> <create=ERR:<ExcSimpleName> | ok desc=<C> csi=<reg-ord-supp|null>
         dw=<n|ERR> cidA=<n|ERR> cidHi=<n|ERR> wA=<w|ERR> wHi=<w|ERR>
         c2g=<Identity|stream|absent|name:<x>|<type>|->>

Where pypdfbox *intentionally* diverges from upstream's construction contract
(documented in CHANGES.md, wave 1513) the case name is listed in
``_DIVERGENCES`` with the pypdfbox-side expectation; for every other case the
probe line is the contract pypdfbox must meet verbatim (width tokens compared
numerically).

The single production divergence this wave UNCOVERED and FIXED is the
``PDCIDSystemInfo.get_supplement`` default — upstream returns ``-1`` (not 0)
for an absent / non-numeric ``/Supplement`` (``COSDictionary.getInt`` one-arg
default). That fix is exercised live by the ``csi_no_supplement`` /
``csi_empty_dict`` / ``csi_as_array`` cases below (they assert ``-1`` on both
sides).

Hand-written (not ported from upstream JUnit). ``@requires_oracle`` so it
skips cleanly without Java + the jar.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "Type0FontFuzzProbe"
_TOL = 1e-2

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT = COSName.get_pdf_name("Font")
_BASE_FONT = COSName.get_pdf_name("BaseFont")
_ENCODING = COSName.get_pdf_name("Encoding")
_DESCENDANT_FONTS = COSName.get_pdf_name("DescendantFonts")
_CID_SYSTEM_INFO = COSName.get_pdf_name("CIDSystemInfo")
_CID_TO_GID_MAP = COSName.get_pdf_name("CIDToGIDMap")
_W = COSName.get_pdf_name("W")
_DW = COSName.get_pdf_name("DW")
_REGISTRY = COSName.get_pdf_name("Registry")
_ORDERING = COSName.get_pdf_name("Ordering")
_SUPPLEMENT = COSName.get_pdf_name("Supplement")


# ---------- COS builders (mirror Type0FontFuzzProbe.java) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _arr(*items: object) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _cid_to_gid_stream() -> COSStream:
    s = COSStream()
    s.set_data(bytes([0, 0, 0, 0, 0, 0, 0, 77, 0, 88]))
    return s


def _csi(
    registry: str | None, ordering: str | None, supplement: int | None
) -> COSDictionary:
    d = COSDictionary()
    if registry is not None:
        d.set_string(_REGISTRY, registry)
    if ordering is not None:
        d.set_string(_ORDERING, ordering)
    if supplement is not None:
        d.set_int(_SUPPLEMENT, supplement)
    return d


def _cid_font(subtype: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    if subtype is not None:
        d.set_item(_SUBTYPE, _n(subtype))
    d.set_item(_BASE_FONT, _n("Arial"))
    d.set_item(_CID_SYSTEM_INFO, _csi("Adobe", "Identity", 0))
    return d


def _desc_array(cid: COSDictionary) -> COSArray:
    a = COSArray()
    a.add(cid)
    return a


def _type0(descendants: object | None, encoding: str | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, _FONT)
    d.set_item(_SUBTYPE, _n("Type0"))
    d.set_item(_BASE_FONT, _n("Arial-Identity-H"))
    if encoding is not None:
        d.set_item(_ENCODING, _n(encoding))
    if descendants is not None:
        d.set_item(_DESCENDANT_FONTS, descendants)
    return d


def _build_cases() -> dict[str, COSDictionary]:
    """Return {case_name: type0_font_dict} mirroring Type0FontFuzzProbe.main()."""
    cases: dict[str, COSDictionary] = {}

    # ===== descendant /Subtype variants =====
    cases["desc_cidtype2"] = _type0(
        _desc_array(_cid_font("CIDFontType2")), "Identity-H"
    )
    cases["desc_cidtype0"] = _type0(
        _desc_array(_cid_font("CIDFontType0")), "Identity-H"
    )
    cases["desc_unknown_subtype"] = _type0(
        _desc_array(_cid_font("CIDFontTypeX")), "Identity-H"
    )
    cases["desc_missing_subtype"] = _type0(
        _desc_array(_cid_font(None)), "Identity-H"
    )

    # ===== /DescendantFonts shape variants =====
    cases["descendants_missing"] = _type0(None, "Identity-H")
    cases["descendants_empty"] = _type0(COSArray(), "Identity-H")
    cases["descendants_as_dict"] = _type0(
        _cid_font("CIDFontType2"), "Identity-H"
    )
    cases["descendants_as_name"] = _type0(_n("Bogus"), "Identity-H")
    cases["descendants_first_nonarray_elem"] = _type0(_arr(_i(42)), "Identity-H")
    two = _desc_array(_cid_font("CIDFontType2"))
    two.add(_cid_font("CIDFontType0"))
    cases["descendants_two"] = _type0(two, "Identity-H")

    # ===== /Encoding variants =====
    cases["encoding_identity_v"] = _type0(
        _desc_array(_cid_font("CIDFontType2")), "Identity-V"
    )
    cases["encoding_missing"] = _type0(
        _desc_array(_cid_font("CIDFontType2")), None
    )
    cases["encoding_unknown_name"] = _type0(
        _desc_array(_cid_font("CIDFontType2")), "NoSuchCMap-Frob"
    )
    cases["encoding_predefined_cjk"] = _type0(
        _desc_array(_cid_font("CIDFontType2")), "GBK-EUC-H"
    )
    enc_stream = _type0(_desc_array(_cid_font("CIDFontType2")), None)
    enc_stream.set_item(_ENCODING, COSStream())
    cases["encoding_empty_stream"] = enc_stream

    # ===== /W width-array shapes =====
    w_form1 = _cid_font("CIDFontType2")
    w_form1.set_item(_W, _arr(_i(0x41), _arr(_i(600), _i(601), _i(602))))
    cases["w_form1_covers_A"] = _type0(_desc_array(w_form1), "Identity-H")

    w_form2 = _cid_font("CIDFontType2")
    w_form2.set_item(_W, _arr(_i(0x41), _i(0x50), _i(777)))
    cases["w_form2_range_covers_A"] = _type0(_desc_array(w_form2), "Identity-H")

    w_ooo = _cid_font("CIDFontType2")
    w_ooo.set_item(_W, _arr(_i(0x50), _i(0x41), _i(777)))
    cases["w_form2_out_of_order"] = _type0(_desc_array(w_ooo), "Identity-H")

    w_bad_first = _cid_font("CIDFontType2")
    w_bad_first.set_item(_W, _arr(_n("X"), _arr(_i(600))))
    cases["w_nonnumeric_first_cid"] = _type0(
        _desc_array(w_bad_first), "Identity-H"
    )

    w_inner_hole = _cid_font("CIDFontType2")
    w_inner_hole.set_item(
        _W, _arr(_i(0x41), _arr(_i(600), COSNull.NULL, _n("Bad"), _i(603)))
    )
    cases["w_inner_array_holes"] = _type0(
        _desc_array(w_inner_hole), "Identity-H"
    )

    w_trunc = _cid_font("CIDFontType2")
    w_trunc.set_item(_W, _arr(_i(0x41)))
    cases["w_truncated_tail"] = _type0(_desc_array(w_trunc), "Identity-H")

    w_trunc2 = _cid_font("CIDFontType2")
    w_trunc2.set_item(_W, _arr(_i(0x41), _i(0x50)))
    cases["w_truncated_range_tail"] = _type0(
        _desc_array(w_trunc2), "Identity-H"
    )

    w_dict = _cid_font("CIDFontType2")
    w_dict.set_item(_W, COSDictionary())
    cases["w_as_dict"] = _type0(_desc_array(w_dict), "Identity-H")

    w_float = _cid_font("CIDFontType2")
    w_float.set_item(
        _W, _arr(_i(0x41), _arr(COSFloat(600.5), COSFloat(601.25)))
    )
    cases["w_float_widths"] = _type0(_desc_array(w_float), "Identity-H")

    # ===== /DW default-width shapes =====
    cases["dw_missing"] = _type0(
        _desc_array(_cid_font("CIDFontType2")), "Identity-H"
    )

    dw_explicit = _cid_font("CIDFontType2")
    dw_explicit.set_int(_DW, 500)
    cases["dw_explicit_500"] = _type0(_desc_array(dw_explicit), "Identity-H")

    dw_float = _cid_font("CIDFontType2")
    dw_float.set_item(_DW, COSFloat(444.5))
    cases["dw_float"] = _type0(_desc_array(dw_float), "Identity-H")

    dw_string = _cid_font("CIDFontType2")
    dw_string.set_item(_DW, COSString("600"))
    cases["dw_as_string"] = _type0(_desc_array(dw_string), "Identity-H")

    dw_neg = _cid_font("CIDFontType2")
    dw_neg.set_int(_DW, -250)
    cases["dw_negative"] = _type0(_desc_array(dw_neg), "Identity-H")

    # ===== /CIDToGIDMap shapes (CIDFontType2 only) =====
    c2g_identity = _cid_font("CIDFontType2")
    c2g_identity.set_item(_CID_TO_GID_MAP, _n("Identity"))
    cases["cid2gid_identity"] = _type0(_desc_array(c2g_identity), "Identity-H")

    c2g_stream = _cid_font("CIDFontType2")
    c2g_stream.set_item(_CID_TO_GID_MAP, _cid_to_gid_stream())
    cases["cid2gid_stream"] = _type0(_desc_array(c2g_stream), "Identity-H")

    cases["cid2gid_absent"] = _type0(
        _desc_array(_cid_font("CIDFontType2")), "Identity-H"
    )

    c2g_bad_name = _cid_font("CIDFontType2")
    c2g_bad_name.set_item(_CID_TO_GID_MAP, _n("Frobnicate"))
    cases["cid2gid_bad_name"] = _type0(_desc_array(c2g_bad_name), "Identity-H")

    c2g_arr = _cid_font("CIDFontType2")
    c2g_arr.set_item(_CID_TO_GID_MAP, _arr(_i(1), _i(2)))
    cases["cid2gid_as_array"] = _type0(_desc_array(c2g_arr), "Identity-H")

    c2g_on_type0 = _cid_font("CIDFontType0")
    c2g_on_type0.set_item(_CID_TO_GID_MAP, _n("Identity"))
    cases["cid2gid_on_cidtype0"] = _type0(
        _desc_array(c2g_on_type0), "Identity-H"
    )

    # ===== /CIDSystemInfo shapes =====
    csi_missing = _cid_font("CIDFontType2")
    csi_missing.remove_item(_CID_SYSTEM_INFO)
    cases["csi_missing"] = _type0(_desc_array(csi_missing), "Identity-H")

    csi_no_ordering = _cid_font("CIDFontType2")
    csi_no_ordering.set_item(_CID_SYSTEM_INFO, _csi("Adobe", None, 0))
    cases["csi_no_ordering"] = _type0(_desc_array(csi_no_ordering), "Identity-H")

    csi_no_registry = _cid_font("CIDFontType2")
    csi_no_registry.set_item(_CID_SYSTEM_INFO, _csi(None, "Japan1", 2))
    cases["csi_no_registry"] = _type0(_desc_array(csi_no_registry), "Identity-H")

    csi_no_supp = _cid_font("CIDFontType2")
    csi_no_supp.set_item(_CID_SYSTEM_INFO, _csi("Adobe", "GB1", None))
    cases["csi_no_supplement"] = _type0(_desc_array(csi_no_supp), "Identity-H")

    csi_empty = _cid_font("CIDFontType2")
    csi_empty.set_item(_CID_SYSTEM_INFO, COSDictionary())
    cases["csi_empty_dict"] = _type0(_desc_array(csi_empty), "Identity-H")

    csi_name_reg = _cid_font("CIDFontType2")
    csi_nr = COSDictionary()
    csi_nr.set_item(_REGISTRY, _n("Adobe"))
    csi_nr.set_item(_ORDERING, _n("Korea1"))
    csi_nr.set_int(_SUPPLEMENT, 1)
    csi_name_reg.set_item(_CID_SYSTEM_INFO, csi_nr)
    cases["csi_name_typed_fields"] = _type0(
        _desc_array(csi_name_reg), "Identity-H"
    )

    csi_arr = _cid_font("CIDFontType2")
    csi_arr.set_item(_CID_SYSTEM_INFO, _arr(_i(1)))
    cases["csi_as_array"] = _type0(_desc_array(csi_arr), "Identity-H")

    return cases


# ----- Intentional pypdfbox robustness divergences (CHANGES.md, wave 1513) -----
#
# Lazy Type 0 construction. Upstream's ``PDType0Font`` constructor eagerly
# reads ``/DescendantFonts`` (and ``readEncoding``) and throws ``IOException``
# (probe: ``create=ERR:IOException``) when the descendant array is missing /
# empty / a non-array / a dict, when the first element isn't a dictionary,
# when the descendant ``/Subtype`` is unknown or missing, or when the
# ``/Encoding`` is an unknown predefined name / an unparseable stream.
# pypdfbox's ``PDType0Font`` is lazy (descendant + CMap read on demand): the
# wrapper always constructs, ``get_descendant_font()`` returns ``None`` for a
# malformed descendant (so ``desc=null``, widths fall to ``0.0``), and an
# unknown/unparseable ``/Encoding`` simply yields no CMap (``code_to_cid``
# echoes the raw code / CID 0) instead of raising. A deliberate robustness
# choice — extends the wave-1510 family to the deeper descendant-/Subtype and
# /Encoding-stream cases. See test_font_factory_fuzz_wave1510.py "(B)".
#
# Value per case is the pypdfbox-side expected verdict string. The probe's
# Java verdict is asserted to genuinely differ; both sides are pinned so a
# regression on either trips.

_LAZY_NULL_DESC = (
    "create=ok desc=null csi=null dw=- cidA=65 cidHi=19968 "
    "wA=0.000 wHi=0.000 c2g=-"
)

_DIVERGENCES: dict[str, str] = {
    "desc_unknown_subtype": _LAZY_NULL_DESC,
    "desc_missing_subtype": _LAZY_NULL_DESC,
    "descendants_missing": _LAZY_NULL_DESC,
    "descendants_empty": _LAZY_NULL_DESC,
    "descendants_as_dict": _LAZY_NULL_DESC,
    "descendants_as_name": _LAZY_NULL_DESC,
    "descendants_first_nonarray_elem": _LAZY_NULL_DESC,
    # Encoding unknown / unparseable: upstream throws; pypdfbox resolves no
    # CMap and reads the descendant /DW (1000) for both samples.
    "encoding_missing": (
        "create=ok desc=PDCIDFontType2 csi=Adobe-Identity-0 dw=1000 "
        "cidA=65 cidHi=19968 wA=1000.000 wHi=1000.000 c2g=absent"
    ),
    "encoding_unknown_name": (
        "create=ok desc=PDCIDFontType2 csi=Adobe-Identity-0 dw=1000 "
        "cidA=65 cidHi=19968 wA=1000.000 wHi=1000.000 c2g=absent"
    ),
    # Empty CMap stream: no codespace -> codeToCID echoes 0 for both samples.
    "encoding_empty_stream": (
        "create=ok desc=PDCIDFontType2 csi=Adobe-Identity-0 dw=1000 "
        "cidA=0 cidHi=0 wA=1000.000 wHi=1000.000 c2g=absent"
    ),
}


def _py_verdict(name: str, font_dict: COSDictionary) -> str:
    """Reproduce the probe's CASE line for pypdfbox."""
    del name
    try:
        font = PDFontFactory.create_font(font_dict)
    except Exception as exc:  # noqa: BLE001
        return f"create=ERR:{type(exc).__name__}"
    if not isinstance(font, PDType0Font):
        return "create=ERR:NotType0"
    try:
        desc = font.get_descendant_font()
    except Exception:  # noqa: BLE001
        desc = None
    desc_name = "null" if desc is None else type(desc).__name__
    if desc is None:
        csi_str = "null"
    else:
        try:
            info = font.get_cid_system_info()
            csi_str = "null" if info is None else str(info)
        except Exception:  # noqa: BLE001
            csi_str = "null"
    try:
        dw = (
            "-"
            if desc is None
            else str(desc.get_cos_object().get_int(_DW, 1000))
        )
    except Exception:  # noqa: BLE001
        dw = "ERR"
    cid_a = _sample_cid(font, 0x0041)
    cid_hi = _sample_cid(font, 0x4E00)
    w_a = _sample_width(font, 0x0041)
    w_hi = _sample_width(font, 0x4E00)
    c2g = "-" if desc is None else _cid_to_gid_kind(desc)
    return (
        f"create=ok desc={desc_name} csi={csi_str} dw={dw} "
        f"cidA={cid_a} cidHi={cid_hi} wA={w_a} wHi={w_hi} c2g={c2g}"
    )


def _sample_cid(font: PDType0Font, code: int) -> str:
    try:
        return str(font.code_to_cid(code))
    except Exception:  # noqa: BLE001
        return "ERR"


def _sample_width(font: PDType0Font, code: int) -> str:
    try:
        return f"{float(font.get_width(code)):.3f}"
    except Exception:  # noqa: BLE001
        return "ERR"


def _cid_to_gid_kind(desc: object) -> str:
    """Mirror the Java probe's ``cidToGidKind`` — read the raw COS entry."""
    cos = desc.get_cos_object()
    subtype = cos.get_name_as_string(_SUBTYPE)
    if subtype != "CIDFontType2":
        return "-"
    entry = cos.get_dictionary_object(_CID_TO_GID_MAP)
    if entry is None:
        return "absent"
    if isinstance(entry, COSStream):
        return "stream"
    if isinstance(entry, COSName):
        nm = entry.name
        return "Identity" if nm == "Identity" else f"name:{nm}"
    return type(entry).__name__


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


def _tokens(verdict: str) -> dict[str, str]:
    toks: dict[str, str] = {}
    for part in verdict.split():
        k, _, v = part.partition("=")
        toks[k] = v
    return toks


def _verdicts_match(java: str, py: str) -> bool:
    """Compare two verdict strings; width tokens compared numerically."""
    if not (java.startswith("create=ok") and py.startswith("create=ok")):
        return java == py
    jt, pt = _tokens(java), _tokens(py)
    if set(jt) != set(pt):
        return False
    for k in jt:
        jv, pv = jt[k], pt[k]
        if k in ("wA", "wHi"):
            if jv == "ERR" or pv == "ERR":
                if jv != pv:
                    return False
                continue
            try:
                if abs(float(jv) - float(pv)) > _TOL and not (
                    math.isnan(float(jv)) and math.isnan(float(pv))
                ):
                    return False
            except ValueError:
                return False
        elif jv != pv:
            return False
    return True


@requires_oracle
def test_type0_font_fuzz_matches_pdfbox() -> None:
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
        py = _py_verdict(name, font_dict)

        if name in _DIVERGENCES:
            expected_py = _DIVERGENCES[name]
            if _verdicts_match(java, expected_py):
                mismatches.append(
                    f"{name}: divergence collapsed — java now matches "
                    f"pypdfbox ({java!r}); drop it from _DIVERGENCES"
                )
            if not _verdicts_match(expected_py, py):
                mismatches.append(
                    f"{name}: py={py!r} != pinned {expected_py!r}"
                )
            continue

        if not _verdicts_match(java, py):
            mismatches.append(f"{name}: java={java!r} py={py!r}")

    assert not mismatches, "type0/CID fuzz divergences:\n" + "\n".join(
        mismatches
    )


@requires_oracle
def test_probe_covers_the_composite_leniency_surface() -> None:
    """Sanity: the corpus spans the documented Type 0 / CID leniency axes."""
    probe = _parse_probe(run_probe_text(_PROBE))
    assert any(k.startswith("desc_") for k in probe)
    assert any(k.startswith("descendants_") for k in probe)
    assert any(k.startswith("encoding_") for k in probe)
    assert any(k.startswith("w_") for k in probe)
    assert any(k.startswith("dw_") for k in probe)
    assert any(k.startswith("cid2gid_") for k in probe)
    assert any(k.startswith("csi_") for k in probe)
    # The /CIDToGIDMap KIND axis must be exercised end-to-end.
    assert "c2g=stream" in probe["cid2gid_stream"]
    assert "c2g=Identity" in probe["cid2gid_identity"]


def test_supplement_default_is_minus_one_oracle_free() -> None:
    """Frozen contract (the production fix this wave landed): an absent /
    non-numeric ``/Supplement`` reads back as ``-1`` (upstream
    ``COSDictionary.getInt`` one-arg default), not 0. Drives the same dicts
    the probe's ``csi_no_supplement`` / ``csi_empty_dict`` / ``csi_as_array``
    cases use, without needing Java."""
    cases = _build_cases()
    for case in ("csi_no_supplement", "csi_empty_dict"):
        font = PDFontFactory.create_font(cases[case])
        info = font.get_cid_system_info()
        assert info is not None
        assert info.get_supplement() == -1


def test_w_table_form_lookups_oracle_free() -> None:
    """Frozen contract: /W form-1 ``c [w...]`` and form-2 ``c1 c2 w`` both map
    code 'A' (CID 65 under Identity-H), and an out-of-order range assigns
    nothing (falls to /DW)."""
    cases = _build_cases()
    f1 = PDFontFactory.create_font(cases["w_form1_covers_A"])
    assert f1.get_width(0x41) == pytest.approx(600.0, abs=_TOL)
    f2 = PDFontFactory.create_font(cases["w_form2_range_covers_A"])
    assert f2.get_width(0x41) == pytest.approx(777.0, abs=_TOL)
    ooo = PDFontFactory.create_font(cases["w_form2_out_of_order"])
    assert ooo.get_width(0x41) == pytest.approx(1000.0, abs=_TOL)
