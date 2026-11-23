"""The buffer-scanning fast path of ``COSParser.parse_direct_object`` and the
chunk-scanning fast paths of the ``BaseParser`` token readers must give the
same objects, end positions and errors as the byte-at-a-time reference code.

The reference is obtained by disabling the fast paths: a ``COSParser``
subclass whose ``_fast_path_applies`` returns ``False`` and whose
``_fast_chunk`` returns ``None`` runs exactly the pre-existing code.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

import pypdfbox.pdfparser.cos_parser as cos_parser_module
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
    COSString,
)
from pypdfbox.io import RandomAccessReadBuffer, RandomAccessReadBufferedFile
from pypdfbox.pdfparser.base_parser import BaseParser
from pypdfbox.pdfparser.cos_parser import COSParser


class _ReferenceParser(COSParser):
    """``COSParser`` with every fast path switched off."""

    def _fast_path_applies(self) -> bool:
        return False

    def _fast_chunk(self) -> None:
        return None


def _dump(obj: object) -> object:
    if isinstance(obj, COSObject):
        return ("ref", obj.object_number, obj.generation_number)
    if isinstance(obj, COSDictionary):
        return (
            "dict",
            obj.is_direct(),
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
    if obj is COSNull.NULL:
        return ("null",)
    return ("other", repr(obj))


def _parse_all(parser_cls: type[COSParser], source, allow_ref: bool) -> list:
    document = COSDocument()
    parser = parser_cls(source, document=document)
    out: list = []
    try:
        for _ in range(3):
            try:
                obj = parser.parse_direct_object(allow_indirect_reference=allow_ref)
            except RecursionError as exc:
                # Where Python's stack runs out depends on the caller's
                # stack depth (pytest-xdist adds frames), not on the parser.
                out.append(("error", type(exc).__name__, str(exc)))
                break
            except Exception as exc:
                out.append(("error", type(exc).__name__, str(exc), source.get_position()))
                break
            out.append(("ok", _dump(obj), source.get_position()))
        keys = document.get_object_keys()
        out.append(sorted((k.object_number, k.generation_number) for k in keys))
        out.append(parser._recursion_depth)
    finally:
        document.close()
    return out


def _compare(data: bytes, tmp_path: Path) -> None:
    for allow_ref in (True, False):
        expected = _parse_all(_ReferenceParser, RandomAccessReadBuffer(data), allow_ref)
        actual = _parse_all(COSParser, RandomAccessReadBuffer(data), allow_ref)
        assert actual == expected, data
        for suffix in (b"", b"\nendobj\n"):
            path = tmp_path / "object.bin"
            path.write_bytes(data + suffix)
            ref_src = RandomAccessReadBufferedFile(path)
            try:
                expected = _parse_all(_ReferenceParser, ref_src, allow_ref)
            finally:
                ref_src.close()
            fast_src = RandomAccessReadBufferedFile(path)
            try:
                actual = _parse_all(COSParser, fast_src, allow_ref)
            finally:
                fast_src.close()
            assert actual == expected, data


_CASES = [
    b"<< /Type /Annot /Rect [ 48.42 747.98 96.12 759.14 ] /Border [ 0 0 0 ] >>",
    b"<< /K [ 1 0 R 2 0 R 3 0 R ] /P 9 0 R /S /Span /Pg 4 0 R >>",
    b"<< /S /Table#20text#20#289#29 /A#41 1 >>",
    b"[12 R]",
    b"[120 R]",
    b"<</A 120 R>>",
    b"[1 %5 0 R\n 2 0 R]",
    b"[1 0 RG 2 0 R]",
    b"[-1 0 R]",
    b"[-0 0 R +3 0 R]",
    b"[1 0.5 R]",
    b"[1 0e R]",
    b"[1E 2e 3.5e2 4.]",
    b"[.5 -.5 +.5 5. -0]",
    b"[9999999999999999999999 -9999999999999999999999]",
    b"[(abc) (a(b)c) (a\\)b) (x\r\n/y) <414243> <41 4> <4G> <>]",
    b"[true false null truex nul]",
    b"<< /A [ << /B << /C (d) >> >> ] >>",
    b"<< /A 1 >",
    b"<< /A 1 % comment\r\n /B 2 >>",
    b"<< 1 >>",
    b"[1 2",
    b"<</A",
    b"(unterminated",
    b"1 0 R",
    b"12",
    b"/Name",
    b"endobj",
    b"R",
    b"[" * 499 + b"]" * 499,
    b"[" * 501 + b"]" * 501,
]


@pytest.mark.parametrize("data", _CASES, ids=[f"case{i}" for i in range(len(_CASES))])
def test_fast_path_matches_reference(data: bytes, tmp_path: Path) -> None:
    _compare(data, tmp_path)


@pytest.mark.parametrize("window", [1, 3, 17])
def test_tiny_windows_match_reference(
    window: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Forces the file-window path through repeated grow-and-retry rounds.
    monkeypatch.setattr(cos_parser_module, "_FP_FIRST_WINDOW", window)
    for data in _CASES[:20]:
        _compare(data, tmp_path)


_ESCAPED_NAME_CASES = [
    b"/A#20B",
    b"/#41#42#43",
    b"<< /K#65y /V#61l#20ue /N /x#2fy >>",
    b"[ /A#41 /B#4 /C ]",
    b"<< /A#G1 1 >>",
    b"<< /A# 1 >>",
    b"<< /A#4",
    b"/A#",
    b"/A#4",
    b"<< /A#4g 2 /B#4 >>",
    b"<< /#00 1 /#ff#FE 2 >>",
    b"[/A#41#]",
]


@pytest.mark.parametrize(
    "data",
    _ESCAPED_NAME_CASES,
    ids=[f"name{i}" for i in range(len(_ESCAPED_NAME_CASES))],
)
@pytest.mark.parametrize("window", [1, 3, 4096])
def test_escaped_names_match_reference(
    data: bytes, window: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Small windows cut the names (and their ``#XX`` escapes) at every byte.
    monkeypatch.setattr(cos_parser_module, "_FP_FIRST_WINDOW", window)
    _compare(data, tmp_path)


def test_random_token_soup_matches_reference(tmp_path: Path) -> None:
    atoms = [
        b"/Type", b"/A#20B", b"/", b"12", b"-3", b"+4", b"3.5", b".5", b"1e5",
        b"1 0 R", b"12 R", b"R", b"true", b"null", b"(s)", b"(a(b))", b"<41>",
        b"<<", b">>", b"[", b"]", b"%c\n", b" ", b"\r\n", b"\x00", b"endobj",
    ]
    rng = random.Random(1234)
    for _ in range(150):
        body = b" ".join(rng.choice(atoms) for _ in range(rng.randint(1, 10)))
        _compare(b"<<" + body + b">>", tmp_path)
        _compare(b"[" + body + b"]", tmp_path)


def test_subclass_override_disables_fast_path() -> None:
    class KeywordParser(COSParser):
        def read_keyword(self) -> bytes:
            return b"X" + super().read_keyword()

    parser = KeywordParser(RandomAccessReadBuffer(b"[1 2 R]"))
    assert not parser._fast_path_applies()
    assert COSParser(RandomAccessReadBuffer(b"")).__class__ is COSParser
    assert COSParser(RandomAccessReadBuffer(b""))._fast_path_applies()


@pytest.mark.parametrize(
    "data",
    [b"  12 0 obj", b"%c\r\n-7 x", b"+", b"", b"abc def", b"\x00\x0c\tobj<<"],
    ids=["header", "comment", "sign", "empty", "words", "nul"],
)
def test_base_token_readers_match_reference(data: bytes, tmp_path: Path) -> None:
    ops = ["skip_whitespace", "read_int", "read_keyword", "read_string", "read_int"]

    def run(parser_cls: type[BaseParser], source) -> list:
        parser = parser_cls(source)
        out = []
        for op in ops:
            try:
                out.append(("ok", getattr(parser, op)(), source.get_position()))
            except Exception as exc:
                out.append(("error", type(exc).__name__, str(exc), source.get_position()))
        return out

    class ReferenceBase(BaseParser):
        def _fast_chunk(self) -> None:
            return None

    assert run(BaseParser, RandomAccessReadBuffer(data)) == run(
        ReferenceBase, RandomAccessReadBuffer(data)
    )
    path = tmp_path / "tokens.bin"
    path.write_bytes(data)
    results = []
    for cls in (BaseParser, ReferenceBase):
        src = RandomAccessReadBufferedFile(path)
        try:
            results.append(run(cls, src))
        finally:
            src.close()
    assert results[0] == results[1]


def test_chunk_fast_paths_apply_to_subclasses_that_keep_the_helpers() -> None:
    from pypdfbox.pdfparser import base_parser as base_parser_module
    from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser

    for cls in (BaseParser, COSParser, PDFStreamParser):
        assert base_parser_module._fast_paths_apply(cls)
        assert cls(RandomAccessReadBuffer(b"12 0 obj"))._fast_chunk() is not None

    class DigitParser(COSParser):
        @classmethod
        def is_digit(cls, b: int) -> bool:
            return False

    assert not base_parser_module._fast_paths_apply(DigitParser)
    assert DigitParser(RandomAccessReadBuffer(b"12"))._fast_chunk() is None


# Values the dictionary-entry and array-item matches read in one go: flat
# arrays of numbers and references, hex strings, keywords, escaped names, and
# the shapes next to them that must still take the general path.
_ENTRY_VALUE_CASES = [
    b"<< /A [1 2 3] /B [1 0 R 2 0 R] /C [0 18 0 R 8 19 0 R] /D [] /E [ ] >>",
    b"<< /A [1 2 R] /B [1 2 3 R] /C [1 0 R 2] /D [1 0 R]>>",
    b"<< /A [+5 0 R] /B [-0 0 R] /C [5 +0 R] /D [5 -1 R] /E [-5 0 R] >>",
    b"<< /A [5. .5 -.5 +.5 -0 007 +3] /B [1.5.3] /C [1..5] /D [1e5 2] >>",
    b"<< /A [1\t2\n3\r4\x0c5] /B [1\x002] /C [1\x0b2] /D [1%c\n2] >>",
    b"<< /A [1 0\nR] /B [1 0 R/N] /C [1 0 R(s)] /D [1 0 RR] /E [1 0 R]>>",
    b"<< /A [1-2] /B [1+2] /C [--1] /D [+-1] /E [. 1] /F [- 1] >>",
    b"<< /A [" + b"9" * 4001 + b"] /B [" + b"9" * 4000 + b" 0 R] >>",
    b"<< /A [" + b"1 " * 3000 + b"] /B [" + b"1.25 " * 300 + b"] >>",
    b"<< /A [[1 2] [3 0 R] [/N 1]] /B [[[]]] >>",
    b"[[1 2] [3 4 R] [5 0 R 6] [.5 -1]]",
    b"<< /A <41 42> /B <4> /C <> /D <4\x081> /E <4G> /F <41><42> /G < 4 1 > >>",
    b"<< /A <41\r\n42\t43\x0c> /B <414>/C <ab CD ef>>>",
    b"<< /A true /B false /C null /D truex /E nullnull /F true/G false[1] >>",
    b"<< /A true>> ",
    b"<< /A null",
    b"<< /A /B#20C /B /#41#42 /C /x#2 /D /x#zz /E /x# /F /x#41#4 >>",
    b"<< /A /B#20C>> ",
    b"[/A#20B /C#43 /D#4 /E]",
    b"<< /A 5 %c\n0 R /B 5 0 %c\nR /C 5 %c\n 6 /D 7 0%c\n R >>",
    b"<< /A 5%c\n /B 1.5%c\n /C /N%c\n /D (s)%c\n >>",
    b"<< /A 1 2 R >>",
    b"<< /A 1 0 R%c\n>>",
    b"<< /A [1 0 R%c\n] >>",
    b"<< /A 1 /A 2 /B [1] /B (x) /A <41> >>",
]


@pytest.mark.parametrize(
    "data",
    _ENTRY_VALUE_CASES,
    ids=[f"value{i}" for i in range(len(_ENTRY_VALUE_CASES))],
)
@pytest.mark.parametrize("window", [1, 7, 4096])
def test_entry_values_match_reference(
    data: bytes, window: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cos_parser_module, "_FP_FIRST_WINDOW", window)
    _compare(data, tmp_path)


def test_nested_flat_arrays_at_the_recursion_limit_match_reference(
    tmp_path: Path,
) -> None:
    for depth in range(240, 252):
        _compare(b"<< /A " * depth + b"[1 0 R 2]" + b" >>" * depth, tmp_path)
        _compare(b"[" * (depth * 2) + b"[1 2]" + b"]" * (depth * 2), tmp_path)


def test_flat_array_and_hex_values_after_a_failed_entry_match_reference(
    tmp_path: Path,
) -> None:
    rng = random.Random(4321)
    atoms = [
        b"[1 2]", b"[1 0 R]", b"[]", b"[.5 2.]", b"<41>", b"<4>", b"true",
        b"null", b"/A#20B", b"/A#2", b"<< /X [1] >>", b"%c\n", b"(s)", b"5 0 R",
        b"-1", b"[1 0 R 2 0 R 3]", b"\x00", b"\x0b",
    ]
    for _ in range(150):
        values = [rng.choice(atoms) for _ in range(rng.randint(1, 6))]
        body = b"".join(b" /K%d " % k + v for k, v in enumerate(values))
        _compare(b"<<" + body + b" >>", tmp_path)
        _compare(b"[" + b" ".join(values) + b"]", tmp_path)


def test_repeated_reals_keep_their_text_and_value() -> None:
    from pypdfbox.cos import cos_float as cos_float_module

    tokens = [b"1.5", b"-.25", b"5.", b"0.0", b"1e5", b"3.4e39", b"0.00001"]
    for token in tokens * 3:
        if b"e" in token:
            continue
        fresh = COSFloat(token.decode("ascii"))
        cached = cos_float_module._parsed_real(token)
        assert type(cached) is COSFloat
        assert cached._original == fresh._original
        assert cached._value == fresh._value or (
            cached._value != cached._value and fresh._value != fresh._value
        )
        assert vars(cached).keys() == vars(fresh).keys()
        assert list(vars(cached)) == list(vars(fresh))
        assert cached is not cos_float_module._parsed_real(token)


def test_parsed_real_cache_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    from pypdfbox.cos import cos_float as cos_float_module

    monkeypatch.setattr(cos_float_module, "_PARSED_REALS_MAX", 4)
    cos_float_module._PARSED_REALS.clear()
    for k in range(10):
        cos_float_module._parsed_real(b"%d.5" % k)
        assert len(cos_float_module._PARSED_REALS) <= 4
    assert cos_float_module._parsed_real(b"9.5").float_value() == 9.5


def test_fast_containers_have_the_constructor_attributes() -> None:
    parser = COSParser(RandomAccessReadBuffer(b"<< /A [1 2] /B [/N] >>"))
    d = parser.parse_direct_object()
    reference = COSDictionary()
    reference.set_direct(True)
    assert list(vars(d)) == list(vars(reference))
    assert d.is_direct()
    for key in ("A", "B"):
        array = d.get_item(key)
        assert list(vars(array)) == list(vars(COSArray([])))
        assert array.is_direct()
        assert array.get_update_state().get_origin_document_state() is None
    assert d.get_update_state().get_origin_document_state() is None
