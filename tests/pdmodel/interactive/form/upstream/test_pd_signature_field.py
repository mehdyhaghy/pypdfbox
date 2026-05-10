"""Ported from upstream PDFBox 3.0 ``PDSignatureFieldTest``.

Source:
``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDSignatureFieldTest.java``

Skipped upstream cases:
- ``testGetContents`` (PDFBOX-4822) — exercises low-level signed
  byte-range extraction over the raw document byte stream
  (``PDSignature.getContents(byte[])`` and ``getContents(InputStream)``).
  pypdfbox's :class:`PDSignature` exposes ``get_contents()`` which reads
  ``/Contents`` from the COS dictionary directly, plus
  ``get_signed_data(document_bytes)`` for the byte-range slice — the
  upstream test belongs in the digital-signature test cluster, not here.
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


def test_set_value_for_abstracted_signature_field(acro_form: PDAcroForm) -> None:
    """Upstream: ``setValueForAbstractedSignatureField`` — calling
    ``setValue(String)`` on a signature field throws
    ``UnsupportedOperationException``. The lite port surfaces the same
    contract via :class:`NotImplementedError` — strings are explicitly
    rejected at the Python boundary because ``/V`` must be a signature
    dictionary, not free text.
    """
    sig_field = PDSignatureField(acro_form)
    sig_field.set_partial_name("SignatureField")
    with pytest.raises(NotImplementedError):
        sig_field.set_value("Can't set value using String")


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


# ---------------------------------------------------------------------------
# Wave 246 round-out — small remaining gaps on the lite surface.
# ---------------------------------------------------------------------------


def test_ft_sig_constant_matches_ft(acro_form: PDAcroForm) -> None:
    """``FT_SIG`` is a public alias of ``FT`` mirroring upstream
    ``COSName.SIG``. Both must equal the literal ``"Sig"`` and stay in
    sync to guard against accidental drift."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    assert PDSignatureField.FT_SIG == "Sig"
    assert PDSignatureField.FT_SIG == PDSignatureField.FT

    # Class-level constant is also reachable via instance attribute access.
    sig = PDSignatureField(acro_form)
    assert sig.FT_SIG == "Sig"
    assert sig.get_field_type() == sig.FT_SIG


def test_is_signature_type_returns_true_for_fresh_field(
    acro_form: PDAcroForm,
) -> None:
    """A freshly constructed signature field has ``/FT == "Sig"`` directly
    on its dictionary, so the predicate returns ``True``."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    sig = PDSignatureField(acro_form)
    assert sig.is_signature_type() is True


def test_is_signature_type_walks_inheritable_attribute_chain(
    acro_form: PDAcroForm,
) -> None:
    """``is_signature_type`` resolves ``/FT`` via the inheritable-attribute
    walk — a child whose ``/FT`` is inherited from a parent is still
    classified by the effective type."""
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    parent = PDNonTerminalField(acro_form)
    parent.get_cos_object().set_name(_FT, "Sig")

    # Build a signature field whose own dict has no /FT — the parent
    # provides it via the inheritable chain.
    bare = COSDictionary()
    child = PDSignatureField(acro_form, bare, parent=parent)
    # Strip the /FT that the constructor would've set when handed an
    # already-existing dict — verify inheritance covers the gap.
    bare.remove_item(_FT)
    assert child.get_field_type() == "Sig"
    assert child.is_signature_type() is True


def test_is_signature_type_false_when_ft_unrelated(
    acro_form: PDAcroForm,
) -> None:
    """``/FT`` resolving to a non-``"Sig"`` value yields ``False``."""
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    field = COSDictionary()
    field.set_name(_FT, "Tx")
    sig = PDSignatureField(acro_form, field)
    assert sig.is_signature_type() is False


def test_is_signature_type_false_when_ft_absent(
    acro_form: PDAcroForm,
) -> None:
    """No ``/FT`` anywhere on the chain → ``get_field_type`` returns
    ``None`` and the predicate is ``False``."""
    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    field = COSDictionary()
    sig = PDSignatureField(acro_form, field)
    # No /FT on field, no parent, AcroForm has none either.
    assert sig.get_field_type() is None
    assert sig.is_signature_type() is False


def test_get_default_signature_alias_round_trip(acro_form: PDAcroForm) -> None:
    """``get_default_signature`` is a typed alias for ``get_default_value``
    — both return the same wrapper instance content for a populated
    ``/DV``, and ``None`` when ``/DV`` is absent."""
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    sig_field = PDSignatureField(acro_form)
    assert sig_field.get_default_signature() is None
    assert sig_field.get_default_value() is None

    dv_sig = PDSignature()
    dv_sig.set_name("DefaultSigner")
    sig_field.set_default_value(dv_sig)

    via_default = sig_field.get_default_signature()
    via_alias = sig_field.get_default_value()
    assert via_default is not None
    assert via_alias is not None
    # Both wrap the same backing COSDictionary.
    assert via_default.get_cos_object() is via_alias.get_cos_object()
    assert via_default.get_cos_object() is dv_sig.get_cos_object()


def test_get_default_signature_returns_none_for_non_dict_dv(
    acro_form: PDAcroForm,
) -> None:
    """When ``/DV`` is set to a non-dictionary value (e.g. a stray
    ``COSString``), ``get_default_signature`` returns ``None`` rather
    than wrapping the wrong type."""
    from pypdfbox.cos import COSName, COSString
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    sig_field = PDSignatureField(acro_form)
    sig_field.get_cos_object().set_item(
        COSName.get_pdf_name("DV"), COSString("oops")
    )
    assert sig_field.get_default_signature() is None
    assert sig_field.get_default_value() is None


def test_has_visible_widget_fresh_field_is_invisible(
    acro_form: PDAcroForm,
) -> None:
    """A fresh signature field has a single widget with no ``/Rect`` —
    the visibility predicate returns ``False``."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    sig = PDSignatureField(acro_form)
    assert sig.has_visible_widget() is False


def test_has_visible_widget_zero_rect_is_invisible(
    acro_form: PDAcroForm,
) -> None:
    """A widget with an explicitly zero-width-and-height rectangle is
    still considered invisible (PDF 32000-1 convention for invisible
    signatures)."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(0, 0, 0, 0))
    assert sig.has_visible_widget() is False


def test_has_visible_widget_non_zero_rect_is_visible(
    acro_form: PDAcroForm,
) -> None:
    """Non-zero rectangle and neither hidden nor no-view → visible."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(100, 100, 200, 50))
    assert sig.has_visible_widget() is True


def test_has_visible_widget_hidden_flag_overrides_rect(
    acro_form: PDAcroForm,
) -> None:
    """A widget with non-zero rectangle but ``/F`` hidden bit set is
    still considered invisible."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(0, 0, 100, 50))
    widget.set_hidden(True)
    assert sig.has_visible_widget() is False


def test_has_visible_widget_no_view_flag_overrides_rect(
    acro_form: PDAcroForm,
) -> None:
    """``/F`` no-view bit also overrides a non-zero rectangle."""
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(0, 0, 100, 50))
    widget.set_no_view(True)
    assert sig.has_visible_widget() is False


def test_has_visible_widget_matches_construct_appearances_warning(
    acro_form: PDAcroForm, caplog: pytest.LogCaptureFixture
) -> None:
    """``has_visible_widget`` returns ``True`` exactly when
    ``construct_appearances`` would emit the PDFBOX-3524 warning. Locking
    these in lockstep guards against accidental drift between the two
    visibility tests."""
    import logging

    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(10, 20, 100, 50))

    assert sig.has_visible_widget() is True
    with caplog.at_level(logging.WARNING):
        sig.construct_appearances()
    assert any(
        "PDFBOX-3524" in record.getMessage() for record in caplog.records
    )


# ---------------------------------------------------------------------------
# Wave 1262 round-out — explicit `generate_partial_name` exposure.
# ---------------------------------------------------------------------------


def test_generate_partial_name_returns_first_unused_signature_slot(
    acro_form: PDAcroForm,
) -> None:
    """Mirrors upstream ``PDSignatureField.generatePartialName`` — when the
    AcroForm carries no other signature fields, the generator returns
    ``"Signature1"``. Subsequent fields walk to the next unused index.
    """
    sig_a = PDSignatureField(acro_form)
    acro_form.set_fields([sig_a])
    assert sig_a.get_partial_name() == "Signature1"

    sig_b = PDSignatureField(acro_form)
    acro_form.set_fields([sig_a, sig_b])
    assert sig_b.get_partial_name() == "Signature2"

    # Direct invocation skips the lowest used index.
    assert sig_b.generate_partial_name() == "Signature3"


def test_generate_partial_name_only_considers_signature_fields(
    acro_form: PDAcroForm,
) -> None:
    """Upstream walks the entire field tree but the lite port narrows the
    candidate set to ``PDSignatureField`` instances — a non-signature
    field happening to be named ``Signature1`` should not bump the next
    signature's index off ``Signature1``.
    """
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

    text = PDTextField(acro_form)
    text.set_partial_name("Signature1")
    acro_form.set_fields([text])

    sig = PDSignatureField(acro_form)
    # Generator was invoked at construction; the suggested name is still
    # "Signature1" because the existing PDTextField with that name is not
    # a signature field.
    assert sig.get_partial_name() == "Signature1"
