"""The one-window fast path of ``PDFParser._load_indirect_object_at`` (header,
body and ``endobj`` scanned together) must give the same objects, cursor
positions and errors as the separate header / body / trailer reads.

The reference is the same method with ``_fast_load_indirect_object``
switched off, which runs exactly the pre-existing sequence.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

import pypdfbox.pdfparser.pdf_parser as pdf_parser_module
from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSDocument,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer, RandomAccessReadBufferedFile
from pypdfbox.pdfparser.cos_parser import COSParser
from pypdfbox.pdfparser.pdf_parser import PDFParser

_PREFIX = b"%PDF-1.4\n"


class _ReferenceParser(PDFParser):
    """``PDFParser`` without the one-window object fast path."""

    def _fast_load_indirect_object(self, obj):  # type: ignore[no-untyped-def]
        return None


def _dump(obj: object) -> object:
    if isinstance(obj, COSObject):
        return ("ref", obj.object_number, obj.generation_number)
    if isinstance(obj, COSStream):
        return (
            "stream",
            [(k.get_bytes(), _dump(v)) for k, v in obj.entry_set()],
            obj.get_raw_data_bytes() if hasattr(obj, "get_raw_data_bytes") else None,
        )
    if isinstance(obj, COSDictionary):
        key = obj.get_key()
        return (
            "dict",
            obj.is_direct(),
            None if key is None else (key.object_number, key.generation_number),
            [(k.get_bytes(), _dump(v)) for k, v in obj.entry_set()],
        )
    if isinstance(obj, COSArray):
        return ("array", obj.is_direct(), [_dump(v) for v in obj])
    if isinstance(obj, COSString):
        return ("string", obj.get_bytes(), obj._force_hex_form)
    if isinstance(obj, COSFloat):
        return ("float", obj.float_value(), obj.to_string())
    if isinstance(obj, COSInteger):
        return ("int", obj.value, obj.is_valid())
    if isinstance(obj, COSName):
        return ("name", obj.get_bytes())
    if isinstance(obj, COSBoolean):
        return ("bool", obj.get_value())
    if obj is COSNull.NULL or obj is None:
        return ("null",)
    return ("other", repr(obj))


def _load(parser_cls: type[PDFParser], source, number: int, generation: int) -> list:
    parser = parser_cls(source)
    document = COSDocument()
    parser._document = document
    parser._cos_parser = COSParser(source, document=document)
    out: list = []
    try:
        try:
            body = parser._load_indirect_object_at(
                len(_PREFIX), COSObject(number, generation)
            )
        except RecursionError as exc:
            out.append(("error", type(exc).__name__))
        except Exception as exc:
            out.append(("error", type(exc).__name__, str(exc), source.get_position()))
        else:
            out.append(("ok", _dump(body), source.get_position()))
        keys = document.get_object_keys()
        out.append(sorted((k.object_number, k.generation_number) for k in keys))
        out.append(parser._cos_parser._recursion_depth)
    finally:
        document.close()
    return out


def _compare(data: bytes, tmp_path: Path, number: int = 7, generation: int = 0) -> None:
    full = _PREFIX + data
    expected = _load(_ReferenceParser, RandomAccessReadBuffer(full), number, generation)
    actual = _load(PDFParser, RandomAccessReadBuffer(full), number, generation)
    assert actual == expected, data
    for padding in (b"", b"\n" * 3):
        path = tmp_path / "object.pdf"
        path.write_bytes(full + padding)
        results = []
        for parser_cls in (_ReferenceParser, PDFParser):
            src = RandomAccessReadBufferedFile(path)
            try:
                results.append(_load(parser_cls, src, number, generation))
            finally:
                src.close()
        assert results[1] == results[0], data


_BODIES = [
    b"<< /Type /Annot /Rect [ 48.42 747.98 96.12 759.14 ] /Border [ 0 0 0 ] >>",
    b"<< /K [ 1 0 R 2 0 R 3 0 R ] /P 9 0 R /S /Span /Pg 4 0 R /MCID 5 >>",
    b"<< /S /Table#20text /A#41 1 /B -2 /C 3.5 /D (str) /E <41> >>",
    b"<</A 120 R/B 12/C/D>>",
    b"[1 0 R 2 3 /N (x) 4.5 true null]",
    b"42",
    b"1 0 R",
    b"/Name",
    b"(a(b)c)",
    b"<< /A << /B [ << /C 1 >> ] >> >>",
    b"<< /A 1 % comment\n /B 2 >>",
    b"<< /A >>",
    b"<< /A 1 /B >",
    b"<< /A",
    b"[1 2",
    b"",
    b"[" * 260 + b"]" * 260,
]

_TAILS = [
    b"\nendobj\n",
    b"endobj",
    b" endobjX\n",
    b"\r\n%c\nendobj\n",
    b"\nendob\n",
    b"\nobj\n",
    b"\n",
    b"",
    b"\nstream\nabc\nendstream\nendobj\n",
    b"\nsomething else\n",
]


@pytest.mark.parametrize(
    "body", _BODIES, ids=[f"body{i}" for i in range(len(_BODIES))]
)
def test_fast_object_load_matches_reference(body: bytes, tmp_path: Path) -> None:
    for tail in _TAILS:
        _compare(b"7 0 obj\n" + body + tail, tmp_path)


@pytest.mark.parametrize(
    "header",
    [b"7 0 obj", b"  7  0  obj ", b"%c\n7 0 obj", b"7 1 obj", b"8 0 obj",
     b"7 0 ob", b"7 0 objx", b"+7 0 obj", b"7 0", b"x 0 obj", b"7 0 R"],
    ids=["plain", "spaces", "comment", "gen", "number", "short", "long",
         "sign", "nokw", "junk", "ref"],
)
def test_fast_object_load_headers_match_reference(
    header: bytes, tmp_path: Path
) -> None:
    _compare(header + b"\n<< /A 1 >>\nendobj\n", tmp_path)


def test_stream_object_matches_reference(tmp_path: Path) -> None:
    _compare(b"7 0 obj\n<< /Length 3 >>\nstream\nabc\nendstream\nendobj\n", tmp_path)
    _compare(b"7 0 obj\n<< /Length 9 >>\nstream\nabc\nendstream\nendobj\n", tmp_path)


@pytest.mark.parametrize("window", [1, 8, 33])
def test_tiny_windows_match_reference(
    window: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Forces the grow-and-retry rounds and the window-end guards.
    monkeypatch.setattr(pdf_parser_module, "_FAST_OBJECT_WINDOW", window)
    for body in _BODIES[:12]:
        for tail in _TAILS[:4]:
            _compare(b"7 0 obj\n" + body + tail, tmp_path)


def test_random_token_soup_matches_reference(tmp_path: Path) -> None:
    atoms = [
        b"/Type", b"/A#20B", b"/", b"12", b"-3", b"3.5", b"1e5", b"1 0 R",
        b"12 R", b"R", b"true", b"null", b"(s)", b"(a(b))", b"<41>", b"<<",
        b">>", b"[", b"]", b"%c\n", b" ", b"\r\n", b"endobj", b"stream",
    ]
    rng = random.Random(4321)
    for _ in range(60):
        body = b" ".join(rng.choice(atoms) for _ in range(rng.randint(1, 8)))
        _compare(b"7 0 obj <<" + body + b">> endobj\n", tmp_path)
        _compare(b"7 0 obj [" + body + b"] endobj\n", tmp_path)
