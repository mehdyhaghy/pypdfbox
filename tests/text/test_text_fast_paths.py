"""Fast paths of the text extraction hot loop agree with their references.

``PDFTextStripper`` batches its float32 narrowings into multi-value
``struct`` round trips, precomputes upright glyph geometry, memoizes glyph
decoding, and indexes the duplicate suppressor with a flat grid;
``PDFStreamParser.tokens`` matches common tokens straight off the buffer.
Each has a reference it must reproduce exactly:

* every packer raising ``OverflowError`` sends each batched step to its
  one-value-at-a-time reference, so a whole extraction is rerun on the
  reference arithmetic and compared glyph by glyph;
* the batched helpers are compared with their references on random and
  out-of-range inputs;
* ``tokens()`` is compared with the ``parse_next_token`` loop on real
  content streams and on random token soup.

Hand-written (not ported from upstream JUnit).
"""

import math
import random
import struct
from pathlib import Path

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel import PDDocument
from pypdfbox.text import PDFTextStripper, TextPosition
from pypdfbox.text import pdf_text_stripper as stripper_module
from pypdfbox.text.pdf_text_stripper import (
    _JavaGeometry,
    _tj_step,
    _tj_step_reference,
)

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_SAMPLES = [
    "text/BidiSample.pdf",
    "text/fake_bold_overlap.pdf",
    "text/rotated_text_dir.pdf",
    "text/input/eu-001.pdf",
    "pdmodel/font/PDFBOX-3044-010197-p5-ligatures.pdf",
    "multipdf/rot90.pdf",
    "multipdf/rot270.pdf",
    "multipdf/PDFBOX-6049-ExpectedResult.pdf",
]
_FIELDS = (
    "text",
    "x",
    "y",
    "font_size",
    "width",
    "width_of_space",
    "dir",
    "rotation",
    "page_width",
    "page_height",
    "text_matrix",
    "font_size_in_pt",
    "height",
    "individual_widths",
    "device_x",
    "device_y",
    "device_end_x",
    "device_end_y",
)
_GEOMETRY = _JavaGeometry.__slots__


class _RefusingStruct:
    """A ``struct.Struct`` stand-in whose ``pack`` always overflows."""

    def __init__(self, fmt: str) -> None:
        self._struct = struct.Struct(fmt)
        self.unpack = self._struct.unpack

    def pack(self, *values: float) -> bytes:
        raise OverflowError("forced reference path")


def _force_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*values: float) -> bytes:
        raise OverflowError("forced reference path")

    for name in ("_f32_pack", "_f32x2_pack", "_f32x3_pack", "_f32x4_pack"):
        monkeypatch.setattr(stripper_module, name, refuse)
    monkeypatch.setattr(stripper_module, "_F32X5_STRUCT", _RefusingStruct("<5f"))


def _key(value: object) -> object:
    # ``repr`` keeps the sign of zero and NaN apart from plain equality.
    if isinstance(value, list):
        return [_key(v) for v in value]
    return repr(value)


def _extract(path: Path, sort: bool) -> tuple[str, list[list[object]]]:
    pages: list[list[object]] = []

    class Recorder(PDFTextStripper):
        def process_page(self, page):
            out = super().process_page(page)
            rows = []
            for article in self.get_characters_by_article():
                for pos in article:
                    geometry = getattr(pos, "_java_geometry", None)
                    if geometry is None:
                        geometry = _JavaGeometry(pos)
                    rows.append(
                        [_key(getattr(pos, f)) for f in _FIELDS]
                        + [_key(getattr(geometry, f)) for f in _GEOMETRY]
                    )
            pages.append(rows)
            return out

    doc = PDDocument.load(str(path))
    try:
        stripper = Recorder()
        stripper.set_sort_by_position(sort)
        text = stripper.get_text(doc)
    finally:
        doc.close()
    return text, pages


@pytest.mark.parametrize("sort", [False, True], ids=["default", "sort"])
@pytest.mark.parametrize("name", _SAMPLES)
def test_extraction_matches_reference_arithmetic(
    name: str, sort: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _FIXTURES / name
    fast = _extract(path, sort)
    _force_reference(monkeypatch)
    reference = _extract(path, sort)
    assert fast[0] == reference[0]
    assert fast[1] == reference[1]


def test_upright_geometry_matches_lazy_geometry() -> None:
    """The geometry ``_emit_glyphs`` builds up front equals the one
    ``_JavaGeometry`` derives from the folded position."""
    doc = PDDocument.load(str(_FIXTURES / "text/input/eu-001.pdf"))
    try:
        stripper = PDFTextStripper()
        stripper.get_text(doc)
        positions = [p for a in stripper.get_characters_by_article() for p in a]
    finally:
        doc.close()
    upright = [p for p in positions if "_java_geometry" in vars(p)]
    assert upright
    for pos in upright:
        built = pos._java_geometry
        lazy = _JavaGeometry(pos)
        assert [_key(getattr(built, f)) for f in _GEOMETRY] == [
            _key(getattr(lazy, f)) for f in _GEOMETRY
        ]


def _random_float(rnd: random.Random) -> float:
    choice = rnd.random()
    if choice < 0.05:
        return rnd.choice([0.0, -0.0, 1.0, -1.0, 1e38, -1e38, 3.4e38, 1e-40])
    if choice < 0.1:
        return rnd.choice([math.inf, -math.inf, math.nan])
    return rnd.uniform(-1000.0, 1000.0) * rnd.choice([1.0, 1e-3, 1e3])


def test_tj_step_matches_reference() -> None:
    rnd = random.Random(1234)
    for _ in range(5000):
        args = [_random_float(rnd) for _ in range(7)]
        assert [_key(v) for v in _tj_step(*args)] == [
            _key(v) for v in _tj_step_reference(*args)
        ]


def test_emit_glyphs_matches_reference_on_random_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Random text state and glyph runs, including values beyond the
    float32 range, through ``_emit_glyphs`` with and without batching."""
    rnd = random.Random(99)

    def run(seed: int) -> list[object]:
        local = random.Random(seed)
        stripper = PDFTextStripper()
        stripper._crop_lower_left_x = local.choice([0.0, 12.0])
        stripper._crop_lower_left_y = local.choice([0.0, -7.5])
        stripper._page_height = 792.0
        stripper._page_rotation = 0
        stripper._fold_upright_geometry = True
        stripper._active_font_height = 0.7
        stripper._active_avg_advance = 5.0
        stripper._space_width_cache = {}
        state = stripper_module._TextState()
        state.ctm = stripper_module.Matrix(
            local.choice([1.0, 2.0, 0.5]), 0.0, 0.0, local.choice([1.0, -1.0, 3.0]),
            local.uniform(-50, 50), local.uniform(-50, 50),
        )
        state.font_size = local.choice([12.0, 9.5, 1.0, 1e30])
        state.char_spacing = local.choice([0.0, 0.25, -1.0])
        state.word_spacing = local.choice([0.0, 2.0])
        state.horizontal_scaling = local.choice([1.0, 0.8, 1.25])
        state.tm_a = local.choice([1.0, 10.0, 1e9])
        state.tm_d = state.tm_a
        state.text_x = local.uniform(0, 600)
        state.text_y = local.uniform(0, 800)
        glyphs = [
            (
                local.choice(["a", " ", None]),
                local.choice([0.5, 0.278, 0.0, 1e10]),
                1,
                local.choice([32, 65]),
            )
            for _ in range(local.randint(1, 8))
        ]
        positions: list[TextPosition] = []
        try:
            stripper._emit_glyphs(state, positions, None, None, glyphs)
        except ValueError as exc:
            return ["raised", str(exc)]
        rows: list[object] = [_key(state.text_x), _key(state.text_y)]
        for pos in positions:
            rows.append([_key(getattr(pos, f)) for f in _FIELDS])
            geometry = getattr(pos, "_java_geometry", None)
            if geometry is not None:
                rows.append([_key(getattr(geometry, f)) for f in _GEOMETRY])
        return rows

    seeds = [rnd.randrange(1 << 30) for _ in range(300)]
    fast = [run(seed) for seed in seeds]
    # Most runs emit glyphs (with geometry); a few overflow and raise.
    emitted = [rows for rows in fast if rows[0] != "raised"]
    assert len(emitted) > 200
    assert any(len(rows) > 4 for rows in emitted)
    _force_reference(monkeypatch)
    reference = [run(seed) for seed in seeds]
    assert fast == reference


# ---------------------------------------------------------------------------
# PDFStreamParser.tokens fast tokenizer
# ---------------------------------------------------------------------------


def _norm(token: object) -> object:
    if isinstance(token, Operator):
        params = token.get_image_parameters()
        return ("op", token.get_name(), token.get_image_data(), _norm(params))
    if isinstance(token, COSArray):
        return ("array", tuple(_norm(item) for item in token))
    if isinstance(token, COSDictionary):
        return ("dict", tuple((str(k), _norm(v)) for k, v in token.items()))
    if isinstance(token, COSFloat):
        return ("float", repr(token), repr(token.float_value()))
    if isinstance(token, COSInteger):
        return ("int", token.long_value(), token.is_valid())
    if isinstance(token, COSString):
        return ("string", token.get_bytes(), token.is_force_hex_form())
    if isinstance(token, COSName):
        return ("name", token.get_name())
    if token is None or token is COSNull.NULL or isinstance(token, COSBoolean):
        return repr(token)
    return (type(token).__name__, repr(token))


def _reference_tokens(data: bytes) -> object:
    parser = PDFStreamParser(RandomAccessReadBuffer(data))
    tokens = []
    try:
        while True:
            token = parser.parse_next_token()
            if token is None:
                break
            tokens.append(_norm(token))
    except Exception as exc:
        return ("raised", type(exc).__name__, tokens)
    return tokens


def _fast_tokens(data: bytes) -> object:
    parser = PDFStreamParser(RandomAccessReadBuffer(data))
    tokens = []
    try:
        for token in parser.tokens():
            tokens.append(_norm(token))
    except Exception as exc:
        return ("raised", type(exc).__name__, tokens)
    return tokens


@pytest.mark.parametrize("name", _SAMPLES)
def test_tokens_match_reference_on_page_content(name: str) -> None:
    doc = PDDocument.load(str(_FIXTURES / name))
    try:
        for page in doc.get_pages():
            body = page.get_contents()
            if body:
                assert _fast_tokens(body) == _reference_tokens(body)
    finally:
        doc.close()


_PIECES = [
    b"0", b"-0", b"007", b"1", b"-2", b"3.5", b".5", b"-.25", b"5.", b"--3",
    b"+4", b"1.2.3", b"-", b".", b"+", b"1e5", b"7-8", b"123456789012345678",
    b"1234567890123456789", b"-99999999999999999999", b"/F1", b"/A#20B",
    b"/A#", b"/", b"/a{b}", b"(abc)", b"(a\\nb)", b"(\\101\\7x)", b"(\\1234)",
    b"(\\\r\nx)", b"(\\\ny)", b"(x\\", b"(\\)", b"(a\\(b)", b"(\\q\\\\)",
    b"(\\8)", b"(\\\r)", b"(a\\)b)", b"(a(b)c)", b"(\r\n)", b"(x", b"<414>",
    b"<41 42>", b"<4G>", b"<>", b"<<", b">>", b"<</A 1>>", b"[", b"]",
    b"[1 (a) -2]", b"[1 0 R]", b"[(a)<41>3.5]", b"[ ]", b"[\x001]",
    b"[(a\\051)-250(b)]", b"Tj", b"TJ", b"BT", b"ET", b"T*", b"'", b'"', b"d0",
    b"d1", b"null", b"true", b"false", b"nullx", b"BI", b"ID", b"EI", b"Ix",
    b"B*", b"q", b"Q", b"cm", b"re", b"%comment\n", b"%c", b" ", b"\n",
    b"\r\n", b"\t", b"\x00", b"\x0c", b"{", b"}", b")", b">", b"\x80", b"e",
    b"R", b"Do",
]


def test_tokens_match_reference_on_random_token_soup() -> None:
    rnd = random.Random(20261023)
    for _ in range(4000):
        parts = []
        for _ in range(rnd.randint(1, 14)):
            parts.append(rnd.choice(_PIECES))
            if rnd.random() < 0.7:
                parts.append(rnd.choice([b" ", b"\n", b""]))
        data = b"".join(parts)
        assert _fast_tokens(data) == _reference_tokens(data), data


def test_tokens_subclass_uses_reference_loop() -> None:
    calls = []

    class Counting(PDFStreamParser):
        def parse_next_token(self):
            calls.append(1)
            return super().parse_next_token()

    tokens = list(Counting(RandomAccessReadBuffer(b"1 2 Td (a) Tj")).tokens())
    assert [_norm(t) for t in tokens] == _reference_tokens(b"1 2 Td (a) Tj")
    assert len(calls) == len(tokens) + 1
