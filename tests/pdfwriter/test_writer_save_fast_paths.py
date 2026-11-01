"""The save-path fast paths must emit exactly what the reference algorithms
emit: ``serialize_packed_objects`` vs ``COSWriterObjectStream.write_object``
over the writer's pool shim, the object-stream / xref-stream output of whole
saves, incremental saves, and deeply nested structures that a recursive
writer could not handle."""

import io
import pathlib
import re
import sys
import zlib

import pytest

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
from pypdfbox.pdfwriter.compress import cos_writer_object_stream as objstm_mod
from pypdfbox.pdfwriter.compress.compress_parameters import CompressParameters
from pypdfbox.pdfwriter.compress.cos_writer_object_stream import (
    COSWriterObjectStream,
    serialize_packed_objects,
)
from pypdfbox.pdfwriter.cos_writer import COSWriter, _ObjStmPoolShim, _pack_unsigned
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage

_FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
_FIXTURE_PDFS = [
    _FIXTURES / "pdfwriter" / "unencrypted.pdf",
    _FIXTURES / "pdfwriter" / "acroform.pdf",
    _FIXTURES / "multipdf" / "AcroFormForMerge.pdf",
    _FIXTURES / "multipdf" / "PDFA3A.pdf",
    _FIXTURES / "multipdf" / "rot90.pdf",
]


def _reference_serialize(
    objects: list, object_keys: dict, value_pool: dict
) -> list[bytes]:
    """The pre-fast-path algorithm: the compact object-stream writer over
    the writer's pool shim, one ``BytesIO`` per packed object."""
    writer = COSWriterObjectStream(_ObjStmPoolShim(object_keys, value_pool))
    out = []
    for obj in objects:
        buf = io.BytesIO()
        writer.write_object(buf, obj, top_level=True)
        out.append(buf.getvalue())
    return out


def _reference_serialize_shared(
    objects: list, object_keys: dict, value_pool: dict, ref_cache=None
) -> list[bytes]:
    return _reference_serialize(objects, object_keys, value_pool)


def _sample_graph() -> tuple[list, dict, dict]:
    """A packed-object batch covering every token kind and pool outcome."""
    indirect_dict = COSDictionary()
    indirect_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Page"))
    indirect_arr = COSArray([COSInteger.get(1), COSInteger.get(2)])
    indirect_int = COSInteger.get(4242)
    keyed_wrapper = COSObject(9, 0, resolved=COSDictionary())
    keyed_wrapper.set_key(COSObjectKey(9, 0))
    dangling = COSObject(77, 0)  # no loader: resolves to None -> ``null``
    unkeyed_wrapper = COSObject(12, 0, resolved=indirect_dict)

    object_keys = {
        id(indirect_dict): COSObjectKey(3, 0),
        id(indirect_arr): COSObjectKey(4, 0),
        id(indirect_int): COSObjectKey(5, 0),
    }
    # The value pool makes a *direct* value-equal integer a reference.
    value_pool = {indirect_int: COSObjectKey(5, 0)}

    inner = COSDictionary()
    inner.set_item("Esc aped#Name", COSName.get_pdf_name("Val ue/(x)"))
    inner.set_item("Fresh", COSName.get_pdf_name("NeverWrittenBefore_ZZ_9"))
    inner.set_item("Str", COSString(b"lit(er)al\\"))
    inner.set_item("Hex", COSString(b"\x00\xffbin"))
    inner.set_item("Real", COSFloat(3.25))
    inner.set_item("Neg", COSFloat(-0.001))
    inner.set_item("T", COSBoolean.TRUE)
    inner.set_item("F", COSBoolean.FALSE)
    inner.set_item("Null", COSNull.NULL)
    inner.set_item("Pooled", COSInteger.get(4242))
    inner.set_item("Plain", COSInteger.get(-17))
    inner.set_item("Big", COSInteger.get(2**40))

    arr = COSArray()
    arr.add(indirect_dict)
    arr.add(indirect_arr)
    arr.add(keyed_wrapper)
    arr.add(unkeyed_wrapper)
    arr.add(dangling)
    arr.add(COSNull.NULL)
    arr.add(COSArray([COSArray([COSName.get_pdf_name("Deep")])]))
    arr.add(COSString(b"x"))
    arr.add(COSFloat(1.5))
    arr.add(COSBoolean.TRUE)

    top = COSDictionary()
    top.set_item("Inner", inner)
    top.set_item("Arr", arr)
    top.set_item("Ref", indirect_dict)
    top.set_item("Kids", COSArray([unkeyed_wrapper, keyed_wrapper]))

    objects = [
        top,
        arr,
        inner,
        indirect_dict,  # top-level: written inline, not as a self-reference
        COSInteger.get(4242),  # top-level scalar stays inline
        COSName.get_pdf_name("TopName"),
        COSString(b"top"),
        COSFloat(2.0),
        COSBoolean.FALSE,
        COSNull.NULL,
        unkeyed_wrapper,
        dangling,
    ]
    return objects, object_keys, value_pool


def test_serialize_matches_reference_writer() -> None:
    objects, object_keys, value_pool = _sample_graph()
    expected = _reference_serialize(objects, object_keys, value_pool)
    assert serialize_packed_objects(objects, object_keys, value_pool) == expected


def test_serialize_matches_reference_without_value_pool() -> None:
    objects, object_keys, _ = _sample_graph()
    expected = _reference_serialize(objects, object_keys, {})
    assert serialize_packed_objects(objects, object_keys, {}) == expected


def test_serialize_shared_ref_cache_matches_reference() -> None:
    objects, object_keys, value_pool = _sample_graph()
    expected = _reference_serialize(objects, object_keys, value_pool)
    cache: dict = {}
    first = serialize_packed_objects(objects, object_keys, value_pool, cache)
    second = serialize_packed_objects(objects, object_keys, value_pool, cache)
    assert first == expected
    assert second == expected
    assert cache  # references were memoised


def test_serialize_value_pool_kinds() -> None:
    """Pool lookups by value apply per scalar kind (name / string / float /
    boolean too), exactly like the shim."""
    name = COSName.get_pdf_name("PooledName")
    string = COSString(b"pooled")
    real = COSFloat(7.5)
    value_pool = {
        name: COSObjectKey(20, 0),
        COSString(b"pooled"): COSObjectKey(21, 0),
        COSFloat(7.5): COSObjectKey(22, 0),
        COSBoolean.TRUE: COSObjectKey(23, 0),
    }
    holder = COSDictionary()
    holder.set_item("N", name)
    holder.set_item("S", string)
    holder.set_item("R", real)
    holder.set_item("B", COSBoolean.TRUE)
    holder.set_item("Other", COSFloat(7.25))
    holder.set_item("A", COSArray([name, string, real, COSInteger.get(1)]))
    objects = [holder, COSArray([holder])]
    expected = _reference_serialize(objects, {}, value_pool)
    assert serialize_packed_objects(objects, {}, value_pool) == expected
    assert b"20 0 R" in expected[0]


def test_serialize_unknown_type_raises_like_reference() -> None:
    bad = COSArray()
    bad._items.append(object())
    with pytest.raises(OSError, match="Unknown type"):
        _reference_serialize([bad], {}, {})
    with pytest.raises(OSError, match="Unknown type"):
        serialize_packed_objects([bad], {}, {})


def _nested_arrays(depth: int) -> COSArray:
    root = COSArray()
    current = root
    for i in range(depth):
        child = COSArray()
        current.add(COSInteger.get(i))
        current.add(child)
        current = child
    current.add(COSName.get_pdf_name("Bottom"))
    return root


def _nested_dicts(depth: int) -> COSDictionary:
    root = COSDictionary()
    current = root
    for i in range(depth):
        child = COSDictionary()
        current.set_item("I", COSInteger.get(i))
        current.set_item("K", child)
        current = child
    current.set_item("End", COSBoolean.TRUE)
    return root


def test_serialize_moderate_nesting_matches_reference() -> None:
    """Nesting past the recursive fast path's depth bound switches to the
    explicit-stack walker mid-structure; bytes must not change."""
    objects = [_nested_arrays(300), _nested_dicts(300)]
    expected = _reference_serialize(objects, {}, {})
    assert serialize_packed_objects(objects, {}, {}) == expected


def test_serialize_deep_nesting_beyond_recursion_limit() -> None:
    depth = sys.getrecursionlimit() * 3
    arrays = serialize_packed_objects([_nested_arrays(depth)], {}, {})[0]
    expected = (
        b"[" + b"".join(b"%d [" % i for i in range(depth)) + b"/Bottom "
        + b"] " * (depth + 1)
    )
    assert arrays == expected
    dicts = serialize_packed_objects([_nested_dicts(depth)], {}, {})[0]
    expected = (
        b"<<" + b"".join(b"/I %d /K <<" % i for i in range(depth))
        + b"/End true " + b">> " * (depth + 1)
    )
    assert dicts == expected


def _save(doc: PDDocument, params: CompressParameters | None = None) -> bytes:
    buf = io.BytesIO()
    if params is None:
        doc.save(buf)
    else:
        doc.save(buf, params)
    return buf.getvalue()


@pytest.mark.parametrize("path", _FIXTURE_PDFS, ids=lambda p: p.name)
def test_compressed_save_matches_reference_serializer(
    path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with PDDocument.load(path) as doc:
        fast = _save(doc, CompressParameters.DEFAULT_COMPRESSION)
    monkeypatch.setattr(
        objstm_mod, "serialize_packed_objects", _reference_serialize_shared
    )
    with PDDocument.load(path) as doc:
        reference = _save(doc, CompressParameters.DEFAULT_COMPRESSION)
    assert _strip_id(fast) == _strip_id(reference)


def _strip_id(data: bytes) -> bytes:
    return re.sub(rb"/ID \[<[0-9A-Fa-f]*> ?<[0-9A-Fa-f]*>\]", b"/ID []", data)


@pytest.mark.parametrize("path", _FIXTURE_PDFS, ids=lambda p: p.name)
def test_resave_is_deterministic_and_round_trips(path: pathlib.Path) -> None:
    with PDDocument.load(path) as doc:
        first = _save(doc, CompressParameters.DEFAULT_COMPRESSION)
        pages = doc.get_number_of_pages()
    with PDDocument.load(path) as doc:
        second = _save(doc, CompressParameters.DEFAULT_COMPRESSION)
    assert _strip_id(first) == _strip_id(second)
    with PDDocument.load(io.BytesIO(first)) as reloaded:
        assert reloaded.get_number_of_pages() == pages
    _check_xref_stream_rows(first)


def _check_xref_stream_rows(data: bytes) -> None:
    """Every xref-stream row must equal the three ``_pack_unsigned`` fields
    (the reference packing the row-at-once fast path replaced)."""
    start = int(data[data.rindex(b"startxref") + 9 :].split()[0])
    head = data[start : data.index(b"stream", start)]
    widths = [int(w) for w in re.search(rb"/W ?\[([0-9 ]+)\]", head).group(1).split()]
    length = int(re.search(rb"/Length (\d+)", head).group(1))
    body_start = data.index(b"stream", start) + len(b"stream")
    while data[body_start : body_start + 1] in (b"\r", b"\n"):
        body_start += 1
    body = zlib.decompress(data[body_start : body_start + length])
    row = sum(widths)
    assert row > 0
    assert len(body) % row == 0
    for off in range(0, len(body), row):
        fields = []
        pos = off
        for w in widths:
            fields.append(int.from_bytes(body[pos : pos + w], "big") if w else 0)
            pos += w
        packed = b"".join(
            _pack_unsigned(v, w) for v, w in zip(fields, widths, strict=True)
        )
        assert packed == body[off : off + row]


def _xref_stream_save(doc: PDDocument, *, object_stream: bool) -> bytes:
    buf = io.BytesIO()
    with COSWriter(buf, xref_stream=True, object_stream=object_stream) as writer:
        writer.write(doc)
    return buf.getvalue()


@pytest.mark.parametrize("object_stream", [False, True], ids=["xref", "objstm"])
def test_xref_stream_save_round_trips(object_stream: bool) -> None:
    path = _FIXTURES / "pdfwriter" / "unencrypted.pdf"
    with PDDocument.load(path) as doc:
        data = _xref_stream_save(doc, object_stream=object_stream)
        pages = doc.get_number_of_pages()
    assert b"/Type /XRef" in data or b"/Type/XRef" in data
    _check_xref_stream_rows(data)
    with PDDocument.load(io.BytesIO(data)) as reloaded:
        assert reloaded.get_number_of_pages() == pages


def test_incremental_save_after_edit_round_trips(tmp_path: pathlib.Path) -> None:
    src = tmp_path / "in.pdf"
    with PDDocument.load(_FIXTURES / "pdfwriter" / "unencrypted.pdf") as doc:
        src.write_bytes(_save(doc, CompressParameters.DEFAULT_COMPRESSION))
    original = src.read_bytes()
    with PDDocument.load(src) as doc:
        info = doc.get_document_information()
        info.set_title("fast path")
        info.get_cos_object().set_needs_to_be_updated(True)
        out = io.BytesIO()
        doc.save_incremental(out)
    data = out.getvalue()
    assert data.startswith(original)
    with PDDocument.load(io.BytesIO(data)) as reloaded:
        assert reloaded.get_document_information().get_title() == "fast path"


def _deep_indirect_chain_doc(depth: int) -> PDDocument:
    doc = PDDocument()
    doc.add_page(PDPage())
    catalog = doc.get_document_catalog().get_cos_object()
    head = COSDictionary()
    current = head
    for i in range(depth):
        child = COSDictionary()
        child.set_direct(False)
        current.set_item("Next", child)
        current.set_int("N", i)
        current = child
    head.set_direct(False)
    catalog.set_item("DeepChain", head)
    # Deep *direct* nesting lives in a packable (non-catalog) dictionary, so
    # it is serialised by the object-stream fast path.
    holder = COSDictionary()
    holder.set_direct(False)
    holder.set_item("DeepArray", _nested_arrays(depth))
    catalog.set_item("DeepHolder", holder)
    return doc


def test_compressed_save_of_deep_structures() -> None:
    """Deeply chained indirect dictionaries and direct arrays nested far past
    the recursion limit save (and reload) through the object-stream path."""
    depth = sys.getrecursionlimit() * 2
    doc = _deep_indirect_chain_doc(depth)
    try:
        data = _save(doc, CompressParameters.DEFAULT_COMPRESSION)
    finally:
        doc.close()
    assert b"/Type /ObjStm" in data
    with PDDocument.load(io.BytesIO(data)) as reloaded:
        catalog = reloaded.get_document_catalog().get_cos_object()
        node = catalog.get_cos_dictionary(COSName.get_pdf_name("DeepChain"))
        count = 0
        while node is not None and count < depth:
            assert node.get_int("N") == count
            node = node.get_cos_dictionary(COSName.get_pdf_name("Next"))
            count += 1
        assert count == depth
    # The (recursive) parser cannot reload the deep array, so check the
    # packed bytes directly in the decoded object streams.
    expected = (
        b"/DeepArray [" + b"".join(b"%d [" % i for i in range(depth))
        + b"/Bottom " + b"] " * (depth + 1)
    )
    assert any(expected in body for body in _objstm_bodies(data))


def _objstm_bodies(data: bytes) -> list[bytes]:
    bodies = []
    for match in re.finditer(rb"/Type /ObjStm", data):
        dict_start = data.rindex(b"obj", 0, match.start())
        head = data[dict_start : data.index(b"stream", match.start())]
        length = int(re.search(rb"/Length (\d+)", head).group(1))
        body_start = data.index(b"stream", match.start()) + len(b"stream")
        while data[body_start : body_start + 1] in (b"\r", b"\n"):
            body_start += 1
        bodies.append(zlib.decompress(data[body_start : body_start + length]))
    return bodies
