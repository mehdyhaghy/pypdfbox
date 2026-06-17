"""Live PDFBox differential parity for the ``PDFStreamEngine`` form-XObject
``Do`` recursion guard.

A form XObject that invokes itself (directly, ``/Self Do``) or via a cycle
(``FormA -> FormB -> FormA``) must NOT infinite-loop. Upstream PDFBox 3.0.7
guards this in ``DrawObject.process``: it calls ``increaseLevel()`` before
drawing a form and, when ``getLevel() > 50``, logs *"recursion is too deep,
skipping form XObject"* and returns without recursing. The dispatch therefore
terminates at a finite, deterministic operator count.

``FormRecursionGuardProbe`` builds the two PDFs (self-referencing form;
two-form cycle), drives PDFBox's engine over each with a counting
``PDFStreamEngine`` subclass, and emits the finite total operator count.
pypdfbox loads the **same saved bytes**, registers the mirror ``DrawObject``
processor, counts every ``process_operator`` dispatch, and asserts the same
finite counts — proving termination plus behaviour parity of the depth cap.

Canonical output (must match ``oracle/probes/FormRecursionGuardProbe.java``)::

    SELF <count>
    CYCLE <count>
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator.draw_object import DrawObject
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text


class _CountingEngine(PDFStreamEngine):
    """Counts every dispatched operator and draws form XObjects, mirroring
    the Java ``CountingEngine`` in the probe."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0
        self.add_operator(DrawObject())

    def process_operator(
        self, operator: object, operands: list[COSBase] | None
    ) -> None:
        self.count += 1
        super().process_operator(operator, operands)


def _count_for(pdf_path: Path) -> int:
    with PDDocument.load(pdf_path) as doc:
        engine = _CountingEngine()
        engine.process_page(doc.get_page(0))
        return engine.count


@requires_oracle
def test_form_recursion_guard_matches_pdfbox() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        self_pdf = Path(tmp) / "self_ref.pdf"
        cycle_pdf = Path(tmp) / "cycle.pdf"

        lines = run_probe_text(
            "FormRecursionGuardProbe", str(self_pdf), str(cycle_pdf)
        ).splitlines()
        java = dict(line.split(" ", 1) for line in lines if line)
        java_self = int(java["SELF"])
        java_cycle = int(java["CYCLE"])

        # Both forms terminate (depth cap), at the same finite count upstream
        # measured. The cap is depth-based, so self and cycle agree.
        assert java_self == java_cycle

        py_self = _count_for(self_pdf)
        py_cycle = _count_for(cycle_pdf)

    assert py_self == java_self
    assert py_cycle == java_cycle
