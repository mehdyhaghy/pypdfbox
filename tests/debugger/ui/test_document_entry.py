"""Hand-written tests for ``pypdfbox.debugger.ui.DocumentEntry``."""

from pypdfbox.debugger.ui import DocumentEntry, PageEntry
from pypdfbox.debugger.ui import document_entry as module
from pypdfbox.pdmodel import PDDocument, PDPage, PDPageLabels
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange


def test_basic_two_pages() -> None:
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    entry = DocumentEntry(doc, "sample.pdf")
    try:
        assert str(entry) == "sample.pdf"
        assert entry.get_page_count() == 2

        first = entry.get_page(0)
        second = entry.get_page(1)
        assert isinstance(first, PageEntry)
        assert isinstance(second, PageEntry)
        assert first.get_page_num() == 1
        assert second.get_page_num() == 2

        # index_of is the inverse of page-num.
        assert entry.index_of(first) == 0
        assert entry.index_of(second) == 1
    finally:
        doc.close()


def test_empty_document_has_zero_pages() -> None:
    doc = PDDocument()
    try:
        entry = DocumentEntry(doc, "empty.pdf")
        assert entry.get_page_count() == 0
    finally:
        doc.close()


# ---- page-label lookup ----------------------------------------------------


def test_page_label_lookup_returns_string_when_labels_present() -> None:
    """A document with a ``/PageLabels`` number tree should surface
    the per-page label via ``DocumentEntry.get_page``."""
    doc = PDDocument()
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    doc.add_page(PDPage())
    try:
        labels = PDPageLabels(doc)
        roman = PDPageLabelRange()
        roman.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
        labels.set_label_item(0, roman)
        decimal = PDPageLabelRange()
        decimal.set_style(PDPageLabelRange.STYLE_DECIMAL)
        decimal.set_start(1)
        labels.set_label_item(2, decimal)
        doc.get_document_catalog().set_page_labels(labels)

        entry = DocumentEntry(doc, "labeled.pdf")
        first = entry.get_page(0)
        second = entry.get_page(1)
        third = entry.get_page(2)
        assert str(first).startswith("Page: 1 -")
        assert str(second).startswith("Page: 2 -")
        # Third page switches to decimal style with start=1 → label "1".
        assert str(third) == "Page: 3 - 1"
    finally:
        doc.close()


def test_page_label_lookup_returns_none_when_labels_absent() -> None:
    """Without ``/PageLabels`` the helper short-circuits to ``None``."""
    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        # No catalog ``/PageLabels`` set → ``_get_page_label`` returns None.
        result = module._get_page_label(doc, 0)
        assert result is None
        entry = DocumentEntry(doc, "x.pdf")
        page = entry.get_page(0)
        assert str(page) == "Page: 1"
    finally:
        doc.close()


def test_page_label_lookup_returns_none_for_out_of_range_index() -> None:
    """Asking for a page index past the labels list yields ``None``."""
    doc = PDDocument()
    doc.add_page(PDPage())
    try:
        labels = PDPageLabels(doc)
        rng = PDPageLabelRange()
        rng.set_style(PDPageLabelRange.STYLE_DECIMAL)
        labels.set_label_item(0, rng)
        doc.get_document_catalog().set_page_labels(labels)

        # Index 5 is past the 1-page document — list lookup returns None.
        assert module._get_page_label(doc, 5) is None
    finally:
        doc.close()


def test_page_label_lookup_for_dict_label_map(monkeypatch) -> None:
    """If the wrapper returns a dict instead of a list, dict.get is used."""

    class _FakeLabels:
        def get_labels_by_page_indices(self) -> dict[int, str]:
            return {0: "i", 1: "ii"}

    class _FakeCatalog:
        def get_page_labels(self) -> _FakeLabels:
            return _FakeLabels()

    class _FakeDoc:
        def get_document_catalog(self) -> _FakeCatalog:
            return _FakeCatalog()

    fake = _FakeDoc()
    assert module._get_page_label(fake, 0) == "i"
    assert module._get_page_label(fake, 1) == "ii"
    # Missing keys map to ``None`` via ``dict.get``.
    assert module._get_page_label(fake, 5) is None


def test_page_label_lookup_returns_none_when_wrapper_returns_none() -> None:
    """Catalog returning ``None`` for ``get_page_labels`` skips the lookup."""

    class _FakeCatalog:
        def get_page_labels(self) -> None:
            return None

    class _FakeDoc:
        def get_document_catalog(self) -> _FakeCatalog:
            return _FakeCatalog()

    assert module._get_page_label(_FakeDoc(), 0) is None
