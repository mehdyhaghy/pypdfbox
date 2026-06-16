from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import Operator, OperatorProcessor, PDFStreamEngine
from pypdfbox.cos import COSBase, COSDictionary
from pypdfbox.pdmodel import PDResources


class _Recorder(OperatorProcessor):
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.calls: list[tuple[Operator, list[COSBase]]] = []

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self.calls.append((operator, list(operands)))

    def get_name(self) -> str:
        return self._name


class _ExceptionRecordingEngine(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.exceptions: list[tuple[str, list[COSBase], OSError]] = []

    def operator_exception(
        self,
        operator: Operator,
        operands: list[COSBase],
        exception: OSError,
    ) -> None:
        self.exceptions.append((operator.get_name(), list(operands), exception))


def test_inline_image_without_parser_payload_uses_empty_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With data present but no parameter dict, the engine synthesises an
    empty ``COSDictionary`` and forwards the engine resources unchanged.

    A ``BI`` whose data slot is ``None`` (truly malformed stream) is
    short-circuited before the constructor — upstream's graphics
    ``BeginInlineImage.process`` guard ``if (data == null ...) return``
    (wave 1537, pinned against the live PDFBox 3.0.7 oracle: ``draws=0``)."""
    captured: list[tuple[COSDictionary, bytes, PDResources | None]] = []
    resources = PDResources()

    class _InlineImage:
        def __init__(
            self,
            params: COSDictionary,
            data: bytes,
            resources_arg: PDResources | None,
        ) -> None:
            captured.append((params, data, resources_arg))

        def is_empty(self) -> bool:
            return False

        def is_stencil(self) -> bool:
            return False

    class _Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.images: list[Any] = []

        def show_inline_image(self, inline_image: Any) -> None:
            self.images.append(inline_image)

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.image.pd_inline_image.PDInlineImage",
        _InlineImage,
    )
    engine = _Engine()
    engine.set_resources(resources)
    processor = _Recorder("BI")
    engine.add_operator(processor)

    # data is None → short-circuit: no constructor call, no draw, but the
    # registry stub still fires.
    engine.process_operator("BI", None)
    assert captured == []
    assert engine.images == []
    assert [call[0].get_name() for call in processor.calls] == ["BI"]

    # With data present and no parameter dict, the empty-dict synthesis path
    # runs: one constructor call with an empty dict + the engine resources.
    op = Operator.get_operator("BI")
    op.set_image_data(b"\x00")
    engine.process_operator(op, [])
    assert len(captured) == 1
    params, data, seen_resources = captured[0]
    assert isinstance(params, COSDictionary)
    assert data == b"\x00"
    assert seen_resources is resources
    assert len(engine.images) == 1
    assert [call[0].get_name() for call in processor.calls] == ["BI", "BI"]


def test_inline_image_constructor_error_is_triaged_without_stub_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _InlineImage:
        def __init__(
            self,
            params: COSDictionary,
            data: bytes,
            resources: PDResources | None,
        ) -> None:
            raise OSError("bad inline image")

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.image.pd_inline_image.PDInlineImage",
        _InlineImage,
    )
    engine = _ExceptionRecordingEngine()
    processor = _Recorder("BI")
    engine.add_operator(processor)

    op = Operator.get_operator("BI")
    op.set_image_data(b"\x00")  # non-empty so the constructor is reached
    engine.process_operator(op, [])

    assert [(name, str(exc)) for name, _, exc in engine.exceptions] == [
        ("BI", "bad inline image")
    ]
    assert processor.calls == []


def test_inline_image_show_error_is_triaged_without_stub_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _InlineImage:
        def __init__(
            self,
            params: COSDictionary,
            data: bytes,
            resources: PDResources | None,
        ) -> None:
            pass

        def is_empty(self) -> bool:
            return False

        def is_stencil(self) -> bool:
            return False

    class _Engine(_ExceptionRecordingEngine):
        def show_inline_image(self, inline_image: Any) -> None:
            raise OSError("draw failed")

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.image.pd_inline_image.PDInlineImage",
        _InlineImage,
    )
    engine = _Engine()
    processor = _Recorder("BI")
    engine.add_operator(processor)

    op = Operator.get_operator("BI")
    op.set_image_data(b"\x00")  # non-empty so the draw path is reached
    engine.process_operator(op, [])

    assert [(name, str(exc)) for name, _, exc in engine.exceptions] == [
        ("BI", "draw failed")
    ]
    assert processor.calls == []


def test_adopt_parser_operator_preserves_image_parameters_and_data() -> None:
    from pypdfbox.pdfparser.pdf_stream_parser import Operator as ParserOperator

    params = COSDictionary()
    parser_operator = ParserOperator(
        "BI",
        image_data=b"abc",
        image_parameters=params,
    )

    adopted = PDFStreamEngine._adopt_parser_operator(parser_operator)

    assert adopted.get_name() == "BI"
    assert adopted.get_image_data() == b"abc"
    assert adopted.get_image_parameters() is params


def test_save_graphics_stack_keeps_reference_when_copy_raises_value_error() -> None:
    class _ValueErrorOnCopy:
        def __copy__(self) -> _ValueErrorOnCopy:
            raise ValueError("cannot copy")

    engine = PDFStreamEngine()
    frame = _ValueErrorOnCopy()
    engine._graphics_stack.append(frame)

    snapshot = engine.save_graphics_stack()

    assert snapshot == [frame]
    assert engine.get_graphics_state() is frame


def test_operator_exception_reraises_non_do_oserror() -> None:
    engine = PDFStreamEngine()
    operator = Operator.get_operator("Tj")
    original = OSError("boom")

    with pytest.raises(OSError) as exc_info:
        engine.operator_exception(operator, [], original)

    assert exc_info.value is original
