"""Live PDFBox differential fuzz parity for ``PDViewerPreferences`` (wave 1540,
agent B).

Sibling of ``oracle/probes/ViewerPrefsFuzzProbe.java``. Where the wave-1521
``ViewerPreferencesFuzzProbe`` already drove the boolean / name surface, this
wave widens the corpus to drive *every* upstream-exposed getter
(``getHideToolbar``..``getPrintScaling``) plus a per-field projection of the
enrichment surface (``/NumCopies``, ``/PrintPageRange``, ``/Enforce``,
``/PickTrayByPDFSize``) that PDFBox 3.0.7 has no getter for.

Five subcommands, each emitting ONE canonical line, in identical grammar on
both sides:

* ``bool`` — every boolean flag set to absent / true / false / null / int /
  int-zero / name / string / float / indirect-true / indirect-null. Confirms
  PDFBox's documented default-false semantics: anything that is not an actual
  ``COSBoolean.TRUE`` reads ``false`` (``COSDictionary.getBoolean`` only honours
  a real boolean).
* ``name`` — every name-valued enum field set to valid / bogus-keyword /
  string / empty-string / wrong-type-int / wrong-type-bool / null / indirect
  variants. Confirms the documented enum defaults
  (``NonFullScreenPageMode``→``UseNone``, ``Direction``→``L2R``, the four page
  boundaries→``CropBox``, ``PrintScaling``→``AppDefault``, ``Duplex``→absent
  ⇒ ``NULL`` with no spec default), and that ``getNameAsString`` returns a
  ``COSString``'s decoded text verbatim (the ``string`` / ``empty`` cases) but
  falls back to the default for a non-name / non-string shape (``wrong_*``).
* ``num`` — ``/NumCopies`` as 1 / 3 / 0 / negative / huge(>2^31) / float /
  name / string / null / indirect-zero. Confirms the Table-150 default of 1 and
  the ``>= 1`` clamp (``get_num_copies``), including the 32-bit wraparound of a
  >2^31 integer (``huge`` wraps negative ⇒ clamps to 1, matching Java's
  ``intValue()`` overflow).
* ``range`` — ``/PrintPageRange`` as a valid pair / two pairs / odd-length /
  non-int element / out-of-order / negative / empty array / wrong-type / null.
  Confirms the PDF 32000-2 §12.4.4 pair-decode (``get_print_page_range_pairs``):
  odd-length or non-int arrays decode to the empty list; out-of-order and
  negative pairs are still decoded (validity is a separate predicate).
* ``enforce`` — ``/Enforce`` as a name array / single name / mixed
  name+int / empty / wrong-type / null. Confirms the name-decode
  (``get_enforce_names``) skips non-name elements.

ALL 50 cases reach byte-for-byte parity with the live PDFBox oracle on the
compared portion. NO real production bug was found on this surface — the
boolean default-false resolution, the name-enum defaults, the ``getNameAsString``
coercion, the ``/NumCopies`` clamp + wraparound, and the spec pair/name decoders
are all parity with Apache PDFBox 3.0.7.

One documented, both-sides-pinned divergence FAMILY exists: the enrichment
getters (``get_num_copies`` / ``get_print_page_range`` / ``get_enforce`` and
their decoded companions) are pypdfbox enrichment — PDFBox 3.0.7's
``PDViewerPreferences`` has NO ``getNumCopies`` / ``getPrintPageRange`` /
``getEnforce`` accessor (its probe prints ``api=unsupported``; pypdfbox prints
``api=present``). The *value* each side computes off the raw COS dictionary is
identical; only the presence of the typed getter differs. This is intentional
PDF 32000-1 / 32000-2 Table 150 enrichment, not a bug, so the ``api=`` token is
asserted to diverge (Java unsupported, pypdfbox present) while every other token
on the line is asserted equal.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.pd_viewer_preferences import PDViewerPreferences
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders (mirror ViewerPrefsFuzzProbe helpers) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _ind(v: COSBase) -> COSObject:
    """An indirect reference resolving to ``v`` (mirrors ``new COSObject(v)``)."""
    return COSObject(1, 0, resolved=v)


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _b(v: bool) -> str:
    return "true" if v else "false"


def _nz(v: str | None) -> str:
    return "NULL" if v is None else v


def _raw(value: COSBase | None) -> str:
    """Canonical structural digest of one raw COS value (mirrors Java _raw)."""
    if value is None:
        return "null"
    if isinstance(value, COSBoolean):
        return "bool:" + ("true" if value.value else "false")
    if isinstance(value, COSName):
        return "name:" + value.name
    if isinstance(value, COSString):
        return "string:" + value.get_string()
    if isinstance(value, COSInteger):
        return "int:" + str(value.value)
    if isinstance(value, COSFloat):
        return "float:" + _float_repr(value.value)
    if isinstance(value, COSArray):
        return "array:" + str(value.size())
    if isinstance(value, COSDictionary):
        return "dict"
    return type(value).__name__


def _float_repr(v: float) -> str:
    """Render a float the way Java ``Float.toString`` does for our corpus
    (``2.0f`` -> ``"2.0"``). Our only float case is exactly representable."""
    if v == int(v):
        return f"{int(v)}.0"
    return repr(v)


# ---------- boolean corpus ----------

_BOOLEAN_KEYS = [
    "HideToolbar",
    "HideMenubar",
    "HideWindowUI",
    "FitWindow",
    "CenterWindow",
    "DisplayDocTitle",
    "PickTrayByPDFSize",
]

_BOOL_CASES = [
    "absent",
    "true",
    "false",
    "null",
    "int",
    "int_zero",
    "name",
    "string",
    "float",
    "ind_true",
    "ind_null",
]


def _bool_value(case: str) -> COSBase:
    return {
        "true": COSBoolean.TRUE,
        "false": COSBoolean.FALSE,
        "null": COSNull.NULL,
        "int": COSInteger.ONE,
        "int_zero": COSInteger.ZERO,
        "name": _n("true"),
        "string": COSString("true"),
        "float": COSFloat(1.0),
        "ind_true": _ind(COSBoolean.TRUE),
        "ind_null": _ind(COSNull.NULL),
    }[case]


def _emit_bool(case: str) -> str:
    d = COSDictionary()
    if case != "absent":
        value = _bool_value(case)
        for key in _BOOLEAN_KEYS:
            d.set_item(_n(key), value)
    p = PDViewerPreferences(d)
    pt = d.get_boolean(_n("PickTrayByPDFSize"), False)
    return (
        f"ht={_b(p.hide_toolbar())}"
        f" hm={_b(p.hide_menubar())}"
        f" hw={_b(p.hide_window_ui())}"
        f" fw={_b(p.fit_window())}"
        f" cw={_b(p.center_window())}"
        f" dd={_b(p.display_doc_title())}"
        f" pt={_b(pt)}"
    )


# ---------- name corpus ----------

_NAME_KEYS = [
    "NonFullScreenPageMode",
    "Direction",
    "ViewArea",
    "ViewClip",
    "PrintArea",
    "PrintClip",
    "Duplex",
    "PrintScaling",
]
_NAME_VALID = [
    "UseOutlines",
    "R2L",
    "MediaBox",
    "BleedBox",
    "TrimBox",
    "ArtBox",
    "Simplex",
    "None",
]

_NAME_CASES = [
    "absent",
    "valid",
    "bogus",
    "string",
    "empty",
    "wrong_int",
    "wrong_bool",
    "null",
    "ind_valid",
    "ind_string",
    "ind_null",
]


def _name_value(case: str, valid: str) -> COSBase:
    return {
        "valid": _n(valid),
        "bogus": _n("Bogus"),
        "string": COSString("Text"),
        "empty": COSString(""),
        "wrong_int": COSInteger.ONE,
        "wrong_bool": COSBoolean.TRUE,
        "null": COSNull.NULL,
        "ind_valid": _ind(_n(valid)),
        "ind_string": _ind(COSString("Text")),
        "ind_null": _ind(COSNull.NULL),
    }[case]


def _emit_name(case: str) -> str:
    d = COSDictionary()
    if case != "absent":
        for i, key in enumerate(_NAME_KEYS):
            d.set_item(_n(key), _name_value(case, _NAME_VALID[i]))
    p = PDViewerPreferences(d)
    return (
        f"nfs={_nz(p.get_non_full_screen_page_mode())}"
        f" dir={_nz(p.get_reading_direction())}"
        f" va={_nz(p.get_view_area())}"
        f" vc={_nz(p.get_view_clip())}"
        f" pa={_nz(p.get_print_area())}"
        f" pc={_nz(p.get_print_clip())}"
        f" dup={_nz(p.get_duplex())}"
        f" ps={_nz(p.get_print_scaling())}"
    )


# ---------- /NumCopies corpus ----------

_NUM_CASES = [
    "absent",
    "one",
    "three",
    "zero",
    "negative",
    "huge",
    "float",
    "name",
    "string",
    "null",
    "ind_zero",
]


def _num_value(case: str) -> COSBase:
    return {
        "one": COSInteger.ONE,
        "three": COSInteger.get(3),
        "zero": COSInteger.ZERO,
        "negative": COSInteger.get(-5),
        "huge": COSInteger.get(2147483648),
        "float": COSFloat(2.0),
        "name": _n("Three"),
        "string": COSString("3"),
        "null": COSNull.NULL,
        "ind_zero": _ind(COSInteger.ZERO),
    }[case]


def _emit_num(case: str) -> str:
    d = COSDictionary()
    if case != "absent":
        d.set_item(_n("NumCopies"), _num_value(case))
    p = PDViewerPreferences(d)
    v = d.get_dictionary_object(_n("NumCopies"))
    # pypdfbox HAS get_num_copies (enrichment); Java does not. The decoded
    # spec int is identical on both sides.
    return f"api=present raw={_raw(v)} spec={p.get_num_copies()}"


# ---------- /PrintPageRange corpus ----------

_RANGE_CASES = [
    "absent",
    "pair",
    "two_pairs",
    "odd",
    "nonint",
    "out_order",
    "negative",
    "empty",
    "wrong",
    "null",
]


def _range_value(case: str) -> COSBase:
    return {
        "pair": _arr(COSInteger.ONE, COSInteger.get(3)),
        "two_pairs": _arr(
            COSInteger.ONE, COSInteger.get(3), COSInteger.get(5), COSInteger.get(9)
        ),
        "odd": _arr(COSInteger.ONE, COSInteger.get(3), COSInteger.get(5)),
        "nonint": _arr(COSInteger.ONE, _n("Two")),
        "out_order": _arr(COSInteger.get(9), COSInteger.ONE),
        "negative": _arr(COSInteger.get(-1), COSInteger.get(3)),
        "empty": COSArray(),
        "wrong": COSDictionary(),
        "null": COSNull.NULL,
    }[case]


def _emit_range(case: str) -> str:
    d = COSDictionary()
    if case != "absent":
        d.set_item(_n("PrintPageRange"), _range_value(case))
    p = PDViewerPreferences(d)
    v = d.get_dictionary_object(_n("PrintPageRange"))
    pairs = ";".join(f"{s},{e}" for s, e in p.get_print_page_range_pairs())
    return f"api=present raw={_raw(v)} pairs=[{pairs}]"


# ---------- /Enforce corpus ----------

_ENFORCE_CASES = [
    "absent",
    "names",
    "one_name",
    "mixed",
    "empty",
    "wrong",
    "null",
]


def _enforce_value(case: str) -> COSBase:
    return {
        "names": _arr(_n("PrintScaling"), _n("Duplex")),
        "one_name": _arr(_n("PrintScaling")),
        "mixed": _arr(_n("Direction"), COSInteger.ONE, _n("Duplex")),
        "empty": COSArray(),
        "wrong": _n("PrintScaling"),
        "null": COSNull.NULL,
    }[case]


def _emit_enforce(case: str) -> str:
    d = COSDictionary()
    if case != "absent":
        d.set_item(_n("Enforce"), _enforce_value(case))
    p = PDViewerPreferences(d)
    v = d.get_dictionary_object(_n("Enforce"))
    names = ",".join(p.get_enforce_names())
    return f"api=present raw={_raw(v)} names=[{names}]"


# ---------- documented divergence: enrichment getters absent upstream ----------
#
# Subcommands whose Java line carries an ``api=`` token that pypdfbox emits as
# ``present`` while PDFBox 3.0.7 emits ``unsupported``. Every OTHER token on the
# line is asserted equal. (The boolean / name subcommands carry no ``api=``
# token and are compared verbatim.)
_ENRICHMENT_SUBCOMMANDS = {"num", "range", "enforce"}


def _split_tokens(line: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tok in line.split(" "):
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k] = v
        else:  # token with a space inside a bracket; rejoin later
            out.setdefault("_extra", "")
            out["_extra"] += " " + tok
    return out


# ---------- dispatch ----------

_EMITTERS = {
    "bool": _emit_bool,
    "name": _emit_name,
    "num": _emit_num,
    "range": _emit_range,
    "enforce": _emit_enforce,
}

_CASE_LISTS = {
    "bool": _BOOL_CASES,
    "name": _NAME_CASES,
    "num": _NUM_CASES,
    "range": _RANGE_CASES,
    "enforce": _ENFORCE_CASES,
}


def _all_cases() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for sub, cases in _CASE_LISTS.items():
        for case in cases:
            out.append((sub, case))
    return out


@pytest.fixture(scope="module")
def _java() -> dict[tuple[str, str], str]:
    """Run the live oracle once per (subcommand, case); cache the line."""
    out: dict[tuple[str, str], str] = {}
    for sub, case in _all_cases():
        out[(sub, case)] = run_probe_text("ViewerPrefsFuzzProbe", sub, case).strip()
    return out


@requires_oracle
def test_corpus_count() -> None:
    """50 fuzz cases across the five subcommands; no duplicate names per sub."""
    cases = _all_cases()
    assert len(cases) == 50, f"expected 50 cases, built {len(cases)}"
    for sub, lst in _CASE_LISTS.items():
        assert len(lst) == len(set(lst)), f"duplicate case in {sub}"


@requires_oracle
@pytest.mark.parametrize(
    "sub,case",
    _all_cases(),
    ids=[f"{s}-{c}" for s, c in _all_cases()],
)
def test_viewer_prefs_fuzz_case(
    sub: str, case: str, _java: dict[tuple[str, str], str]
) -> None:
    """Each case's pypdfbox digest matches the live PDFBox oracle.

    Boolean and name subcommands match the whole line verbatim. Enrichment
    subcommands match every token except the documented ``api=`` divergence
    (pypdfbox ``present`` vs PDFBox 3.0.7 ``unsupported``)."""
    py_line = _EMITTERS[sub](case)
    java_line = _java[(sub, case)]

    if sub not in _ENRICHMENT_SUBCOMMANDS:
        assert py_line == java_line, (
            f"{sub}-{case}: pypdfbox diverged from the live PDFBox oracle.\n"
            f"  pypdfbox: {py_line!r}\n  pdfbox  : {java_line!r}"
        )
        return

    # Enrichment: pin the api= divergence both sides, compare the rest.
    py_tokens = _split_tokens(py_line)
    java_tokens = _split_tokens(java_line)
    assert py_tokens.get("api") == "present", (
        f"{sub}-{case}: pypdfbox should expose the enrichment getter "
        f"(api=present); got {py_tokens.get('api')!r}"
    )
    assert java_tokens.get("api") == "unsupported", (
        f"{sub}-{case}: PDFBox 3.0.7 unexpectedly now exposes this enrichment "
        f"getter (api={java_tokens.get('api')!r}). The documented divergence "
        f"(upstream has no getNumCopies/getPrintPageRange/getEnforce) no longer "
        f"holds — drop the api= pin and compare the line verbatim."
    )
    # Every non-api token must be byte-identical.
    py_rest = {k: v for k, v in py_tokens.items() if k != "api"}
    java_rest = {k: v for k, v in java_tokens.items() if k != "api"}
    assert py_rest == java_rest, (
        f"{sub}-{case}: enrichment value diverged from the live PDFBox oracle "
        f"(off the raw /ViewerPreferences dictionary).\n"
        f"  pypdfbox: {py_line!r}\n  pdfbox  : {java_line!r}"
    )
