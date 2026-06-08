"""Live Apache PDFBox differential fuzz of
``PDAnnotation.create_annotation(COSBase)`` dispatch + per-subtype geometry
accessor leniency (wave 1515, agent A).

The existing annotation oracle suite covers the well-formed-dispatch surface
(``test_annotation_factory_oracle`` — a handful of subtypes with a clean
/Subtype) and the heavy appearance-stream generators pinned in waves
1508/1509. None exercise the MALFORMED CONSTRUCTION + GEOMETRY subset a buggy
or hostile producer can emit:

  - /Subtype missing / unknown / mistyped (a COSString instead of a COSName) /
    lowercase / empty -> which concrete class create_annotation returns
    (typed subclass vs the generic ``PDAnnotationUnknown`` fallback).
  - /Rect missing / wrong-arity (2, 3, 5) / non-numeric member / inverted.
  - per-subtype geometry through the typed accessor: /QuadPoints (text-markup
    & Link), /L (Line), /Vertices (Polygon/PolyLine), /InkList (Ink,
    array-of-arrays), /CL callout + /RD rect-differences (FreeText) — each
    fuzzed with wrong arity, non-numeric members, wrong COS type, nested-array
    shape errors.
  - /C color arity, /CA constant alpha (real/int/string/missing), /F flags.

Strategy (mirrors wave-1513 ActionFactory fuzz): build the deterministic
corpus of annotation dictionaries directly as COS, embed them as entries of a
non-standard ``/FuzzAnnots`` COSArray hung off the document catalog, and save
ONE ``corpus.pdf`` plus a ``manifest.txt`` (one case name per line, in array
order) into a tmp dir. The ``AnnotationDispatchFuzzProbe`` loads that single
pdf, walks the array, feeds each raw COSDictionary to
``PDAnnotation.createAnnotation`` and projects a stable framed line. Both
libraries read the exact same bytes on disk, so the contract is comparable.

Validation, not blind pinning: the Java line is ground truth. Each case asserts
pypdfbox's ``PDAnnotation.create_annotation`` produces the identical
``class=... rect=... geom=... color=... ca=... flags=...`` line. A real
divergence is fixed in production; a defensible robustness divergence is pinned
in ``_PINNED_DIVERGENCES`` with a reason + a matching CHANGES.md row.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNumber,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationFreeText,
    PDAnnotationInk,
    PDAnnotationLine,
    PDAnnotationMarkup,
    PDAnnotationPolygon,
    PDAnnotationPolyline,
    PDAnnotationTextMarkup,
)
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _n(name: str) -> COSName:
    return COSName.get_pdf_name(name)


# --------------------------------------------------------------- COS builders


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _nums(*vals: float) -> COSArray:
    return _arr(*[COSInteger.get(int(v)) if float(v).is_integer()
                  else COSFloat(float(v)) for v in vals])


def _annot(sub: str | None, **entries: COSBase) -> COSDictionary:
    """An annotation dict with /Type /Annot and the given /Subtype + entries.

    ``sub`` of None omits /Subtype. To set /Subtype mistyped (a COSString) pass
    it through ``entries`` (Subtype=COSString(...)) and leave ``sub`` None.
    """
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Annot"))
    if sub is not None:
        d.set_item(_n("Subtype"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, COSDictionary]:
    """Deterministic, ordered annotation-dictionary corpus."""
    c: dict[str, COSDictionary] = {}

    # ----- /Subtype dispatch edge cases -----
    c["sub_missing"] = _annot(None)
    c["sub_unknown"] = _annot("BogusAnnot")
    c["sub_empty"] = _annot("")
    c["sub_lowercase_link"] = _annot("link")
    # /Subtype as a COSString (mistyped) — getNameAsString still resolves it.
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Annot"))
    d.set_item(_n("Subtype"), COSString("Link"))
    c["sub_as_string"] = d
    c["sub_widget"] = _annot("Widget")
    c["sub_popup"] = _annot("Popup")
    c["sub_movie"] = _annot("Movie")
    c["sub_screen"] = _annot("Screen")
    c["sub_printermark"] = _annot("PrinterMark")
    c["sub_caret"] = _annot("Caret")
    c["sub_stamp"] = _annot("Stamp")
    c["sub_redact"] = _annot("Redact")
    c["sub_watermark"] = _annot("Watermark")
    c["sub_fileattach"] = _annot("FileAttachment")
    c["sub_sound"] = _annot("Sound")
    c["sub_3d"] = _annot("3D")
    c["sub_trapnet"] = _annot("TrapNet")

    # ----- /Rect edge cases (on a plain Text annot) -----
    c["rect_good"] = _annot("Text", Rect=_nums(10, 20, 110, 220))
    c["rect_missing"] = _annot("Text")
    c["rect_two"] = _annot("Text", Rect=_nums(10, 20))
    c["rect_three"] = _annot("Text", Rect=_nums(10, 20, 30))
    c["rect_five"] = _annot("Text", Rect=_nums(10, 20, 30, 40, 50))
    c["rect_inverted"] = _annot("Text", Rect=_nums(110, 220, 10, 20))
    c["rect_nonnumeric"] = _annot(
        "Text", Rect=_arr(COSInteger.get(0), _n("X"), COSInteger.get(2), COSInteger.get(3))
    )
    c["rect_not_array"] = _annot("Text", Rect=COSString("0 0 1 1"))

    # ----- /L (Line) -----
    c["line_good"] = _annot("Line", L=_nums(0, 0, 100, 100))
    c["line_missing"] = _annot("Line")
    c["line_two"] = _annot("Line", L=_nums(0, 0))
    c["line_six"] = _annot("Line", L=_nums(0, 0, 1, 2, 3, 4))
    c["line_nonnumeric"] = _annot(
        "Line", L=_arr(COSInteger.get(0), _n("Y"), COSInteger.get(2), COSInteger.get(3))
    )
    c["line_not_array"] = _annot("Line", L=COSInteger.get(5))

    # ----- /QuadPoints (text-markup) -----
    c["hl_qp_good"] = _annot("Highlight", QuadPoints=_nums(0, 0, 1, 0, 0, 1, 1, 1))
    c["hl_qp_missing"] = _annot("Highlight")  # ctor seeds empty array
    c["hl_qp_odd"] = _annot("Highlight", QuadPoints=_nums(0, 0, 1, 0, 0))
    c["hl_qp_nonnumeric"] = _annot(
        "Highlight",
        QuadPoints=_arr(COSInteger.get(0), _n("Q"), COSInteger.get(2)),
    )
    c["hl_qp_not_array"] = _annot("Highlight", QuadPoints=COSInteger.get(9))
    c["underline_qp"] = _annot("Underline", QuadPoints=_nums(0, 0, 1, 1, 2, 2, 3, 3))
    c["strikeout_qp"] = _annot("StrikeOut", QuadPoints=_nums(4, 4, 5, 5, 6, 6, 7, 7))
    c["squiggly_qp"] = _annot("Squiggly", QuadPoints=_nums(8, 8, 9, 9, 10, 10, 11, 11))

    # ----- /Vertices (Polygon / PolyLine) -----
    c["polygon_v_good"] = _annot("Polygon", Vertices=_nums(0, 0, 10, 0, 10, 10))
    c["polygon_v_missing"] = _annot("Polygon")
    c["polygon_v_odd"] = _annot("Polygon", Vertices=_nums(0, 0, 10))
    c["polygon_v_nonnumeric"] = _annot(
        "Polygon", Vertices=_arr(COSInteger.get(0), _n("V"), COSInteger.get(2))
    )
    c["polyline_v_good"] = _annot("PolyLine", Vertices=_nums(1, 1, 2, 2, 3, 3))
    c["polyline_v_not_array"] = _annot("PolyLine", Vertices=COSString("0 0"))

    # ----- /InkList (Ink, array-of-arrays) -----
    c["ink_good"] = _annot(
        "Ink", InkList=_arr(_nums(0, 0, 1, 1), _nums(2, 2, 3, 3))
    )
    c["ink_missing"] = _annot("Ink")
    c["ink_flat"] = _annot("Ink", InkList=_nums(0, 0, 1, 1))  # numbers, not sub-arrays
    c["ink_mixed"] = _annot(
        "Ink", InkList=_arr(_nums(0, 0), COSInteger.get(9), _nums(1, 1))
    )
    c["ink_not_array"] = _annot("Ink", InkList=COSInteger.get(3))
    c["ink_empty"] = _annot("Ink", InkList=_arr())

    # ----- /CL callout + /RD (FreeText) -----
    c["ft_cl4"] = _annot("FreeText", CL=_nums(0, 0, 10, 10))
    c["ft_cl6"] = _annot("FreeText", CL=_nums(0, 0, 5, 5, 10, 10))
    c["ft_cl_odd"] = _annot("FreeText", CL=_nums(0, 0, 10))
    c["ft_cl_nonnumeric"] = _annot(
        "FreeText", CL=_arr(COSInteger.get(0), _n("C"), COSInteger.get(2))
    )
    c["ft_cl_missing"] = _annot("FreeText")
    c["ft_rd_good"] = _annot("FreeText", RD=_nums(1, 2, 3, 4))
    c["ft_rd_short"] = _annot("FreeText", RD=_nums(1, 2))
    c["ft_rd_nonnumeric"] = _annot(
        "FreeText",
        RD=_arr(COSInteger.get(1), _n("R"), COSInteger.get(3), COSInteger.get(4)),
    )

    # ----- /C color arity (on a Text annot) -----
    c["color_empty"] = _annot("Text", C=_arr())
    c["color_gray"] = _annot("Text", C=_nums(0))
    c["color_rgb"] = _annot("Text", C=_nums(1, 0, 0))
    c["color_cmyk"] = _annot("Text", C=_nums(0, 0, 0, 1))
    c["color_five"] = _annot("Text", C=_nums(1, 2, 3, 4, 5))
    c["color_not_array"] = _annot("Text", C=COSInteger.get(0))

    # ----- /CA constant alpha -----
    c["ca_real"] = _annot("Text", CA=COSFloat(0.5))
    c["ca_int"] = _annot("Text", CA=COSInteger.get(1))
    c["ca_string"] = _annot("Text", CA=COSString("0.5"))
    c["ca_missing"] = _annot("Text")

    # ----- /F flags -----
    c["flags_int"] = _annot("Text", F=COSInteger.get(4))
    c["flags_real"] = _annot("Text", F=COSFloat(4.0))
    c["flags_string"] = _annot("Text", F=COSString("4"))
    c["flags_missing"] = _annot("Text")

    return c


# --------------------------------------------------------------- projection
#
# Mirrors AnnotationDispatchFuzzProbe.java exactly.


def _jfloat(f: float) -> str:
    """Render a float as Java ``Float.toString`` does for the simple,
    exactly-float32-representable values used in this corpus (integers and
    short decimals like 0.5). ``COSFloat`` already coerces to float32 on both
    sides, so for these inputs Python ``str(float)`` and Java ``Float.toString``
    agree (both emit "1.0", "0.5", "-3.0", ...)."""
    return str(float(f))


def _fmt_arr(a: list[float] | None) -> str:
    if a is None:
        return "null"
    return "[" + " ".join(_jfloat(x) for x in a) + "]"


def _rect_proj(a: PDAnnotation) -> str:
    try:
        r = a.get_rectangle()
        if r is None:
            return "null"
        return (
            f"{_jfloat(r.get_lower_left_x())},{_jfloat(r.get_lower_left_y())},"
            f"{_jfloat(r.get_width())},{_jfloat(r.get_height())}"
        )
    except Exception as exc:  # noqa: BLE001 - contract probe
        return "ERR:" + _java_exc(exc)


def _rd_proj(m: PDAnnotationMarkup) -> str:
    try:
        r = m.get_rect_difference()
        if r is None:
            return "null"
        return (
            f"{_jfloat(r.get_lower_left_x())},{_jfloat(r.get_lower_left_y())},"
            f"{_jfloat(r.get_width())},{_jfloat(r.get_height())}"
        )
    except Exception as exc:  # noqa: BLE001 - contract probe
        return "ERR:" + _java_exc(exc)


def _geom_proj(a: PDAnnotation) -> str:
    try:
        if isinstance(a, PDAnnotationLine):
            return "L=" + _fmt_arr(a.get_line())
        if isinstance(a, PDAnnotationTextMarkup):
            return "QP=" + _fmt_arr(a.get_quad_points())
        if isinstance(a, PDAnnotationPolygon):
            return "V=" + _fmt_arr(a.get_vertices())
        if isinstance(a, PDAnnotationPolyline):
            return "V=" + _fmt_arr(a.get_vertices())
        if isinstance(a, PDAnnotationInk):
            paths = a.get_ink_paths()
            return "INK=[" + ",".join(_fmt_arr(p) for p in paths) + "]"
        if isinstance(a, PDAnnotationFreeText):
            return "CL=" + _fmt_arr(a.get_callout()) + " RD=" + _rd_proj(a)
        return "n/a"
    except Exception as exc:  # noqa: BLE001 - contract probe
        return "ERR:" + _java_exc(exc)


def _color_proj(a: PDAnnotation) -> str:
    c = a.get_cos_object().get_dictionary_object(_n("C"))
    if isinstance(c, COSArray):
        return "arr" + str(c.size())
    return "null"


def _ca_proj(a: PDAnnotation) -> str:
    ca = a.get_cos_object().get_dictionary_object(_n("CA"))
    if isinstance(ca, COSNumber):
        return _jfloat(ca.float_value())
    return "null"


# Java exception-class name mapping for the rare ERR projection. pypdfbox
# raises Python exceptions; map the ones the geometry/rect accessors can throw
# to the Java simple name the probe would emit. Empty unless a divergence in
# error-raising surfaces during the run.
_EXC_MAP: dict[str, str] = {}


def _java_exc(exc: Exception) -> str:
    return _EXC_MAP.get(type(exc).__name__, type(exc).__name__)


def _py_line(name: str, d: COSDictionary | None) -> str:
    try:
        a = PDAnnotation.create_annotation(d)
        cls = type(a).__name__
        return (
            f"CASE {name} class={cls} rect={_rect_proj(a)} "
            f"geom={_geom_proj(a)} color={_color_proj(a)} "
            f"ca={_ca_proj(a)} flags={a.get_annotation_flags()}"
        )
    except Exception as exc:  # noqa: BLE001 - contract probe
        return f"CASE {name} class=ERR:{_java_exc(exc)}"


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(dir_path: Path, corpus: dict[str, COSDictionary]) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        arr = COSArray()
        for dd in corpus.values():
            arr.add(dd)
        catalog.set_item(_n("FuzzAnnots"), arr)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()
    (dir_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )


# Module-level keep-alive so a reloaded document isn't garbage-collected
# before projection reads its annotation dicts.
_doc_keepalive: list[object] = []


def _reload_corpus(
    dir_path: Path, order: list[str]
) -> dict[str, COSDictionary | None]:
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    out: dict[str, COSDictionary | None] = {}
    catalog = doc.get_document_catalog().get_cos_object()
    arr = catalog.get_dictionary_object(_n("FuzzAnnots"))
    for i, name in enumerate(order):
        entry = arr.get_object(i)
        out[name] = entry if isinstance(entry, COSDictionary) else None
    return out


# --------------------------------------------------------------- pinned diffs

# Intentional, documented divergences from the Java line.
#
# pypdfbox's create_annotation dispatch table is a deliberate SUPERSET of
# upstream PDFBox 3.0.7's truncated switch: Movie, Screen, PrinterMark, Redact,
# Watermark, 3D and TrapNet resolve to their typed subclasses, where upstream
# 3.0.7 falls back to PDAnnotationUnknown. This superset is intentional and is
# already pinned by the value-based tests in test_pd_annotation.py and noted in
# test_annotation_factory_oracle.py; we re-pin it here (CHANGES.md) so the fuzz
# diff stays green without weakening the production dispatch. Each pinned line is
# the pypdfbox projection (typed class), asserted to remain stable.
_PINNED_DIVERGENCES: dict[str, str] = {
    "sub_movie": (
        "CASE sub_movie class=PDAnnotationMovie rect=null geom=n/a "
        "color=null ca=null flags=0"
    ),
    "sub_screen": (
        "CASE sub_screen class=PDAnnotationScreen rect=null geom=n/a "
        "color=null ca=null flags=0"
    ),
    "sub_printermark": (
        "CASE sub_printermark class=PDAnnotationPrinterMark rect=null "
        "geom=n/a color=null ca=null flags=0"
    ),
    "sub_redact": (
        "CASE sub_redact class=PDAnnotationRedact rect=null geom=n/a "
        "color=null ca=null flags=0"
    ),
    "sub_watermark": (
        "CASE sub_watermark class=PDAnnotationWatermark rect=null geom=n/a "
        "color=null ca=null flags=0"
    ),
    "sub_3d": (
        "CASE sub_3d class=PDAnnotation3D rect=null geom=n/a "
        "color=null ca=null flags=0"
    ),
    "sub_trapnet": (
        "CASE sub_trapnet class=PDAnnotationTrapNet rect=null geom=n/a "
        "color=null ca=null flags=0"
    ),
}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_annotation_dispatch_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed / edge-case annotation dict dispatches + projects
    identically on pypdfbox ``PDAnnotation.create_annotation`` and Apache
    PDFBox 3.0.7 ``PDAnnotation.createAnnotation``, reading the same on-disk
    bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("AnnotationDispatchFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )

    reloaded = _reload_corpus(tmp_path, list(corpus))
    py_by_name = {name: _py_line(name, d) for name, d in reloaded.items()}

    mismatches: list[str] = []
    for jline in java_lines:
        name = jline.split(" ", 2)[1]
        pline = py_by_name[name]
        if name in _PINNED_DIVERGENCES:
            if pline != _PINNED_DIVERGENCES[name]:
                mismatches.append(
                    f"{name}: PINNED py expected "
                    f"{_PINNED_DIVERGENCES[name]!r} got {pline!r} "
                    f"(java {jline!r})"
                )
            continue
        if pline != jline:
            mismatches.append(f"{name}:\n  py   {pline}\n  java {jline}")

    assert not mismatches, "annotation-dispatch divergence(s):\n" + "\n".join(
        mismatches
    )
