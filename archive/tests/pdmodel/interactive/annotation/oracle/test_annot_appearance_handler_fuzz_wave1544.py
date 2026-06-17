"""Live Apache PDFBox differential fuzz of the markup-annotation
APPEARANCE-HANDLER surface (wave 1544, agent E).

The existing annotation-appearance oracle suite pins the WELL-FORMED token
streams of the ``PDAbstractAppearanceHandler`` subclasses byte-for-byte
(LineAppearanceProbe, SquareCircleSolidProbe, PolyAppearanceProbe,
InkAppearanceProbe, HighlightBlendProbe, StrikeoutSquigglyProbe,
CloudyBorderProbe, BorderStyleProbe, FreeText*). NONE feed the handlers
MALFORMED / edge-case COS fields and compare what ``constructAppearances``
synthesises. This fuzz fills that gap:

  - /C stroke colour arrays of arity 0 / 1 / 3 / 4 (and absent) — drives the
    ``getColor() is None or size()==0 -> return`` guards and the device
    colour-space selection (Gray / RGB / CMYK) in the handlers.
  - /IC interior colour present / empty / wrong arity (Square, Circle, Polygon,
    Line line-endings).
  - /BS width 0 / negative + /D dash empty / all-zero (dropped) / real — the
    ``ab.width < 1e-5`` thin-line gating and the all-zero dash drop in
    AnnotationBorder.
  - /L line coordinates missing / short (2 elems) / long (6 elems) (Line).
  - /Vertices odd-length / empty (Polygon, PolyLine).
  - /InkList empty / flat-not-nested / nested (Ink).
  - /LE start/end line-ending names valid / unknown (Line).
  - /RD rectangle differences negative / oversized (Square / Circle).
  - /QuadPoints wrong arity (5, 7) / empty (Highlight / Underline / StrikeOut /
    Squiggly).
  - zero-area /Rect (degenerate bbox).

Strategy mirrors wave-1515 AnnotationDispatchFuzz: build the deterministic
corpus directly as COS, embed it in a non-standard ``/FuzzAnnots`` COSArray on
the catalog, save ONE ``corpus.pdf``. The ``AnnotAppearanceHandlerFuzzProbe``
loads that single pdf, walks the array, wraps each dict in its typed subclass,
calls ``constructAppearances(doc)``, and projects a STABLE SHAPE robust to
numeric drift: whether an /AP /N stream was produced, its /BBox, the sorted set
of distinct content-stream operators, and stroke/fill/closepath presence flags.

Validation, not blind pinning: the Java line is ground truth. Each case asserts
pypdfbox's ``construct_appearances`` produces the identical projected shape. A
real divergence is fixed in production; a defensible robustness divergence is
pinned in ``_PINNED_DIVERGENCES`` with a reason + a matching CHANGES.md row.
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
)
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation
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


def _bs(width: float, dash: COSArray | None = None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Border"))
    d.set_item(_n("W"), COSFloat(float(width)))
    if dash is not None:
        d.set_item(_n("S"), _n("D"))
        d.set_item(_n("D"), dash)
    return d


def _le(start: str, end: str) -> COSArray:
    return _arr(_n(start), _n(end))


# --------------------------------------------------------------- corpus build


def _build_corpus() -> list[COSDictionary]:
    """Deterministic, ordered appearance-handler fuzz corpus."""
    c: list[COSDictionary] = []
    rect = lambda: _nums(50, 500, 250, 620)  # noqa: E731 - terse builder

    # ----- Line: /L arity + /C arity + /BS width + /LE -----
    c.append(_annot("Line", Rect=rect(), L=_nums(60, 520, 240, 600), C=_nums(1, 0, 0)))
    c.append(_annot("Line", Rect=rect(), L=_nums(60, 520, 240, 600)))  # /C absent
    c.append(_annot("Line", Rect=rect(), L=_nums(60, 520, 240, 600), C=_arr()))  # empty
    c.append(_annot("Line", Rect=rect(), L=_nums(60, 520, 240, 600), C=_nums(0.5)))  # gray
    c.append(
        _annot("Line", Rect=rect(), L=_nums(60, 520, 240, 600), C=_nums(0, 0, 0, 1))
    )  # cmyk
    c.append(_annot("Line", Rect=rect(), C=_nums(1, 0, 0)))  # /L absent
    c.append(_annot("Line", Rect=rect(), L=_nums(60, 520), C=_nums(1, 0, 0)))  # /L short
    c.append(
        _annot("Line", Rect=rect(), L=_nums(60, 520, 240, 600, 1, 2), C=_nums(1, 0, 0))
    )  # /L long
    c.append(
        _annot(
            "Line",
            Rect=rect(),
            L=_nums(60, 520, 240, 600),
            C=_nums(0, 0, 1),
            BS=_bs(0),
        )
    )  # zero width
    c.append(
        _annot(
            "Line",
            Rect=rect(),
            L=_nums(60, 520, 240, 600),
            C=_nums(0, 0, 1),
            BS=_bs(-2),
        )
    )  # negative width
    c.append(
        _annot(
            "Line",
            Rect=rect(),
            L=_nums(60, 520, 240, 600),
            C=_nums(0, 0, 1),
            BS=_bs(2, _arr()),
        )
    )  # empty dash
    c.append(
        _annot(
            "Line",
            Rect=rect(),
            L=_nums(60, 520, 240, 600),
            C=_nums(0, 0, 1),
            BS=_bs(2, _nums(0, 0)),
        )
    )  # all-zero dash dropped
    c.append(
        _annot(
            "Line",
            Rect=rect(),
            L=_nums(60, 520, 240, 600),
            C=_nums(0, 0, 1),
            IC=_nums(1, 1, 0),
            LE=_le("ClosedArrow", "Diamond"),
        )
    )  # closed-arrow + diamond interior fill
    c.append(
        _annot(
            "Line",
            Rect=rect(),
            L=_nums(60, 520, 240, 600),
            C=_nums(0, 0, 1),
            LE=_le("Bogus", "AlsoBogus"),
        )
    )  # unknown LE names
    c.append(
        _annot(
            "Line",
            Rect=rect(),
            L=_nums(60, 520, 240, 600),
            C=_nums(0, 0, 1),
            IC=_arr(),
        )
    )  # empty /IC

    # ----- Square / Circle: /C, /IC, /BS, /RD -----
    c.append(_annot("Square", Rect=rect(), C=_nums(1, 0, 0)))
    c.append(_annot("Square", Rect=rect(), C=_nums(1, 0, 0), IC=_nums(0, 1, 0)))
    c.append(_annot("Square", Rect=rect(), C=_nums(1, 0, 0), BS=_bs(0)))  # zero width
    c.append(_annot("Square", Rect=rect(), C=_arr(), IC=_nums(0, 0, 1)))  # /C empty fill only
    c.append(
        _annot("Square", Rect=rect(), C=_nums(1, 0, 0), RD=_nums(-5, -5, -5, -5))
    )  # negative /RD
    c.append(
        _annot("Square", Rect=rect(), C=_nums(1, 0, 0), RD=_nums(500, 500, 500, 500))
    )  # oversized /RD
    c.append(_annot("Circle", Rect=rect(), C=_nums(0, 0, 1), IC=_nums(1, 1, 0)))
    c.append(
        _annot("Circle", Rect=rect(), C=_nums(0, 0, 1), BS=_bs(3, _nums(3, 2)))
    )  # dashed circle

    # ----- Polygon / PolyLine: /Vertices arity -----
    tri = _nums(60, 520, 240, 520, 150, 600)
    c.append(_annot("Polygon", Rect=rect(), Vertices=tri, C=_nums(1, 0, 0)))
    c.append(
        _annot("Polygon", Rect=rect(), Vertices=_nums(60, 520, 240), C=_nums(1, 0, 0))
    )  # odd
    c.append(_annot("Polygon", Rect=rect(), Vertices=_arr(), C=_nums(1, 0, 0)))  # empty
    c.append(
        _annot(
            "Polygon",
            Rect=rect(),
            Vertices=_nums(60, 520, 240, 520, 150, 600),
            C=_nums(1, 0, 0),
            IC=_nums(0.8, 0.8, 0.8),
        )
    )
    c.append(
        _annot(
            "PolyLine", Rect=rect(), Vertices=_nums(60, 520, 240, 600), C=_nums(0, 0.5, 0)
        )
    )
    c.append(
        _annot("PolyLine", Rect=rect(), Vertices=_nums(60, 520, 1), C=_nums(0, 0.5, 0))
    )  # odd

    # ----- Ink: /InkList shape -----
    c.append(
        _annot(
            "Ink",
            Rect=rect(),
            InkList=_arr(_nums(60, 520, 120, 580, 180, 540)),
            C=_nums(1, 0, 0),
        )
    )
    c.append(_annot("Ink", Rect=rect(), InkList=_arr(), C=_nums(1, 0, 0)))  # empty
    c.append(
        _annot(
            "Ink",
            Rect=rect(),
            InkList=_arr(_nums(60, 520), _nums(120, 580)),
            C=_nums(1, 0, 0),
        )
    )  # nested 2-elem paths

    # ----- Text markup: /QuadPoints arity -----
    quad = _nums(60, 520, 240, 520, 60, 500, 240, 500)  # one well-formed quad
    c.append(_annot("Highlight", Rect=rect(), QuadPoints=quad, C=_nums(1, 1, 0)))
    c.append(
        _annot(
            "Highlight", Rect=rect(), QuadPoints=_nums(60, 520, 240, 520, 60), C=_nums(1, 1, 0)
        )
    )  # 5
    c.append(_annot("Highlight", Rect=rect(), QuadPoints=_arr(), C=_nums(1, 1, 0)))  # empty
    c.append(
        _annot(
            "Underline",
            Rect=rect(),
            QuadPoints=_nums(60, 520, 240, 520, 60, 500, 240, 500),
            C=_nums(0, 0, 1),
        )
    )
    c.append(
        _annot(
            "StrikeOut",
            Rect=rect(),
            QuadPoints=_nums(60, 520, 240, 520, 60, 500, 240, 500),
            C=_nums(1, 0, 0),
        )
    )
    c.append(
        _annot(
            "StrikeOut",
            Rect=rect(),
            QuadPoints=_nums(60, 520, 240, 520, 60, 500, 240),
            C=_nums(1, 0, 0),
        )
    )  # 7
    c.append(
        _annot(
            "Squiggly",
            Rect=rect(),
            QuadPoints=_nums(60, 520, 240, 520, 60, 500, 240, 500),
            C=_nums(0, 1, 0),
        )
    )

    # ----- zero-area /Rect -----
    c.append(
        _annot("Square", Rect=_nums(100, 100, 100, 100), C=_nums(1, 0, 0))
    )  # degenerate rect

    return c


# --------------------------------------------------------------- projection
#
# Mirrors AnnotAppearanceHandlerFuzzProbe.java exactly.


_STROKE_OPS = frozenset({"RG", "G", "K", "SC", "SCN", "CS"})
_FILL_OPS = frozenset({"rg", "g", "k", "sc", "scn", "cs"})

# Java exception simple-name the probe emits for the few cases where BOTH
# libraries crash identically (a short /L read past the end of the float
# array). pypdfbox raises the Python equivalent; map it so the cross-language
# record matches. This is name-spelling normalisation, NOT a behaviour pin:
# both implementations throw on the same out-of-range index.
_EXC_MAP: dict[str, str] = {
    "IndexError": "ArrayIndexOutOfBoundsException",
}


def _canon(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


def _bbox_str(stream) -> str:
    bbox = stream.get_bbox()
    if bbox is None:
        return "none"
    return ",".join(
        _canon(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
        )
    )


def _operators(stream) -> list[str]:
    parser = PDFStreamParser.from_content_stream(stream)
    ops: list[str] = []
    while True:
        token = parser.parse_next_token()
        if token is None:
            break
        if isinstance(token, Operator):
            ops.append(token.get_name())
    return ops


def _py_record(idx: int, d: COSDictionary | None) -> list[str]:
    no_ap = [
        f"CASE {idx}",
        "AP no",
        "BBOX none",
        "OPS -",
        "FLAGS stroke=0 fill=0 close=0",
        "END",
    ]
    if d is None:
        return no_ap
    try:
        annot = PDAnnotation.create_annotation(d)
    except Exception as exc:  # noqa: BLE001 - contract probe
        return [
            f"CASE {idx}",
            f"AP ERR:{type(exc).__name__}",
            "BBOX none",
            "OPS -",
            "FLAGS stroke=0 fill=0 close=0",
            "END",
        ]
    if annot is None:
        return no_ap
    try:
        annot.construct_appearances()
    except Exception as exc:  # noqa: BLE001 - contract probe
        name = _EXC_MAP.get(type(exc).__name__, type(exc).__name__)
        return [
            f"CASE {idx}",
            f"AP ERR:{name}",
            "BBOX none",
            "OPS -",
            "FLAGS stroke=0 fill=0 close=0",
            "END",
        ]
    stream = annot.get_normal_appearance_stream()
    if stream is None:
        return no_ap
    ops_seen = _operators(stream)
    distinct = sorted(set(ops_seen))
    stroke = any(o in _STROKE_OPS for o in ops_seen)
    fill = any(o in _FILL_OPS for o in ops_seen)
    close = "h" in ops_seen
    return [
        f"CASE {idx}",
        "AP yes",
        f"BBOX {_bbox_str(stream)}",
        "OPS " + (" ".join(distinct) if distinct else "-"),
        f"FLAGS stroke={int(stroke)} fill={int(fill)} close={int(close)}",
        "END",
    ]


# --------------------------------------------------------------- corpus pdf


def _write_corpus_pdf(dir_path: Path, corpus: list[COSDictionary]) -> None:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        catalog = doc.get_document_catalog().get_cos_object()
        arr = COSArray()
        for dd in corpus:
            arr.add(dd)
        catalog.set_item(_n("FuzzAnnots"), arr)
        buf = io.BytesIO()
        doc.save(buf)
        (dir_path / "corpus.pdf").write_bytes(buf.getvalue())
    finally:
        doc.close()


_doc_keepalive: list[object] = []


def _reload_corpus(dir_path: Path, count: int) -> list[COSDictionary | None]:
    doc = PDDocument.load(str(dir_path / "corpus.pdf"))
    _doc_keepalive.append(doc)
    out: list[COSDictionary | None] = []
    catalog = doc.get_document_catalog().get_cos_object()
    arr = catalog.get_dictionary_object(_n("FuzzAnnots"))
    for i in range(count):
        entry = arr.get_object(i)
        out.append(entry if isinstance(entry, COSDictionary) else None)
    return out


# --------------------------------------------------------------- pinned diffs

# Intentional, documented divergences from the Java projection (per case index).
# Each pin is the pypdfbox record block, asserted to remain stable, with a
# matching CHANGES.md row.
#
# HIGHLIGHT (cases 32/33/34): upstream PDHighlightAppearanceHandler wraps the
# quad fill in a TWO-form-XObject transparency group (an outer /AP /N stream
# that only sets the alpha+Multiply ExtGState then paints the inner form via
# ``Do``). PDFormXObject is not implemented in the pypdfbox lite surface yet
# (PRD §6.x), so the highlight handler INLINES the alpha+Multiply ExtGState and
# the quad fill directly into the /AP /N stream. The visible result is
# equivalent for single-quad highlights; the divergence is purely structural
# (inline ``gs rg ... f`` vs ``Do gs``). This is already documented on the
# handler class docstring and re-pinned here so the fuzz diff stays green
# without weakening the production handler. Underline / StrikeOut / Squiggly do
# NOT diverge — upstream draws those directly (Squiggly via its own form, which
# pypdfbox already mirrors with ``Do``).
_PINNED_DIVERGENCES: dict[int, list[str]] = {
    32: [
        "CASE 32",
        "AP yes",
        "BBOX 50,494.5,250,620",
        "OPS c f gs l m rg",
        "FLAGS stroke=0 fill=1 close=0",
        "END",
    ],
    33: [
        "CASE 33",
        "AP yes",
        "BBOX 50,500,250,620",
        "OPS gs rg",
        "FLAGS stroke=0 fill=1 close=0",
        "END",
    ],
    34: [
        "CASE 34",
        "AP yes",
        "BBOX 50,500,250,620",
        "OPS gs rg",
        "FLAGS stroke=0 fill=1 close=0",
        "END",
    ],
}


# --------------------------------------------------------------------- the test


def _split_records(lines: list[str]) -> dict[int, list[str]]:
    records: dict[int, list[str]] = {}
    current: list[str] = []
    idx = -1
    for ln in lines:
        if ln.startswith("CASE "):
            if current:
                records[idx] = current
            idx = int(ln.split(" ", 1)[1])
            current = [ln]
        else:
            current.append(ln)
    if current:
        records[idx] = current
    return records


@requires_oracle
def test_annot_appearance_handler_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed / edge-case markup annotation synthesises an identical
    /AP shape (presence, /BBox, distinct operator set, stroke/fill/close flags)
    on pypdfbox ``construct_appearances`` and Apache PDFBox 3.0.7
    ``constructAppearances``, reading the same on-disk bytes."""
    corpus = _build_corpus()
    _write_corpus_pdf(tmp_path, corpus)

    raw = run_probe_text("AnnotAppearanceHandlerFuzzProbe", str(tmp_path))
    java_records = _split_records(
        [ln for ln in raw.splitlines() if ln.strip()]
    )
    assert len(java_records) == len(corpus), (
        f"probe emitted {len(java_records)} records for {len(corpus)} cases:\n{raw}"
    )

    reloaded = _reload_corpus(tmp_path, len(corpus))
    mismatches: list[str] = []
    for i, d in enumerate(reloaded):
        py_block = _py_record(i, d)
        java_block = java_records[i]
        if i in _PINNED_DIVERGENCES:
            # Validate the documented divergence is still produced by pypdfbox
            # (catches a regression that changes the handler's output) rather
            # than blindly skipping the case.
            if py_block != _PINNED_DIVERGENCES[i]:
                mismatches.append(
                    f"case {i}: PINNED divergence drifted\n"
                    f"  py       {py_block}\n  expected {_PINNED_DIVERGENCES[i]}\n"
                    f"  (java    {java_block})"
                )
            continue
        if py_block != java_block:
            mismatches.append(
                f"case {i}:\n  py   {py_block}\n  java {java_block}"
            )

    assert not mismatches, (
        "appearance-handler fuzz divergence(s):\n" + "\n".join(mismatches)
    )
