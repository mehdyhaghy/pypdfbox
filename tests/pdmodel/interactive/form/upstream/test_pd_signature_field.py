"""Ported from upstream PDFBox 3.0 ``PDSignatureFieldTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDSignatureFieldTest.java``

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

    Note: upstream additionally promotes the field dict to a widget by
    writing ``/Type /Annot`` and ``/Subtype /Widget``. That promotion is
    deferred in this lite port and is recorded in ``CHANGES.md``.
    """
    sig_field = PDSignatureField(acro_form)
    sig_field.set_partial_name("SignatureField")

    assert sig_field.get_field_type() == sig_field.get_cos_object().get_name(_FT)
    assert sig_field.get_field_type() == "Sig"

    acro_form.set_fields([sig_field])
    assert acro_form.get_field("SignatureField") is not None
