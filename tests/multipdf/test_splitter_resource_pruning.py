"""Hand-written tests for the splitter's unused-resource pruning.

pypdfbox divergence from upstream (see CHANGES.md): ``Splitter`` rebuilds
each imported page's ``/Resources`` so a chunk carries only the entries
its content actually references. Upstream copies the page's — possibly
inherited, document-wide — resource dictionary wholesale, which makes a
one-page split of a shared-resources document as heavy as the source.
"""
from __future__ import annotations

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.multipdf import Splitter

_RESOURCES = COSName.get_pdf_name("Resources")
_FONT = COSName.get_pdf_name("Font")
_XOBJECT = COSName.get_pdf_name("XObject")
_PROC_SET = COSName.get_pdf_name("ProcSet")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_ANNOTS = COSName.get_pdf_name("Annots")
_AP = COSName.get_pdf_name("AP")


def _content_stream(payload: bytes) -> COSStream:
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        out.write(payload)
    return stream


def _font_dict(name: str) -> COSDictionary:
    font = COSDictionary()
    font.set_item(COSName.get_pdf_name("Type"), _FONT)
    font.set_item(_SUBTYPE, COSName.get_pdf_name("Type1"))
    font.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name(name)
    )
    return font


def _image_xobject() -> COSStream:
    image = COSStream()
    image.set_item(COSName.get_pdf_name("Type"), _XOBJECT)
    image.set_item(_SUBTYPE, COSName.get_pdf_name("Image"))
    image.set_item(COSName.get_pdf_name("Width"), COSName.get_pdf_name("1"))
    with image.create_raw_output_stream() as out:
        out.write(b"\x00")
    return image


def _shared_resources() -> COSDictionary:
    """A document-wide resource pool: two fonts, two images, a ProcSet."""
    fonts = COSDictionary()
    fonts.set_item(COSName.get_pdf_name("F1"), _font_dict("Helvetica"))
    fonts.set_item(COSName.get_pdf_name("F2"), _font_dict("Courier"))
    xobjects = COSDictionary()
    xobjects.set_item(COSName.get_pdf_name("Im0"), _image_xobject())
    xobjects.set_item(COSName.get_pdf_name("Im1"), _image_xobject())
    proc_set = COSArray()
    proc_set.add(COSName.get_pdf_name("PDF"))
    resources = COSDictionary()
    resources.set_item(_FONT, fonts)
    resources.set_item(_XOBJECT, xobjects)
    resources.set_item(_PROC_SET, proc_set)
    return resources


def _resource_names(page_dict: COSDictionary, category: COSName) -> set[str]:
    res = page_dict.get_dictionary_object(_RESOURCES)
    assert isinstance(res, COSDictionary)
    sub = res.get_dictionary_object(category)
    if not isinstance(sub, COSDictionary):
        return set()
    return {k.get_name() for k in sub.key_set()}


# ---------- inherited (page-tree level) resources ----------


def test_inherited_resources_pruned_to_page_usage() -> None:
    """Pages inherit a shared /Resources from the page-tree node; each
    chunk keeps only what its page draws."""
    resources = _shared_resources()
    src = PDDocument()
    page1 = PDPage()
    page1.set_contents(_content_stream(b"q /Im0 Do Q BT /F1 9 Tf (a) Tj ET"))
    page2 = PDPage()
    page2.set_contents(_content_stream(b"q /Im1 Do Q"))
    src.add_page(page1)
    src.add_page(page2)
    # Hoist the resources to the /Pages tree node (inheritable attribute).
    pages_root = page1.get_cos_parent()
    assert pages_root is not None
    pages_root.set_item(_RESOURCES, resources)
    assert not page1.get_cos_object().contains_key(_RESOURCES)

    chunks = Splitter().split(src)
    assert len(chunks) == 2

    chunk1_dict = chunks[0].get_page(0).get_cos_object()
    assert _resource_names(chunk1_dict, _XOBJECT) == {"Im0"}
    assert _resource_names(chunk1_dict, _FONT) == {"F1"}
    chunk2_dict = chunks[1].get_page(0).get_cos_object()
    assert _resource_names(chunk2_dict, _XOBJECT) == {"Im1"}
    assert _resource_names(chunk2_dict, _FONT) == set()

    # /ProcSet is not name-keyed — kept wholesale.
    chunk1_res = chunk1_dict.get_dictionary_object(_RESOURCES)
    assert isinstance(
        chunk1_res.get_dictionary_object(_PROC_SET), COSArray
    )

    # The source document's shared dictionary is never mutated.
    src_fonts = resources.get_dictionary_object(_FONT)
    assert {k.get_name() for k in src_fonts.key_set()} == {"F1", "F2"}
    src_xobjects = resources.get_dictionary_object(_XOBJECT)
    assert {k.get_name() for k in src_xobjects.key_set()} == {"Im0", "Im1"}

    for chunk in chunks:
        chunk.close()
    src.close()


# ---------- direct page-level resources ----------


def test_direct_page_resources_pruned() -> None:
    src = PDDocument()
    page = PDPage()
    page.get_cos_object().set_item(_RESOURCES, _shared_resources())
    page.set_contents(_content_stream(b"BT /F2 9 Tf (b) Tj ET"))
    src.add_page(page)

    chunks = Splitter().split(src)
    chunk_dict = chunks[0].get_page(0).get_cos_object()
    assert _resource_names(chunk_dict, _FONT) == {"F2"}
    assert _resource_names(chunk_dict, _XOBJECT) == set()
    chunks[0].close()
    src.close()


# ---------- form XObject recursion ----------


def test_form_xobject_dependencies_survive_pruning() -> None:
    """A form XObject without its own /Resources resolves names against
    the page dictionary — its references must be treated as used."""
    resources = _shared_resources()
    form = COSStream()
    form.set_item(COSName.get_pdf_name("Type"), _XOBJECT)
    form.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    with form.create_raw_output_stream() as out:
        out.write(b"q /Im1 Do Q BT /F2 7 Tf (nested) Tj ET")
    resources.get_dictionary_object(_XOBJECT).set_item(
        COSName.get_pdf_name("Fm0"), form
    )

    src = PDDocument()
    page = PDPage()
    page.get_cos_object().set_item(_RESOURCES, resources)
    page.set_contents(_content_stream(b"q /Fm0 Do Q"))
    src.add_page(page)

    chunks = Splitter().split(src)
    chunk_dict = chunks[0].get_page(0).get_cos_object()
    assert _resource_names(chunk_dict, _XOBJECT) == {"Fm0", "Im1"}
    assert _resource_names(chunk_dict, _FONT) == {"F2"}
    chunks[0].close()
    src.close()


# ---------- annotation appearance streams ----------


def test_appearance_stream_without_resources_keeps_page_entries() -> None:
    """An /AP stream lacking its own /Resources falls back to the page's
    dictionary in real-world viewers — its names count as used."""
    ap_stream = COSStream()
    ap_stream.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    with ap_stream.create_raw_output_stream() as out:
        out.write(b"BT /F2 5 Tf (ap) Tj ET")
    ap = COSDictionary()
    ap.set_item(COSName.get_pdf_name("N"), ap_stream)
    annot = COSDictionary()
    annot.set_item(_SUBTYPE, COSName.get_pdf_name("Text"))
    annot.set_item(_AP, ap)
    annots = COSArray()
    annots.add(annot)

    src = PDDocument()
    page = PDPage()
    page.get_cos_object().set_item(_RESOURCES, _shared_resources())
    page.get_cos_object().set_item(_ANNOTS, annots)
    page.set_contents(_content_stream(b"BT /F1 9 Tf (body) Tj ET"))
    src.add_page(page)

    chunks = Splitter().split(src)
    chunk_dict = chunks[0].get_page(0).get_cos_object()
    assert _resource_names(chunk_dict, _FONT) == {"F1", "F2"}
    chunks[0].close()
    src.close()


# ---------- blank page ----------


def test_blank_page_keeps_only_non_prunable_categories() -> None:
    """A page with no content references nothing — every name-keyed
    category empties out (and is dropped); /ProcSet survives."""
    src = PDDocument()
    page = PDPage()
    page.get_cos_object().set_item(_RESOURCES, _shared_resources())
    src.add_page(page)

    chunks = Splitter().split(src)
    chunk_dict = chunks[0].get_page(0).get_cos_object()
    res = chunk_dict.get_dictionary_object(_RESOURCES)
    assert isinstance(res, COSDictionary)
    assert not res.contains_key(_FONT)
    assert not res.contains_key(_XOBJECT)
    assert isinstance(res.get_dictionary_object(_PROC_SET), COSArray)
    chunks[0].close()
    src.close()
