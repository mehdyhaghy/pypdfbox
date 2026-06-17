"""Wave 1588 — fuzz the registered marked-content operator family.

The operators wired into :class:`PDFStreamEngine` via the operator
registry are (see ``operator_registry.py``):

* ``BMC`` → :class:`BeginMarkedContent`
* ``BDC`` → :class:`BeginMarkedContentWithProps`
* ``EMC`` → :class:`EndMarkedContent`
* ``MP``  → :class:`DefineMarkedContentPoint`
* ``DP``  → :class:`DefineMarkedContentPointWithProps`

This module hammers those five with a recording engine that mirrors the
upstream PDFBox ``PDFStreamEngine.beginMarkedContentSequence`` /
``endMarkedContentSequence`` / ``markedContentPoint`` contract and keeps
a balanced marked-content stack — exactly the behaviour of the upstream
operators plus ``PDFMarkedContentExtractor``.

Parity reference: PDFBox 3.x
``org.apache.pdfbox.contentstream.operator.markedcontent.*`` and
``PDFStreamEngine.beginMarkedContentSequence``.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent import (
    BeginMarkedContent,
    BeginMarkedContentWithProps,
    DefineMarkedContentPoint,
    DefineMarkedContentPointWithProps,
    EndMarkedContent,
)
from pypdfbox.contentstream.operator_processor import MissingOperandException
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.pd_resources import PDResources


class RecordingEngine(PDFStreamEngine):
    """Engine that records every marked-content notification and keeps a
    balanced nesting stack — the stack mirrors upstream
    ``PDFMarkedContentExtractor``'s ``markedContents`` Deque."""

    def __init__(self, resources: PDResources | None = None) -> None:
        super().__init__()
        if resources is not None:
            self._resources = resources
        self.begins: list[tuple[COSName | None, COSDictionary | None]] = []
        self.ends: int = 0
        self.points: list[tuple[COSName | None, COSDictionary | None]] = []
        self.stack: list[tuple[COSName | None, COSDictionary | None]] = []

    def begin_marked_content_sequence(
        self, tag: COSName | None, properties: COSDictionary | None
    ) -> None:
        self.begins.append((tag, properties))
        self.stack.append((tag, properties))

    def end_marked_content_sequence(self) -> None:
        self.ends += 1
        # Upstream silently no-ops on an unbalanced EMC (empty stack).
        if self.stack:
            self.stack.pop()

    def marked_content_point(
        self, tag: COSName | None, properties: COSDictionary | None
    ) -> None:
        self.points.append((tag, properties))


def _bind(engine: RecordingEngine, processor) -> None:
    engine.add_operator(processor)


def _resources_with_property(name: str, props: COSDictionary) -> PDResources:
    """Build a PDResources whose ``/Properties`` maps ``name`` → ``props``."""
    res_dict = COSDictionary()
    properties = COSDictionary()
    properties.set_item(COSName.get_pdf_name(name), props)
    res_dict.set_item(COSName.get_pdf_name("Properties"), properties)
    return PDResources(res_dict)


def _mcid(value: int) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("MCID"), COSInteger.get(value))
    return d


OP_BMC = Operator.get_operator("BMC")
OP_BDC = Operator.get_operator("BDC")
OP_EMC = Operator.get_operator("EMC")
OP_MP = Operator.get_operator("MP")
OP_DP = Operator.get_operator("DP")


# ---------------------------------------------------------------------------
# 1. Operator-name surface
# ---------------------------------------------------------------------------

def test_operator_names() -> None:
    assert BeginMarkedContent().get_name() == "BMC"
    assert BeginMarkedContentWithProps().get_name() == "BDC"
    assert EndMarkedContent().get_name() == "EMC"
    assert DefineMarkedContentPoint().get_name() == "MP"
    assert DefineMarkedContentPointWithProps().get_name() == "DP"


# ---------------------------------------------------------------------------
# 2. BMC — bare begin with a tag
# ---------------------------------------------------------------------------

def test_bmc_with_tag_pushes_with_none_props() -> None:
    e = RecordingEngine()
    p = BeginMarkedContent()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_BMC, [tag])
    assert e.begins == [(tag, None)]
    assert e.stack == [(tag, None)]


def test_bmc_artifact_tag() -> None:
    e = RecordingEngine()
    p = BeginMarkedContent()
    _bind(e, p)
    tag = COSName.get_pdf_name("Artifact")
    p.process(OP_BMC, [tag])
    assert e.begins[0][0] == tag


def test_bmc_last_name_wins() -> None:
    # Upstream BeginMarkedContentSequence keeps the LAST COSName seen.
    e = RecordingEngine()
    p = BeginMarkedContent()
    _bind(e, p)
    a = COSName.get_pdf_name("A")
    b = COSName.get_pdf_name("B")
    p.process(OP_BMC, [a, b])
    assert e.begins[0][0] == b


def test_bmc_skips_leading_junk() -> None:
    e = RecordingEngine()
    p = BeginMarkedContent()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_BMC, [COSInteger.get(1), COSString("x"), tag])
    assert e.begins[0][0] == tag


def test_bmc_no_name_tag_is_none() -> None:
    # Bare BMC tolerates a missing name: tag becomes None, sequence opens.
    e = RecordingEngine()
    p = BeginMarkedContent()
    _bind(e, p)
    p.process(OP_BMC, [COSInteger.get(1)])
    assert e.begins == [(None, None)]


def test_bmc_empty_operands_tag_none() -> None:
    e = RecordingEngine()
    p = BeginMarkedContent()
    _bind(e, p)
    p.process(OP_BMC, [])
    assert e.begins == [(None, None)]


def test_bmc_no_context_no_crash() -> None:
    p = BeginMarkedContent()  # unbound
    p.process(OP_BMC, [COSName.get_pdf_name("Span")])  # must not raise


# ---------------------------------------------------------------------------
# 3. BDC — begin with a property list (inline dict)
# ---------------------------------------------------------------------------

def test_bdc_inline_dict() -> None:
    e = RecordingEngine()
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    props = _mcid(7)
    p.process(OP_BDC, [tag, props])
    assert e.begins == [(tag, props)]
    assert e.stack[-1][1] is props


def test_bdc_tag_is_first_operand_not_last_name() -> None:
    # The property operand of the /Name form is itself a COSName; the tag
    # must remain operands[0], never the trailing name.
    e = RecordingEngine()
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    props = _mcid(3)
    res = _resources_with_property("P1", props)
    e2 = RecordingEngine(res)
    p2 = BeginMarkedContentWithProps()
    _bind(e2, p2)
    tag = COSName.get_pdf_name("Span")
    name = COSName.get_pdf_name("P1")
    p2.process(OP_BDC, [tag, name])
    assert e2.begins[0][0] == tag  # tag, not the trailing name


def test_bdc_named_property_resolved_from_resources() -> None:
    props = _mcid(11)
    res = _resources_with_property("MC0", props)
    e = RecordingEngine(res)
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("OC")
    name = COSName.get_pdf_name("MC0")
    p.process(OP_BDC, [tag, name])
    assert len(e.begins) == 1
    assert e.begins[0][0] == tag
    assert e.begins[0][1] is not None
    # resolved dict carries the MCID
    assert e.begins[0][1].get_int(COSName.get_pdf_name("MCID"), -1) == 11


def test_bdc_oc_optional_content_reference() -> None:
    # /OC with a named property list (OCG/OCMD) — common real-world form.
    ocg = COSDictionary()
    ocg.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("OCG"))
    ocg.set_item(COSName.get_pdf_name("Name"), COSString("layer1"))
    res = _resources_with_property("oc1", ocg)
    e = RecordingEngine(res)
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("OC")
    p.process(OP_BDC, [tag, COSName.get_pdf_name("oc1")])
    assert len(e.begins) == 1
    assert e.begins[0][0] == tag


def test_bdc_unresolved_name_does_not_open() -> None:
    # Name not in /Properties → upstream NPEs / engine swallows; pypdfbox
    # deliberately does not open a sequence.
    res = _resources_with_property("known", _mcid(1))
    e = RecordingEngine(res)
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_BDC, [tag, COSName.get_pdf_name("missing")])
    assert e.begins == []
    assert e.stack == []


def test_bdc_named_no_resources_does_not_open() -> None:
    e = RecordingEngine()  # no resources
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_BDC, [tag, COSName.get_pdf_name("P1")])
    assert e.begins == []


def test_bdc_tag_not_a_name_returns() -> None:
    e = RecordingEngine()
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    p.process(OP_BDC, [COSInteger.get(5), _mcid(2)])
    assert e.begins == []


def test_bdc_props_neither_name_nor_dict_does_not_open() -> None:
    e = RecordingEngine()
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_BDC, [tag, COSInteger.get(9)])
    assert e.begins == []


def test_bdc_missing_operand_raises() -> None:
    e = RecordingEngine()
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    with pytest.raises(MissingOperandException):
        p.process(OP_BDC, [COSName.get_pdf_name("Span")])


def test_bdc_empty_operands_raises() -> None:
    e = RecordingEngine()
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    with pytest.raises(MissingOperandException):
        p.process(OP_BDC, [])


def test_bdc_no_context_no_crash() -> None:
    p = BeginMarkedContentWithProps()  # unbound
    p.process(OP_BDC, [COSName.get_pdf_name("Span"), _mcid(1)])


def test_bdc_extra_operands_ignored() -> None:
    e = RecordingEngine()
    p = BeginMarkedContentWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    props = _mcid(4)
    p.process(OP_BDC, [tag, props, COSInteger.get(99), COSString("z")])
    assert e.begins == [(tag, props)]


# ---------------------------------------------------------------------------
# 4. EMC — end / pop the stack
# ---------------------------------------------------------------------------

def test_emc_pops_balanced() -> None:
    e = RecordingEngine()
    bmc = BeginMarkedContent()
    emc = EndMarkedContent()
    _bind(e, bmc)
    _bind(e, emc)
    bmc.process(OP_BMC, [COSName.get_pdf_name("Span")])
    assert len(e.stack) == 1
    emc.process(OP_EMC, [])
    assert e.stack == []
    assert e.ends == 1


def test_emc_unbalanced_empty_stack_no_crash() -> None:
    # EMC with nothing open: upstream silently no-ops, never raises.
    e = RecordingEngine()
    emc = EndMarkedContent()
    _bind(e, emc)
    emc.process(OP_EMC, [])
    assert e.ends == 1
    assert e.stack == []


def test_emc_ignores_stray_operands() -> None:
    e = RecordingEngine()
    bmc = BeginMarkedContent()
    emc = EndMarkedContent()
    _bind(e, bmc)
    _bind(e, emc)
    bmc.process(OP_BMC, [COSName.get_pdf_name("Span")])
    emc.process(OP_EMC, [COSInteger.get(1), COSName.get_pdf_name("X")])
    assert e.stack == []


def test_emc_no_context_no_crash() -> None:
    p = EndMarkedContent()  # unbound
    p.process(OP_EMC, [])


def test_double_emc_after_single_bmc() -> None:
    # First EMC pops; second EMC underflows but must not raise.
    e = RecordingEngine()
    bmc = BeginMarkedContent()
    emc = EndMarkedContent()
    _bind(e, bmc)
    _bind(e, emc)
    bmc.process(OP_BMC, [COSName.get_pdf_name("Span")])
    emc.process(OP_EMC, [])
    emc.process(OP_EMC, [])
    assert e.stack == []
    assert e.ends == 2


# ---------------------------------------------------------------------------
# 5. Nesting — BDC/BMC ... EMC EMC
# ---------------------------------------------------------------------------

def test_nested_bdc_bmc_emc_emc() -> None:
    res = _resources_with_property("P1", _mcid(1))
    e = RecordingEngine(res)
    bdc = BeginMarkedContentWithProps()
    bmc = BeginMarkedContent()
    emc = EndMarkedContent()
    for proc in (bdc, bmc, emc):
        _bind(e, proc)
    bdc.process(OP_BDC, [COSName.get_pdf_name("Span"), COSName.get_pdf_name("P1")])
    bmc.process(OP_BMC, [COSName.get_pdf_name("Artifact")])
    assert len(e.stack) == 2
    emc.process(OP_EMC, [])
    assert len(e.stack) == 1
    assert e.stack[0][0] == COSName.get_pdf_name("Span")
    emc.process(OP_EMC, [])
    assert e.stack == []


def test_deeply_nested_balanced() -> None:
    e = RecordingEngine()
    bmc = BeginMarkedContent()
    emc = EndMarkedContent()
    _bind(e, bmc)
    _bind(e, emc)
    depth = 12
    for i in range(depth):
        bmc.process(OP_BMC, [COSName.get_pdf_name(f"L{i}")])
    assert len(e.stack) == depth
    for _ in range(depth):
        emc.process(OP_EMC, [])
    assert e.stack == []
    assert e.ends == depth


def test_nesting_unbalanced_extra_emc() -> None:
    e = RecordingEngine()
    bmc = BeginMarkedContent()
    emc = EndMarkedContent()
    _bind(e, bmc)
    _bind(e, emc)
    bmc.process(OP_BMC, [COSName.get_pdf_name("A")])
    emc.process(OP_EMC, [])
    emc.process(OP_EMC, [])  # extra
    emc.process(OP_EMC, [])  # extra
    assert e.stack == []
    assert e.ends == 3


# ---------------------------------------------------------------------------
# 6. MP — marked-content point (no props)
# ---------------------------------------------------------------------------

def test_mp_with_tag() -> None:
    e = RecordingEngine()
    p = DefineMarkedContentPoint()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_MP, [tag])
    assert e.points == [(tag, None)]
    assert e.stack == []  # MP never opens a sequence


def test_mp_last_name_wins() -> None:
    e = RecordingEngine()
    p = DefineMarkedContentPoint()
    _bind(e, p)
    a = COSName.get_pdf_name("A")
    b = COSName.get_pdf_name("B")
    p.process(OP_MP, [a, b])
    assert e.points[0][0] == b


def test_mp_no_name_tag_none() -> None:
    e = RecordingEngine()
    p = DefineMarkedContentPoint()
    _bind(e, p)
    p.process(OP_MP, [COSInteger.get(1)])
    assert e.points == [(None, None)]


def test_mp_no_context_no_crash() -> None:
    p = DefineMarkedContentPoint()  # unbound
    p.process(OP_MP, [COSName.get_pdf_name("Span")])


# ---------------------------------------------------------------------------
# 7. DP — marked-content point with properties
# ---------------------------------------------------------------------------

def test_dp_inline_dict() -> None:
    e = RecordingEngine()
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    props = _mcid(8)
    p.process(OP_DP, [tag, props])
    assert e.points == [(tag, props)]
    assert e.stack == []  # DP never opens a sequence


def test_dp_named_property_resolved() -> None:
    props = _mcid(22)
    res = _resources_with_property("DP0", props)
    e = RecordingEngine(res)
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_DP, [tag, COSName.get_pdf_name("DP0")])
    assert len(e.points) == 1
    assert e.points[0][0] == tag
    assert e.points[0][1].get_int(COSName.get_pdf_name("MCID"), -1) == 22


def test_dp_tag_is_first_operand() -> None:
    props = _mcid(2)
    res = _resources_with_property("Q1", props)
    e = RecordingEngine(res)
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    tag = COSName.get_pdf_name("Span")
    p.process(OP_DP, [tag, COSName.get_pdf_name("Q1")])
    assert e.points[0][0] == tag


def test_dp_unresolved_name_no_point() -> None:
    res = _resources_with_property("known", _mcid(1))
    e = RecordingEngine(res)
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    p.process(OP_DP, [COSName.get_pdf_name("Span"), COSName.get_pdf_name("missing")])
    assert e.points == []


def test_dp_tag_not_name_returns() -> None:
    e = RecordingEngine()
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    p.process(OP_DP, [COSInteger.get(3), _mcid(1)])
    assert e.points == []


def test_dp_missing_operand_raises() -> None:
    e = RecordingEngine()
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    with pytest.raises(MissingOperandException):
        p.process(OP_DP, [COSName.get_pdf_name("Span")])


def test_dp_empty_operands_raises() -> None:
    e = RecordingEngine()
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    with pytest.raises(MissingOperandException):
        p.process(OP_DP, [])


def test_dp_no_context_no_crash() -> None:
    p = DefineMarkedContentPointWithProps()  # unbound
    p.process(OP_DP, [COSName.get_pdf_name("Span"), _mcid(1)])


# ---------------------------------------------------------------------------
# 8. Mixed full content-stream sequence through the registry
# ---------------------------------------------------------------------------

def test_full_stream_through_registered_operators() -> None:
    """Drive the five operators in document order, as the engine would
    dispatch them, asserting the stack stays balanced."""
    res = _resources_with_property("P1", _mcid(5))
    e = RecordingEngine(res)
    bmc = BeginMarkedContent()
    bdc = BeginMarkedContentWithProps()
    emc = EndMarkedContent()
    mp = DefineMarkedContentPoint()
    dp = DefineMarkedContentPointWithProps()
    for proc in (bmc, bdc, emc, mp, dp):
        _bind(e, proc)

    bdc.process(OP_BDC, [COSName.get_pdf_name("Span"), COSName.get_pdf_name("P1")])
    mp.process(OP_MP, [COSName.get_pdf_name("Point")])
    bmc.process(OP_BMC, [COSName.get_pdf_name("Artifact")])
    dp.process(OP_DP, [COSName.get_pdf_name("Span"), _mcid(6)])
    emc.process(OP_EMC, [])  # closes Artifact
    emc.process(OP_EMC, [])  # closes Span

    assert e.stack == []
    assert len(e.begins) == 2
    assert len(e.points) == 2
    assert e.ends == 2


def test_dp_array_operand_type_rejected() -> None:
    # A COSArray as the property operand is neither a name nor a dict.
    e = RecordingEngine()
    p = DefineMarkedContentPointWithProps()
    _bind(e, p)
    p.process(OP_DP, [COSName.get_pdf_name("Span"), COSArray()])
    assert e.points == []
