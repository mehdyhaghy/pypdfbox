from __future__ import annotations

import io
from typing import IO, Any

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    OperatorProcessor,
    PDContentStream,
    PDFStreamEngine,
)
from pypdfbox.contentstream import (
    Operator as EngineOperator,
)
from pypdfbox.cos import COSBase, COSDictionary, COSInteger
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDRectangle, PDResources


def _parser(data: bytes) -> PDFStreamParser:
    return PDFStreamParser(RandomAccessReadBuffer(data))


class _BytesContentStream(PDContentStream):
    def __init__(
        self, data: bytes, resources: PDResources | None = None
    ) -> None:
        self._data = data
        self._resources = resources

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_contents_for_stream_parsing(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return self._resources

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 1.0, 1.0)

    def get_matrix(self) -> Any:
        return None


class _ProbeProcessor(OperatorProcessor):
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.calls: list[tuple[str, list[COSBase]]] = []
        self.resources_seen: list[PDResources | None] = []

    def process(
        self, operator: EngineOperator, operands: list[COSBase]
    ) -> None:
        self.calls.append((operator.get_name(), list(operands)))
        self.resources_seen.append(self.get_context().get_resources())

    def get_name(self) -> str:
        return self._name


def test_id_operator_accepts_crlf_separator_and_captures_payload() -> None:
    p = _parser(b"ID\r\nabc\nEI Q")

    token = p.parse_next_token()
    next_token = p.parse_next_token()

    assert isinstance(token, Operator)
    assert token.get_name() == "ID"
    assert token.get_image_data() == b"abc\n"
    assert isinstance(next_token, Operator)
    assert next_token.get_name() == "Q"


def test_inline_image_ei_followed_by_binary_is_kept_in_payload() -> None:
    token = _parser(b"BI /W 5 /H 1 ID\nabEI \xffcd\nEI Q").parse()[0]

    assert isinstance(token, Operator)
    assert token.get_name() == "BI"
    assert token.get_image_data() == b"abEI \xffcd\n"


def test_operator_reader_stops_before_digit_except_d0_d1() -> None:
    tokens = _parser(b"abc123 d0 d1").parse()

    assert isinstance(tokens[0], Operator)
    assert tokens[0].get_name() == "abc"
    assert isinstance(tokens[1], COSInteger)
    assert tokens[1].int_value() == 123
    assert [token.get_name() for token in tokens[2:]] == ["d0", "d1"]


def test_operator_equality_uses_name_and_image_data_not_parameters() -> None:
    left = Operator("BI", image_data=b"same", image_parameters=COSDictionary())
    right = Operator("BI", image_data=b"same", image_parameters=COSDictionary())
    different_data = Operator("BI", image_data=b"other")

    assert left == right
    assert left != different_data
    assert left != object()
    assert hash(left) == hash(right)


def test_has_no_following_bin_data_restores_position() -> None:
    p = _parser(b" Q")
    start = p.get_position()

    assert p.has_next_space_or_return() is True
    assert p._has_no_following_bin_data() is True  # noqa: SLF001

    assert p.get_position() == start
    assert p.parse_next_token().get_name() == "Q"


def test_process_stream_temporarily_uses_child_resources() -> None:
    outer = PDResources()
    inner = PDResources()
    engine = PDFStreamEngine()
    engine._resources = outer  # noqa: SLF001
    probe = _ProbeProcessor("Tj")
    engine.add_operator(probe)

    engine.process_stream(_BytesContentStream(b"1 Tj", inner))

    assert probe.resources_seen == [inner]
    assert engine.get_resources() is outer


def test_process_stream_preserves_resources_when_child_has_none() -> None:
    outer = PDResources()
    engine = PDFStreamEngine()
    engine._resources = outer  # noqa: SLF001
    probe = _ProbeProcessor("Tj")
    engine.add_operator(probe)

    engine.process_stream(_BytesContentStream(b"2 Tj", None))

    assert probe.resources_seen == [outer]
    assert engine.get_resources() is outer


def test_nested_stream_aliases_route_through_process_stream() -> None:
    engine = PDFStreamEngine()
    probe = _ProbeProcessor("Tj")
    engine.add_operator(probe)
    stream = _BytesContentStream(b"(x) Tj")

    engine.process_form(stream)  # type: ignore[arg-type]
    engine.process_tiling_pattern(stream, color=object(), color_space=object())
    engine.process_type3_stream(stream, text_matrix=object())

    assert [call[0] for call in probe.calls] == ["Tj", "Tj", "Tj"]
    assert engine.get_level() == 0


def test_set_resources_pushes_previous_resource_frame() -> None:
    first = PDResources()
    second = PDResources()
    engine = PDFStreamEngine()
    engine.set_resources(first)
    engine.set_resources(second)

    assert engine.get_resources() is second
    assert engine._resources_stack == [None, first]  # noqa: SLF001


def test_show_text_uses_text_state_font_and_displacement() -> None:
    class _Font:
        def read_code(self, src: Any) -> int | None:
            value = src.read(1)
            if not value:
                return None
            return value[0]

        def get_displacement(self, code: int) -> tuple[int, int]:
            return (code, code + 1)

    class _TextState:
        font = _Font()

    class _GraphicsState:
        text_state = _TextState()

    class _Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.glyphs: list[tuple[Any, int, Any]] = []

        def show_font_glyph(
            self,
            text_rendering_matrix: Any,
            font: Any,
            code: int,
            displacement: Any,
        ) -> None:
            self.glyphs.append((font, code, displacement))

    engine = _Engine()
    engine._graphics_stack.append(_GraphicsState())  # noqa: SLF001

    engine.show_text(b"AB")

    assert [(code, displacement) for _, code, displacement in engine.glyphs] == [
        (65, (65, 66)),
        (66, (66, 67)),
    ]


def test_decode_codes_stops_when_font_makes_no_progress() -> None:
    class _NoProgressFont:
        def read_code(self, src: Any) -> int:
            return 99

    assert PDFStreamEngine._decode_codes_via_font(  # noqa: SLF001
        b"abc", _NoProgressFont()
    ) == []


def test_glyph_displacement_swallows_font_errors() -> None:
    class _BadFont:
        def get_displacement(self, code: int) -> object:
            raise ValueError("bad glyph")

    assert PDFStreamEngine._glyph_displacement(_BadFont(), 1) is None  # noqa: SLF001


def test_require_min_operands_raises_missing_operand() -> None:
    with pytest.raises(MissingOperandException, match="too few operands"):
        PDFStreamEngine._require_min_operands(  # noqa: SLF001
            EngineOperator.get_operator("Tj"), [], 1
        )
