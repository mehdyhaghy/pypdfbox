"""Live PDFBox differential parity for the ``sh`` (shading fill) content-stream
operator's operand validation and shading-resource lookup.

Two complementary signals per case, matching ``ShadingFillFuzzProbe.java``:

* ENGINE path — a minimal :class:`PDFGraphicsStreamEngine` processes a tiny
  synthetic content stream and records each ``shading_fill(COSName)``
  invocation that survives the engine's ``operator_exception`` triage. A
  ``MissingOperandException`` is logged + swallowed upstream, so an invalid
  ``sh`` produces NO invocation and does not abort the stream.
* PROCESS path — ``ShadingFill.process(op, operands)`` is called directly with
  hand-built operand lists so the raw operand-count / operand-type gate is
  observed without the engine swallow: ``process=ok`` (forwarded to
  ``shading_fill``), or ``process=missing-operand``
  (``MissingOperandException``).

Key oracle findings (PDFBox 3.0.7):

* ``ShadingFill.process`` validates only the leading operand — empty operands
  *or* a non-``COSName`` operand 0 both raise ``MissingOperandException``
  (the latter is a real divergence pypdfbox previously skipped silently; fixed
  in this wave).
* No resource lookup happens in the operator. An unknown shading name, a
  missing ``/Shading`` sub-dict, a wrong-typed ``/Shading`` entry, and even
  ``null`` resources all still invoke ``shading_fill(name)`` — the lookup /
  skip happens inside the downstream hook, not in the operator.
* "Extra operands" (``1 2 /Sh1 sh``) push the name off position 0, so the
  leading operand is a number → ``MissingOperandException`` / no invocation.

Canonical line grammar (must match the probe)::

    engine=fill:<name>   (one per surviving shading_fill call)
    engine=none          (no shading_fill call fired)
    process=ok | process=missing-operand
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.graphics.shading_fill import ShadingFill
from pypdfbox.contentstream.pdf_graphics_stream_engine import (
    PDFGraphicsStreamEngine,
)
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

CASES = [
    "normal",
    "no_operand",
    "extra_operands",
    "non_name_operand",
    "missing_name",
    "no_shading_dict",
    "wrong_type_entry",
    "null_resources",
]

_CONTENT = {
    "no_operand": b"sh\n",
    "extra_operands": b"1 2 /Sh1 sh\n",
    "non_name_operand": b"42 sh\n",
}


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _axial_shading() -> COSDictionary:
    sh = COSDictionary()
    sh.set_int(_name("ShadingType"), 2)
    sh.set_item(_name("ColorSpace"), _name("DeviceRGB"))
    coords = COSArray()
    for value in (0, 0, 100, 0):
        coords.add(COSFloat(value))
    sh.set_item(_name("Coords"), coords)
    fn = COSDictionary()
    fn.set_int(_name("FunctionType"), 2)
    domain = COSArray()
    domain.add(COSFloat(0))
    domain.add(COSFloat(1))
    fn.set_item(_name("Domain"), domain)
    c0 = COSArray()
    for _ in range(3):
        c0.add(COSFloat(0))
    c1 = COSArray()
    for _ in range(3):
        c1.add(COSFloat(1))
    fn.set_item(_name("C0"), c0)
    fn.set_item(_name("C1"), c1)
    fn.set_item(COSName.N, COSFloat(1))
    sh.set_item(_name("Function"), fn)
    return sh


def _build_resources(which: str) -> PDResources:
    res = PDResources()
    if which == "no_shading_dict":
        return res
    if which == "wrong_type_entry":
        sh_dict = COSDictionary()
        sh_dict.set_item(_name("Sh1"), _name("Bogus"))
        res.get_cos_object().set_item(_name("Shading"), sh_dict)
        return res
    if which == "missing_name":
        sh_dict = COSDictionary()
        sh_dict.set_item(_name("Other"), _axial_shading())
        res.get_cos_object().set_item(_name("Shading"), sh_dict)
        return res
    sh_dict = COSDictionary()
    sh_dict.set_item(_name("Sh1"), _axial_shading())
    res.get_cos_object().set_item(_name("Shading"), sh_dict)
    return res


def _operands_for(which: str) -> list[COSBase]:
    if which == "no_operand":
        return []
    if which == "extra_operands":
        return [COSInteger.get(1), COSInteger.get(2), _name("Sh1")]
    if which == "non_name_operand":
        return [COSInteger.get(42)]
    return [_name("Sh1")]


class _RecordingEngine(PDFGraphicsStreamEngine):
    """Engine that records every ``shading_fill`` invocation; all paint
    hooks are no-ops."""

    def __init__(self, page: PDPage) -> None:
        super().__init__(page)
        self.fills: list[str] = []

    def shading_fill(self, shading_name: COSName) -> None:
        self.fills.append(
            "null" if shading_name is None else shading_name.get_name()
        )

    def append_rectangle(self, p0, p1, p2, p3) -> None:  # noqa: ANN001
        pass

    def draw_image(self, pd_image) -> None:  # noqa: ANN001
        pass

    def clip(self, winding_rule: int) -> None:
        pass

    def move_to(self, x: float, y: float) -> None:
        pass

    def line_to(self, x: float, y: float) -> None:
        pass

    def curve_to(self, x1, y1, x2, y2, x3, y3) -> None:  # noqa: ANN001
        pass

    def get_current_point(self) -> tuple[float, float]:
        return (0.0, 0.0)

    def close_path(self) -> None:
        pass

    def end_path(self) -> None:
        pass

    def stroke_path(self) -> None:
        pass

    def fill_path(self, winding_rule: int) -> None:
        pass

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        pass


def _emit(case: str) -> str:
    lines: list[str] = []

    # ENGINE path.
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        if case != "null_resources":
            page.set_resources(_build_resources(case))
        stream = PDStream(doc)
        with stream.create_output_stream() as out:
            out.write(_CONTENT.get(case, b"/Sh1 sh\n"))
        page.set_contents(stream)
        engine = _RecordingEngine(page)
        engine.process_page(page)
        if not engine.fills:
            lines.append("engine=none")
        else:
            lines.extend(f"engine=fill:{f}" for f in engine.fills)
    finally:
        doc.close()

    # PROCESS path.
    doc2 = PDDocument()
    try:
        page2 = PDPage()
        doc2.add_page(page2)
        if case != "null_resources":
            page2.set_resources(_build_resources(case))
        engine2 = _RecordingEngine(page2)
        handler = ShadingFill()
        handler.set_context(engine2)
        try:
            handler.process(Operator.get_operator("sh"), _operands_for(case))
            lines.append("process=ok")
        except MissingOperandException:
            lines.append("process=missing-operand")
    finally:
        doc2.close()

    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize("case", CASES)
def test_shading_fill_fuzz_matches_pdfbox(case: str) -> None:
    java = run_probe_text("ShadingFillFuzzProbe", case)
    py = _emit(case)
    assert py == java
