from __future__ import annotations

from . import test_pdf_merger_utility_wave615 as wave615


def test_wave928_catalog_and_struct_root_helpers() -> None:
    catalog = wave615._Catalog()
    outline = object()
    catalog.outline = outline
    struct_root = wave615._StructRoot()

    assert catalog.get_acro_form() is None
    assert catalog.get_document_outline() is outline
    assert struct_root.get_cos_object() is struct_root._dict

