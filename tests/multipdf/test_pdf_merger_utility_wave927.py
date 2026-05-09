from __future__ import annotations

from . import test_pdf_merger_utility_wave656 as wave656


def test_wave927_catalog_setters_and_pages_helper() -> None:
    catalog = wave656._Catalog()
    outline = object()
    struct_tree = object()

    catalog.set_document_outline(outline)
    catalog.set_struct_tree_root(struct_tree)

    assert catalog.get_document_outline() is outline
    assert catalog.get_struct_tree_root() is struct_tree
    assert catalog.get_pages() == []

