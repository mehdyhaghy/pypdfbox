"""Deeply nested direct arrays and dictionaries hit upstream's depth limit,
never Python's ``RecursionError``.

Upstream ``BaseParser`` keeps one ``recursionDepth`` counter: every
``parseDirObject``, ``parseCOSArray`` and ``parseCOSDictionary`` call adds one
and anything past ``MAX_RECURSION_DEPTH`` (500) throws ``IOException("Reached
maximum recursion depth 500")``. A container nested in a container therefore
costs two units. The boundaries below were measured against PDFBox 3.0.8:

* indirect-object body (``parseDirObject`` first): 249 arrays around a number
  parse, 250 do not (250 empty arrays still do); a failed body resolves to
  ``null``;
* trailer (``parseCOSDictionary`` first): a value nested 249 deep parses, 250
  fails and the trailer is rebuilt from the object scan;
* content stream (``parseCOSArray`` / ``parseCOSDictionary`` first): 250 levels
  parse, 251 stop the token stream (upstream's "Stop reading invalid array /
  dictionary from content stream").
"""

from __future__ import annotations

import sys

import pytest

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_integer import COSInteger
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfparser.cos_parser import COSParser
from pypdfbox.pdfparser.parse_error import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdmodel.pd_document import PDDocument

DEEP = 5000
LIMIT_MESSAGE = "Reached maximum recursion depth 500"
_A = COSName.get_pdf_name("A")


class _ReferenceParser(COSParser):
    """``COSParser`` without the regex fast path."""

    def _fast_path_applies(self) -> bool:
        return False


def _arrays(n: int, leaf: bytes = b"1") -> bytes:
    return b"[" * n + leaf + b"]" * n


def _dicts(n: int, leaf: bytes = b"1") -> bytes:
    return b"<< /A " * n + leaf + b" >>" * n


def _mixed(n: int) -> bytes:
    """``n`` levels alternating array / dictionary, ending in ``1``."""
    head = b""
    tail = b""
    for level in range(n):
        if level % 2 == 0:
            head += b"["
            tail = b"]" + tail
        else:
            head += b"<< /A "
            tail = b" >>" + tail
    return head + b"1" + tail


def _depth_of(obj: object) -> tuple[int, object]:
    """Number of nested containers above the leaf and the leaf itself,
    walked without recursion."""
    depth = 0
    while isinstance(obj, (COSArray, COSDictionary)):
        if isinstance(obj, COSArray):
            if obj.size() == 0:  # innermost ``[]``
                return depth + 1, None
            assert obj.size() == 1
            obj = obj.get(0)
        else:
            assert list(obj.key_set()) == [_A]
            obj = obj.get_item(_A)
        depth += 1
    return depth, obj


def _pdf(obj4: bytes, trailer_extra: bytes = b"") -> bytes:
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] >>",
        obj4,
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(bodies, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(bodies) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R" % (len(bodies) + 1)
    out += trailer_extra + b" >>\nstartxref\n%d\n%%%%EOF\n" % xref
    return bytes(out)


@pytest.fixture(params=["buffer", "file"])
def load(request, tmp_path):
    """Load PDF bytes from memory or from a file (the two fast-path source
    types)."""

    def _load(data: bytes) -> PDDocument:
        if request.param == "buffer":
            return PDDocument.load(data)
        path = tmp_path / "deep.pdf"
        path.write_bytes(data)
        return PDDocument.load(str(path))

    return _load


def _object4(document: PDDocument) -> object:
    return document.get_document().get_object_from_pool(COSObjectKey(4, 0)).get_object()


# ---------- indirect-object bodies ----------


@pytest.mark.parametrize("body", [_arrays, _dicts, _mixed], ids=["array", "dict", "mixed"])
def test_object_nested_5000_deep_resolves_to_null(load, body) -> None:
    with load(_pdf(body(DEEP))) as document:
        assert _object4(document) is None
        # The rest of the document is unaffected.
        assert document.get_number_of_pages() == 1


@pytest.mark.parametrize(
    ("body", "depth", "parses"),
    [
        (_arrays, 249, True),
        (_arrays, 250, False),
        (_dicts, 249, True),
        (_dicts, 250, False),
        (_mixed, 249, True),
        (_mixed, 250, False),
    ],
    ids=["array249", "array250", "dict249", "dict250", "mixed249", "mixed250"],
)
def test_object_nesting_boundary_matches_pdfbox(load, body, depth, parses) -> None:
    with load(_pdf(body(depth))) as document:
        obj = _object4(document)
        if parses:
            assert _depth_of(obj) == (depth, COSInteger.get(1))
        else:
            assert obj is None


def test_object_empty_innermost_array_boundary(load) -> None:
    # An empty innermost array parses no element, so it reaches one level
    # further than ``[[...[1]...]]``.
    with load(_pdf(_arrays(250, b""))) as document:
        assert _depth_of(_object4(document))[0] == 250
    with load(_pdf(_arrays(251, b""))) as document:
        assert _object4(document) is None


def test_object_moderate_nesting_structure(load) -> None:
    with load(_pdf(_mixed(100))) as document:
        obj = _object4(document)
        assert _depth_of(obj) == (100, COSInteger.get(1))
        assert isinstance(obj, COSArray)
        assert isinstance(obj.get(0), COSDictionary)
        assert obj.get(0).is_direct()


# ---------- trailer ----------


@pytest.mark.parametrize("body", [_arrays, _dicts, _mixed], ids=["array", "dict", "mixed"])
def test_trailer_nested_5000_deep_is_rebuilt(load, body) -> None:
    with load(_pdf(b"5", b" /X " + body(DEEP))) as document:
        trailer = document.get_document().get_trailer()
        assert trailer.get_item(COSName.get_pdf_name("X")) is None
        assert trailer.get_dictionary_object(COSName.ROOT) is not None
        assert document.get_number_of_pages() == 1


@pytest.mark.parametrize(("body", "depth"), [(_arrays, 249), (_dicts, 249), (_mixed, 249)])
def test_trailer_nested_249_deep_parses(load, body, depth) -> None:
    with load(_pdf(b"5", b" /X " + body(depth))) as document:
        trailer = document.get_document().get_trailer()
        value = trailer.get_item(COSName.get_pdf_name("X"))
        assert _depth_of(value) == (depth, COSInteger.get(1))
        assert trailer.get_int(COSName.SIZE) == 5


@pytest.mark.parametrize("body", [_arrays, _dicts], ids=["array", "dict"])
def test_trailer_nested_250_deep_is_rebuilt(load, body) -> None:
    with load(_pdf(b"5", b" /X " + body(250))) as document:
        trailer = document.get_document().get_trailer()
        assert trailer.get_item(COSName.get_pdf_name("X")) is None


# ---------- content streams ----------


def _tokens(data: bytes) -> list:
    return PDFStreamParser(RandomAccessReadBuffer(data)).parse()


def _ops(tokens: list) -> list[str]:
    return [t.get_name() for t in tokens if isinstance(t, Operator)]


@pytest.mark.parametrize("body", [_arrays, _dicts, _mixed], ids=["array", "dict", "mixed"])
def test_content_stream_nested_5000_deep_stops_reading(body) -> None:
    tokens = _tokens(b"q " + body(DEEP) + b" TJ Q 1 0 0 1 0 0 cm")
    # Upstream logs "Stop reading invalid array/dictionary from content
    # stream" and closes the parser.
    assert _ops(tokens) == ["q"]
    assert len(tokens) == 1


@pytest.mark.parametrize("body", [_arrays, _dicts, _mixed], ids=["array", "dict", "mixed"])
def test_content_stream_nesting_boundary_matches_pdfbox(body) -> None:
    tokens = _tokens(b"q " + body(250) + b" TJ Q 1 0 0 1 0 0 cm")
    assert _ops(tokens) == ["q", "TJ", "Q", "cm"]
    assert _depth_of(tokens[1]) == (250, COSInteger.get(1))
    assert _ops(_tokens(b"q " + body(251) + b" TJ Q 1 0 0 1 0 0 cm")) == ["q"]


def test_content_stream_marked_content_properties_5000_deep() -> None:
    tokens = _tokens(b"/Span " + _dicts(DEEP) + b" BDC EMC 0 g")
    assert len(tokens) == 1
    tokens = _tokens(b"/Span " + _dicts(200) + b" BDC EMC 0 g")
    assert _ops(tokens) == ["BDC", "EMC", "g"]
    assert _depth_of(tokens[1]) == (200, COSInteger.get(1))


def test_content_stream_inline_image_parameter_5000_deep() -> None:
    data = b"BI /W 1 /H 1 /D " + _arrays(DEEP) + b" ID \x00 EI Q"
    tokens = _tokens(data)
    assert _ops(tokens) == ["BI"]
    data = b"BI /W 1 /H 1 /D " + _arrays(250) + b" ID \x00 EI Q"
    tokens = _tokens(data)
    assert _ops(tokens) == ["BI", "Q"]
    params = tokens[0].get_image_parameters()
    assert _depth_of(params.get_item(COSName.get_pdf_name("D"))) == (250, COSInteger.get(1))


# ---------- parser API ----------


@pytest.mark.parametrize(
    "parse",
    [
        lambda data: COSParser(RandomAccessReadBuffer(data)).parse_direct_object(),
        lambda data: _ReferenceParser(RandomAccessReadBuffer(data)).parse_direct_object(),
        lambda data: BaseParser(RandomAccessReadBuffer(data)).parse_dir_object(),
    ],
    ids=["cos-fast", "cos-reference", "base"],
)
@pytest.mark.parametrize("body", [_arrays, _dicts, _mixed], ids=["array", "dict", "mixed"])
def test_parsers_raise_depth_error_not_recursion_error(parse, body) -> None:
    with pytest.raises(PDFParseError, match=LIMIT_MESSAGE):
        parse(body(DEEP))
    obj = parse(body(249))
    assert _depth_of(obj) == (249, COSInteger.get(1))


@pytest.mark.parametrize("parser_cls", [COSParser, _ReferenceParser])
def test_depth_counter_is_restored_after_failure(parser_cls) -> None:
    data = _mixed(DEEP) + b" " + _mixed(3)
    parser = parser_cls(RandomAccessReadBuffer(data))
    with pytest.raises(PDFParseError, match=LIMIT_MESSAGE):
        parser.parse_direct_object()
    assert parser._recursion_depth == 0


@pytest.mark.parametrize("depth", [1, 2, 3, 100, 248, 249, 250, 251, 499, 500, 501])
@pytest.mark.parametrize("body", [_arrays, _dicts, _mixed], ids=["array", "dict", "mixed"])
def test_fast_path_matches_reference_at_every_depth(depth, body) -> None:
    def run(parser_cls):
        parser = parser_cls(RandomAccessReadBuffer(body(depth)))
        try:
            result = _depth_of(parser.parse_direct_object())
        except PDFParseError as exc:
            result = ("error", exc.get_message())
        return result, parser._recursion_depth

    assert run(COSParser) == run(_ReferenceParser)


def test_deepest_allowed_nesting_fits_a_deep_caller_stack() -> None:
    """The depth limit keeps the parser within about 500 Python frames, so a
    249-deep structure parses even when the caller already uses a few hundred
    frames."""
    caller_frames = max(sys.getrecursionlimit() - 600, 0)

    def burn(n: int):
        if n == 0:
            return [
                _depth_of(COSParser(RandomAccessReadBuffer(_dicts(249))).parse_direct_object()),
                _depth_of(BaseParser(RandomAccessReadBuffer(_dicts(249))).parse_dir_object()),
                _depth_of(_tokens(_dicts(250))[0]),
            ]
        return burn(n - 1)

    assert burn(caller_frames) == [
        (249, COSInteger.get(1)),
        (249, COSInteger.get(1)),
        (250, COSInteger.get(1)),
    ]
