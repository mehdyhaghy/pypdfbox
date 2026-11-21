"""PDFBOX-6301 (XObject /StructParent(s) offsets in merge) and PDFBOX-6298
(stream-cache function on input) regression tests."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSStream
from pypdfbox.io.io_utils import IOUtils
from pypdfbox.multipdf import DocumentMergeMode, PDFMergerUtility
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_resources import PDResources

from .upstream.test_pdf_merger_utility_xobject_mapping import (
    build_octopdf_like_sample,
    check_with_number_tree,
)

_N = COSName.get_pdf_name


def _merge_twice(tmp_path: Path, data: bytes) -> Path:
    src = tmp_path / "src.pdf"
    src.write_bytes(data)
    out = tmp_path / "merged.pdf"
    merger = PDFMergerUtility()
    merger.add_source(str(src))
    merger.add_source(str(src))
    merger.set_destination_file_name(str(out))
    merger.merge_documents()
    return out


def test_image_struct_parent_offset_and_objr_follows_clone(tmp_path: Path) -> None:
    out = _merge_twice(tmp_path, build_octopdf_like_sample())
    with PDDocument.load(out) as doc:
        im1 = doc.get_page(0).get_resources().get_x_object(_N("Im1"))
        im1b = doc.get_page(2).get_resources().get_x_object(_N("Im1"))
        assert isinstance(im1, PDImageXObject)
        assert isinstance(im1b, PDImageXObject)
        assert im1.get_struct_parent() == 4
        assert im1b.get_struct_parent() == 4 + 16
        tree = (
            doc.get_document_catalog()
            .get_struct_tree_root()
            .get_parent_tree()
            .get_tree_as_map()
        )
        figure = tree[20].get_cos_object()
        objr = figure.get_dictionary_object(_N("K"))
        assert objr.get_dictionary_object(_N("Obj")) is im1b.get_cos_object()


def test_shared_form_is_offset_once(tmp_path: Path) -> None:
    out = _merge_twice(tmp_path, build_octopdf_like_sample())
    with PDDocument.load(out) as doc:
        r8_p3 = doc.get_page(2).get_resources().get_x_object(_N("R8"))
        r8_p4 = doc.get_page(3).get_resources().get_x_object(_N("R8"))
        assert isinstance(r8_p3, PDFormXObject)
        assert r8_p3.get_cos_object() is r8_p4.get_cos_object()
        assert r8_p3.get_struct_parents() == 16


def test_untagged_merge_leaves_x_objects_alone(tmp_path: Path) -> None:
    src = tmp_path / "src.pdf"
    src.write_bytes(build_octopdf_like_sample())
    out = tmp_path / "merged.pdf"
    merger = PDFMergerUtility()
    merger.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    merger.add_source(str(src))
    merger.add_source(str(src))
    merger.set_destination_file_name(str(out))
    merger.merge_documents()
    with PDDocument.load(out) as doc:
        r9 = doc.get_page(2).get_resources().get_x_object(_N("R9"))
        assert isinstance(r9, PDFormXObject)
        assert r9.get_struct_parents() == 2


def _form(struct_parents: int) -> COSStream:
    form = COSStream()
    form.set_item(_N("Type"), _N("XObject"))
    form.set_item(_N("Subtype"), _N("Form"))
    form.set_item(_N("StructParents"), COSInteger.get(struct_parents))
    form.set_data(b"")
    return form


def _resources(**entries: COSStream) -> PDResources:
    xobj = COSDictionary()
    for name, stream in entries.items():
        xobj.set_item(_N(name), stream)
    res = COSDictionary()
    res.set_item(_N("XObject"), xobj)
    return PDResources(res)


def test_self_referencing_form_terminates() -> None:
    old = _form(3)
    old.set_item(_N("Resources"), _resources(Me=old).get_cos_object())
    new = _form(3)
    new.set_item(_N("Resources"), _resources(Me=new).get_cos_object())
    mapping: dict[int, COSDictionary] = {}
    PDFMergerUtility._update_struct_parent_entries_for_resources(
        _resources(F=old), _resources(F=new), 10, mapping, set()
    )
    assert new.get_int(_N("StructParents")) == 13
    assert mapping[id(old)] is new


def test_missing_resources_or_old_x_object_is_skipped() -> None:
    new = _form(1)
    mapping: dict[int, COSDictionary] = {}
    PDFMergerUtility._update_struct_parent_entries_for_resources(
        None, _resources(F=new), 10, mapping, set()
    )
    PDFMergerUtility._update_struct_parent_entries_for_resources(
        _resources(), _resources(F=new), 10, mapping, set()
    )
    PDFMergerUtility._update_struct_parent_entries_for_resources(
        _resources(F=new), None, 10, mapping, set()
    )
    assert new.get_int(_N("StructParents")) == 1
    assert mapping == {}


def test_negative_struct_parents_not_offset_or_mapped() -> None:
    old = _form(-1)
    new = _form(-1)
    mapping: dict[int, COSDictionary] = {}
    PDFMergerUtility._update_struct_parent_entries_for_resources(
        _resources(F=old), _resources(F=new), 10, mapping, set()
    )
    assert new.get_int(_N("StructParents")) == -1
    assert mapping == {}


@pytest.mark.parametrize(
    "mode",
    [DocumentMergeMode.PDFBOX_LEGACY_MODE, DocumentMergeMode.OPTIMIZE_RESOURCES_MODE],
    ids=["legacy", "optimize"],
)
def test_stream_cache_function_with_file_sources(tmp_path: Path, mode: object) -> None:
    """PDFBOX-6298: sources are loaded while a stream-cache function is set."""
    src = tmp_path / "src.pdf"
    with PDDocument() as doc:
        doc.add_page(PDPage())
        doc.save(str(src))
    out = io.BytesIO()
    merger = PDFMergerUtility()
    merger.set_document_merge_mode(mode)  # type: ignore[arg-type]
    merger.add_source(str(src))
    merger.add_source(str(src))
    merger.set_destination_stream(out)
    merger.merge_documents(IOUtils.create_memory_only_stream_cache())
    with PDDocument.load(out.getvalue()) as merged:
        assert merged.get_number_of_pages() == 2


def test_source_check_with_number_tree_passes(tmp_path: Path) -> None:
    out = _merge_twice(tmp_path, build_octopdf_like_sample())
    with PDDocument.load(out) as doc:
        check_with_number_tree(doc)
