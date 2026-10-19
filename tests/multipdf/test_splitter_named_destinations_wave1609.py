"""PDFBOX-6283: the Splitter keeps named destinations and rebuilds the
``/Names /Dests`` name tree and the legacy ``/Root/Dests`` dictionary in
each split document, resolving a named destination to its page only when
the name is a "broken string" (contains a NUL character)."""

import io

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.multipdf.splitter import Splitter
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination_name_tree_node import (  # noqa: E501
    PDDestinationNameTreeNode,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary

_DESTS = COSName.get_pdf_name("Dests")
_DEST = COSName.get_pdf_name("Dest")
_NAMES = COSName.get_pdf_name("Names")
_D = COSName.get_pdf_name("D")
_FIT = COSName.get_pdf_name("Fit")


def _make_doc(num_pages: int) -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        doc.add_page(PDPage())
    return doc


def _fit_dest(page: PDPage) -> PDPageFitDestination:
    dest = PDPageFitDestination()
    dest.set_page(page)
    return dest


def _set_name_tree(doc: PDDocument, dests: dict) -> None:
    names = PDDocumentNameDictionary(doc.get_document_catalog())
    tree = PDDestinationNameTreeNode()
    tree.set_names(dests)
    names.set_dests(tree)
    doc.get_document_catalog().set_names(names)


def _add_link(page: PDPage, dest_value) -> PDAnnotationLink:
    link = PDAnnotationLink()
    link.set_rectangle(PDRectangle(10, 600, 100, 100))
    link.get_cos_object().set_item(_DEST, dest_value)
    annots = list(page.get_annotations())
    annots.append(link)
    page.set_annotations(annots)
    return link


def _close(*docs) -> None:
    for d in docs:
        d.close()


# ---------- named destination kept ----------


def test_named_dest_kept_when_target_page_in_split() -> None:
    src = _make_doc(2)
    _set_name_tree(src, {"target": _fit_dest(src.get_page(1))})
    _add_link(src.get_page(0), COSString("target"))

    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    try:
        assert len(chunks) == 1
        chunk = chunks[0]
        link = chunk.get_page(0).get_annotations()[0]
        dest = link.get_destination()
        assert isinstance(dest, PDNamedDestination)
        assert dest.get_named_destination() == "target"

        tree = chunk.get_document_catalog().get_names().get_dests()
        resolved = tree.get_value("target")
        assert isinstance(resolved, PDPageFitDestination)
        assert resolved.get_page() is chunk.get_page(1).get_cos_object()
        # the cloned destination is a fresh array, not the source one
        src_tree = src.get_document_catalog().get_names().get_dests()
        assert resolved.get_cos_object() is not (
            src_tree.get_value("target").get_cos_object()
        )
        # the source tree still targets the source page
        assert src_tree.get_value("target").get_page() is (
            src.get_page(1).get_cos_object()
        )
        # catalog-level lookup in the chunk resolves through the new tree
        found = chunk.get_document_catalog().find_named_destination_page(dest)
        assert found.get_page() is chunk.get_page(1).get_cos_object()
    finally:
        _close(*chunks, src)


def test_named_dest_in_goto_action_kept() -> None:
    src = _make_doc(2)
    _set_name_tree(src, {"target": _fit_dest(src.get_page(1))})
    link = PDAnnotationLink()
    action = PDActionGoTo()
    action.get_cos_object().set_item(_D, COSName.get_pdf_name("target"))
    link.set_action(action)
    src.get_page(0).set_annotations([link])

    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    try:
        cloned = chunks[0].get_page(0).get_annotations()[0]
        cloned_action = cloned.get_action()
        assert isinstance(cloned_action, PDActionGoTo)
        dest = cloned_action.get_destination()
        assert isinstance(dest, PDNamedDestination)
        assert dest.get_named_destination() == "target"
    finally:
        _close(*chunks, src)


def test_named_dest_link_kept_even_when_target_in_other_chunk() -> None:
    """The link keeps its name; the name tree entry only lands in the chunk
    owning the target page, so the name doesn't resolve in the link's
    chunk (upstream behavior)."""
    src = _make_doc(2)
    _set_name_tree(src, {"target": _fit_dest(src.get_page(1))})
    _add_link(src.get_page(0), COSString("target"))

    chunks = Splitter().split(src)
    try:
        assert len(chunks) == 2
        dest = chunks[0].get_page(0).get_annotations()[0].get_destination()
        assert isinstance(dest, PDNamedDestination)
        assert dest.get_named_destination() == "target"
        assert chunks[0].get_document_catalog().get_names() is None
        tree = chunks[1].get_document_catalog().get_names().get_dests()
        assert tree.get_value("target").get_page() is (
            chunks[1].get_page(0).get_cos_object()
        )
    finally:
        _close(*chunks, src)


def test_name_tree_survives_save_and_reload() -> None:
    src = _make_doc(2)
    _set_name_tree(src, {"a": _fit_dest(src.get_page(0))})
    _add_link(src.get_page(1), COSString("a"))
    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    try:
        buf = io.BytesIO()
        chunks[0].save(buf)
        with PDDocument.load(buf.getvalue()) as reloaded:
            tree = reloaded.get_document_catalog().get_names().get_dests()
            dest = tree.get_value("a")
            assert isinstance(dest, PDPageDestination)
            assert reloaded.get_pages().index_of(dest.get_page()) == 0
            link = reloaded.get_page(1).get_annotations()[0]
            assert link.get_destination().get_named_destination() == "a"
    finally:
        _close(*chunks, src)


# ---------- /Names /Dests name tree ----------


def test_name_tree_entries_outside_split_are_dropped() -> None:
    src = _make_doc(3)
    _set_name_tree(
        src,
        {
            "p0": _fit_dest(src.get_page(0)),
            "p1": _fit_dest(src.get_page(1)),
            "p2": _fit_dest(src.get_page(2)),
        },
    )
    splitter = Splitter()
    splitter.set_start_page(2)
    splitter.set_end_page(2)
    chunks = splitter.split(src)
    try:
        assert len(chunks) == 1
        names = chunks[0].get_document_catalog().get_names().get_dests().get_names()
        assert list(names) == ["p1"]
        assert names["p1"].get_page() is chunks[0].get_page(0).get_cos_object()
    finally:
        _close(*chunks, src)


def test_no_names_dict_when_no_entry_targets_the_chunk() -> None:
    src = _make_doc(3)
    _set_name_tree(src, {"p0": _fit_dest(src.get_page(0))})
    splitter = Splitter()
    splitter.set_start_page(2)
    chunks = splitter.split(src)
    try:
        assert len(chunks) == 2
        for chunk in chunks:
            assert chunk.get_document_catalog().get_names() is None
    finally:
        _close(*chunks, src)


def test_multi_level_name_tree_is_flattened_per_chunk() -> None:
    src = _make_doc(2)
    names = PDDocumentNameDictionary(src.get_document_catalog())
    root = PDDestinationNameTreeNode()
    kid_a = PDDestinationNameTreeNode()
    kid_a.set_names({"a": _fit_dest(src.get_page(0))})
    kid_b = PDDestinationNameTreeNode()
    kid_b.set_names(
        {"b": _fit_dest(src.get_page(1)), "c": _fit_dest(src.get_page(0))}
    )
    root.set_kids([kid_a, kid_b])
    names.set_dests(root)
    src.get_document_catalog().set_names(names)

    chunks = Splitter().split(src)
    try:
        first = chunks[0].get_document_catalog().get_names().get_dests()
        assert sorted(first.get_names()) == ["a", "c"]
        second = chunks[1].get_document_catalog().get_names().get_dests()
        assert sorted(second.get_names()) == ["b"]
    finally:
        _close(*chunks, src)


def test_broken_name_tree_value_is_skipped() -> None:
    src = _make_doc(1)
    tree_dict = COSDictionary()
    arr = COSArray()
    arr.add(COSString("bogus"))
    arr.add(COSString("not a destination"))
    arr.add(COSString("good"))
    arr.add(_fit_dest(src.get_page(0)).get_cos_object())
    tree_dict.set_item(_NAMES, arr)
    names = PDDocumentNameDictionary(src.get_document_catalog())
    names.set_dests(PDDestinationNameTreeNode(tree_dict))
    src.get_document_catalog().set_names(names)

    chunks = Splitter().split(src)
    try:
        dests = chunks[0].get_document_catalog().get_names().get_dests().get_names()
        assert list(dests) == ["good"]
    finally:
        _close(*chunks, src)


def test_xyz_destination_parameters_preserved() -> None:
    from pypdfbox.cos import COSInteger

    src = _make_doc(1)
    xyz = COSArray()
    xyz.add(src.get_page(0).get_cos_object())
    xyz.add(COSName.get_pdf_name("XYZ"))
    xyz.add(COSInteger.get(10))
    xyz.add(COSInteger.get(20))
    xyz.add(COSInteger.get(0))
    tree = PDDestinationNameTreeNode()
    tree_dict = tree.get_cos_object()
    names_arr = COSArray()
    names_arr.add(COSString("x"))
    names_arr.add(xyz)
    tree_dict.set_item(_NAMES, names_arr)
    names = PDDocumentNameDictionary(src.get_document_catalog())
    names.set_dests(tree)
    src.get_document_catalog().set_names(names)

    chunks = Splitter().split(src)
    try:
        dest = chunks[0].get_document_catalog().get_names().get_dests().get_value("x")
        arr = dest.get_cos_object()
        assert arr.size() == 5
        assert arr.get_object(0) is chunks[0].get_page(0).get_cos_object()
        assert arr.get_object(1) == COSName.get_pdf_name("XYZ")
        assert arr.get_int(2) == 10
        assert arr.get_int(3) == 20
        # source array untouched
        assert xyz.get_object(0) is src.get_page(0).get_cos_object()
    finally:
        _close(*chunks, src)


# ---------- legacy /Root/Dests ----------


def _set_root_dests(doc: PDDocument, entries: dict) -> COSDictionary:
    dests = COSDictionary()
    for key, value in entries.items():
        dests.set_item(COSName.get_pdf_name(key), value)
    doc.get_document_catalog().get_cos_object().set_item(_DESTS, dests)
    return dests


def test_root_dests_page_entries_go_to_owning_chunk() -> None:
    src = _make_doc(3)
    _set_root_dests(
        src,
        {
            "d0": _fit_dest(src.get_page(0)).get_cos_object(),
            "d2": _fit_dest(src.get_page(2)).get_cos_object(),
        },
    )
    chunks = Splitter().split(src)
    try:
        d0 = chunks[0].get_document_catalog().get_dests()
        assert d0.get_names() == ["d0"]
        assert d0.get_destination("d0").get_page() is (
            chunks[0].get_page(0).get_cos_object()
        )
        assert chunks[1].get_document_catalog().get_dests() is None
        d2 = chunks[2].get_document_catalog().get_dests()
        assert d2.get_names() == ["d2"]
        assert d2.get_destination("d2").get_page() is (
            chunks[2].get_page(0).get_cos_object()
        )
    finally:
        _close(*chunks, src)


def test_root_dests_dictionary_form_is_resolved() -> None:
    """A ``{/D [page /Fit]}`` value is cloned as the bare destination
    array (upstream sets the cloned PDPageDestination)."""
    src = _make_doc(1)
    wrapper = COSDictionary()
    wrapper.set_item(_D, _fit_dest(src.get_page(0)).get_cos_object())
    _set_root_dests(src, {"wrapped": wrapper})
    chunks = Splitter().split(src)
    try:
        dests = chunks[0].get_document_catalog().get_dests()
        value = dests.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("wrapped")
        )
        assert isinstance(value, COSArray)
        assert value.get_object(0) is chunks[0].get_page(0).get_cos_object()
        assert value.get_object(1) == _FIT
    finally:
        _close(*chunks, src)


def test_root_dests_non_page_destination_added_to_every_chunk() -> None:
    src = _make_doc(2)
    wrapper = COSDictionary()
    wrapper.set_item(_D, COSName.get_pdf_name("elsewhere"))
    _set_root_dests(src, {"alias": wrapper})
    chunks = Splitter().split(src)
    try:
        assert len(chunks) == 2
        for chunk in chunks:
            dests = chunk.get_document_catalog().get_dests()
            assert dests is not None
            # upstream stores the destination's COS object (here the bare
            # name the /D entry held), not the original {/D ...} wrapper
            value = dests.get_cos_object().get_dictionary_object(
                COSName.get_pdf_name("alias")
            )
            assert value == COSName.get_pdf_name("elsewhere")
    finally:
        _close(*chunks, src)


def test_root_dests_entries_outside_split_and_unresolvable_dropped() -> None:
    src = _make_doc(3)
    _set_root_dests(
        src,
        {
            "d0": _fit_dest(src.get_page(0)).get_cos_object(),
            "junk": COSString("not a destination"),
        },
    )
    splitter = Splitter()
    splitter.set_start_page(2)
    chunks = splitter.split(src)
    try:
        for chunk in chunks:
            assert chunk.get_document_catalog().get_dests() is None
    finally:
        _close(*chunks, src)


def test_empty_root_dests_not_copied() -> None:
    src = _make_doc(1)
    _set_root_dests(src, {})
    chunks = Splitter().split(src)
    try:
        assert chunks[0].get_document_catalog().get_dests() is None
    finally:
        _close(*chunks, src)


def test_name_tree_and_root_dests_both_rebuilt() -> None:
    src = _make_doc(1)
    _set_name_tree(src, {"tree": _fit_dest(src.get_page(0))})
    _set_root_dests(src, {"legacy": _fit_dest(src.get_page(0)).get_cos_object()})
    chunks = Splitter().split(src)
    try:
        catalog = chunks[0].get_document_catalog()
        assert list(catalog.get_names().get_dests().get_names()) == ["tree"]
        assert catalog.get_dests().get_names() == ["legacy"]
    finally:
        _close(*chunks, src)


# ---------- broken-string fallback ----------


def test_broken_string_named_dest_resolved_to_page_destination() -> None:
    """A name containing NUL after decoding (0xAD is undefined in
    PDFDocEncoding and decodes to U+0000) is replaced by the actual
    destination, retargeted at the chunk page."""
    src = _make_doc(2)
    broken = COSString(b"a\xadb")
    assert "\x00" in broken.get_string()
    tree_dict = COSDictionary()
    arr = COSArray()
    arr.add(broken)
    arr.add(_fit_dest(src.get_page(1)).get_cos_object())
    tree_dict.set_item(_NAMES, arr)
    names = PDDocumentNameDictionary(src.get_document_catalog())
    names.set_dests(PDDestinationNameTreeNode(tree_dict))
    src.get_document_catalog().set_names(names)
    _add_link(src.get_page(0), COSString(b"a\xadb"))

    splitter = Splitter()
    splitter.set_split_at_page(2)
    chunks = splitter.split(src)
    try:
        chunk = chunks[0]
        dest = chunk.get_page(0).get_annotations()[0].get_destination()
        assert isinstance(dest, PDPageFitDestination)
        assert dest.get_page() is chunk.get_page(1).get_cos_object()
        # source link untouched
        src_dest = src.get_page(0).get_annotations()[0].get_destination()
        assert isinstance(src_dest, PDNamedDestination)
    finally:
        _close(*chunks, src)


def test_broken_string_named_dest_cross_chunk_is_nulled() -> None:
    from pypdfbox.cos import COSNull

    src = _make_doc(2)
    _set_root_dests(src, {"x": _fit_dest(src.get_page(1)).get_cos_object()})
    # the legacy /Dests key is a name; a broken *string* reference to it
    # still resolves through find_named_destination_page's NUL-decoded name
    src.get_document_catalog().get_cos_object().get_dictionary_object(
        _DESTS
    ).set_item(COSName.get_pdf_name("a\x00b"), _fit_dest(src.get_page(1)).get_cos_object())
    _add_link(src.get_page(0), COSString(b"a\xadb"))

    chunks = Splitter().split(src)
    try:
        dest = chunks[0].get_page(0).get_annotations()[0].get_destination()
        assert isinstance(dest, PDPageDestination)
        assert dest.get_cos_object().get_object(0) in (None, COSNull.NULL)
    finally:
        _close(*chunks, src)


def test_unresolvable_broken_string_keeps_original_name() -> None:
    src = _make_doc(1)
    _add_link(src.get_page(0), COSString(b"missing\xad"))
    chunks = Splitter().split(src)
    try:
        dest = chunks[0].get_page(0).get_annotations()[0].get_destination()
        assert isinstance(dest, PDNamedDestination)
        assert dest.get_named_destination() == "missing\x00"
    finally:
        _close(*chunks, src)
