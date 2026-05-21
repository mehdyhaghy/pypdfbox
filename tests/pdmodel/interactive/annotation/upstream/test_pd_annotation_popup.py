"""Upstream-parity port for ``PDAnnotationPopup``.

Mirrors ``PDAnnotationPopup.java`` (PDFBox 3.0.x). Upstream ships no
JUnit test for the popup wrapper — this module ports the source's
behavioural contract: SUB_TYPE stamp, /Open flag default false, /Parent
typed lookup via PDAnnotation.createAnnotation, the silent null when the
parent's annotation subtype is not markup, and the /P-as-fallback parser
tolerance.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text import PDAnnotationText

_SUBTYPE = COSName.get_pdf_name("Subtype")
_OPEN = COSName.get_pdf_name("Open")
_PARENT = COSName.get_pdf_name("Parent")
_P = COSName.get_pdf_name("P")


def test_default_constructor_stamps_subtype():
    popup = PDAnnotationPopup()
    assert popup.get_subtype() == "Popup"
    assert popup.get_cos_object().get_name(_SUBTYPE) == "Popup"


def test_open_default_false():
    # Upstream: ``getBoolean("Open", false)``.
    popup = PDAnnotationPopup()
    assert popup.get_open() is False


def test_open_set_round_trip():
    popup = PDAnnotationPopup()
    popup.set_open(True)
    assert popup.get_open() is True
    assert popup.get_cos_object().get_boolean(_OPEN, False) is True
    popup.set_open(False)
    assert popup.get_open() is False


def test_parent_default_none():
    popup = PDAnnotationPopup()
    assert popup.get_parent() is None
    assert popup.get_parent_markup() is None


def test_set_parent_via_markup_annotation():
    # Upstream: setParent(PDAnnotationMarkup) writes /Parent to the
    # underlying COSDictionary.
    popup = PDAnnotationPopup()
    text = PDAnnotationText()
    text.set_title_popup("Author")
    popup.set_parent(text)
    fetched = popup.get_parent_markup()
    assert fetched is not None
    assert fetched.get_title_popup() == "Author"


def test_get_parent_falls_back_to_p_key():
    # pypdfbox extends upstream's PARENT-only lookup to also try /P (the
    # standard annotation parent key on some legacy producers).
    d = COSDictionary()
    d.set_name(_SUBTYPE, "Popup")
    parent_dict = COSDictionary()
    parent_dict.set_name(_SUBTYPE, "Text")
    d.set_item(_P, parent_dict)
    popup = PDAnnotationPopup(d)
    fetched = popup.get_parent()
    assert isinstance(fetched, COSDictionary)


def test_get_parent_markup_returns_none_for_non_markup_subtype():
    # Upstream logs an error and returns null when the resolved parent
    # is not a PDAnnotationMarkup.
    d = COSDictionary()
    d.set_name(_SUBTYPE, "Popup")
    parent_dict = COSDictionary()
    parent_dict.set_name(_SUBTYPE, "Widget")  # not a markup
    d.set_item(_PARENT, parent_dict)
    popup = PDAnnotationPopup(d)
    assert popup.get_parent_markup() is None


def test_sub_type_constant_equals_popup():
    assert PDAnnotationPopup.SUB_TYPE == "Popup"
