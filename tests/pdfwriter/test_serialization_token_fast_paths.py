"""Byte-exact output of the writers' token fast paths: cached ``/Name ``
tokens (including names that need ``#xx`` escaping and names never written
before), pre-formatted integers, inline string escaping, odd floats and
nested dictionaries / arrays, for both the compact object-stream writer
and the main ``COSWriter`` visitor (which coalesces tokens into fewer sink
writes)."""

import io
import itertools

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSObjectKey,
    COSString,
)
from pypdfbox.pdfwriter.compress.cos_writer_object_stream import (
    COSWriterObjectStream,
    serialize_packed_objects,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter, _ObjStmPoolShim

_TAGS = itertools.count()


def _fresh_tag() -> str:
    return f"Fresh{next(_TAGS)}x"


def _name(text: str, tag: str) -> COSName:
    return COSName.get_pdf_name(text.replace("QQ", tag))


def build_graph(tag: str = "QQ") -> list[tuple[str, object]]:
    """Named sample containers; ``tag`` replaces ``QQ`` in every name so a
    test can use names that were never serialized before."""
    leaf = COSDictionary()
    leaf.set_item(_name("TypeQQ", tag), _name("Leaf QQ", tag))
    ref_a = COSObject(41, 0, resolved=leaf)
    ref_b = COSObject(42, 0, resolved=COSArray([COSInteger.get(1)]))

    nested = COSDictionary()
    nested.set_direct(True)
    nested.set_item(_name("Resources", tag), COSDictionary())
    nested.set_item(_name("A(QQ)", tag), COSArray([_name("x/QQ", tag), COSInteger.get(-3)]))

    main = COSDictionary()
    main.set_item(_name("Esc aped#QQ", tag), _name("Va lue/(QQ)%", tag))
    main.set_item(_name("QQé", tag), _name("üQQ", tag))
    main.set_item(_name("IntSmall", tag), COSInteger.get(7))
    main.set_item(_name("IntNeg", tag), COSInteger.get(-129))
    main.set_item(_name("IntEdge", tag), COSInteger.get(2047))
    main.set_item(_name("IntPast", tag), COSInteger.get(2048))
    main.set_item(_name("IntBig", tag), COSInteger.get(2**40))
    main.set_item(_name("FloatTiny", tag), COSFloat(1e-7))
    main.set_item(_name("FloatBig", tag), COSFloat(123456789.0))
    main.set_item(_name("FloatNegZero", tag), COSFloat(-0.0))
    main.set_item(_name("FloatThird", tag), COSFloat(1.0 / 3.0))
    main.set_item(_name("FloatParsed", tag), COSFloat("0.10000"))
    main.set_item(_name("StrParens", tag), COSString(b"a(b)c\\d"))
    main.set_item(_name("StrCR", tag), COSString(b"line\rbreak"))
    main.set_item(_name("StrLF", tag), COSString(b"line\nbreak"))
    main.set_item(_name("StrHigh", tag), COSString(b"caf\xe9"))
    main.set_item(_name("StrEmpty", tag), COSString(b""))
    main.set_item(_name("StrHex", tag), COSString(b"plain", force_hex=True))
    main.set_item(_name("True", tag), COSBoolean.TRUE)
    main.set_item(_name("Null", tag), COSNull.NULL)
    main.set_item(_name("Ref", tag), ref_a)
    main.set_item(_name("Nested", tag), nested)
    main.set_item(_name("Arr", tag), COSArray([ref_b, COSArray([]), nested]))

    # 25 elements: slow (nested) values sit on the every-10th EOL separator
    # positions, so the coalesced writes must keep the EOL state exact.
    mixed = COSArray()
    for i in range(25):
        if i == 9:
            inline = COSDictionary()
            inline.set_direct(True)
            inline.set_item(_name("AtNineQQ", tag), COSInteger.get(9))
            mixed.add(inline)
        elif i == 19:
            mixed.add(COSArray([COSInteger.get(i)]))
        elif i == 12:
            mixed.add(COSString(b"s(12)"))
        elif i == 14:
            mixed.add(None)
        elif i % 3 == 0:
            mixed.add(ref_a)
        elif i % 3 == 1:
            mixed.add(_name("N#QQ", tag))
        else:
            mixed.add(COSInteger.get(i * 1000))
    fast_only = COSArray([COSInteger.get(i) for i in range(21)])
    slow_last = COSArray([COSInteger.get(1), COSString(b"end")])
    slow_first = COSArray([COSFloat(2.5), _name("AfterQQ", tag)])
    eol_then_slow = COSArray([COSInteger.get(i) for i in range(10)])
    eol_then_slow.add(COSString(b"eleventh"))
    return [
        ("dict_main", main),
        ("dict_empty", COSDictionary()),
        ("arr_mixed", mixed),
        ("arr_fast_only", fast_only),
        ("arr_slow_last", slow_last),
        ("arr_slow_first", slow_first),
        ("arr_eol_then_slow", eol_then_slow),
        ("arr_empty", COSArray()),
    ]


def _visit(value: object) -> tuple[bytes, bool, int]:
    sink = io.BytesIO()
    with COSWriter(sink) as writer:
        if isinstance(value, COSArray):
            writer.visit_from_array(value)
        else:
            writer.visit_from_dictionary(value)
        out = writer._standard_output
        return sink.getvalue(), out.is_on_newline(), out.get_position()


# Generated with the one-write-per-token visitor (pypdfbox 2.6.1).
_EXPECTED_VISITOR: dict[str, bytes] = {
    "dict_main": (
        b'<<\n'
        b'/Esc#20aped#23QQ /Va#20lue#2F#28QQ#29#25\n'
        b'/QQ#C3#A9 /#C3#BCQQ\n'
        b'/IntSmall 7\n'
        b'/IntNeg -129\n'
        b'/IntEdge 2047\n'
        b'/IntPast 2048\n'
        b'/IntBig 1099511627776\n'
        b'/FloatTiny 0.0000001\n'
        b'/FloatBig 123456790\n'
        b'/FloatNegZero -0.0\n'
        b'/FloatThird 0.33333334\n'
        b'/FloatParsed 0.10000\n'
        b'/StrParens (a\\(b\\)c\\\\d)\n'
        b'/StrCR <6C696E650D627265616B>\n'
        b'/StrLF <6C696E650A627265616B>\n'
        b'/StrHigh <636166E9>\n'
        b'/StrEmpty ()\n'
        b'/StrHex <706C61696E>\n'
        b'/True true\n'
        b'/Null null\n'
        b'/Ref 1 0 R\n'
        b'/Nested <<\n'
        b'/Resources <<\n'
        b'>>\n'
        b'/A#28QQ#29 [/x#2FQQ -3]\n'
        b'>>\n'
        b'/Arr [2 0 R []\n'
        b' <<\n'
        b'/Resources <<\n'
        b'>>\n'
        b'/A#28QQ#29 [/x#2FQQ -3]\n'
        b'>>\n'
        b']\n'
        b'>>\n'
    ),
    "dict_empty": (
        b'<<\n'
        b'>>\n'
    ),
    "arr_mixed": (
        b'[1 0 R /N#23QQ 2000 1 0 R /N#23QQ 5000 1 0 R /N#23QQ 8000 <<\n'
        b'/AtNineQQ 9\n'
        b'>>\n'
        b'/N#23QQ 11000 (s\\(12\\)) /N#23QQ null 1 0 R /N#23QQ 17000 1 0 R [19]\n'
        b'20000 1 0 R /N#23QQ 23000 1 0 R]\n'
    ),
    "arr_fast_only": (
        b'[0 1 2 3 4 5 6 7 8 9\n'
        b'10 11 12 13 14 15 16 17 18 19\n'
        b'20]\n'
    ),
    "arr_slow_last": (
        b'[1 (end)]\n'
    ),
    "arr_slow_first": (
        b'[2.5 /AfterQQ]\n'
    ),
    "arr_eol_then_slow": (
        b'[0 1 2 3 4 5 6 7 8 9\n'
        b'(eleventh)]\n'
    ),
    "arr_empty": (
        b'[]\n'
    ),
}


def _reference_packed(objects: list, object_keys: dict) -> list[bytes]:
    writer = COSWriterObjectStream(_ObjStmPoolShim(object_keys, {}))
    out = []
    for obj in objects:
        buf = io.BytesIO()
        writer.write_object(buf, obj, top_level=True)
        out.append(buf.getvalue())
    return out


def test_packed_fresh_names_match_reference() -> None:
    """Names never serialized before (no cached token yet) and names
    needing ``#xx`` escapes come out exactly as the reference writer's,
    on the first (uncached) and the second (cached) pass alike."""
    graph = [value for _label, value in build_graph(_fresh_tag())]
    ref = graph[0].get_item(COSName.get_pdf_name("Ref"))
    object_keys = {id(ref.get_object()): COSObjectKey(41, 0)}
    first = serialize_packed_objects(graph, object_keys, {})
    second = serialize_packed_objects(graph, object_keys, {})
    assert first == second
    assert first == _reference_packed(graph, object_keys)
    assert b"41 0 R " in first[0]


def test_packed_name_tokens_escape_like_write_pdf() -> None:
    tag = _fresh_tag()
    names = [_name(text, tag) for text in ("A B", "#QQ", "x/y", "(QQ)", "é", "ok-_.")]
    holder = COSDictionary()
    for index, name in enumerate(names):
        holder.set_item(name, COSArray([name, COSInteger.get(index)]))
    (body,) = serialize_packed_objects([holder], {}, {})
    expected = b"<<"
    for index, name in enumerate(names):
        sink = io.BytesIO()
        name.write_pdf(sink)
        token = sink.getvalue()
        expected += token + b" [" + token + b" %d ] " % index
    assert body == expected + b">> "
    assert b"/A#20B" in body
    assert b"/#23" in body
    assert b"/x#2Fy" in body
    assert b"/#C3#A9" in body


def test_packed_strings_and_ints_match_reference() -> None:
    holder = COSDictionary()
    values = [
        COSString(b"a(b)c\\d"),
        COSString(b"cr\rhere"),
        COSString(b"lf\nhere"),
        COSString(b"\x80\xff"),
        COSString(b""),
        COSString(b"hex", force_hex=True),
        COSInteger.get(-128),
        COSInteger.get(-129),
        COSInteger.get(2047),
        COSInteger.get(2048),
        COSInteger.get(-(2**63)),
        COSFloat(0.1),
        COSFloat(-1e-5),
        COSFloat("1.50"),
    ]
    for index, value in enumerate(values):
        holder.set_item(f"K{index}", value)
    arr = COSArray(list(values))
    objects = [holder, arr, COSArray([holder, arr])]
    assert serialize_packed_objects(objects, {}, {}) == _reference_packed(objects, {})


def test_visitor_matches_one_write_per_token_output() -> None:
    for name, value in build_graph():
        data, on_new_line, position = _visit(value)
        assert data == _EXPECTED_VISITOR[name], name
        assert on_new_line is True, name
        assert position == len(data), name


def test_visitor_fresh_names_match_cached_output() -> None:
    tag = _fresh_tag()
    for name, value in build_graph(tag):
        data, _, _ = _visit(value)
        expected = _EXPECTED_VISITOR[name].replace(b"QQ", tag.encode("ascii"))
        assert data == expected, name
