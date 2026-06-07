"""Round-out tests for :class:`PDFMergerUtility`.

Covers the surface that ``test_pdf_merger_utility.py`` doesn't already
exercise:

- :meth:`PDFMergerUtility.merge_documents_random_access_read` and bytes
  / :class:`RandomAccessRead` / file-stream handling in :meth:`add_source`.
- :meth:`PDFMergerUtility.set_destination` overload routing.
- ``/PageMode`` is carried over first-source-wins; ``/Lang`` /
  ``/ViewerPreferences`` / ``/MarkInfo`` are merged ONLY inside the
  structure-tree block (matching upstream gating, wave 1506); ``/PageLayout``
  is never merged.
- ``/Outlines`` concatenation and ``/PageLabels`` index shift.
- :meth:`PDFMergerUtility.set_ignore_acro_form_errors` toggle behaviour.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.multipdf import (
    AcroFormMergeMode,
    DocumentMergeMode,
    PDFMergerUtility,
)
from pypdfbox.pdmodel import PDDocument, PDPage

# ---------- helpers ----------


def _seed_page(page: PDPage, body: bytes = b"q Q\n") -> None:
    s = COSStream()
    s.set_raw_data(body)
    page.set_contents(s)


def _build_doc(num_pages: int, body: bytes = b"q Q\n") -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage()
        _seed_page(page, body)
        doc.add_page(page)
    return doc


def _save_to_path(doc: PDDocument, path: Path) -> None:
    doc.save(path)
    doc.close()


def _file_bytes(path: Path) -> bytes:
    return path.read_bytes()


# ---------- RandomAccessRead source path ----------


def test_merge_documents_random_access_read(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(2), a)
    _save_to_path(_build_doc(3), b)

    util = PDFMergerUtility()
    util.set_destination_file_name(str(out))
    util.merge_documents_random_access_read(
        [
            RandomAccessReadBuffer(_file_bytes(a)),
            RandomAccessReadBuffer(_file_bytes(b)),
        ]
    )
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 5


def test_merge_documents_random_access_read_rejects_non_rar() -> None:
    util = PDFMergerUtility()
    util.set_destination_stream(io.BytesIO())
    with pytest.raises(TypeError):
        util.merge_documents_random_access_read([b"not a RandomAccessRead"])


def test_add_source_accepts_random_access_read(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)
    util = PDFMergerUtility()
    util.add_source(RandomAccessReadBuffer(_file_bytes(a)))
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 1


def test_add_source_accepts_raw_bytes(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(2), a)
    util = PDFMergerUtility()
    util.add_source(_file_bytes(a))
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 2


def test_add_source_accepts_bytearray(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)
    util = PDFMergerUtility()
    util.add_source(bytearray(_file_bytes(a)))
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 1


# ---------- set_destination overload ----------


def test_set_destination_routes_path(tmp_path: Path) -> None:
    util = PDFMergerUtility()
    util.set_destination(str(tmp_path / "x.pdf"))
    assert util.get_destination_file_name() is not None
    assert util.get_destination_stream() is None


def test_set_destination_routes_stream() -> None:
    util = PDFMergerUtility()
    sink = io.BytesIO()
    util.set_destination(sink)
    assert util.get_destination_stream() is sink
    assert util.get_destination_file_name() is None


def test_set_destination_rejects_unsupported() -> None:
    util = PDFMergerUtility()
    with pytest.raises(TypeError):
        util.set_destination(12345)  # type: ignore[arg-type]


# ---------- merge_documents accepts MemoryUsageSetting ----------


def test_merge_documents_accepts_memory_usage_setting(tmp_path: Path) -> None:
    """MemoryUsageSetting is a parity placeholder — must not affect output
    but also must not raise."""
    from pypdfbox.io.memory_usage_setting import MemoryUsageSetting

    a = tmp_path / "a.pdf"
    out = tmp_path / "out.pdf"
    _save_to_path(_build_doc(1), a)
    util = PDFMergerUtility()
    util.add_source(str(a))
    util.set_destination_file_name(str(out))
    util.merge_documents(MemoryUsageSetting.setup_main_memory_only())
    with PDDocument.load(str(out)) as merged:
        assert merged.get_number_of_pages() == 1


# ---------- catalog carry-over (first-source-wins) ----------


def _catalog_dict(doc: PDDocument) -> COSDictionary:
    return doc.get_document_catalog().get_cos_object()


def test_page_mode_first_source_wins(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    src_a = _build_doc(1)
    _catalog_dict(src_a).set_name("PageMode", "UseOutlines")
    _save_to_path(src_a, a)
    src_b = _build_doc(1)
    _catalog_dict(src_b).set_name("PageMode", "UseThumbs")
    _save_to_path(src_b, b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        assert _catalog_dict(merged).get_name("PageMode") == "UseOutlines"


def test_page_layout_not_merged_for_untagged_sources(tmp_path: Path) -> None:
    """Wave 1506: upstream ``appendDocument`` never merges /PageLayout (there is
    no /PageLayout merge arm in PDFBox at all). pypdfbox previously carried it
    first-source-wins; that inline shim was removed. Untagged sources → the
    merged catalog has no /PageLayout (oracle-confirmed)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    src_a = _build_doc(1)
    _catalog_dict(src_a).set_name("PageLayout", "TwoColumnLeft")
    _save_to_path(src_a, a)
    src_b = _build_doc(1)
    _catalog_dict(src_b).set_name("PageLayout", "OneColumn")
    _save_to_path(src_b, b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        assert _catalog_dict(merged).get_name("PageLayout") is None


def test_lang_not_merged_for_untagged_sources(tmp_path: Path) -> None:
    """Wave 1506: upstream merges /Lang only inside the structure-tree block
    (``mergeLanguage``). Untagged sources → no structure-tree merge → the
    merged catalog has no /Lang (oracle-confirmed)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    src_a = _build_doc(1)
    _catalog_dict(src_a).set_string(COSName.get_pdf_name("Lang"), "en-US")
    _save_to_path(src_a, a)
    src_b = _build_doc(1)
    _catalog_dict(src_b).set_string(COSName.get_pdf_name("Lang"), "fr-FR")
    _save_to_path(src_b, b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        assert (
            _catalog_dict(merged).get_dictionary_object(
                COSName.get_pdf_name("Lang")
            )
            is None
        )


def test_viewer_preferences_not_merged_for_untagged_sources(
    tmp_path: Path,
) -> None:
    """Wave 1506: upstream merges /ViewerPreferences only inside the
    structure-tree block (``mergeViewerPreferences``). Untagged sources → no
    structure-tree merge → the merged catalog has no /ViewerPreferences
    (oracle-confirmed)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    src_a = _build_doc(1)
    vp_a = COSDictionary()
    vp_a.set_boolean(COSName.get_pdf_name("HideToolbar"), True)
    _catalog_dict(src_a).set_item(
        COSName.get_pdf_name("ViewerPreferences"), vp_a
    )
    _save_to_path(src_a, a)
    src_b = _build_doc(1)
    vp_b = COSDictionary()
    vp_b.set_boolean(COSName.get_pdf_name("HideMenubar"), True)
    _catalog_dict(src_b).set_item(
        COSName.get_pdf_name("ViewerPreferences"), vp_b
    )
    _save_to_path(src_b, b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        assert (
            _catalog_dict(merged).get_dictionary_object(
                COSName.get_pdf_name("ViewerPreferences")
            )
            is None
        )


# ---------- /Outlines concatenation ----------


def _attach_outline(doc: PDDocument, titles: list[str]) -> None:
    """Build a simple outline of sibling items under the catalog's
    ``/Outlines``."""
    catalog_dict = _catalog_dict(doc)
    outlines = COSDictionary()
    outlines.set_name("Type", "Outlines")
    items: list[COSDictionary] = []
    for t in titles:
        item = COSDictionary()
        item.set_string(COSName.get_pdf_name("Title"), t)
        item.set_item(COSName.get_pdf_name("Parent"), outlines)
        items.append(item)
    for i, item in enumerate(items):
        if i > 0:
            item.set_item(COSName.get_pdf_name("Prev"), items[i - 1])
        if i + 1 < len(items):
            item.set_item(COSName.get_pdf_name("Next"), items[i + 1])
    if items:
        outlines.set_item(COSName.get_pdf_name("First"), items[0])
        outlines.set_item(COSName.get_pdf_name("Last"), items[-1])
        outlines.set_int(COSName.get_pdf_name("Count"), len(items))
    catalog_dict.set_item(COSName.get_pdf_name("Outlines"), outlines)


def test_outlines_concatenated(tmp_path: Path) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    src_a = _build_doc(1)
    _attach_outline(src_a, ["a.1", "a.2"])
    _save_to_path(src_a, a)
    src_b = _build_doc(1)
    _attach_outline(src_b, ["b.1"])
    _save_to_path(src_b, b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        outline = merged.get_document_catalog().get_document_outline()
        assert outline is not None
        titles: list[str] = []
        node: Any = outline.get_first_child()
        while node is not None:
            titles.append(node.get_title())
            node = node.get_next_sibling()
        assert titles == ["a.1", "a.2", "b.1"]


# ---------- /PageLabels index shift ----------


def _attach_page_labels(doc: PDDocument, *, label_at_zero: str) -> None:
    nums = COSArray()
    nums.add(COSInteger.get(0))
    label = COSDictionary()
    label.set_string(COSName.get_pdf_name("P"), label_at_zero)
    nums.add(label)
    pl = COSDictionary()
    pl.set_item(COSName.get_pdf_name("Nums"), nums)
    _catalog_dict(doc).set_item(COSName.get_pdf_name("PageLabels"), pl)


def test_page_labels_indices_shifted_by_destination_page_count(
    tmp_path: Path,
) -> None:
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    out = tmp_path / "out.pdf"
    src_a = _build_doc(2)  # contributes 2 pages -> shift = 2
    _attach_page_labels(src_a, label_at_zero="A-")
    _save_to_path(src_a, a)
    src_b = _build_doc(3)
    _attach_page_labels(src_b, label_at_zero="B-")
    _save_to_path(src_b, b)

    util = PDFMergerUtility()
    util.add_sources([str(a), str(b)])
    util.set_destination_file_name(str(out))
    util.merge_documents()
    with PDDocument.load(str(out)) as merged:
        pl = _catalog_dict(merged).get_dictionary_object(
            COSName.get_pdf_name("PageLabels")
        )
        assert isinstance(pl, COSDictionary)
        nums = pl.get_dictionary_object(COSName.get_pdf_name("Nums"))
        assert isinstance(nums, COSArray)
        # Source A starts at 0 in destination; source B's "0" must shift
        # by source A's page count (2).
        indices = [
            int(nums.get_object(i).int_value()) for i in range(0, nums.size(), 2)
        ]
        assert indices == [0, 2]


# ---------- ignore_acro_form_errors ----------


class _ExplodingAcroForm:
    """Stand-in AcroForm whose ``get_fields`` blows up — exercises the
    ``ignore_acro_form_errors`` branch without needing a fixture PDF."""

    def __init__(self) -> None:
        self._cos = COSDictionary()
        self._cos.set_item(COSName.get_pdf_name("Fields"), COSArray())

    def get_cos_object(self) -> COSDictionary:
        return self._cos

    def get_fields(self) -> list[Any]:  # pragma: no cover — raises
        raise RuntimeError("boom")

    def get_field_tree(self) -> list[Any]:
        return []

    def get_field(self, _name: str) -> Any:
        return None


class _StubCatalog:
    def __init__(self, acro: Any) -> None:
        self._acro = acro
        self._cos = COSDictionary()

    def get_acro_form(self) -> Any:
        return self._acro

    def get_cos_object(self) -> COSDictionary:
        return self._cos


def test_ignore_acro_form_errors_swallows_exceptions(tmp_path: Path) -> None:
    util = PDFMergerUtility()
    util.set_ignore_acro_form_errors(True)
    assert util.is_ignore_acro_form_errors() is True

    cloner = type(
        "FakeCloner", (), {"clone_for_new_document": staticmethod(lambda x: x)}
    )()
    dest = _StubCatalog(_ExplodingAcroForm())
    src = _StubCatalog(_ExplodingAcroForm())
    # Must not raise — the inner RuntimeError is swallowed.
    util._merge_acro_form(cloner, dest, src)


def test_ignore_acro_form_errors_default_re_raises() -> None:
    util = PDFMergerUtility()
    assert util.is_ignore_acro_form_errors() is False

    cloner = type(
        "FakeCloner", (), {"clone_for_new_document": staticmethod(lambda x: x)}
    )()
    dest = _StubCatalog(_ExplodingAcroForm())
    src = _StubCatalog(_ExplodingAcroForm())
    with pytest.raises(OSError):
        util._merge_acro_form(cloner, dest, src)


def test_set_ignore_acro_form_errors_coerces_to_bool() -> None:
    util = PDFMergerUtility()
    util.set_ignore_acro_form_errors(1)
    assert util.is_ignore_acro_form_errors() is True
    util.set_ignore_acro_form_errors(0)
    assert util.is_ignore_acro_form_errors() is False


# ---------- DocumentMergeMode round-trip ----------


def test_document_merge_mode_round_trip() -> None:
    util = PDFMergerUtility()
    util.set_document_merge_mode(DocumentMergeMode.OPTIMIZE_RESOURCES_MODE)
    assert util.get_document_merge_mode() == DocumentMergeMode.OPTIMIZE_RESOURCES_MODE
    util.set_document_merge_mode(DocumentMergeMode.PDFBOX_LEGACY_MODE)
    assert util.get_document_merge_mode() == DocumentMergeMode.PDFBOX_LEGACY_MODE


def test_acro_form_merge_mode_round_trip() -> None:
    util = PDFMergerUtility()
    util.set_acro_form_merge_mode(AcroFormMergeMode.JOIN_FORM_FIELDS_MODE)
    assert util.get_acro_form_merge_mode() == AcroFormMergeMode.JOIN_FORM_FIELDS_MODE


# ---------- struct-tree-gated catalog scalar merges (wave 1506) ----------


_MULTIPDF_FIXTURES = (
    Path(__file__).resolve().parent.parent / "fixtures" / "multipdf"
)


def test_lang_markinfo_viewer_prefs_merged_inside_struct_tree_block() -> None:
    """When the structure tree IS merged (a tagged source), upstream's
    ``appendDocument`` runs mergeMarkInfo / mergeLanguage /
    mergeViewerPreferences as the last statements inside the
    ``if (mergeStructTree)`` block. pypdfbox mirrors that gating (wave 1506):
    merging a plain AcroForm doc with a tagged PDF/A doc carries /MarkInfo,
    /Lang, and /ViewerPreferences from the tagged source into the destination.

    Oracle-confirmed against PDFBox 3.0.7: the merged catalog carries
    ``/MarkInfo {Marked true, Suspects false}``, ``/Lang (de-DE)``, and
    ``/ViewerPreferences {DisplayDocTitle true}``."""
    a = _MULTIPDF_FIXTURES / "AcroFormForMerge.pdf"
    b = _MULTIPDF_FIXTURES / "PDFA3A.pdf"
    if not (a.is_file() and b.is_file()):
        pytest.skip("merge fixtures AcroFormForMerge.pdf + PDFA3A.pdf missing")

    util = PDFMergerUtility()
    dest = PDDocument()
    try:
        for src in (a, b):
            sd = PDDocument.load(src)
            try:
                util.append_document(dest, sd)
            finally:
                sd.close()
        co = dest.get_document_catalog().get_cos_object()

        mark_info = co.get_dictionary_object(COSName.get_pdf_name("MarkInfo"))
        assert isinstance(mark_info, COSDictionary)
        assert mark_info.get_boolean(COSName.get_pdf_name("Marked"), False) is True

        lang = co.get_dictionary_object(COSName.get_pdf_name("Lang"))
        text = lang.get_string() if hasattr(lang, "get_string") else None
        assert text == "de-DE"

        vp = co.get_dictionary_object(
            COSName.get_pdf_name("ViewerPreferences")
        )
        assert isinstance(vp, COSDictionary)
    finally:
        dest.close()


# ---------- nested-class aliases ----------


def test_nested_class_aliases_match_top_level_enums() -> None:
    """Upstream code references ``PDFMergerUtility.DocumentMergeMode``;
    the nested aliases must point at the same enums."""
    assert PDFMergerUtility.DocumentMergeMode is DocumentMergeMode
    assert PDFMergerUtility.AcroFormMergeMode is AcroFormMergeMode
