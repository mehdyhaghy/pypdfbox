"""Deeper upstream-parity port for ``PDAnnotationWidget``.

Wave 1363's ``test_pd_annotation_widget.py`` already covers the
constructor and subtype stamp. This module ports the rest of the
upstream Java source's behavioural contract: /H validation with the
spec's allowed values, the /A action factory dispatch, the /AA
additional-actions wrapper, and the /BS / /MK typed accessors.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)


def test_highlight_mode_constants_match_spec():
    assert PDAnnotationWidget.HIGHLIGHT_MODE_NONE == "N"
    assert PDAnnotationWidget.HIGHLIGHT_MODE_INVERT == "I"
    assert PDAnnotationWidget.HIGHLIGHT_MODE_OUTLINE == "O"
    assert PDAnnotationWidget.HIGHLIGHT_MODE_PUSH == "P"
    assert PDAnnotationWidget.HIGHLIGHT_MODE_TOGGLE == "T"


def test_get_highlighting_mode_default_invert():
    # Upstream: ``getNameAsString(COSName.H, "I")`` — INVERT is the spec
    # default.
    widget = PDAnnotationWidget()
    assert widget.get_highlighting_mode() == "I"


@pytest.mark.parametrize("mode", ["N", "I", "O", "P", "T"])
def test_set_highlighting_mode_accepts_each_spec_value(mode):
    widget = PDAnnotationWidget()
    widget.set_highlighting_mode(mode)
    assert widget.get_highlighting_mode() == mode


def test_set_highlighting_mode_rejects_invalid_value():
    # Upstream throws IllegalArgumentException; pypdfbox mirrors with
    # ValueError.
    widget = PDAnnotationWidget()
    with pytest.raises(ValueError, match="N, I, O, P, T"):
        widget.set_highlighting_mode("Z")


def test_set_highlighting_mode_none_removes_entry():
    widget = PDAnnotationWidget()
    widget.set_highlighting_mode("P")
    assert widget.get_highlighting_mode() == "P"
    widget.set_highlighting_mode(None)
    # After remove, the default INVERT applies again.
    assert widget.get_highlighting_mode() == "I"


def test_action_get_set_round_trip():
    # Upstream: setAction(PDAction) writes /A as an action dict;
    # getAction() dispatches through PDActionFactory.
    widget = PDAnnotationWidget()
    assert widget.get_action() is None
    action = PDActionURI()
    action.set_uri("https://example.org/")
    widget.set_action(action)
    fetched = widget.get_action()
    assert isinstance(fetched, PDActionURI)
    assert fetched.get_uri() == "https://example.org/"


def test_action_get_returns_none_for_non_dict_payload():
    # /A as a non-dict (a COSName for example) — upstream's
    # getCOSDictionary returns null.
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("Subtype"), "Widget")
    d.set_name(COSName.get_pdf_name("A"), "Foo")
    widget = PDAnnotationWidget(d)
    assert widget.get_action() is None


def test_border_style_get_set_round_trip():
    widget = PDAnnotationWidget()
    assert widget.get_border_style() is None
    bs = PDBorderStyleDictionary()
    bs.set_width(3.0)
    bs.set_style("S")
    widget.set_border_style(bs)
    fetched = widget.get_border_style()
    assert isinstance(fetched, PDBorderStyleDictionary)
    assert fetched.get_width() == 3.0
    assert fetched.get_style() == "S"


def test_appearance_characteristics_get_set_round_trip():
    widget = PDAnnotationWidget()
    assert widget.get_appearance_characteristics() is None
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(90)
    widget.set_appearance_characteristics(mk)
    fetched = widget.get_appearance_characteristics()
    assert isinstance(fetched, PDAppearanceCharacteristicsDictionary)
    assert fetched.get_rotation() == 90


def test_actions_get_none_when_aa_missing():
    widget = PDAnnotationWidget()
    assert widget.get_actions() is None


def test_sub_type_constant_equals_widget():
    assert PDAnnotationWidget.SUB_TYPE == "Widget"
