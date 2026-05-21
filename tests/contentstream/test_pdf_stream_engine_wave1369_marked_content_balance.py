"""Wave 1369 — marked-content sequence balance (BMC / BDC / EMC).

PDF 32000-1 §14.6 marked-content sequences nest. Balanced and
unbalanced sequences must both surface to the engine's hooks so
downstream consumers (text extractor with ``/ActualText`` tracking,
structure-tree extractor, marked-content extractor) see every begin /
end exactly once. These tests pin the engine's dispatch surface — the
operator handlers correctly invoke ``begin_marked_content_sequence`` /
``end_marked_content_sequence`` and the operand shapes (tag,
property-dict-or-name) are forwarded verbatim.
"""

from __future__ import annotations

import io
from typing import IO, Any

from pypdfbox.contentstream import (
    PDContentStream,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content import (
    BeginMarkedContent,
)
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_with_props import (
    BeginMarkedContentWithProps,
)
from pypdfbox.contentstream.operator.markedcontent.end_marked_content import (
    EndMarkedContent,
)
from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDRectangle, PDResources


class _MarkedContentEngine(PDFStreamEngine):
    """Engine that records every marked-content begin/end so tests can
    assert balance, order, and operand shapes."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, Any, Any]] = []

    def begin_marked_content_sequence(
        self, tag: COSName, properties: COSDictionary | None
    ) -> None:
        self.events.append(("begin", tag, properties))

    def end_marked_content_sequence(self) -> None:
        self.events.append(("end", None, None))


class _BytesContentStream(PDContentStream):
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return PDResources()

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 612.0, 792.0)

    def get_matrix(self) -> Any:
        return None


def _register_marked_content_ops(engine: PDFStreamEngine) -> None:
    for proc in (BeginMarkedContent(), BeginMarkedContentWithProps(), EndMarkedContent()):
        engine.add_operator(proc)


# ---------- balanced sequences ----------


def test_balanced_bmc_emc_round_trip() -> None:
    """A simple ``/Span BMC ... EMC`` pair produces exactly one begin
    and one end, in order."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_stream(_BytesContentStream(b"/Span BMC EMC"))
    kinds = [e[0] for e in engine.events]
    assert kinds == ["begin", "end"]
    assert engine.events[0][1] == COSName.get_pdf_name("Span")
    assert engine.events[0][2] is None  # BMC carries no properties


def test_nested_bmc_emc_balance_preserved() -> None:
    """Two nested BMC / EMC pairs surface as two begins followed by two
    ends — the engine's dispatch is order-preserving and does not
    re-balance."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_stream(_BytesContentStream(b"/Outer BMC /Inner BMC EMC EMC"))
    kinds = [e[0] for e in engine.events]
    assert kinds == ["begin", "begin", "end", "end"]
    tags = [e[1] for e in engine.events if e[0] == "begin"]
    assert tags == [COSName.get_pdf_name("Outer"), COSName.get_pdf_name("Inner")]


def test_bdc_with_inline_property_dictionary() -> None:
    """``BDC`` with an inline property dictionary forwards the dict to
    the hook verbatim."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    raw = b"/Span <</ActualText (Hi)>> BDC EMC"
    engine.process_stream(_BytesContentStream(raw))
    kinds = [e[0] for e in engine.events]
    assert kinds == ["begin", "end"]
    tag, props = engine.events[0][1], engine.events[0][2]
    assert tag == COSName.get_pdf_name("Span")
    assert isinstance(props, COSDictionary)
    val = props.get_item(COSName.get_pdf_name("ActualText"))
    assert isinstance(val, COSString)
    assert val.get_bytes() == b"Hi"


def test_bdc_with_named_property_resolves_via_resources() -> None:
    """``/Tag /PropName BDC`` resolves ``/PropName`` against the
    engine's current ``/Properties`` resource frame. When the named
    property is present the hook receives the resolved dictionary."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)

    # Build resources with /Properties → /P1 → dict with /ActualText "ok".
    properties = COSDictionary()
    properties.set_string("ActualText", "ok")
    res_cos = COSDictionary()
    p_map = COSDictionary()
    p_map.set_item(COSName.get_pdf_name("P1"), properties)
    res_cos.set_item(COSName.get_pdf_name("Properties"), p_map)
    engine._resources = PDResources(res_cos)

    engine.process_operator("BDC", [
        COSName.get_pdf_name("Span"),
        COSName.get_pdf_name("P1"),
    ])
    engine.process_operator("EMC", [])
    begin = next(e for e in engine.events if e[0] == "begin")
    assert begin[1] == COSName.get_pdf_name("Span")
    assert isinstance(begin[2], COSDictionary)
    assert begin[2].get_string("ActualText") == "ok"


def test_bdc_unresolvable_named_property_passes_none() -> None:
    """When the named property can't be resolved (no resources, or no
    matching ``/Properties`` entry), the hook receives ``properties=None``
    — the dispatch still fires."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_operator("BDC", [
        COSName.get_pdf_name("Span"),
        COSName.get_pdf_name("Missing"),
    ])
    assert engine.events[0] == ("begin", COSName.get_pdf_name("Span"), None)


# ---------- unbalanced sequences ----------


def test_unbalanced_extra_emc_still_fires_end_hook() -> None:
    """An extra ``EMC`` without a matching open sequence still drives
    the engine's ``end_marked_content_sequence`` hook (it is the
    subclass's job to handle the imbalance — the base engine does not
    swallow the event)."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_stream(_BytesContentStream(b"/Span BMC EMC EMC"))
    kinds = [e[0] for e in engine.events]
    assert kinds == ["begin", "end", "end"]


def test_unbalanced_missing_emc_still_fires_begin_hook() -> None:
    """An open BMC without a closing EMC still surfaces — the hook
    fires once and the stream ends with no terminating ``end`` event."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_stream(_BytesContentStream(b"/Span BMC q Q"))
    kinds = [e[0] for e in engine.events]
    assert kinds == ["begin"]


def test_dangling_emc_at_stream_start_dispatches() -> None:
    """A ``EMC`` at the very start (no opening) still dispatches — the
    engine has no opening-tracking state in the base class."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_stream(_BytesContentStream(b"EMC"))
    kinds = [e[0] for e in engine.events]
    assert kinds == ["end"]


# ---------- malformed operands degrade gracefully ----------


def test_bmc_without_tag_operand_passes_none() -> None:
    """When ``BMC`` arrives with no operand (malformed stream),
    ``extract_tag`` returns ``None`` — the hook still fires so
    subclasses can decide how to handle the malformed dispatch."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_operator("BMC", [])
    assert engine.events[0] == ("begin", None, None)


def test_bdc_without_operands_passes_none() -> None:
    """Same defensive contract for ``BDC``: malformed operand stack ⇒
    the hook fires with ``tag=None, properties=None`` rather than
    raising."""
    engine = _MarkedContentEngine()
    _register_marked_content_ops(engine)
    engine.process_operator("BDC", [])
    assert engine.events[0] == ("begin", None, None)


# ---------- base engine carries no marked-content hooks (no crash) ----------


def test_base_engine_silently_consumes_marked_content_sequence() -> None:
    """The bare :class:`PDFStreamEngine` has the marked-content hooks as
    pure no-ops — even with all three handlers registered, the dispatch
    finishes without raising and without observable side effects."""
    engine = PDFStreamEngine()
    _register_marked_content_ops(engine)
    # Should not raise — base ``begin_marked_content_sequence`` /
    # ``end_marked_content_sequence`` are no-ops.
    engine.process_stream(_BytesContentStream(b"/Span BMC EMC"))
