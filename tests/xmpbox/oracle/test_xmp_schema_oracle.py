"""Live Apache xmpbox differential parity for typed schema property values.

Compares the typed property values pypdfbox's ``DomXmpParser`` reads out of a
real ``/Metadata`` XMP packet against the values Apache xmpbox 3.0.7 reads from
the same packet bytes (via the ``XmpSchemaProbe`` Java probe). This is a
*parsing-fidelity* check on the typed accessors: titles, descriptions,
creator/subject lists, create/modify dates, the PDF producer/keywords, and the
PDF/A part + conformance.

How the comparison stays repr-independent
-----------------------------------------
Both sides emit the same canonical line grammar (``schema.prop = value``):

  * Simple text values render verbatim (``dc.title = ...``).
  * Seq/Bag lists join their items with US (0x1f) so a comma inside a value
    never confuses the boundary.
  * Dates render as ``<epoch-millis>@<offset-minutes>`` — comparing the
    absolute instant plus the explicit zone offset, so Java's ``Calendar`` and
    pypdfbox's ``datetime`` compare without depending on how either side
    formats a wall-clock string. (Java ``XMPBasicSchema.getCreateDate()``
    returns a ``Calendar``; the pypdfbox equivalent is
    ``get_create_date_value()`` — the bare ``get_create_date()`` is the raw
    string, which is a separate, deliberately string-typed accessor.)
  * A property whose value is absent is OMITTED from the output on both sides
    (so the line set is itself part of the assertion). An empty string is a
    *present* value and renders as ``key = `` (trailing space, empty payload).

Strict vs lenient
-----------------
Apache xmpbox's ``DomXmpParser`` defaults to strict parsing and throws
``XmpParsingException`` on a property whose namespace it does not recognise
(e.g. the ``pdfx:`` extension namespace in ``PDFBOX-4417-001031.pdf``). The
upstream test ``TestXMPWithUndefinedSchemas`` documents that the way to read
such a packet is ``setStrictParsing(false)``. pypdfbox mirrors this strict
default but is more tolerant of undefined namespaces even when strict (it
exposes the unknown schema under a generated prefix rather than rejecting the
packet — see CHANGES.md). To keep the *typed-value* comparison apples-to-apples
this test drives both parsers in the same mode per fixture: strict where the
packet only uses known schemas, lenient where it carries an undefined
namespace.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.xmpbox.dom_xmp_parser import DomXmpParser
from tests.oracle.harness import requires_oracle, run_probe_text

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "multipdf"

# US (0x1f) — the list-item separator both probe and helper use so a comma or
# other punctuation inside a value never confuses item boundaries.
_US = "\x1f"

# (relative fixture, run lenient?).
#   PDFA3A.pdf            — dc:creator + pdf/A id (part 3, conformance A); known
#                           schemas only, so strict on both sides.
#   PDFBOX-5811-362972.pdf — dc:title/description + pdf:Producer/Keywords; known
#                           schemas only, strict on both sides.
#   PDFBOX-4417-001031.pdf — carries an undefined pdfx: namespace, so Apache
#                           xmpbox rejects it in strict mode; lenient on both.
_PACKETS: list[tuple[str, bool]] = [
    ("PDFA3A.pdf", False),
    ("PDFBOX-5811-362972.pdf", False),
    ("PDFBOX-4417-001031.pdf", True),
]


def _xmp_packet_bytes(rel: str) -> bytes:
    """Raw XMP packet bytes from the fixture's catalog ``/Metadata`` stream."""
    fixture = _FIXTURES / rel
    assert fixture.is_file(), f"missing fixture: {fixture}"
    doc = PDDocument.load(fixture)
    try:
        metadata = doc.get_document_catalog().get_metadata()
        assert metadata is not None, f"{rel} has no /Metadata stream"
        return metadata.export_xmp_metadata()
    finally:
        doc.close()


def _fmt_instant(dt: datetime) -> str:
    """``<epoch-millis>@<offset-minutes>`` — matches the Java probe fmtCalendar."""
    epoch_millis = int(dt.timestamp() * 1000)
    offset = dt.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    return f"{epoch_millis}@{offset_minutes}"


def _emit(lines: list[str], key: str, value: str | None) -> None:
    if value is not None:
        lines.append(f"{key} = {value}")


def _emit_list(lines: list[str], key: str, values: list[str] | None) -> None:
    if values is not None:
        lines.append(f"{key} = {_US.join(values)}")


def _emit_instant(lines: list[str], key: str, dt: datetime | None) -> None:
    if dt is not None:
        lines.append(f"{key} = {_fmt_instant(dt)}")


def _emit_instants(lines: list[str], key: str, dts: list[datetime] | None) -> None:
    if dts is not None:
        lines.append(f"{key} = {_US.join(_fmt_instant(d) for d in dts)}")


def _pypdfbox_dump(packet: bytes, *, lenient: bool) -> str:
    """Canonical ``schema.prop = value`` dump pypdfbox parses ``packet`` into —
    same grammar the Java ``XmpSchemaProbe`` emits."""
    parser = DomXmpParser()
    if lenient:
        parser.set_strict_parsing(False)
    meta = parser.parse(packet)
    lines: list[str] = []

    dc = meta.get_dublin_core_schema()
    if dc is not None:
        _emit(lines, "dc.title", dc.get_title())
        _emit(lines, "dc.description", dc.get_description())
        _emit_list(lines, "dc.creators", dc.get_creators())
        _emit_instants(lines, "dc.dates", dc.get_dates())
        _emit_list(lines, "dc.subjects", dc.get_subjects())

    xb = meta.get_xmp_basic_schema()
    if xb is not None:
        _emit(lines, "xmp.creatorTool", xb.get_creator_tool())
        _emit_instant(lines, "xmp.createDate", xb.get_create_date_value())
        _emit_instant(lines, "xmp.modifyDate", xb.get_modify_date_value())

    ap = meta.get_adobe_pdf_schema()
    if ap is not None:
        _emit(lines, "pdf.producer", ap.get_producer())
        _emit(lines, "pdf.keywords", ap.get_keywords())
        _emit(lines, "pdf.pdfVersion", ap.get_pdf_version())

    pa = meta.get_pdfa_identification_schema()
    if pa is not None:
        part = pa.get_part()
        if part is not None:
            lines.append(f"pdfaid.part = {part}")
        _emit(lines, "pdfaid.conformance", pa.get_conformance())

    return "".join(line + "\n" for line in lines)


@requires_oracle
@pytest.mark.parametrize(
    ("rel", "lenient"), _PACKETS, ids=[rel for rel, _ in _PACKETS]
)
def test_xmp_typed_values_match_xmpbox(rel: str, lenient: bool, tmp_path: Path) -> None:
    packet = _xmp_packet_bytes(rel)
    # The probe reads the packet from a file argument; hand it the exact bytes
    # pypdfbox parsed so neither side re-serialises the packet differently.
    packet_path = tmp_path / "packet.xmp"
    packet_path.write_bytes(packet)

    probe_args = [str(packet_path)]
    if lenient:
        probe_args.append("lenient")
    java = run_probe_text("XmpSchemaProbe", *probe_args)
    py = _pypdfbox_dump(packet, lenient=lenient)
    assert py == java
