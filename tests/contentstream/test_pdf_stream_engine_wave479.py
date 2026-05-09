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

    engine.process_operator("BI", None)

    assert len(captured) == 1
    params, data, seen_resources = captured[0]
    assert isinstance(params, COSDictionary)
    assert data == b""
    assert seen_resources is resources
    assert len(engine.images) == 1
    assert [call[0].get_name() for call in processor.calls] == ["BI"]


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

    engine.process_operator("BI", [])

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

    engine.process_operator("BI", [])

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
