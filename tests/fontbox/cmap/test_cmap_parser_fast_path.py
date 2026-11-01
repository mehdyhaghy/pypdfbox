"""Differential tests for the in-memory CMap tokenizer fast path.

``CMapParser.parse`` scans a ``_ByteCursor`` with index arithmetic and
regular expressions. Any other ``RandomAccessRead`` (including a
``RandomAccessReadBuffer`` subclass) still goes through the byte-by-byte
reference tokenizer, so the two paths can be compared on the same input.
"""

import random
import re

import pytest

from pypdfbox.fontbox.cmap.cmap_parser import (
    _RESOURCES_DIR,
    CMapParser,
    _ByteCursor,
    _LiteralName,
    _Operator,
)
from pypdfbox.io import RandomAccessReadBuffer


class _ReferenceBuffer(RandomAccessReadBuffer):
    """Not the exact buffer type, so parsing uses the per-byte path."""


def _snapshot(cmap) -> object:
    state = []
    for key in sorted(vars(cmap)):
        value = getattr(cmap, key)
        if key == "_parent_cmaps":
            value = [_snapshot(p) for p in value]
        elif key == "_codespace_ranges":
            value = [(bytes(r._start), bytes(r._end)) for r in value]
        elif key == "_code_to_cid_ranges":
            value = [(r._from, r._to, r._unicode, r._code_length) for r in value]
        state.append((key, value))
    return state


def _normalize_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    return re.sub(r"<[\w.]*\.(_\w+) object at 0x[0-9a-f]+>", r"<\1>", text)


def _outcome(data: bytes, buffer_type: type, strict: bool) -> tuple[object, int]:
    ras = buffer_type(data)
    try:
        result = _snapshot(CMapParser(strict).parse(ras))
    except Exception as exc:
        result = _normalize_error(exc)
    return result, ras.get_position()


def _assert_same(data: bytes) -> None:
    for strict in (False, True):
        fast = _outcome(data, RandomAccessReadBuffer, strict)
        reference = _outcome(data, _ReferenceBuffer, strict)
        assert fast == reference, data


def _token_repr(token: object) -> object:
    if isinstance(token, _LiteralName):
        return ("name", token.name)
    if isinstance(token, _Operator):
        return ("op", token.op)
    if isinstance(token, list):
        return [_token_repr(t) for t in token]
    if isinstance(token, dict):
        return {k: _token_repr(v) for k, v in token.items()}
    return (type(token).__name__, token)


def _tokens(ras) -> list[object]:
    parser = CMapParser()
    out: list[object] = []
    while True:
        try:
            token = parser.parse_next_token(ras)
        except OSError as exc:
            out.append(("error", str(exc), ras.get_position()))
            return out
        out.append((_token_repr(token), ras.get_position()))
        if token is None:
            return out


TRICKY = {
    "comments": b"%!PS\n% c1\r%c2\r\n1 begincidchar %x\n<20>%y\r 5 endcidchar\n%end",
    "comment_at_eof": b"/WMode 1 %trailing",
    "hex_whitespace": b"1 begincidrange <0 0\n2\t0> < 00\x0c7e > 1 endcidrange",
    "hex_odd_digits": b"2 begincidchar <123> 1 <4> 2 endcidchar",
    "hex_empty": b"1 beginbfchar <01> <> endbfchar",
    "hex_bad_digit": b"1 begincidchar <12g4> 1 endcidchar",
    "hex_unterminated": b"1 begincodespacerange <00> <FF",
    "nested_arrays": b"1 beginbfrange <00> <02> [<0041> [<0042>] <0043> <0044>] endbfrange",
    "array_string_close": b"1 beginbfrange <00> <01> [<0041> (]) <0042>] endbfrange",
    "nested_dict": (
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Japan1)"
        b" /Inner << /A 1 /B [1 2] >> /Supplement 6 >> def"
    ),
    "dict_bad_close": b"/CIDSystemInfo << /Registry (Adobe) >x",
    "literal_escapes": b"/Registry (A\\)dobe) /Ordering (Ja\\npan\\050) /Supplement 2",
    "string_unterminated": b"/Registry (Adobe",
    "percent_string_skipped": b"(%not a comment) /WMode 1",
    "truncated_cidrange": b"2 begincidrange <0000> <00ff> 1 <0100>",
    "truncated_bfrange": b"1 beginbfrange <0000> <0001>",
    "unknown_operators": b"foo bar 3 baz <00> qux /WMode 1 xyz endcmap /WMode 0",
    "operator_digit_split": b"1begincidchar<20>7endcidchar",
    "number_forms": b"/CMapVersion 1.5 /CMapType 1.2.3",
    "number_float_count": b"1.0 begincidrange <00> <01> 3 endcidrange",
    "name_delimiters": b"/CMapName/Foo-H def/WMode 1",
    "reversed_bfrange": b"2 beginbfrange <0010> <0001> <0041> <0020> <0021> <0061> endbfrange",
    "reversed_cidrange": b"1 begincidrange <10> <01> 5 endcidrange",
    "length_mismatch": b"1 begincidrange <00> <0001> 5 endcidrange",
    "wrong_end_operator": b"2 begincidchar <00> 1 endbfchar",
    "identity_bfrange": b"1 beginbfrange <0000> <FFFF> <0000> endbfrange",
    "strict_overflow": b"1 beginbfrange <0000> <0005> <00FE> endbfrange",
    "bfrange_null_dst": b"1 beginbfrange <00> <01> null endbfrange",
    "notdef": (
        b"1 beginnotdefrange <00> <03> 1 endnotdefrange"
        b" 1 beginnotdefchar <05> 9 endnotdefchar"
    ),
    "codespace_no_space": b"1 begincodespacerange<00><FF>endcodespacerange",
    "nul_and_ff_padding": b"\x00\x0c1 begincidchar\x00<20>\x0c3\x00endcidchar",
    "usecmap": b"/Identity-H usecmap 1 begincidchar <0001> 7 endcidchar",
    "high_bytes": b"\x80\xff /W\xe9Mode 1 (\xff\xfe)",
    "endcmap_stops": b"/WMode 1 endcmap /WMode 0 <zz>",
    "empty": b"",
}


@pytest.mark.parametrize("name", sorted(TRICKY), ids=sorted(TRICKY))
def test_parse_matches_reference_path(name: str) -> None:
    _assert_same(TRICKY[name])


@pytest.mark.parametrize("name", sorted(TRICKY), ids=sorted(TRICKY))
def test_token_stream_matches_reference_path(name: str) -> None:
    data = TRICKY[name]
    assert _tokens(_ByteCursor(data)) == _tokens(_ReferenceBuffer(data))


def test_whitespace_after_hex_entry_is_not_consumed() -> None:
    cmap = CMapParser().parse(
        b"1 begincodespacerange<00><FF>endcodespacerange "
        b"1 beginbfchar<01><0041>/WMode 1 endbfchar"
    )
    assert cmap.get_codespace_ranges()[0].get_code_length() == 1
    assert cmap.to_unicode(1) == "A"


@pytest.mark.parametrize(
    "name",
    ["90ms-RKSJ-V", "B5pc-H", "GB-EUC-H", "KSC-EUC-H", "UniJIS-UTF16-V", "GBK-EUC-H"],
)
def test_predefined_resources_match_reference_path(name: str) -> None:
    _assert_same((_RESOURCES_DIR / name).read_bytes())


def test_random_mutations_match_reference_path() -> None:
    rng = random.Random(20261031)
    corpus = [*TRICKY.values(), (_RESOURCES_DIR / "B5pc-V").read_bytes()]
    atoms = [b" ", b"\n", b"%", b"<", b">", b"[", b"]", b"(", b")", b"/", b"{", b"7", b"1.5"]
    atoms.append(b"<00 4>")
    for _ in range(300):
        data = bytearray(rng.choice(corpus))
        for _ in range(rng.randint(1, 4)):
            pos = rng.randrange(len(data) + 1)
            choice = rng.random()
            if choice < 0.4:
                del data[pos : pos + rng.randint(1, 4)]
            elif choice < 0.8:
                data[pos:pos] = rng.choice(atoms)
            else:
                del data[pos:]
        _assert_same(bytes(data))


def test_parse_leaves_buffer_positioned_like_reference() -> None:
    data = b"/WMode 1 endcmap trailing bytes"
    fast = RandomAccessReadBuffer(data)
    CMapParser().parse(fast)
    reference = _ReferenceBuffer(data)
    CMapParser().parse(reference)
    assert fast.get_position() == reference.get_position() == data.index(b"trailing")


def test_parse_starts_at_current_buffer_position() -> None:
    data = b"/WMode 1 /WMode 0"
    ras = RandomAccessReadBuffer(data)
    ras.seek(9)
    assert CMapParser().parse(ras).get_wmode() == 0


def _reference_frombfrange(parser, cmap, start_code, count, token_bytes):
    for _ in range(count):
        value = parser.create_string_from_bytes(bytes(token_bytes))
        cmap.add_base_font_character(bytes(start_code), value)
        if not parser.increment(token_bytes, len(token_bytes) - 1, parser._strict_mode):
            break
        parser.increment(start_code, len(start_code) - 1, False)


@pytest.mark.parametrize("strict", [False, True])
@pytest.mark.parametrize(
    ("start", "token", "count"),
    [
        (b"\x00", b"\xfe", 4),
        (b"\x00\xfe", b"\x00\xfd", 5),
        (b"\xff\xff", b"\x00\x41", 3),
        (b"\x01", b"\xd8\x3d\xde\x00", 3),
        (b"\x00\x00\x00", b"\xff", 3),
        (b"\x10", b"\x00\xff\xfe", 4),
    ],
)
def test_add_mapping_frombfrange_matches_bytewise_increment(start, token, count, strict):
    from pypdfbox.fontbox.cmap import CMap

    parser = CMapParser(strict_mode=strict)
    fast_cmap, ref_cmap = CMap(), CMap()
    fast_start, fast_token = bytearray(start), bytearray(token)
    ref_start, ref_token = bytearray(start), bytearray(token)
    parser.add_mapping_frombfrange(fast_cmap, fast_start, count, fast_token)
    _reference_frombfrange(parser, ref_cmap, ref_start, count, ref_token)
    assert _snapshot(fast_cmap) == _snapshot(ref_cmap)
    assert (fast_start, fast_token) == (ref_start, ref_token)


def test_byte_cursor_random_access_contract() -> None:
    cur = _ByteCursor(b"abc")
    assert cur.length() == 3
    assert cur.peek() == ord("a")
    assert cur.read() == ord("a")
    buf = bytearray(5)
    assert cur.read_into(buf) == 2
    assert bytes(buf[:2]) == b"bc"
    assert cur.is_eof()
    assert cur.read() == -1
    cur.rewind(2)
    assert cur.get_position() == 1
    with pytest.raises(OSError):
        cur.rewind(5)
    cur.seek(10)
    assert cur.get_position() == 3
    cur.close()
    assert cur.is_closed()
    with pytest.raises(OSError):
        cur.read()
