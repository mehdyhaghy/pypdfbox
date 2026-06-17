"""Live PDFBox differential parity for the MARKED-POINT facet (MP / DP) at
the engine-dispatch level.

Where ``test_marked_content_oracle`` tokenizes the MP / DP operators at the
``PDFStreamParser`` level (and never resolves a named ``/Properties``
reference), this drives a real ``PDFStreamEngine`` subclass over a saved page
and asserts the engine's ``markedContentPoint(tag, properties)`` callback fires
identically to Apache PDFBox — including:

* bare ``MP /Tag`` (tag only, ``properties`` is ``None``),
* ``DP /Tag <<...>>`` with an inline property dictionary,
* ``DP /Tag /Name`` resolving ``/Name`` against the page's ``/Properties``
  resource frame to the real dictionary, and
* ``DP /Tag /Missing`` where the named property list is absent — upstream's
  ``MarkedContentPointWithProperties.process`` early-returns and fires **no**
  callback, so the line is omitted.

The ``MarkedPointDispatchProbe`` Java oracle builds the one-page PDF (so the
bytes are identical), runs PDFBox's engine, and emits one canonical line per
dispatched mark point. pypdfbox loads the same saved bytes, registers the
mirror operator processors (``MarkedContentPoint`` /
``MarkedContentPointWithProperties``), and renders the same grammar.

Canonical line grammar (must match ``oracle/probes/MarkedPointDispatchProbe.java``)::

    MP /<tag>
    DP /<tag> <propsValue>

where ``<propsValue>`` is ``{ k=<v> ; ... }`` (keys sorted); values use the
``INT:`` / ``REAL:`` / ``NAME:`` / ``STR:`` / ``BOOL:`` / ``NULL`` / ``[..]``
grammar shared with ``TokenizeProbe`` / ``MarkedContentProbe``.
"""

from __future__ import annotations

import struct
import tempfile
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent.marked_content_point import (
    MarkedContentPoint,
)
from pypdfbox.contentstream.operator.markedcontent.marked_content_point_with_properties import (
    MarkedContentPointWithProperties,
)
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
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text


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
    """Mirror of ``MarkedPointDispatchProbe.canonFloat`` (== ``TokenizeProbe``)."""
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
    ``MarkedPointDispatchProbe.canonValue``."""
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
    ``MarkedPointDispatchProbe.canonDict``."""
    items = sorted(
        (key.get_name(), d.get_dictionary_object(key)) for key in d.key_set()
    )
    body = " ; ".join(f"{name}={_canon_value(val)}" for name, val in items)
    return "{ " + body + " }"


class _RecordingEngine(PDFStreamEngine):
    """Engine recording every ``marked_content_point`` dispatch, rendering it
    with the probe's canonical line grammar."""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.add_operator(MarkedContentPoint())
        self.add_operator(MarkedContentPointWithProperties())

    def marked_content_point(
        self, tag: COSName | None, properties: COSDictionary | None
    ) -> None:
        tag_str = tag.get_name() if isinstance(tag, COSName) else "<none>"
        if properties is None:
            self.lines.append(f"MP /{tag_str}")
        else:
            self.lines.append(f"DP /{tag_str} {_canon_dict(properties)}")


def _pypdfbox_render(path: Path) -> str:
    doc = PDDocument.load(path)
    try:
        page = doc.get_page(0)
        engine = _RecordingEngine()
        engine.process_page(page)
    finally:
        doc.close()
    return "".join(line + "\n" for line in engine.lines)


@requires_oracle
def test_marked_point_dispatch_matches_pdfbox() -> None:
    # The probe builds + saves the one-page PDF to this path, runs PDFBox's
    # engine over it, and prints the dispatched mark-point lines. We then load
    # the identical saved bytes and drive pypdfbox's engine the same way.
    with tempfile.TemporaryDirectory() as tmp:
        out_pdf = Path(tmp) / "marked_point_dispatch.pdf"
        java = run_probe_text("MarkedPointDispatchProbe", str(out_pdf))
        assert out_pdf.is_file(), "probe did not write the expected PDF"
        py = _pypdfbox_render(out_pdf)
    assert py == java


# Sanity pin on the exact expected output so a silent regression in either the
# probe or the engine surfaces as a precise diff (not just "they still match").
_EXPECTED = (
    "MP /Pt1\n"
    "DP /Pt2 { Flag=BOOL:true ; MCID=INT:1 ; Title=STR:696e6c696e65 }\n"
    "DP /Pt3 { BBox=[REAL:1.5,INT:0,REAL:99.25,INT:-3] ; "
    "MCID=INT:7 ; Title=STR:6e616d65642d70726f70 ; Type=NAME:/Pagination }\n"
    "MP /Pt5\n"
)


@requires_oracle
def test_marked_point_dispatch_expected_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_pdf = Path(tmp) / "marked_point_dispatch.pdf"
        run_probe_text("MarkedPointDispatchProbe", str(out_pdf))
        py = _pypdfbox_render(out_pdf)
    # /Missing (Pt4, unresolvable named /Properties ref) yields NO line —
    # both PDFBox and pypdfbox early-return without firing the callback.
    assert py == _EXPECTED
