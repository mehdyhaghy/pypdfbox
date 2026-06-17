"""Live PDFBox differential parity for marked-content operators + MCID tracking.

Compares pypdfbox against Apache PDFBox on two fronts, via the
``MarkedContentProbe`` Java oracle:

1. **Operator subsequence** — the ``BMC`` / ``BDC`` / ``EMC`` / ``MP`` / ``DP``
   tokens of a page's content stream as ``PDFStreamParser`` tokenizes them,
   each with its tag and (for ``BDC`` / ``DP``) the inline property dictionary
   or the resource ``/Properties`` name. Property dicts are rendered with
   sorted keys so the comparison is order- and locale-independent.

2. **Marked-content tree** — the ``PDFMarkedContentExtractor`` walk: one line
   per sequence, indented by nesting depth, carrying ``tag`` + ``MCID`` +
   the count of child marked-content sequences.

Canonical line grammar (must match ``oracle/probes/MarkedContentProbe.java``)::

    --- ops ---
    BMC /<tag>
    BDC /<tag> <propsValue>
    EMC
    MP /<tag>
    DP /<tag> <propsValue>
    --- tree ---
    MC depth=<n> tag=<tag> mcid=<n> children=<n>

where ``<propsValue>`` is ``/<name>`` for a resource reference, or
``{ k=<v> ; ... }`` (keys sorted) for an inline dictionary; values use the
``INT:`` / ``REAL:`` / ``NAME:`` / ``STR:`` / ``BOOL:`` / ``NULL`` / ``[..]``
grammar shared with ``TokenizeProbe``.
"""

from __future__ import annotations

import struct
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

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
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text import PDFMarkedContentExtractor
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# Tagged-PDF fixtures exercising marked content: inline /MCID dicts, named
# /Properties references (/OC), nested Artifact/OC sequences, array-valued
# property entries.
_CASES = [
    # Tagged PDF/A: single /Span << /MCID 0 /Lang (en-US) >>.
    ("multipdf/PDFA3A.pdf", 0),
    # Artifact (inline dict with Attached/BBox/Type) + bare-tag BMC + many
    # /P BDC sequences with sequential MCIDs.
    ("multipdf/PDFBOX-5811-362972.pdf", 0),
    ("multipdf/PDFBOX-5811-362972.pdf", 1),
    ("multipdf/PDFBOX-5811-362972.pdf", 3),
    # /P MCIDs + nested Artifact wrapping an /OC named-property BDC.
    ("multipdf/PDFBOX-5762-722238.pdf", 3),
    ("multipdf/PDFBOX-5762-722238.pdf", 4),
    # Heavy BMC usage (81 BMC on page 0).
    ("multipdf/PDFBOX-4417-001031.pdf", 0),
    ("multipdf/PDFBOX-5809-509329.pdf", 0),
    ("multipdf/PDFBOX-5792-240045.pdf", 0),
]


def _float32_shortest(value: float) -> str:
    """Shortest decimal that round-trips through IEEE-754 single precision —
    the Python equivalent of Java's ``Float.toString(float)`` (mirror of
    ``test_tokenize_oracle._float32_shortest``)."""
    target = struct.unpack("f", struct.pack("f", value))[0]
    for prec in range(1, 18):
        candidate = f"{value:.{prec}g}"
        if struct.unpack("f", struct.pack("f", float(candidate)))[0] == target:
            return candidate
    return repr(value)


def _canon_float(value: float) -> str:
    """Mirror of ``MarkedContentProbe.canonFloat`` (== ``TokenizeProbe``)."""
    if value != value:  # NaN
        return "nan"
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    bd = (
        Decimal(_float32_shortest(value))
        .quantize(Decimal("0.00001"), rounding=ROUND_HALF_EVEN)
        .normalize()
    )
    s = format(bd, "f")
    if s == "-0":
        s = "0"
    return s


def _canon_value(b: COSBase | None) -> str:
    """Canonical rendering of a property-dict value — mirror of
    ``MarkedContentProbe.canonValue``."""
    if b is None:
        return "NULL"
    if isinstance(b, COSInteger):
        return f"INT:{b.long_value()}"
    if isinstance(b, COSFloat):
        return f"REAL:{_canon_float(b.float_value())}"
    if isinstance(b, COSName):
        return f"NAME:/{b.get_name()}"
    if isinstance(b, COSString):
        return f"STR:{b.get_bytes().hex()}"
    if isinstance(b, COSBoolean):
        return f"BOOL:{'true' if b.get_value() else 'false'}"
    if isinstance(b, COSNull):
        return "NULL"
    if isinstance(b, COSArray):
        return "[" + ",".join(_canon_value(b.get(i)) for i in range(b.size())) + "]"
    if isinstance(b, COSDictionary):
        return _canon_dict(b)
    return f"COS:{type(b).__name__}"


def _canon_dict(d: COSDictionary) -> str:
    """Canonical dict: ``{ key=value ; ... }`` with keys sorted — mirror of
    ``MarkedContentProbe.canonDict``."""
    items = sorted(
        (key.get_name(), d.get_dictionary_object(key)) for key in d.key_set()
    )
    body = " ; ".join(f"{name}={_canon_value(val)}" for name, val in items)
    return "{ " + body + " }"


def _tag_of(operands: list[COSBase]) -> str:
    for b in operands:
        if isinstance(b, COSName):
            return f"/{b.get_name()}"
    return "<none>"


def _props_of(operands: list[COSBase]) -> str:
    if len(operands) < 2:
        return "<none>"
    prop = operands[1]
    if isinstance(prop, COSName):
        return f"/{prop.get_name()}"
    if isinstance(prop, COSDictionary):
        return _canon_dict(prop)
    return "<bad>"


def _emit_ops(tokens: list[object]) -> list[str]:
    """Tokenize → emit the marked-content operator subsequence, mirroring
    ``MarkedContentProbe.emitOps``."""
    out: list[str] = ["--- ops ---"]
    operands: list[COSBase] = []
    for tok in tokens:
        if isinstance(tok, Operator):
            name = tok.get_name()
            if name == "BMC":
                out.append(f"BMC {_tag_of(operands)}")
            elif name == "BDC":
                out.append(f"BDC {_tag_of(operands)} {_props_of(operands)}")
            elif name == "EMC":
                out.append("EMC")
            elif name == "MP":
                out.append(f"MP {_tag_of(operands)}")
            elif name == "DP":
                out.append(f"DP {_tag_of(operands)} {_props_of(operands)}")
            operands = []
        elif isinstance(tok, COSBase):
            operands.append(tok)
    return out


def _emit_tree(node: object, depth: int, out: list[str]) -> None:
    """Depth-first marked-content tree — mirror of
    ``MarkedContentProbe.emitTree``."""
    from pypdfbox.pdmodel.documentinterchange.markedcontent import PDMarkedContent

    assert isinstance(node, PDMarkedContent)
    children = [c for c in node.get_contents() if isinstance(c, PDMarkedContent)]
    out.append(
        f"MC depth={depth} tag={node.get_tag()} "
        f"mcid={node.get_mcid()} children={len(children)}"
    )
    for child in children:
        _emit_tree(child, depth + 1, out)


def _pypdfbox_render(path: Path, page_index: int) -> str:
    doc = PDDocument.load(path)
    try:
        page = doc.get_page(page_index)
        parser = PDFStreamParser(page.get_contents_for_stream_parsing())
        lines = _emit_ops(parser.parse())

        lines.append("--- tree ---")
        extractor = PDFMarkedContentExtractor()
        extractor.process_page(page)
        for mc in extractor.get_marked_contents():
            _emit_tree(mc, 0, lines)
    finally:
        doc.close()
    return "".join(line + "\n" for line in lines)


def _pypdfbox_render_raw(path: Path) -> str:
    parser = PDFStreamParser.from_bytes(path.read_bytes())
    lines = _emit_ops(parser.parse())
    return "".join(line + "\n" for line in lines)


@requires_oracle
@pytest.mark.parametrize(
    ("rel", "page"),
    _CASES,
    ids=[f"{rel.replace('/', '_')}_p{page}" for rel, page in _CASES],
)
def test_marked_content_matches_pdfbox(rel: str, page: int) -> None:
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    java = run_probe_text("MarkedContentProbe", str(fixture), str(page))
    py = _pypdfbox_render(fixture, page)
    assert py == java


# Raw content-stream case: a hand-built stream exercising every
# marked-content operator (BMC bare, BDC inline dict with nested array /
# string / name, BDC named /Properties reference, MP, DP inline dict, DP
# named reference, nested EMC, stray EMC). The --raw form drives only the
# operator subsequence (no document = no PDFMarkedContentExtractor walk).
_RAW_CASES = [
    "contentstream/marked_content_ops.cs",
]


@requires_oracle
@pytest.mark.parametrize(
    "rel", _RAW_CASES, ids=[r.replace("/", "_") for r in _RAW_CASES]
)
def test_marked_content_raw_matches_pdfbox(rel: str) -> None:
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    java = run_probe_text("MarkedContentProbe", str(fixture), "--raw")
    py = _pypdfbox_render_raw(fixture)
    assert py == java
