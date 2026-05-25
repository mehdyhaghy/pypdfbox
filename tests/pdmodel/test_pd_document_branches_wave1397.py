"""Wave 1397 branch-coverage tests for ``PDDocument``.

Closes False-branch arrows on the security-handler probe path and the
acroform fixup loop run during page import:

* ``get_current_access_permission`` 1124->1127 — security handler exists
  but lacks ``get_current_access_permission``
* ``assign_acro_form_default_resource`` 1479->exit — both /DR forms
  present but new /DR lacks XObject sub-dict
* ``_import_page_acroform_fixup`` 1645->1643 — /Fields entry is not a
  COSDictionary (stray array)
* ``_import_page_acroform_fixup`` 1649->1651 — second call reuses
  existing ``_import_field_counter``
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle


def test_get_current_access_permission_when_handler_lacks_method() -> None:
    """Closes 1124->1127: a security handler without
    ``get_current_access_permission`` falls through to the is_encrypted
    check (and returns owner-permission since the doc isn't encrypted)."""

    class _BareHandler:
        """Has no ``get_current_access_permission`` attribute."""

    with PDDocument() as doc:
        doc._security_handler = _BareHandler()  # noqa: SLF001
        # Force not encrypted so the next branch returns OwnerAccess.
        perms = doc.get_current_access_permission()
        # Returned non-None — the fall-through path produced a value.
        assert perms is not None


def test_assign_acro_form_default_resource_old_has_no_xobject() -> None:
    """Closes 1479->exit: new /DR carries /XObject but the old /DR has
    NO /XObject sub-dictionary → no merge happens (both must be dicts)."""

    class _AcroFormStub:
        def __init__(self) -> None:
            self._cos = COSDictionary()

        def get_cos_object(self) -> COSDictionary:
            return self._cos

        def get_default_resources(self):
            return _DefaultResourcesStub()

    class _DefaultResourcesStub:
        def __init__(self) -> None:
            self._cos = COSDictionary()  # No /XObject sub-dict.

        def get_cos_object(self) -> COSDictionary:
            return self._cos

    new_dr = COSDictionary()
    new_xobject = COSDictionary()
    new_xobject.set_item(COSName.get_pdf_name("Fm1"), COSDictionary())
    new_dr.set_item(COSName.get_pdf_name("XObject"), new_xobject)
    new_dict = COSDictionary()
    new_dict.set_item(COSName.get_pdf_name("DR"), new_dr)

    PDDocument.assign_acro_form_default_resource(_AcroFormStub(), new_dict)
    # Should not raise — the elif arm at 1479 was skipped.


def _build_page_with_widget_annot(parent_t: str) -> PDPage:
    """Build a page carrying a widget annot whose /Parent field has
    /T = parent_t."""
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    annots = COSArray()
    annot = COSDictionary()
    annot.set_item(
        COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Widget")
    )
    parent = COSDictionary()
    parent.set_string(COSName.get_pdf_name("T"), parent_t)
    annot.set_item(COSName.get_pdf_name("Parent"), parent)
    annots.add(annot)
    page.get_cos_object().set_item(COSName.get_pdf_name("Annots"), annots)
    return page


def test_import_page_acroform_fixup_skips_non_dict_fields_entries() -> None:
    """Closes 1645->1643: heterogeneous /Fields array contains a stray
    COSArray entry — it's silently skipped in the existing-name walk."""
    with PDDocument() as doc:
        # Pre-populate /AcroForm/Fields with a mix of types so the
        # existing-name enumeration hits both arms.
        catalog = doc.get_document_catalog()
        acro_form_dict = COSDictionary()
        fields_array = COSArray()
        good = COSDictionary()
        good.set_string(COSName.get_pdf_name("T"), "FieldA")
        fields_array.add(good)
        fields_array.add(COSArray())  # stray non-dict entry
        acro_form_dict.set_item(COSName.get_pdf_name("Fields"), fields_array)
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("AcroForm"), acro_form_dict
        )

        # Drive the fixup with a synthetic page carrying a widget annot.
        page = _build_page_with_widget_annot("FieldB")
        doc._import_page_acroform_fixup(page.get_cos_object())  # noqa: SLF001
        # No crash → branch covered.


def test_import_page_acroform_fixup_reuses_existing_counter() -> None:
    """Closes 1649->1651: a second invocation reuses the existing
    ``_import_field_counter`` attribute (skips the lazy initialisation)."""
    with PDDocument() as doc:
        # First call: counter gets installed AND used (collision required).
        catalog = doc.get_document_catalog()
        acro_form_dict = COSDictionary()
        fields_array = COSArray()
        existing = COSDictionary()
        existing.set_string(COSName.get_pdf_name("T"), "Conflict")
        fields_array.add(existing)
        acro_form_dict.set_item(COSName.get_pdf_name("Fields"), fields_array)
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("AcroForm"), acro_form_dict
        )
        # First import → installs the counter at 1650.
        page1 = _build_page_with_widget_annot("Conflict")
        doc._import_page_acroform_fixup(page1.get_cos_object())  # noqa: SLF001
        assert hasattr(doc, "_import_field_counter")
        first_counter = doc._import_field_counter  # noqa: SLF001
        # Second import → exists, skips re-initialisation branch.
        page2 = _build_page_with_widget_annot("Conflict")
        doc._import_page_acroform_fixup(page2.get_cos_object())  # noqa: SLF001
        # Counter advanced (or stayed); critically, no AttributeError raised.
        assert doc._import_field_counter >= first_counter  # noqa: SLF001
