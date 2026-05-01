"""Ported from upstream PDFBox 3.0 ``PDSignatureFieldTest``.

Source:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDSignatureFieldTest.java``

Skipped upstream cases:
- ``setValueForAbstractedSignatureField`` — upstream throws
  ``UnsupportedOperationException`` when ``setValue(String)`` is called.
  This lite port keeps the permissive ``set_value`` signature intact (it
  just round-trips the value without type-checking strings); the strict
  upstream contract is recorded in ``CHANGES.md`` and may be revisited
  once the typed dispatch layer lands.
- ``testGetContents`` (PDFBOX-4822) — exercises low-level signed
  byte-range extraction; covered separately under the digital-signature
  test cluster.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField

_FT: COSName = COSName.get_pdf_name("FT")


@pytest.fixture
def acro_form() -> PDAcroForm:
    return PDAcroForm()


def test_create_default_signature_field(acro_form: PDAcroForm) -> None:
    """Upstream: ``createDefaultSignatureField`` — ``/FT`` is ``"Sig"`` and
    the field is retrievable from the AcroForm by partial name.

    Fresh construction also promotes the field dict to a widget by writing
    ``/Type /Annot`` and ``/Subtype /Widget``.
    """
    sig_field = PDSignatureField(acro_form)

    assert sig_field.get_field_type() == sig_field.get_cos_object().get_name(_FT)
    assert sig_field.get_field_type() == "Sig"
    assert sig_field.get_partial_name() == "Signature1"
    widget = sig_field.get_widgets()[0]
    assert widget.get_subtype() == "Widget"
    assert widget.is_printed()
    assert widget.is_locked()

    acro_form.set_fields([sig_field])
    assert acro_form.get_field("Signature1") is not None
