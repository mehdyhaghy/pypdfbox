"""Incremental /AcroForm field-collision bookkeeping during ``import_page``.

``PDDocument._import_page_acroform_fixup`` re-attaches widget field roots
into the destination ``/AcroForm /Fields`` array and renames colliding /T
names to ``dummyFieldName<n>``. The bookkeeping is persisted incrementally
on the destination document (a name set + an id() set of appended roots,
invalidated when the /Fields array identity or size changes) so a long
import loop stays linear instead of rescanning the whole array per page.
These tests pin the collision/rename semantics that must be identical to
the naive per-page rescan.
"""

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _make_source(names: list[str]) -> PDDocument:
    """One widget annotation per page, each its own field root with the
    given /T name."""
    doc = PDDocument()
    for name in names:
        page = PDPage()
        widget = COSDictionary()
        widget.set_item(_n("Type"), _n("Annot"))
        widget.set_item(_n("Subtype"), _n("Widget"))
        widget.set_item(_n("FT"), _n("Tx"))
        widget.set_string(_n("T"), name)
        annots = COSArray()
        annots.add(widget)
        page.get_cos_object().set_item(_n("Annots"), annots)
        doc.add_page(page)
    return doc


def _field_names(dest: PDDocument) -> list[str]:
    acro_form = dest.get_document_catalog().get_acro_form(None)
    fields = acro_form.get_cos_object().get_dictionary_object(_n("Fields"))
    return [
        fields.get_object(i).get_string(_n("T"))
        for i in range(fields.size())
    ]


def test_collision_renames_are_incrementally_consistent() -> None:
    src = _make_source(["a", "b", "a", "c", "b", "a"])
    try:
        dest = PDDocument()
        try:
            for page in src.get_pages():
                dest.import_page(page)
            # First occurrence of each name kept verbatim; every later
            # collision renamed to the next dummyFieldName in append order.
            assert _field_names(dest) == [
                "a",
                "b",
                "dummyFieldName1",
                "c",
                "dummyFieldName2",
                "dummyFieldName3",
            ]
        finally:
            dest.close()
    finally:
        src.close()


def test_no_collisions_preserves_all_names_in_order() -> None:
    src = _make_source(["one", "two", "three", "four"])
    try:
        dest = PDDocument()
        try:
            for page in src.get_pages():
                dest.import_page(page)
            assert _field_names(dest) == ["one", "two", "three", "four"]
        finally:
            dest.close()
    finally:
        src.close()


def test_cache_invalidated_by_external_field_mutation() -> None:
    """An externally injected field between imports changes the /Fields
    size, forcing a rebuild so the new name participates in collision
    detection on the next imported page."""
    src = _make_source(["x", "y"])
    try:
        dest = PDDocument()
        try:
            pages = list(src.get_pages())
            dest.import_page(pages[0])  # 'x'
            # Inject a field named 'y' directly (bypasses import bookkeeping).
            acro_form = dest.get_document_catalog().get_acro_form(None)
            fields = acro_form.get_cos_object().get_dictionary_object(
                _n("Fields")
            )
            external = COSDictionary()
            external.set_string(_n("T"), "y")
            fields.add(external)
            dest.import_page(pages[1])  # 'y' collides with the injected 'y'
            assert _field_names(dest) == ["x", "y", "dummyFieldName1"]
        finally:
            dest.close()
    finally:
        src.close()


def test_large_import_loop_stays_linear_and_unique() -> None:
    """Many unique-named widgets import without renames and remain in
    order — exercises the fast (no-rebuild) incremental path repeatedly."""
    names = [f"field{i}" for i in range(200)]
    src = _make_source(names)
    try:
        dest = PDDocument()
        try:
            for page in src.get_pages():
                dest.import_page(page)
            assert _field_names(dest) == names
        finally:
            dest.close()
    finally:
        src.close()
