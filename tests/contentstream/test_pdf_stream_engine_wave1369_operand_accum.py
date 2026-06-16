"""Wave 1369 — operand accumulation + parser-operator adoption parity.

Pins the dispatch-loop bookkeeping that ``_dispatch_tokens`` performs:

- operands are buffered until the next ``Operator`` token, then handed
  to the registered processor (or to ``unsupported_operator``);
- the operand stack is cleared between operators — no leakage across
  dispatches;
- a deep operand stack (long ``TJ`` array, very many numeric pushes
  before the operator) survives without overflow — the engine has no
  hard cap so anything the parser can produce is delivered intact;
- the parser's :class:`Operator` is *promoted* via
  ``Operator.get_operator`` to the canonical contentstream
  :class:`Operator` instance (interning), and any ``image_data`` /
  ``image_parameters`` payload from the parser is attached to the
  adopted instance before dispatch.

These tests complement the surrounding round-trip tests by isolating
the loop itself; if a future refactor accidentally drops operands or
fails to intern the operator instance, this is the first thing to
break.
"""

from __future__ import annotations

import io
from typing import IO, Any

from pypdfbox.contentstream import (
    Operator,
    OperatorProcessor,
    PDContentStream,
    PDFStreamEngine,
)
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
)
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDRectangle, PDResources


class _Recorder(OperatorProcessor):
    """Records the *exact* operand list each dispatch sees."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.calls: list[list[COSBase]] = []

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator
        # Copy: tests need to see what the engine handed in even if it
        # mutates the list later.
        self.calls.append(list(operands))

    def get_name(self) -> str:
        return self._name


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


# ---------- operand accumulation between operators ----------


def test_operands_accumulate_until_operator_then_clear() -> None:
    """Multiple operands between two operators: the first dispatch sees
    *all* of them; the second dispatch sees a fresh, empty stack."""
    engine = PDFStreamEngine()
    proc = _Recorder("foo")
    engine.add_operator(proc)
    end = _Recorder("end")
    engine.add_operator(end)

    # Use literal operators that the parser can tokenize. We'll fake
    # the operands by registering arbitrary-keyword processors and
    # feeding them through process_operator directly.
    engine.process_operator("foo", [COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)])
    engine.process_operator("end", [])
    assert proc.calls == [[COSInteger.get(1), COSInteger.get(2), COSInteger.get(3)]]
    assert end.calls == [[]]


def test_dispatch_tokens_clears_operand_stack_between_operators() -> None:
    """End-to-end through the parser dispatch loop: ``q Q q Q`` fires
    four operator dispatches, each with an empty operand list — no
    operand leaks from one to the next."""
    engine = PDFStreamEngine()
    q_rec = _Recorder("q")
    big_q_rec = _Recorder("Q")
    engine.add_operator(q_rec)
    engine.add_operator(big_q_rec)
    engine.process_stream(_BytesContentStream(b"q Q q Q"))
    assert q_rec.calls == [[], []]
    assert big_q_rec.calls == [[], []]


def test_dispatch_tokens_passes_intervening_operands() -> None:
    """Operands between two operators all reach the second operator —
    none leak forward."""
    engine = PDFStreamEngine()
    proc = _Recorder("cm")
    engine.add_operator(proc)
    engine.process_stream(_BytesContentStream(b"1 0 0 1 100 200 cm"))
    assert len(proc.calls) == 1
    assert len(proc.calls[0]) == 6


# ---------- deep operand stack survives dispatch ----------


def test_deep_operand_stack_dispatches_intact() -> None:
    """A long sequence of operands before a single operator (e.g. a
    ``TJ`` array materialised as positional pushes) is delivered intact
    to the handler. We push 500 numbers then a single operator and
    assert all 500 land."""
    engine = PDFStreamEngine()
    proc = _Recorder("end")
    engine.add_operator(proc)
    nums = b" ".join(str(i).encode("ascii") for i in range(500))
    stream = nums + b" end"
    engine.process_stream(_BytesContentStream(stream))
    assert len(proc.calls) == 1
    assert len(proc.calls[0]) == 500


def test_large_tj_array_survives_dispatch() -> None:
    """TJ array with many string + number entries: every entry is in
    the COSArray passed to the handler."""
    engine = PDFStreamEngine()
    proc = _Recorder("TJ")
    engine.add_operator(proc)
    # Build an array with 100 alternating numbers and string segments.
    parts: list[bytes] = []
    for i in range(50):
        parts.append(b"(x)")
        parts.append(str(-i).encode("ascii"))
    stream = b"[" + b" ".join(parts) + b"] TJ"
    engine.process_stream(_BytesContentStream(stream))
    assert len(proc.calls) == 1
    assert len(proc.calls[0]) == 1
    arr = proc.calls[0][0]
    assert isinstance(arr, COSArray)
    assert arr.size() == 100


# ---------- adoption of parser Operator → contentstream Operator ----------


def test_adopt_parser_operator_interns_via_get_operator() -> None:
    """``_adopt_parser_operator`` re-routes the parser's Operator through
    ``Operator.get_operator`` so the dispatched instance is the
    canonical interned one — saves allocations and enables identity
    comparisons in handlers."""
    from pypdfbox.pdfparser.pdf_stream_parser import Operator as ParserOperator

    parser_op = ParserOperator("Tj")
    adopted = PDFStreamEngine._adopt_parser_operator(parser_op)
    # The adopted instance is the singleton-pool entry.
    assert adopted is Operator.get_operator("Tj")


def test_adopt_parser_operator_preserves_image_data_payload() -> None:
    """For ``BI`` / ``ID``, the parser carries the image bytes on the
    operator. Adoption copies them onto the adopted instance so the
    engine can build a :class:`PDInlineImage` from them."""
    from pypdfbox.pdfparser.pdf_stream_parser import Operator as ParserOperator

    parser_op = ParserOperator("BI")
    parser_op.image_data = b"raster-bytes"
    parser_op.image_parameters = COSDictionary()
    adopted = PDFStreamEngine._adopt_parser_operator(parser_op)
    assert adopted.image_data == b"raster-bytes"
    assert adopted.image_parameters is parser_op.image_parameters


def test_adopt_parser_operator_no_payload_leaves_attrs_unset() -> None:
    """No image payload on the parser side ⇒ no payload on the adopted
    operator. Importantly, the adopted operator's pre-existing
    ``image_data`` / ``image_parameters`` (from a *prior* dispatch
    sharing the same pooled instance) is NOT clobbered by ``None``."""
    from pypdfbox.pdfparser.pdf_stream_parser import Operator as ParserOperator

    # First adopt a Tj with no payload — gets a fresh pooled entry.
    parser_op = ParserOperator("Tj")
    adopted = PDFStreamEngine._adopt_parser_operator(parser_op)
    assert adopted.image_data is None
    assert adopted.image_parameters is None


# ---------- BI dispatch: PDInlineImage construction + show_inline_image hook ----------


def test_bi_dispatch_constructs_pd_inline_image_and_invokes_hook() -> None:
    """End-to-end BI handling: the engine builds a :class:`PDInlineImage`
    from the parser-collated ``BI`` payload and forwards it to
    :meth:`show_inline_image`. Pins the dispatch surface."""
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    class _Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.inline_images: list[PDInlineImage] = []

        def show_inline_image(self, inline_image: PDInlineImage) -> None:
            self.inline_images.append(inline_image)

    engine = _Engine()
    # Use a literal grayscale 2x2 raster; CS=/G is the inline /DeviceGray
    # abbreviation. PDInlineImage will eagerly decode the (empty) filter
    # chain — the data must be exactly W * H * (BPC/8) bytes for the
    # raster to be valid.
    raw = b"BI\n/W 2 /H 2 /CS /G /BPC 8\nID\n\x10\x20\x30\x40\nEI"
    engine.process_stream(_BytesContentStream(raw))
    assert len(engine.inline_images) == 1
    img = engine.inline_images[0]
    assert img.get_width() == 2
    assert img.get_height() == 2


def test_bi_dispatch_with_missing_data_short_circuits() -> None:
    """A truly malformed stream where the parser attached neither
    parameters nor data: upstream's graphics ``BeginInlineImage.process``
    returns before building the image (``data == null`` guard), so no
    image is constructed and the draw hook never fires (wave 1537, pinned
    against the live PDFBox 3.0.7 oracle: ``draws=0``). The parameter dict
    is only synthesised once data is present."""
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    class _Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.inline_images: list[PDInlineImage] = []

        def show_inline_image(self, inline_image: PDInlineImage) -> None:
            self.inline_images.append(inline_image)

    engine = _Engine()
    op = Operator.get_operator("BI")
    # BI bypasses the singleton pool — image_parameters/data default to None.
    assert op.get_image_parameters() is None
    assert op.get_image_data() is None
    engine.process_operator(op, [])
    # data is None → upstream short-circuit, no image built.
    assert len(engine.inline_images) == 0

    # With data present but no parameters, the engine synthesises an empty
    # dict so the PDInlineImage constructor gets a valid argument shape.
    op2 = Operator.get_operator("BI")
    op2.set_image_data(b"\x00")
    engine.process_operator(op2, [])
    assert len(engine.inline_images) == 1
    img = engine.inline_images[0]
    # No /Width set, no /Height set → defaults from PDInlineImage.
    assert img.get_width() == -1
    assert img.get_height() == -1


def test_bi_dispatch_keeps_lite_processor_log_path_live() -> None:
    """After invoking the engine's ``show_inline_image`` hook, the
    dispatch still calls the registered ``BI`` lite stub (so
    upstream-faithful registry observers see the operator). We assert
    via a recorder."""

    class _Engine(PDFStreamEngine):
        def show_inline_image(self, inline_image) -> None:  # type: ignore[override]
            pass

    engine = _Engine()
    rec = _Recorder("BI")
    engine.add_operator(rec)
    op = Operator.get_operator("BI")
    op.set_image_parameters(COSDictionary())
    op.set_image_data(b"")
    engine.process_operator(op, [])
    assert len(rec.calls) == 1


# ---------- get_operators returns a live reference (not a copy) ----------


def test_get_operators_returns_live_map_reference() -> None:
    """``get_operators`` matches upstream's contract — the returned map
    is the *live* registry, not a defensive copy. A test that mutates
    via the returned map should affect subsequent dispatches; pin the
    behaviour so a future copy-on-read refactor is intentional."""
    engine = PDFStreamEngine()
    rec = _Recorder("Tj")
    engine.add_operator(rec)
    ops = engine.get_operators()
    assert ops is engine._operators


# ---------- operator-stack handling for str-form dispatch ----------


def test_process_operator_str_form_normalises_to_operator() -> None:
    """The ``str`` overload of ``process_operator`` re-routes through
    ``Operator.get_operator`` so the handler still receives an
    :class:`Operator` (not a string). Pins the parity overload."""

    class _Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[Operator] = []

        def unsupported_operator(self, operator, operands) -> None:
            self.seen.append(operator)

    engine = _Engine()
    engine.process_operator("ZZ", [])
    assert len(engine.seen) == 1
    assert isinstance(engine.seen[0], Operator)
    assert engine.seen[0].get_name() == "ZZ"


# ---------- malformed token in the middle does not break dispatch ----------


def test_malformed_token_silently_skipped_in_dispatch_loop() -> None:
    """The dispatch loop tolerates non-``Operator``, non-``COSBase``
    tokens by silently skipping them — matches upstream which only
    branches on ``instanceof Operator`` / ``instanceof COSBase``.

    The loop recognises the *parser-internal* :class:`Operator` (in
    :mod:`pypdfbox.pdfparser.pdf_stream_parser`) — distinct from the
    contentstream ``Operator`` it adopts via ``_adopt_parser_operator``.
    """
    from pypdfbox.cos import COSString
    from pypdfbox.pdfparser.pdf_stream_parser import (
        Operator as ParserOperator,
    )

    engine = PDFStreamEngine()
    rec = _Recorder("Tj")
    engine.add_operator(rec)

    class _FakeParser:
        def tokens(self) -> Any:
            yield COSString(b"hello")
            yield object()  # malformed garbage — should be silently dropped
            yield ParserOperator("Tj")

    engine._dispatch_tokens(_FakeParser())
    assert len(rec.calls) == 1
    operands = rec.calls[0]
    assert len(operands) == 1
    assert isinstance(operands[0], COSString)


# ---------- registration-then-context invariant under set_context ----------


def test_set_context_explicit_call_rebinds_processor() -> None:
    """A processor instance can be re-bound to a new engine via
    ``set_context`` directly without going through ``add_operator``.
    Pins the public hook surface."""
    engine_a = PDFStreamEngine()
    engine_b = PDFStreamEngine()
    proc = _Recorder("Tj")
    engine_a.add_operator(proc)
    assert proc.get_context() is engine_a
    proc.set_context(engine_b)
    assert proc.get_context() is engine_b


# ---------- COSName operand on unknown operator surfaces verbatim ----------


def test_unsupported_operator_receives_name_operand_verbatim() -> None:
    """A ``COSName`` operand on an unknown operator is delivered to
    ``unsupported_operator`` as the raw ``COSName`` (no string
    flattening, no quoting). Pins the operand-shape contract."""

    class _Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, list[COSBase]]] = []

        def unsupported_operator(self, operator, operands) -> None:
            self.calls.append((operator.get_name(), list(operands)))

    engine = _Engine()
    name = COSName.get_pdf_name("F1")
    engine.process_operator("XX", [name, COSInteger.get(12)])
    assert engine.calls == [("XX", [name, COSInteger.get(12)])]
