"""Wave 205 round-out coverage for ``PDSignatureField``.

Targets:
- own-dictionary predicates ``has_signature`` / ``has_default_value`` /
  ``has_seed_value`` / ``has_lock`` (pypdfbox extension over upstream).
- visibility-aware ``construct_appearances`` (mirrors upstream
  ``PDSignatureField.constructAppearances`` warn-when-visible behavior).
"""
from __future__ import annotations

import logging

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSignature,
    PDSignatureLock,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


@pytest.fixture
def acro_form() -> PDAcroForm:
    return PDAcroForm()


# ---------------------------------------------------------------------------
# own-dictionary predicates
# ---------------------------------------------------------------------------


def test_has_signature_default_false(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    assert sig.has_signature() is False


def test_has_signature_after_set_value(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    sig.set_value(PDSignature())
    assert sig.has_signature() is True


def test_has_signature_after_set_value_none(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    sig.set_value(PDSignature())
    sig.set_value(None)
    assert sig.has_signature() is False
    assert sig.get_signature() is None


def test_has_default_value_default_false(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    assert sig.has_default_value() is False


def test_has_default_value_after_set(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    sig.set_default_value(PDSignature())
    assert sig.has_default_value() is True
    sig.set_default_value(None)
    assert sig.has_default_value() is False


def test_has_seed_value_default_false(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    assert sig.has_seed_value() is False


def test_has_seed_value_after_set(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    sig.set_seed_value(PDSeedValue())
    assert sig.has_seed_value() is True
    sig.set_seed_value(None)
    assert sig.has_seed_value() is False


def test_has_lock_default_false(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    assert sig.has_lock() is False


def test_has_lock_after_set(acro_form: PDAcroForm) -> None:
    sig = PDSignatureField(acro_form)
    sig.set_lock(PDSignatureLock())
    assert sig.has_lock() is True
    sig.set_lock(None)
    assert sig.has_lock() is False


# ---------------------------------------------------------------------------
# construct_appearances visibility check
# ---------------------------------------------------------------------------


def test_construct_appearances_no_widgets_returns_silently(
    acro_form: PDAcroForm, caplog: pytest.LogCaptureFixture
) -> None:
    sig = PDSignatureField(acro_form)
    # Drop widgets to exercise the empty-widgets branch.
    from pypdfbox.cos import COSArray, COSName

    sig.get_cos_object().set_item(COSName.get_pdf_name("Kids"), COSArray())
    # Also clear the field-as-widget promotion that __init__ performs.
    sig.get_cos_object().remove_item(COSName.get_pdf_name("Subtype"))
    sig.get_cos_object().remove_item(COSName.get_pdf_name("Type"))
    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.interactive.form.pd_signature_field",
    ):
        sig.construct_appearances()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == []


def test_construct_appearances_no_rectangle_is_silent_noop(
    acro_form: PDAcroForm, caplog: pytest.LogCaptureFixture
) -> None:
    sig = PDSignatureField(acro_form)
    # Default-constructed widget has no /Rect — this should remain a no-op
    # without emitting the upstream "not implemented here" warning.
    assert sig.get_widgets()[0].get_rectangle() is None
    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.interactive.form.pd_signature_field",
    ):
        sig.construct_appearances()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == []


def test_construct_appearances_zero_rectangle_is_silent_noop(
    acro_form: PDAcroForm, caplog: pytest.LogCaptureFixture
) -> None:
    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(0.0, 0.0, 0.0, 0.0))
    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.interactive.form.pd_signature_field",
    ):
        sig.construct_appearances()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == []


def test_construct_appearances_hidden_widget_is_silent_noop(
    acro_form: PDAcroForm, caplog: pytest.LogCaptureFixture
) -> None:
    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(10.0, 10.0, 100.0, 50.0))
    widget.set_hidden(True)
    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.interactive.form.pd_signature_field",
    ):
        sig.construct_appearances()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == []


def test_construct_appearances_no_view_widget_is_silent_noop(
    acro_form: PDAcroForm, caplog: pytest.LogCaptureFixture
) -> None:
    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(10.0, 10.0, 100.0, 50.0))
    widget.set_no_view(True)
    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.interactive.form.pd_signature_field",
    ):
        sig.construct_appearances()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == []


def test_construct_appearances_visible_widget_warns(
    acro_form: PDAcroForm, caplog: pytest.LogCaptureFixture
) -> None:
    """Mirrors upstream: visible signature fields emit a 'not implemented
    here' warning so callers know the appearance has not been refreshed."""
    sig = PDSignatureField(acro_form)
    widget = sig.get_widgets()[0]
    widget.set_rectangle(PDRectangle(10.0, 10.0, 100.0, 50.0))
    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="pypdfbox.pdmodel.interactive.form.pd_signature_field",
    ):
        sig.construct_appearances()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "Appearance generation for signature fields" in warnings[0].message
    assert "PDFBOX-3524" in warnings[0].message
