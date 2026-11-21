"""Ported ``PDFMergerUtilityTest.testMappingXObjects`` (PDFBOX-6301) plus the
``checkWithNumberTree`` / ``checkMarkedContents`` helpers in their trunk form.

Upstream reads ``PDFBOX-6301-octopdf-sample.pdf``, which ``pom.xml`` downloads
from the JIRA attachment at build time; it is not a repository resource. The
fixture is rebuilt here programmatically with the same shape the assertions
rely on: page 1 has ``/StructParents 1`` and form XObjects ``R8``
(``/StructParents 0``) and ``R9`` (``/StructParents 2``), ``R9`` nests ``R10``
(``/StructParents 3``), page 2 has ``/StructParents 13``, and the
``/ParentTree`` holds 16 entries (``/ParentTreeNextKey 16``). The extra keys
are filled by an image XObject, link annotations and padding elements.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.io.io_utils import IOUtils
from pypdfbox.multipdf import PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.documentinterchange.logicalstructure import (
    PDStructureElementNumberTreeNode,
    PDStructureTreeRoot,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_marked_content_reference import (
    PDMarkedContentReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_object_reference import (
    PDObjectReference,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_node import (
    PDStructureNode,
)
from pypdfbox.pdmodel.documentinterchange.markedcontent.pd_marked_content import (
    PDMarkedContent,
)
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_page_tree import PDPageTree
from pypdfbox.text.pdf_marked_content_extractor import PDFMarkedContentExtractor

_N = COSName.get_pdf_name


def _stream(data: bytes, entries: dict[str, object] | None = None) -> COSStream:
    stream = COSStream()
    for key, value in (entries or {}).items():
        stream.set_item(_N(key), value)  # type: ignore[arg-type]
    stream.set_data(data)
    return stream


def _form(content: bytes, struct_parents: int, resources: COSDictionary | None) -> COSStream:
    form = _stream(
        content,
        {
            "Type": _N("XObject"),
            "Subtype": _N("Form"),
            "BBox": _bbox(),
            "StructParents": COSInteger.get(struct_parents),
        },
    )
    if resources is not None:
        form.set_item(_N("Resources"), resources)
    return form


def _bbox() -> COSArray:
    arr = COSArray()
    for v in (0, 0, 612, 792):
        arr.add(COSInteger.get(v))
    return arr


def _xobjects(**entries: COSStream) -> COSDictionary:
    xobj = COSDictionary()
    for name, stream in entries.items():
        xobj.set_item(_N(name), stream)
    res = COSDictionary()
    res.set_item(_N("XObject"), xobj)
    return res


def _elem(s: str, parent: COSDictionary, page: COSDictionary | None) -> COSDictionary:
    elem = COSDictionary()
    elem.set_item(_N("Type"), _N("StructElem"))
    elem.set_item(_N("S"), _N(s))
    elem.set_item(_N("P"), parent)
    if page is not None:
        elem.set_item(_N("Pg"), page)
    return elem


def _mcr(mcid: int, page: COSDictionary, stm: COSStream) -> COSDictionary:
    mcr = COSDictionary()
    mcr.set_item(_N("Type"), _N("MCR"))
    mcr.set_item(_N("MCID"), COSInteger.get(mcid))
    mcr.set_item(_N("Pg"), page)
    mcr.set_item(_N("Stm"), stm)
    return mcr


def _objr(obj: COSDictionary, page: COSDictionary) -> COSDictionary:
    objr = COSDictionary()
    objr.set_item(_N("Type"), _N("OBJR"))
    objr.set_item(_N("Obj"), obj)
    objr.set_item(_N("Pg"), page)
    return objr


def _link(struct_parent: int) -> COSDictionary:
    annot = COSDictionary()
    annot.set_item(_N("Type"), _N("Annot"))
    annot.set_item(_N("Subtype"), _N("Link"))
    rect = COSArray()
    for v in (10, 10, 50, 50):
        rect.add(COSInteger.get(v))
    annot.set_item(_N("Rect"), rect)
    annot.set_item(_N("StructParent"), COSInteger.get(struct_parent))
    return annot


def _one(elem: COSDictionary) -> COSArray:
    arr = COSArray()
    arr.add(elem)
    return arr


def build_octopdf_like_sample() -> bytes:
    """Build the stand-in for ``PDFBOX-6301-octopdf-sample.pdf``."""
    doc = PDDocument()
    try:
        page1 = PDPage()
        page2 = PDPage()
        doc.add_page(page1)
        doc.add_page(page2)
        p1 = page1.get_cos_object()
        p2 = page2.get_cos_object()
        mc = b"/P <</MCID 0>> BDC 0 0 m 1 1 l S EMC\n"

        r10 = _form(mc, 3, None)
        r9 = _form(mc + b"/R10 Do\n", 2, _xobjects(R10=r10))
        r8 = _form(mc, 0, None)
        image = _stream(
            b"\x00",
            {
                "Type": _N("XObject"),
                "Subtype": _N("Image"),
                "Width": COSInteger.get(1),
                "Height": COSInteger.get(1),
                "BitsPerComponent": COSInteger.get(8),
                "ColorSpace": _N("DeviceGray"),
                "StructParent": COSInteger.get(4),
            },
        )
        res1 = _xobjects(R8=r8, R9=r9, Im1=image)
        page1.get_cos_object().set_item(_N("Resources"), res1)
        p1.set_item(_N("StructParents"), COSInteger.get(1))
        p1.set_item(
            _N("Contents"),
            _stream(mc + b"/R8 Do /R9 Do /Im1 Do\n"),
        )

        res2 = _xobjects(R8=r8)  # shared form XObject: offset only once
        p2.set_item(_N("Resources"), res2)
        p2.set_item(_N("StructParents"), COSInteger.get(13))
        p2.set_item(_N("Contents"), _stream(mc + b"/R8 Do\n"))

        root = PDStructureTreeRoot()
        root_cos = root.get_cos_object()
        document = _elem("Document", root_cos, None)
        kids = COSArray()
        tree: dict[int, COSDictionary | COSArray] = {}

        e_page1 = _elem("P", document, p1)
        e_page1.set_item(_N("K"), COSInteger.get(0))
        tree[1] = _one(e_page1)
        e_r8 = _elem("P", document, p1)
        e_r8_k = COSArray()
        e_r8_k.add(_mcr(0, p1, r8))
        e_r8_k.add(_mcr(0, p2, r8))
        e_r8.set_item(_N("K"), e_r8_k)
        tree[0] = _one(e_r8)
        e_r9 = _elem("P", document, p1)
        e_r9.set_item(_N("K"), _mcr(0, p1, r9))
        tree[2] = _one(e_r9)
        e_r10 = _elem("P", document, p1)
        e_r10.set_item(_N("K"), _mcr(0, p1, r10))
        tree[3] = _one(e_r10)
        e_fig = _elem("Figure", document, p1)
        e_fig.set_item(_N("K"), _objr(image, p1))
        tree[4] = e_fig
        e_page2 = _elem("P", document, p2)
        e_page2.set_item(_N("K"), COSInteger.get(0))
        tree[13] = _one(e_page2)

        annots1 = COSArray()
        annots2 = COSArray()
        for key in (5, 6, 7, 8, 9, 10, 11, 12, 14, 15):
            annot = _link(key)
            page_dict = p1 if key < 13 else p2
            (annots1 if key < 13 else annots2).add(annot)
            annot.set_item(_N("P"), page_dict)
            e_link = _elem("Link", document, page_dict)
            e_link.set_item(_N("K"), _objr(annot, page_dict))
            tree[key] = e_link
        p1.set_item(_N("Annots"), annots1)
        p2.set_item(_N("Annots"), annots2)

        for key in sorted(tree):
            value = tree[key]
            kids.add(value.get_object(0) if isinstance(value, COSArray) else value)
        document.set_item(_N("K"), kids)
        root_cos.set_item(_N("K"), document)

        parent_tree = PDStructureElementNumberTreeNode()
        nums = COSArray()
        for key in sorted(tree):
            nums.add(COSInteger.get(key))
            nums.add(tree[key])
        parent_tree.get_cos_object().set_item(_N("Nums"), nums)
        root.set_parent_tree(parent_tree)
        root.set_parent_tree_next_key(16)
        doc.get_document_catalog().set_struct_tree_root(root)

        out = io.BytesIO()
        doc.save(out)
        return out.getvalue()
    finally:
        doc.close()


def _same(a: object, b: object) -> bool:
    if a is None or b is None:
        return a is b
    return a.get_cos_object() is b.get_cos_object()  # type: ignore[attr-defined]


def check_with_number_tree(document: PDDocument) -> None:
    """Port of upstream ``checkWithNumberTree`` (trunk version)."""
    catalog = document.get_document_catalog()
    struct_root = catalog.get_struct_tree_root()
    assert struct_root.get_parent_tree_next_key() != -1
    number_tree_as_map = struct_root.get_parent_tree().get_tree_as_map()
    key_set = set(number_tree_as_map)
    acro_form = catalog.get_acro_form()
    if acro_form is not None:
        for field in acro_form.get_field_tree():
            for widget in field.get_widgets():
                if widget.get_struct_parent() >= 0:
                    assert widget.get_struct_parent() in key_set
    page_tree = document.get_pages()
    for page in page_tree:
        page_struct_parent = page.get_struct_parents()
        page_num = page_tree.index_of(page) + 1
        if page_struct_parent < 0:
            continue
        assert page_struct_parent in key_set, (
            f"/StructParents {page_struct_parent} from page {page_num} "
            "not found in /ParentTree"
        )
        extractor = PDFMarkedContentExtractor()
        extractor.process_page(page)
        for marked_content in extractor.get_marked_contents():
            _check_marked_contents(
                marked_content,
                number_tree_as_map,
                page_num,
                page_struct_parent,
                page_tree,
                page,
            )
        for ann in page.get_annotations():
            struct_parent = ann.get_struct_parent()
            if struct_parent < 0:
                continue
            assert struct_parent in key_set
            obj = number_tree_as_map[struct_parent]
            element = PDStructureElement(obj.get_cos_object())
            found = False
            for kid in element.get_kids():
                if isinstance(kid, PDObjectReference):
                    assert _same(ann, kid.get_referenced_object())
                    if kid.get_page() is not None:
                        assert _same(page, kid.get_page())
                    found = True
            assert found, (
                f"/StructureTree entry {struct_parent} for page {page_num} "
                "doesn't have expected page and annotation"
            )


def _check_marked_contents(
    marked_content: PDMarkedContent,
    number_tree_as_map: dict,
    page_num: int,
    page_struct_parent: int,
    page_tree: PDPageTree,
    page: PDPage,
) -> None:
    for content in marked_content.get_contents():
        if isinstance(content, PDMarkedContent):
            _check_marked_contents(
                content,
                number_tree_as_map,
                page_num,
                page_struct_parent,
                page_tree,
                page,
            )
    struct_parent = marked_content.get_struct_parent()
    mcid = marked_content.get_mcid()
    if mcid < 0 or struct_parent < 0:
        return
    obj = number_tree_as_map[struct_parent]
    array = obj.get_cos_object()
    assert isinstance(array, COSArray), f"Expected array in page {page_num}"
    assert mcid < array.size()
    elem_dict = array.get_object(mcid)
    assert elem_dict is not None
    element = PDStructureNode.create(elem_dict)
    assert isinstance(element, PDStructureElement)
    # MCIDs are only unique per content stream: content with the page's
    # /StructParents key is page content, anything else is form content.
    is_page_content = struct_parent == page_struct_parent
    found = False
    for kid in element.get_kids():
        if isinstance(kid, int):
            if is_page_content and kid == mcid:
                found = True
                assert _same(page, element.get_page()), (
                    f"mcid {mcid} of page {page_num} references another page"
                )
                break
        elif isinstance(kid, PDMarkedContentReference):
            stm = kid.get_cos_object().get_cos_stream(COSName.STM)  # type: ignore[attr-defined]
            mcr_is_page_content = stm is None
            if mcid == kid.get_mcid() and is_page_content == mcr_is_page_content:
                actual_page = (
                    kid.get_page() if kid.get_page() is not None else element.get_page()
                )
                if not _same(page, actual_page):
                    # Upstream breaks on the first matching MCR; our fixture
                    # puts one MCR per page for the shared R8 form.
                    continue
                found = True
                if not mcr_is_page_content:
                    form = PDFormXObject(stm)
                    assert form.get_struct_parents() == struct_parent, (
                        f"MCR /Stm form for MCID {mcid} on page {page_num} "
                        "has a different /StructParents"
                    )
                break
    assert found, (
        f"page: {page_num}, mcid: {mcid}, expected "
        f"{'page' if is_page_content else 'form'} content kid not found in "
        f"/ParentTree entry for StructParent {struct_parent}"
    )


def test_mapping_x_objects(tmp_path: Path) -> None:
    """``testMappingXObjects`` / PDFBOX-6301: form XObjects are mapped."""
    sample = tmp_path / "PDFBOX-6301-octopdf-sample.pdf"
    sample.write_bytes(build_octopdf_like_sample())
    with PDDocument.load(sample) as doc:
        check_with_number_tree(doc)
    merged = tmp_path / "PDFBOX-6301-octopdf-sample-merged3.pdf"
    merger = PDFMergerUtility()
    merger.add_source(str(sample))
    merger.add_source(str(sample))
    merger.set_destination_file_name(str(merged))
    merger.merge_documents(IOUtils.create_memory_only_stream_cache())

    with PDDocument.load(merged) as doc:
        struct_root = doc.get_document_catalog().get_struct_tree_root()
        parent_tree_next_key = struct_root.get_parent_tree_next_key()
        key_set = set(struct_root.get_parent_tree().get_tree_as_map())
        assert len(key_set) == 16 * 2  # original file has 16 elements
        assert parent_tree_next_key == 16 * 2
        check_with_number_tree(doc)
        page1 = doc.get_page(0)
        page2 = doc.get_page(1)
        page3 = doc.get_page(2)
        page4 = doc.get_page(3)
        assert page1.get_struct_parents() == 1
        assert page2.get_struct_parents() == 13
        half = parent_tree_next_key // 2
        assert page3.get_struct_parents() == page1.get_struct_parents() + half
        assert page4.get_struct_parents() == page2.get_struct_parents() + half

        def form(page: PDPage, name: str) -> PDFormXObject:
            xobject = page.get_resources().get_x_object(_N(name))
            assert isinstance(xobject, PDFormXObject)
            return xobject

        r8 = form(page1, "R8")
        r9 = form(page1, "R9")
        r10 = r9.get_resources().get_x_object(_N("R10"))
        assert isinstance(r10, PDFormXObject)
        for xobject in (r8, r9, r10):
            assert xobject.get_struct_parents() in key_set
        assert r8.get_struct_parents() == 0
        assert r9.get_struct_parents() == 2
        assert r10.get_struct_parents() == 3
        r8b = form(page3, "R8")
        r9b = form(page3, "R9")
        r10b = r9b.get_resources().get_x_object(_N("R10"))
        assert isinstance(r10b, PDFormXObject)
        assert r8b.get_struct_parents() == r8.get_struct_parents() + half
        assert r9b.get_struct_parents() == r9.get_struct_parents() + half
        assert r10b.get_struct_parents() == r10.get_struct_parents() + half
        for xobject in (r8b, r9b, r10b):
            assert xobject.get_struct_parents() in key_set
