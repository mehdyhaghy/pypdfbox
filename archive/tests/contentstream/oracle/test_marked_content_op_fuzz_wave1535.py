"""Wave 1535 — live-oracle parity for the marked-content content-stream
operator PROCESSORS (BMC / BDC / EMC / MP / DP).

Where ``tests/contentstream/oracle/test_marked_content_*`` (if any) and the
generic ``MarkedContentProbe`` check a *page's* token stream, this module
drives the registered operator-processor classes
(``pypdfbox.contentstream.operator.markedcontent.*``) directly with a
recording context that maintains the marked-content stack exactly like
upstream ``PDFMarkedContentExtractor`` — then projects the resulting tree in
the same canonical format the Java probe emits and asserts byte-for-byte
parity against the live PDFBox 3.0.7 oracle.

The fuzz angle is the operator-processor OPERAND HANDLING + the
marked-content STACK:
- BMC / MP tag selection (last ``COSName`` wins; leading junk skipped),
- BDC / DP property resolution (inline dict vs ``/Name`` -> ``/Properties``
  lookup; unknown name / wrong type / missing operand all SUPPRESS the
  sequence — upstream returns without pushing a node),
- EMC underflow (no-op), unbalanced BMC (residue), nesting.

Probe: ``oracle/probes/MarkedContentOpFuzzProbe.java``.
"""

from __future__ import annotations

import contextlib

import pytest

from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.markedcontent import (
    BeginMarkedContent,
    BeginMarkedContentWithProps,
    DefineMarkedContentPoint,
    DefineMarkedContentPointWithProps,
    EndMarkedContent,
)
from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_property_list import (
    PDPropertyList,
)
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

# Named fuzz cases — identical content-stream text to the Java probe.
CASES: dict[str, str] = {
    "balanced": "/Span BMC EMC",
    "nested": "/Span BMC /Quote BMC EMC EMC",
    "bmc_no_operand": "BMC EMC",
    "bmc_non_name_tag": "42 BMC EMC",
    "bmc_trailing_name": "1 (x) /Span BMC EMC",
    "bdc_inline_dict": "/Span << /MCID 3 >> BDC EMC",
    "bdc_named_props": "/Span /P0 BDC EMC",
    "bdc_unknown_name": "/Span /NoSuch BDC EMC",
    "bdc_missing_props": "/Span BDC EMC",
    "bdc_no_operands": "BDC EMC",
    "bdc_wrong_props_type": "/Span (props) BDC EMC",
    "bdc_non_name_tag": "5 << /MCID 1 >> BDC EMC",
    "emc_underflow": "EMC",
    "emc_double_underflow": "/Span BMC EMC EMC",
    "unbalanced_bmc": "/Span BMC",
    "unbalanced_two_bmc": "/A BMC /B BMC EMC",
    "mp_point": "/Span MP",
    "mp_no_operand": "MP",
    "dp_inline_dict": "/Span << /MCID 9 >> DP",
    "dp_named_props": "/Span /P0 DP",
    "dp_missing_props": "/Span DP",
    "dp_no_operands": "DP",
    "dp_wrong_props_type": "/Span (props) DP",
}


class _RecordingContext:
    """Minimal stream-engine stand-in for the marked-content operators.

    Mirrors upstream ``PDFMarkedContentExtractor``'s stack handling:
    ``begin_marked_content_sequence`` pushes a ``PDMarkedContent`` (nesting
    under the current top), ``end_marked_content_sequence`` pops (no-op on
    underflow), ``marked_content_point`` is a no-op (matching upstream).
    Exposes ``get_resources`` so the ``/Name`` -> ``/Properties`` branch of
    BDC/DP resolves against a real :class:`PDResources`.
    """

    def __init__(self, resources: PDResources) -> None:
        self._resources = resources
        self.roots: list[PDMarkedContent] = []
        self._stack: list[PDMarkedContent] = []

    def get_resources(self) -> PDResources:
        return self._resources

    def begin_marked_content_sequence(
        self, tag: COSName | None, properties: COSDictionary | None
    ) -> None:
        node = PDMarkedContent.create(tag, properties)
        if not self._stack:
            self.roots.append(node)
        else:
            self._stack[-1].add_marked_content(node)
        self._stack.append(node)

    def end_marked_content_sequence(self) -> None:
        if self._stack:
            self._stack.pop()

    def marked_content_point(
        self, tag: COSName | None, properties: COSDictionary | None
    ) -> None:
        del tag, properties  # upstream no-op


def _make_resources() -> PDResources:
    resources = PDResources()
    mc0 = COSDictionary()
    mc0.set_int(COSName.get_pdf_name("MCID"), 7)
    mc0.set_string(COSName.get_pdf_name("Lang"), "en-US")
    resources.put(COSName.get_pdf_name("P0"), PDPropertyList.create(mc0))
    return resources


def _processors(context: _RecordingContext) -> dict[str, object]:
    procs: dict[str, object] = {}
    for cls in (
        BeginMarkedContent,
        BeginMarkedContentWithProps,
        EndMarkedContent,
        DefineMarkedContentPoint,
        DefineMarkedContentPointWithProps,
    ):
        proc = cls()
        proc.set_context(context)  # type: ignore[arg-type]
        procs[proc.get_name()] = proc
    return procs


def _project(content: str) -> str:
    """Drive a content stream through the operator processors; emit the
    canonical ``err= / roots= / MC depth=…`` projection.

    ``MissingOperandException`` is caught *per operator* — mirroring
    upstream ``PDFStreamEngine.processOperator`` (and pypdfbox's
    ``operator_exception``), which logs and continues rather than aborting
    the whole stream. The engine never surfaces it to the page driver, so
    the projected ``err`` stays ``<none>`` for the underflow cases.
    """
    context = _RecordingContext(_make_resources())
    procs = _processors(context)
    err = "<none>"
    raw = content.encode("latin-1")
    operands: list[object] = []
    with RandomAccessReadBuffer(raw) as src:
        parser = PDFStreamParser(src)
        for token in parser.tokens():
            if isinstance(token, Operator):
                proc = procs.get(token.get_name())
                if proc is not None:
                    # The engine catches MissingOperandException (via
                    # ``operator_exception``), logs, and continues — so the
                    # underflow operators leave no observable effect.
                    with contextlib.suppress(MissingOperandException):
                        proc.process(token, operands)  # type: ignore[attr-defined]
                operands = []
            else:
                operands.append(token)

    lines = [f"err={err}", f"roots={len(context.roots)}"]
    for root in context.roots:
        _emit(root, 0, lines)
    return "\n".join(lines) + "\n" if lines else ""


def _emit(node: PDMarkedContent, depth: int, out: list[str]) -> None:
    tag = node.get_tag()
    children = [c for c in node.get_contents() if isinstance(c, PDMarkedContent)]
    out.append(
        f"MC depth={depth} tag={tag if tag is not None else '<null>'} "
        f"mcid={node.get_mcid()} children={len(children)}"
    )
    for child in children:
        _emit(child, depth + 1, out)


@requires_oracle
@pytest.mark.parametrize("case", list(CASES), ids=list(CASES))
def test_marked_content_op_matches_oracle(case: str) -> None:
    """pypdfbox operator-processor projection == live PDFBox projection."""
    java = run_probe_text("MarkedContentOpFuzzProbe", case)
    py = _project(CASES[case])
    # Normalise trailing newline differences.
    assert py.strip() == java.strip()


def test_extract_tag_last_name_wins() -> None:
    """Regression for the wave-1535 ``extract_tag`` fix: BMC/MP take the
    LAST ``COSName`` operand, skipping leading junk (upstream iterates the
    whole operand list)."""
    from pypdfbox.contentstream.operator.markedcontent import extract_tag
    from pypdfbox.cos import COSInteger, COSString

    span = COSName.get_pdf_name("Span")
    assert extract_tag([COSInteger.get(1), COSString("x"), span]) is span
    a = COSName.get_pdf_name("A")
    b = COSName.get_pdf_name("B")
    assert extract_tag([a, b]) is b
    assert extract_tag([COSInteger.get(1)]) is None
    assert extract_tag([]) is None
