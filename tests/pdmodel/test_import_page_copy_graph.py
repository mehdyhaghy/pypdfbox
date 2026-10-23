"""Pin the object-graph semantics of the ``import_page`` deep copy.

``_deep_copy_cos_graph`` replaced a recursive copier; these tests lock in
the observable behaviour the replacement must keep (which occurrence of a
shared container is copied, leaf sharing, stream bodies, dropped dangling
references) plus the one intended difference: no recursion-depth limit.
"""

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.pd_document import _deep_copy_cos_graph

_N = COSName.get_pdf_name


def _stream(payload: bytes) -> COSStream:
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(payload)
    return stream


def test_second_occurrence_of_shared_container_is_the_original() -> None:
    shared = COSDictionary()
    shared.set_item(_N("A"), COSInteger.get(1))
    root = COSDictionary()
    root.set_item(_N("X"), shared)
    root.set_item(_N("Y"), COSObject(7, resolved=shared))
    seen: set[int] = set()

    copy = _deep_copy_cos_graph(root, seen)

    first = copy.get_item(_N("X"))
    assert first is not shared
    assert first.get_item(_N("A")) is shared.get_item(_N("A"))
    # Revisits (here through an indirect reference) share the source
    # instance instead of the first copy.
    assert copy.get_item(_N("Y")) is shared
    assert seen == {id(root), id(shared)}


def test_seeded_seen_set_is_shared_not_copied() -> None:
    page = COSDictionary()
    annot = COSDictionary()
    annot.set_item(_N("P"), page)
    annots = COSArray([annot])

    copy = _deep_copy_cos_graph(annots, {id(page)})

    assert copy is not annots
    assert copy.get(0) is not annot
    assert copy.get(0).get_item(_N("P")) is page


def test_leaves_are_shared_and_order_is_preserved() -> None:
    name, num, real, text = _N("V"), COSInteger.get(5000), COSFloat(1.5), COSString("s")
    src = COSDictionary()
    for key, value in (("Z", name), ("A", num), ("M", real), ("B", text)):
        src.set_item(_N(key), value)
    arr = COSArray([num, real, text, name])
    src.set_item(_N("Arr"), arr)

    copy = _deep_copy_cos_graph(src, set())

    assert [k.get_name() for k in copy.key_set()] == ["Z", "A", "M", "B", "Arr"]
    for key in ("Z", "A", "M", "B"):
        assert copy.get_item(_N(key)) is src.get_item(_N(key))
    copied_arr = copy.get_item(_N("Arr"))
    assert copied_arr is not arr
    assert copied_arr.is_direct()
    assert [copied_arr.get(i) for i in range(4)] == [num, real, text, name]
    assert all(copied_arr.get(i) is arr.get(i) for i in range(4))


def test_stream_copy_keeps_raw_body_and_syncs_length() -> None:
    stream = _stream(b"q 1 0 0 1 0 0 cm Q")
    stream.set_item(_N("Filter"), _N("FlateDecode"))
    stream.set_item(_N("Length"), COSObject(9, resolved=COSInteger.get(999)))

    copy = _deep_copy_cos_graph(stream, set())

    assert isinstance(copy, COSStream)
    assert copy is not stream
    assert copy.get_raw_data() == stream.get_raw_data()
    keys = [k.get_name() for k in copy.key_set()]
    assert keys == [k.get_name() for k in stream.key_set()]
    assert copy.get_item(_N("Length")).int_value() == len(stream.get_raw_data())


def test_dangling_reference_is_dropped_from_dicts_and_kept_as_none_in_arrays() -> None:
    src = COSDictionary()
    src.set_item(_N("Gone"), COSObject(3))
    src.set_item(_N("Kept"), COSInteger.get(1))
    src.set_item(_N("Arr"), COSArray([COSObject(4), COSInteger.get(2)]))

    copy = _deep_copy_cos_graph(src, set())

    assert not copy.contains_key(_N("Gone"))
    assert copy.get_item(_N("Kept")) is src.get_item(_N("Kept"))
    arr = copy.get_item(_N("Arr"))
    assert arr.size() == 2
    assert arr.get(0) is None


def test_cycles_terminate_and_share_the_original() -> None:
    a = COSDictionary()
    b = COSDictionary()
    a.set_item(_N("B"), b)
    b.set_item(_N("A"), a)

    copy = _deep_copy_cos_graph(a, set())

    assert copy is not a
    assert copy.get_item(_N("B")) is not b
    assert copy.get_item(_N("B")).get_item(_N("A")) is a


def test_deep_nesting_has_no_recursion_limit() -> None:
    root = COSArray()
    node = root
    for _ in range(20000):
        child = COSArray()
        node.add(child)
        node = child
    node.add(COSInteger.get(42))

    copy = _deep_copy_cos_graph(root, set())

    depth = 0
    node = copy
    while isinstance(node, COSArray) and node.size() and isinstance(node.get(0), COSArray):
        assert node is not root
        node = node.get(0)
        depth += 1
    assert depth == 20000
    assert node.get(0).int_value() == 42


def test_import_page_copies_nested_resources_and_skips_parent() -> None:
    src = PDDocument()
    page = PDPage()
    font = COSDictionary()
    font.set_item(_N("Widths"), COSArray([COSInteger.get(i) for i in range(300)]))
    fonts = COSDictionary()
    fonts.set_item(_N("F1"), font)
    fonts.set_item(_N("F2"), font)
    resources = COSDictionary()
    resources.set_item(_N("Font"), fonts)
    page.get_cos_object().set_item(_N("Resources"), resources)
    page.get_cos_object().set_item(_N("Contents"), _stream(b"/F1 1 Tf"))
    src.add_page(page)

    dst = PDDocument()
    imported = dst.import_page(page)

    imported_fonts = imported.get_cos_object().get_dictionary_object(
        _N("Resources")
    ).get_dictionary_object(_N("Font"))
    assert imported_fonts is not fonts
    first = imported_fonts.get_item(_N("F1"))
    assert first is not font
    assert first.get_item(_N("Widths")).size() == 300
    # Within one import_page call the second reference shares the source.
    assert imported_fonts.get_item(_N("F2")) is font
    parent = imported.get_cos_object().get_dictionary_object(_N("Parent"))
    assert parent is dst.get_pages().get_cos_object()
