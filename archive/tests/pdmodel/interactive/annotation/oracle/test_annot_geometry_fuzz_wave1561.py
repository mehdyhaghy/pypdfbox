"""Live Apache PDFBox differential fuzz of the GEOMETRY ACCESSORS of the markup
annotations (wave 1561, agent A).

The appearance-handler fuzz of wave 1544 drives the ``/AP`` stream GENERATORS;
the type-accessor fuzz of wave 1554 covers the scalar accessors of the OTHER
subtypes. Neither projects the raw geometry arrays a buggy or hostile producer
can stuff into these dictionaries:

  - Square/Circle: get_rect_differences (/RD four/short/long/negative/
    non-numeric/non-array) -> float list; get_interior_color (/IC arity
    0/1/3/4/non-array) -> PDColor.
  - Polygon: get_vertices (/Vertices odd/empty/non-numeric/non-array).
  - Polyline: get_vertices; get_start_point_ending_style /
    get_end_point_ending_style (/LE valid/unknown/string/short).
  - Ink: get_ink_paths (/InkList empty/flat/nested/non-array/mixed) -> float[][].
  - Line: get_line (/L short/long/non-numeric/non-array); get_interior_color.

Strategy (mirrors the wave-1554 sibling): build the deterministic corpus of
annotation dictionaries directly as COS, embed them as entries of a
non-standard ``/FuzzAnnots`` COSArray hung off the document catalog and save ONE
``corpus.pdf`` plus a ``manifest.txt`` (one case name per line, array order).
``AnnotGeometryFuzzProbe`` loads that pdf, walks the array, feeds each raw
COSDictionary to ``PDAnnotation.createAnnotation`` and projects a stable framed
line. Both libraries read the exact same bytes on disk.

Validation, not blind pinning: the Java line is ground truth. Each case asserts
pypdfbox's ``PDAnnotation.create_annotation`` produces the identical projection.

Findings (all parity-clean for the surfaces compared against the oracle):
  - get_rect_differences (square/circle) reads via getCOSArray + toFloatArray
    with NO arity check — a short/long/non-numeric /RD round-trips byte-for-byte
    (non-numeric members become 0.0). Absent/non-array -> empty list (upstream
    float[0]).
  - get_vertices / get_line read the WHOLE array via toFloatArray, no slicing;
    None only when the entry is absent or not a COSArray.
  - get_ink_paths mirrors float[][]: empty list when absent, empty inner list
    for a non-array entry.
  - get_interior_color of square/circle/line returns the raw /IC array whose
    components equal PDColor.getComponents() for ANY arity (including 0/2/5,
    where upstream's colourspace is null but the PDColor object is non-null).
    None only when /IC is absent or not a COSArray -> matches upstream null.
  - /LE endpoint styles: upstream guards size() >= 2, reads via
    COSArray.getName(index, "None") — a non-COSName entry (e.g. a COSString)
    resolves to "None". pypdfbox matches both the guard and the name-only read.

DIVERGENCE pinned self-contained (NOT compared against the oracle): the polygon
/polyline ``get_interior_color`` is a lite accessor returning a 3-tuple
[r, g, b] ONLY when arity >= 3, else None (typed PDColor lands with the
rendering cluster, PRD 6.12). Upstream returns a non-null PDColor for arity
1/4 too. This is the documented lite-accessor divergence; the polygon /IC is
therefore omitted from the probe's polygon projection.
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
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationCircle,
    PDAnnotationInk,
    PDAnnotationLine,
    PDAnnotationPolygon,
    PDAnnotationPolyline,
    PDAnnotationSquare,
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
    return _arr(
        *[
            COSInteger.get(int(v)) if float(v).is_integer() else COSFloat(float(v))
            for v in vals
        ]
    )


def _annot(sub: str, **entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Annot"))
    d.set_item(_n("Subtype"), _n(sub))
    for k, v in entries.items():
        d.set_item(_n(k), v)
    return d


# --------------------------------------------------------------- corpus build


def _build_corpus() -> dict[str, COSDictionary]:
    c: dict[str, COSDictionary] = {}

    # ----- Square /RD + /IC -----
    c["sq_rd_four"] = _annot("Square", RD=_nums(1, 2, 3, 4))
    c["sq_rd_missing"] = _annot("Square")  # -> empty list / float[0]
    c["sq_rd_short"] = _annot("Square", RD=_nums(1, 2))
    c["sq_rd_long"] = _annot("Square", RD=_nums(1, 2, 3, 4, 5))
    c["sq_rd_negative"] = _annot("Square", RD=_nums(-1, -2.5, 3, 4))
    c["sq_rd_nonnumeric"] = _annot(
        "Square",
        RD=_arr(COSInteger.get(1), _n("X"), COSString("y"), COSInteger.get(4)),
    )
    c["sq_rd_not_array"] = _annot("Square", RD=COSInteger.get(7))  # -> empty list
    c["sq_ic_three"] = _annot("Square", IC=_nums(1, 0, 0))
    c["sq_ic_one"] = _annot("Square", IC=_nums(0.5))
    c["sq_ic_four"] = _annot("Square", IC=_nums(0, 0, 0, 1))
    c["sq_ic_zero"] = _annot("Square", IC=_arr())  # empty -> non-null PDColor []
    c["sq_ic_two"] = _annot("Square", IC=_nums(0.2, 0.4))  # arity 2 -> null cs
    c["sq_ic_missing"] = _annot("Square")  # -> null
    c["sq_ic_not_array"] = _annot("Square", IC=COSString("red"))  # -> null

    # ----- Circle (shares the SquareCircle base) -----
    c["ci_rd_four"] = _annot("Circle", RD=_nums(5, 4, 3, 2))
    c["ci_ic_three"] = _annot("Circle", IC=_nums(0, 1, 0))
    c["ci_rd_not_array"] = _annot("Circle", RD=_n("Bogus"))

    # ----- Polygon /Vertices -----
    c["poly_v_even"] = _annot("Polygon", Vertices=_nums(0, 0, 10, 0, 10, 10))
    c["poly_v_odd"] = _annot("Polygon", Vertices=_nums(0, 0, 10, 0, 5))
    c["poly_v_empty"] = _annot("Polygon", Vertices=_arr())
    c["poly_v_nonnumeric"] = _annot(
        "Polygon", Vertices=_arr(COSInteger.get(1), _n("Z"), COSInteger.get(3))
    )
    c["poly_v_not_array"] = _annot("Polygon", Vertices=COSInteger.get(4))  # -> null
    c["poly_v_missing"] = _annot("Polygon")  # -> null

    # ----- Polyline /Vertices + /LE -----
    c["pl_v_even"] = _annot("PolyLine", Vertices=_nums(1, 2, 3, 4))
    c["pl_le_valid"] = _annot(
        "PolyLine",
        Vertices=_nums(1, 2, 3, 4),
        LE=_arr(_n("OpenArrow"), _n("Diamond")),
    )
    c["pl_le_unknown"] = _annot(
        "PolyLine", LE=_arr(_n("Bogus"), _n("AlsoBogus"))
    )
    c["pl_le_short"] = _annot("PolyLine", LE=_arr(_n("Square")))  # -> None,None
    c["pl_le_string"] = _annot(
        "PolyLine", LE=_arr(COSString("Square"), _n("Circle"))
    )  # start non-name -> None
    c["pl_le_missing"] = _annot("PolyLine")  # -> None,None

    # ----- Ink /InkList -----
    c["ink_nested"] = _annot(
        "Ink", InkList=_arr(_nums(0, 0, 1, 1), _nums(2, 2, 3, 3, 4, 4))
    )
    c["ink_empty_outer"] = _annot("Ink", InkList=_arr())  # -> []
    c["ink_flat"] = _annot("Ink", InkList=_nums(0, 0, 1, 1))  # flat -> inner []s
    c["ink_mixed"] = _annot(
        "Ink", InkList=_arr(_nums(0, 0), COSInteger.get(9), _nums(1, 1))
    )  # non-array entry -> empty inner
    c["ink_not_array"] = _annot("Ink", InkList=COSInteger.get(3))  # -> []
    c["ink_missing"] = _annot("Ink")  # -> []

    # ----- Line /L + /LE + /IC -----
    c["ln_l_four"] = _annot("Line", L=_nums(0, 0, 100, 100))
    c["ln_l_short"] = _annot("Line", L=_nums(0, 0))
    c["ln_l_long"] = _annot("Line", L=_nums(0, 0, 1, 1, 2, 2))
    c["ln_l_nonnumeric"] = _annot(
        "Line", L=_arr(COSInteger.get(0), _n("Q"), COSInteger.get(2), COSInteger.get(3))
    )
    c["ln_l_not_array"] = _annot("Line", L=COSString("nope"))  # -> None
    c["ln_le_ic"] = _annot(
        "Line",
        L=_nums(0, 0, 1, 1),
        LE=_arr(_n("Circle"), _n("None")),
        IC=_nums(1, 1, 0),
    )

    return c


# --------------------------------------------------------------- projection
#
# Mirrors AnnotGeometryFuzzProbe.java exactly.


def _canon(value: float) -> str:
    # Round half-even to 3 decimals; strip trailing zeros; normalise -0.
    q = round(value, 3)
    if q == 0:
        q = 0.0
    s = f"{q:.3f}".rstrip("0").rstrip(".")
    if s in ("", "-0"):
        s = "0"
    return s


def _floats(a: list[float] | None) -> str:
    if a is None:
        return "null"
    return "[" + " ".join(_canon(x) for x in a) + "]"


def _floats2(a: list[list[float]] | None) -> str:
    if a is None:
        return "null"
    return "[" + " ".join(_floats(inner) for inner in a) + "]"


def _color(comps: list[float] | None) -> str:
    """Mirror the Java probe's PDColor projection. pypdfbox square/circle/line
    get_interior_color returns the raw /IC float list (or None) — equal to
    PDColor.getComponents(); None maps to upstream null."""
    if comps is None:
        return "null"
    return "C" + _floats(comps)


def _interior_color_components(a: PDAnnotation) -> list[float] | None:
    """Square/Circle return the raw COSArray; Line returns a float list. Both
    surface the components directly — equal to PDColor.getComponents() on the
    Java side. Normalised to a plain list | None."""
    ic = a.get_interior_color()
    if ic is None:
        return None
    if isinstance(ic, COSArray):
        return ic.to_float_array()
    return list(ic)


def _acc_proj(a: PDAnnotation) -> str:
    try:
        if isinstance(a, (PDAnnotationSquare, PDAnnotationCircle)):
            return (
                f"rd={_floats(a.get_rect_differences())} "
                f"ic={_color(_interior_color_components(a))}"
            )
        if isinstance(a, PDAnnotationPolygon):
            return f"v={_floats(a.get_vertices())}"
        if isinstance(a, PDAnnotationPolyline):
            return (
                f"v={_floats(a.get_vertices())} "
                f"le={a.get_start_point_ending_style()},"
                f"{a.get_end_point_ending_style()}"
            )
        if isinstance(a, PDAnnotationInk):
            return f"ink={_floats2(a.get_ink_paths())}"
        if isinstance(a, PDAnnotationLine):
            return (
                f"l={_floats(a.get_line())} "
                f"le={a.get_start_point_ending_style()},"
                f"{a.get_end_point_ending_style()} "
                f"ic={_color(_interior_color_components(a))}"
            )
        return "n/a"
    except Exception as exc:  # noqa: BLE001 - contract probe
        return "ERR:" + type(exc).__name__


def _py_line(name: str, d: COSDictionary | None) -> str:
    try:
        a = PDAnnotation.create_annotation(d)
        return f"CASE {name} {_acc_proj(a)}"
    except Exception as exc:  # noqa: BLE001 - contract probe
        return f"CASE {name} ERR:{type(exc).__name__}"


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
    (dir_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")


# Module-level keep-alive so a reloaded document isn't garbage-collected before
# projection reads its annotation dicts.
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


# --------------------------------------------------------------------- tests


@requires_oracle
def test_annot_geometry_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed / edge-case geometry array projects identically on
    pypdfbox and Apache PDFBox 3.0.7, reading the same on-disk bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("AnnotGeometryFuzzProbe", str(tmp_path))
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
        if pline != jline:
            mismatches.append(f"{name}:\n  py   {pline}\n  java {jline}")

    assert not mismatches, "annotation geometry divergence(s):\n" + "\n".join(
        mismatches
    )


def test_rect_differences_no_arity_check() -> None:
    """get_rect_differences returns the WHOLE /RD via to_float_array (no arity
    check), empty list when absent or non-array, 0.0 for non-numeric members —
    matching upstream getRectDifferences (getCOSArray + toFloatArray | float[0]).

    Self-contained.
    """
    sq = PDAnnotationSquare(_annot("Square", RD=_nums(1, 2, 3, 4, 5)))
    assert sq.get_rect_differences() == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert PDAnnotationSquare(_annot("Square")).get_rect_differences() == []
    assert (
        PDAnnotationSquare(
            _annot("Square", RD=COSInteger.get(7))
        ).get_rect_differences()
        == []
    )
    nn = PDAnnotationCircle(
        _annot("Circle", RD=_arr(COSInteger.get(1), _n("X"), COSString("y"), COSFloat(4.0)))
    )
    assert nn.get_rect_differences() == [1.0, 0.0, 0.0, 4.0]


def test_vertices_line_inklist_whole_array() -> None:
    """get_vertices / get_line return the whole array (None for non-array);
    get_ink_paths mirrors float[][] (empty list absent, empty inner non-array).

    Self-contained.
    """
    poly = PDAnnotationPolygon(_annot("Polygon", Vertices=_nums(0, 0, 10, 0, 5)))
    assert poly.get_vertices() == [0.0, 0.0, 10.0, 0.0, 5.0]
    assert PDAnnotationPolygon(_annot("Polygon")).get_vertices() is None
    assert (
        PDAnnotationPolygon(
            _annot("Polygon", Vertices=COSInteger.get(4))
        ).get_vertices()
        is None
    )

    line = PDAnnotationLine(_annot("Line", L=_nums(0, 0)))
    assert line.get_line() == [0.0, 0.0]
    assert PDAnnotationLine(_annot("Line", L=COSString("x"))).get_line() is None

    ink = PDAnnotationInk(
        _annot("Ink", InkList=_arr(_nums(0, 0), COSInteger.get(9), _nums(1, 1)))
    )
    assert ink.get_ink_paths() == [[0.0, 0.0], [], [1.0, 1.0]]
    assert PDAnnotationInk(_annot("Ink")).get_ink_paths() == []
    assert (
        PDAnnotationInk(_annot("Ink", InkList=COSInteger.get(3))).get_ink_paths()
        == []
    )


def test_le_endpoint_styles_guard_and_name_only() -> None:
    """Polyline /LE endpoint styles guard size() >= 2 and read name-only — a
    short array or a non-COSName entry resolves to 'None', matching upstream
    COSArray.getName(index, 'None') behind the size>=2 gate.

    Self-contained.
    """
    pl = PDAnnotationPolyline(
        _annot("PolyLine", LE=_arr(_n("OpenArrow"), _n("Diamond")))
    )
    assert pl.get_start_point_ending_style() == "OpenArrow"
    assert pl.get_end_point_ending_style() == "Diamond"
    # Single-element /LE: both endpoints fall to "None" (size < 2 gate).
    short = PDAnnotationPolyline(_annot("PolyLine", LE=_arr(_n("Square"))))
    assert short.get_start_point_ending_style() == "None"
    assert short.get_end_point_ending_style() == "None"
    # Non-COSName start entry resolves to "None"; valid end name resolves.
    mixed = PDAnnotationPolyline(
        _annot("PolyLine", LE=_arr(COSString("Square"), _n("Circle")))
    )
    assert mixed.get_start_point_ending_style() == "None"
    assert mixed.get_end_point_ending_style() == "Circle"
    # Missing /LE -> both "None".
    assert PDAnnotationPolyline(_annot("PolyLine")).get_start_point_ending_style() == "None"


def test_polygon_polyline_interior_color_lite_divergence() -> None:
    """DIVERGENCE pin: polygon/polyline get_interior_color is a lite accessor
    returning the FIRST 3 components ([r, g, b]) when arity >= 3, else None.
    Upstream getInteriorColor returns a non-null PDColor for ANY /IC COSArray
    (arity 1 -> DeviceGray, 4 -> DeviceCMYK, 0/2 -> null colourspace). Two
    intentional narrowings: arity 1/2 -> None (vs non-null upstream), and arity
    4 -> first 3 comps only (vs a 4-component CMYK PDColor upstream). Typed
    PDColor lands with the rendering cluster (PRD 6.12), so /IC is NOT compared
    against the oracle for polygon/polyline.

    Self-contained.
    """
    assert (
        PDAnnotationPolygon(_annot("Polygon", IC=_nums(1, 0, 0))).get_interior_color()
        == (1.0, 0.0, 0.0)
    )
    # arity 4 -> first 3 comps (CMYK truncated); upstream keeps all 4.
    assert (
        PDAnnotationPolyline(_annot("PolyLine", IC=_nums(0, 0, 0, 1))).get_interior_color()
        == (0.0, 0.0, 0.0)
    )
    # arity 1 / 2 -> None here, but a non-null PDColor upstream (the divergence).
    assert PDAnnotationPolygon(_annot("Polygon", IC=_nums(0.5))).get_interior_color() is None
    assert (
        PDAnnotationPolyline(_annot("PolyLine", IC=_nums(0.2, 0.4))).get_interior_color()
        is None
    )
    assert PDAnnotationPolygon(_annot("Polygon")).get_interior_color() is None
