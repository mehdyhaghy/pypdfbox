"""Differential operand / lookup fuzz of the GRAPHICS content-stream operator
processors vs Apache PDFBox 3.0.7 (wave 1534).

Surface: the *gatekeeping* of the three graphics operators that take a resource
name or a transform matrix —

* ``cm`` — :class:`ConcatenateMatrix` (upstream
  ``org.apache.pdfbox.contentstream.operator.state.Concatenate``): six number
  operands → CTM concatenate; arity / whole-list type guard.
* ``Do`` — :class:`InvokeNamedXObject` (upstream
  ``org.apache.pdfbox.contentstream.operator.graphics.DrawObject``): name
  operand → /XObject lookup → image vs form vs transparency-group dispatch;
  ``MissingOperandException`` / silent-skip / ``MissingResourceException`` /
  non-stream entry.
* ``gs`` — :class:`SetGraphicsStateParameters` (upstream
  ``...operator.state.SetGraphicsStateParameters``): name operand → /ExtGState
  lookup; ``MissingOperandException`` / silent-skip / lookup-miss.

How the oracle works
--------------------
``oracle/probes/GraphicsOperatorFuzzProbe.java`` instantiates each processor
(constructor-injected engine) and calls its ``process(Operator, List)``
DIRECTLY — routing through ``processOperator`` would swallow the exception into
``operatorException`` and hide the arity/type contract. For each case it emits::

    <id>\\tERR:<SimpleExceptionName>     # process() threw
    <id>\\tINVOKED|<detail>             # process() did real work (hook fired)
    <id>\\tSKIP                         # process() returned a no-op
    <id>\\tOK                           # gs clean return (no observable hook)

The pypdfbox side replays the IDENTICAL operand lists through the SAME canonical
graphics processors (``ConcatenateMatrix`` / ``InvokeNamedXObject`` /
``SetGraphicsStateParameters`` — the ones ``PDFGraphicsStreamEngine`` registers)
bound to a recording engine that tracks the CTM and which draw hook fired, and
emits the same projection.

Real bugs this wave caught
--------------------------
1. ``cm`` (``ConcatenateMatrix``): pypdfbox guarded only ``operands[:6]`` for
   COSNumber-ness while upstream's ``Concatenate.process`` calls
   ``checkArrayTypesClass(arguments, COSNumber.class)`` over the WHOLE list. A
   malformed ``a b c d e f /Name cm`` (seven operands, trailing non-number) made
   pypdfbox apply the matrix while upstream silently dropped it. Fixed to guard
   the full operand list; ``cm_seven_trailing_*`` pin it (same class of bug as
   ``Tm`` in wave 1525).
2. ``Do`` (``InvokeNamedXObject``): pypdfbox painted a resolved image XObject
   unconditionally, missing upstream's ``if (!image.isStencil() &&
   !context.isShouldProcessColorOperators()) return;`` guard. With colour-op
   processing suppressed a non-stencil image must be SKIPPED, not drawn. Fixed;
   ``do_image`` pins it.

Pinned (intentional) divergence
-------------------------------
pypdfbox's ``PDFStreamEngine._should_process_color_operators`` DEFAULTS to
``True`` (documented divergence — see the engine constructor) whereas upstream's
``shouldProcessColorOperators`` defaults to ``false`` outside an active stream
run. To make the ``do_image`` comparison apples-to-apples we drive the pypdfbox
recording engine with the flag forced ``False`` (the state the Java probe runs
in). During a real render both engines set the flag ``True`` and paint the
image identically; the default only differs for direct ``process`` calls.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.graphics.concatenate_matrix import (
    ConcatenateMatrix,
)
from pypdfbox.contentstream.operator.graphics.invoke_named_xobject import (
    InvokeNamedXObject,
)
from pypdfbox.contentstream.operator.state.set_graphics_state_parameters import (
    SetGraphicsStateParameters,
)
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
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text


def _identity() -> list[float]:
    return [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def _mul(m1: list[float], m2: list[float]) -> list[float]:
    """Row-vector affine product (m1 * m2) matching upstream
    ``Matrix.multiplyArrays`` — ``cm`` concatenates new = matrix * CTM."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return [
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    ]


class _RecordingEngine(PDFGraphicsStreamEngine):
    """A graphics engine that tracks the CTM (for ``cm``) and which draw hook
    fired (for ``Do``), so the post-call projection matches the Java probe."""

    def __init__(self, resources: PDResources) -> None:
        super().__init__(None)
        self.set_resources(resources)
        self._ctm = _identity()
        self.trace = ""
        # Match the state the Java probe runs in (see module docstring).
        self._set_should_process_color_operators(False)

    def reset(self) -> None:
        self._ctm = _identity()
        self.trace = ""

    # cm hook -----------------------------------------------------------------
    def transform(self, matrix: Any) -> None:
        self._ctm = _mul(list(matrix), self._ctm)

    # Do hooks ----------------------------------------------------------------
    def draw_image(self, pd_image: Any) -> None:
        self.trace = "image"

    def show_form(self, form: Any) -> None:
        self.trace = "form"

    def show_transparency_group(self, form: Any) -> None:
        self.trace = "group"

    # Unused abstract path hooks ---------------------------------------------
    def append_rectangle(self, p0: Any, p1: Any, p2: Any, p3: Any) -> None:
        pass

    def clip(self, winding_rule: int) -> None:
        pass

    def move_to(self, x: float, y: float) -> None:
        pass

    def line_to(self, x: float, y: float) -> None:
        pass

    def curve_to(
        self, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float
    ) -> None:
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

    def shading_fill(self, shading_name: COSName) -> None:
        pass

    # cm projection -----------------------------------------------------------
    def cm_fingerprint(self) -> str:
        m = self._ctm
        if m == _identity():
            return "SKIP"
        return f"INVOKED|a={_g4(m[0])}|d={_g4(m[3])}|e={_g4(m[4])}"


def _g4(value: float) -> str:
    """Match Java's ``%.4g`` rendering for the CTM fingerprint floats. Java's
    ``%g`` keeps trailing zeros to the requested precision; Python's plain
    ``:g`` strips them, so use the alternate form (``#``) which preserves
    them — ``1.5 -> 1.500``, ``2.0 -> 2.000``, ``1e30 -> 1.000e+30``."""
    return f"{value:#.4g}"


def _rect() -> COSArray:
    a = COSArray()
    a.add(COSInteger.get(0))
    a.add(COSInteger.get(0))
    a.add(COSInteger.get(1))
    a.add(COSInteger.get(1))
    return a


def _form_stream() -> COSStream:
    s = COSStream()
    s.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    s.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Form"))
    s.set_item(COSName.get_pdf_name("BBox"), _rect())
    return s


def _image_stream() -> COSStream:
    s = COSStream()
    s.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    s.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    s.set_item(COSName.get_pdf_name("Width"), COSInteger.get(1))
    s.set_item(COSName.get_pdf_name("Height"), COSInteger.get(1))
    s.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    s.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray"))
    return s


def _build_resources() -> PDResources:
    root = COSDictionary()

    xobjects = COSDictionary()
    xobjects.set_item(COSName.get_pdf_name("Frm"), _form_stream())
    xobjects.set_item(COSName.get_pdf_name("Img"), _image_stream())
    xobjects.set_item(COSName.get_pdf_name("Bad"), COSDictionary())
    root.set_item(COSName.XOBJECT, xobjects)

    extgs = COSDictionary()
    good_gs = COSDictionary()
    good_gs.set_item(COSName.TYPE, COSName.get_pdf_name("ExtGState"))
    good_gs.set_item(COSName.get_pdf_name("LW"), COSFloat(3.0))
    extgs.set_item(COSName.get_pdf_name("GS"), good_gs)
    extgs.set_item(COSName.get_pdf_name("GSbad"), COSName.get_pdf_name("nope"))
    root.set_item(COSName.get_pdf_name("ExtGState"), extgs)

    return PDResources(root)


# --- reusable operands (mirror the Java probe one-for-one) -----------------
_NUM = COSFloat(1.5)
_HUGE = COSFloat(1.0e30)
_INT = COSInteger.get(2)
_NAME_FRM = COSName.get_pdf_name("Frm")
_NAME_IMG = COSName.get_pdf_name("Img")
_NAME_BAD = COSName.get_pdf_name("Bad")
_NAME_MISS = COSName.get_pdf_name("Nope")
_NAME_GS = COSName.get_pdf_name("GS")
_NAME_GSBAD = COSName.get_pdf_name("GSbad")
_NAME_GSMISS = COSName.get_pdf_name("Zzz")
_STR = COSString("x")
_ARR = COSArray()
_NULL = COSNull.NULL


def _ops(*items: COSBase) -> list[COSBase]:
    return list(items)


# Each entry: (op-kind, id, operands).
def _cm_cases() -> list[tuple[str, list[COSBase]]]:
    return [
        ("cm_empty", _ops()),
        ("cm_five", _ops(_NUM, _NUM, _NUM, _NUM, _NUM)),
        ("cm_six", _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM)),
        ("cm_six_int", _ops(_INT, _NUM, _NUM, _NUM, _NUM, _NUM)),
        ("cm_six_first_name", _ops(_NAME_FRM, _NUM, _NUM, _NUM, _NUM, _NUM)),
        ("cm_six_one_str", _ops(_NUM, _NUM, _STR, _NUM, _NUM, _NUM)),
        ("cm_six_one_null", _ops(_NUM, _NUM, _NUM, _NUM, _NULL, _NUM)),
        ("cm_huge", _ops(_HUGE, _NUM, _NUM, _HUGE, _NUM, _NUM)),
        ("cm_seven_all_num", _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NUM)),
        (
            "cm_seven_trailing_name",
            _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NAME_FRM),
        ),
        (
            "cm_seven_trailing_null",
            _ops(_NUM, _NUM, _NUM, _NUM, _NUM, _NUM, _NULL),
        ),
    ]


def _do_cases() -> list[tuple[str, list[COSBase]]]:
    return [
        ("do_empty", _ops()),
        ("do_num", _ops(_NUM)),
        ("do_str", _ops(_STR)),
        ("do_null", _ops(_NULL)),
        ("do_form", _ops(_NAME_FRM)),
        ("do_image", _ops(_NAME_IMG)),
        ("do_missing", _ops(_NAME_MISS)),
        ("do_nonstream", _ops(_NAME_BAD)),
        ("do_extra_trailing", _ops(_NAME_FRM, _NUM)),
    ]


def _gs_cases() -> list[tuple[str, list[COSBase]]]:
    return [
        ("gs_empty", _ops()),
        ("gs_num", _ops(_NUM)),
        ("gs_str", _ops(_STR)),
        ("gs_null", _ops(_NULL)),
        ("gs_arr", _ops(_ARR)),
        ("gs_good", _ops(_NAME_GS)),
        ("gs_missing", _ops(_NAME_GSMISS)),
        ("gs_nondict", _ops(_NAME_GSBAD)),
        ("gs_extra_trailing", _ops(_NAME_GS, _NUM)),
    ]


_IDS = (
    [c[0] for c in _cm_cases()]
    + [c[0] for c in _do_cases()]
    + [c[0] for c in _gs_cases()]
)


def _pypdfbox_outcomes() -> dict[str, str]:
    engine = _RecordingEngine(_build_resources())
    out: dict[str, str] = {}

    cm = ConcatenateMatrix()
    cm.set_context(engine)
    for case_id, operands in _cm_cases():
        engine.reset()
        try:
            cm.process(Operator.get_operator("cm"), operands)
        except OSError as exc:
            out[case_id] = f"ERR:{_err_name(exc)}"
            continue
        out[case_id] = engine.cm_fingerprint()

    do_op = InvokeNamedXObject()
    do_op.set_context(engine)
    for case_id, operands in _do_cases():
        engine.reset()
        try:
            do_op.process(Operator.get_operator("Do"), operands)
        except OSError as exc:
            out[case_id] = f"ERR:{_err_name(exc)}"
            continue
        out[case_id] = "SKIP" if not engine.trace else "INVOKED|" + engine.trace

    gs = SetGraphicsStateParameters()
    gs.set_context(engine)
    for case_id, operands in _gs_cases():
        engine.reset()
        try:
            gs.process(Operator.get_operator("gs"), operands)
        except OSError as exc:
            out[case_id] = f"ERR:{_err_name(exc)}"
            continue
        out[case_id] = "OK"

    return out


def _err_name(exc: Exception) -> str:
    """Map pypdfbox exception class to the upstream simple name the probe
    emits. ``MissingOperandException`` / ``MissingResourceException`` carry
    over verbatim; a generic non-stream ``OSError`` maps to upstream's
    ``IOException``."""
    name = type(exc).__name__
    if name == "OSError":
        return "IOException"
    return name


def _parse_java(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        case_id, _, outcome = line.partition("\t")
        result[case_id] = outcome
    return result


@requires_oracle
def test_graphics_operator_fuzz_parity() -> None:
    java = _parse_java(run_probe_text("GraphicsOperatorFuzzProbe"))
    py = _pypdfbox_outcomes()
    assert set(py) == set(java), (
        f"case-id mismatch: py-only={set(py) - set(java)} "
        f"java-only={set(java) - set(py)}"
    )
    diffs = {
        cid: (java[cid], py[cid]) for cid in java if java[cid] != py[cid]
    }
    assert not diffs, (
        "graphics-operator operand-fuzz divergences (java, py):\n"
        + "\n".join(
            f"  {cid}: java={j!r} py={p!r}" for cid, (j, p) in sorted(diffs.items())
        )
    )


@pytest.mark.parametrize("case_id", _IDS)
def test_pypdfbox_outcomes_present(case_id: str) -> None:
    """Cheap non-oracle guard: every case yields a non-empty outcome so a
    builder regression can't silently drop cases when the oracle is absent."""
    out = _pypdfbox_outcomes()
    assert out[case_id]


def test_cm_whole_list_type_guard() -> None:
    """Regression pin for the wave-1534 ``cm`` fix: a seventh trailing
    non-number operand makes ``cm`` a silent no-op (whole-list guard),
    matching upstream ``checkArrayTypesClass(arguments, COSNumber.class)``."""
    out = _pypdfbox_outcomes()
    assert out["cm_seven_all_num"].startswith("INVOKED")
    assert out["cm_seven_trailing_name"] == "SKIP"
    assert out["cm_seven_trailing_null"] == "SKIP"
    assert out["cm_six_one_str"] == "SKIP"


def test_do_image_skip_when_colors_suppressed() -> None:
    """Regression pin for the wave-1534 ``Do`` fix: a non-stencil image is
    SKIPPED (not painted) when colour-operator processing is suppressed,
    mirroring upstream's ``!isStencil() && !isShouldProcessColorOperators()``
    early return."""
    out = _pypdfbox_outcomes()
    assert out["do_image"] == "SKIP"
    assert out["do_form"] == "INVOKED|form"
    assert out["do_missing"] == "ERR:MissingResourceException"
    assert out["do_nonstream"] == "ERR:IOException"
