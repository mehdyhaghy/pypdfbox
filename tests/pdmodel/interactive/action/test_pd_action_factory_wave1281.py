"""Tests for ``PDActionFactory``."""

from __future__ import annotations

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.interactive.action.pd_action_factory import PDActionFactory
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_java_script import PDActionJavaScript
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI


def _make_dict(subtype: str) -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), subtype)
    return d


def test_create_action_goto() -> None:
    action = PDActionFactory.create_action(_make_dict(PDActionGoTo.SUB_TYPE))
    assert isinstance(action, PDActionGoTo)


def test_create_action_javascript() -> None:
    action = PDActionFactory.create_action(_make_dict(PDActionJavaScript.SUB_TYPE))
    assert isinstance(action, PDActionJavaScript)


def test_create_action_uri() -> None:
    action = PDActionFactory.create_action(_make_dict(PDActionURI.SUB_TYPE))
    assert isinstance(action, PDActionURI)


def test_create_action_none_for_unknown_subtype() -> None:
    assert PDActionFactory.create_action(_make_dict("Unknown")) is None


def test_create_action_none_for_missing_dict() -> None:
    assert PDActionFactory.create_action(None) is None
