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


# ---------------------------------------------------------------------------
# Round-out parity gaps below (not from upstream JUnit but mirroring upstream
# Java contracts on PDSignatureField.setValue / getValueAsString).
# ---------------------------------------------------------------------------


def test_set_value_invokes_apply_change(acro_form: PDAcroForm) -> None:
    """Upstream PDSignatureField.setValue(PDSignature) ends with applyChange().
    Verify the lite port routes set_value through apply_change as well so any
    subclass that overrides apply_change for cache invalidation gets notified.
    """
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    calls: list[str] = []

    class TrackedSignatureField(PDSignatureField):
        def apply_change(self) -> None:  # type: ignore[override]
            calls.append("apply_change")
            super().apply_change()

    sig_field = TrackedSignatureField(acro_form)
    calls.clear()
    sig_field.set_value(PDSignature())
    assert calls == ["apply_change"]


def test_get_value_as_string_for_populated_signature(acro_form: PDAcroForm) -> None:
    """Upstream returns ``signature.toString()``; lite port returns
    ``str(signature)`` which surfaces the populated identity fields."""
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    sig_field = PDSignatureField(acro_form)
    assert sig_field.get_value_as_string() == ""

    sig = PDSignature()
    sig.set_name("Carol")
    sig.set_reason("Approval")
    sig_field.set_value(sig)

    s = sig_field.get_value_as_string()
    assert "name=Carol" in s
    assert "reason=Approval" in s
