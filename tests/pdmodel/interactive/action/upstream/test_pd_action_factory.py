"""Upstream-parity port for ``PDActionFactory``.

Mirrors the Java source ``PDActionFactory.java`` (PDFBox 3.0.x). Upstream
ships no dedicated JUnit test for the factory — this module ports the
behavioural contract exercised by the upstream source itself, parametrised
across every supported ``/S`` subtype, plus the null-input and
unknown-subtype branches.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_factory import PDActionFactory
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.action.pd_action_import_data import PDActionImportData
from pypdfbox.pdmodel.interactive.action.pd_action_java_script import PDActionJavaScript
from pypdfbox.pdmodel.interactive.action.pd_action_launch import PDActionLaunch
from pypdfbox.pdmodel.interactive.action.pd_action_movie import PDActionMovie
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import PDActionRemoteGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_reset_form import PDActionResetForm
from pypdfbox.pdmodel.interactive.action.pd_action_sound import PDActionSound
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import PDActionSubmitForm
from pypdfbox.pdmodel.interactive.action.pd_action_thread import PDActionThread
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI

_S = COSName.get_pdf_name("S")


def _make(subtype: str) -> COSDictionary:
    """Build a minimal action dictionary with ``/S /<subtype>``."""
    d = COSDictionary()
    d.set_name(_S, subtype)
    return d


@pytest.mark.parametrize(
    "sub_type,expected_cls",
    [
        ("JavaScript", PDActionJavaScript),
        ("GoTo", PDActionGoTo),
        ("Launch", PDActionLaunch),
        ("GoToR", PDActionRemoteGoTo),
        ("URI", PDActionURI),
        ("Named", PDActionNamed),
        ("Sound", PDActionSound),
        ("Movie", PDActionMovie),
        ("ImportData", PDActionImportData),
        ("ResetForm", PDActionResetForm),
        ("Hide", PDActionHide),
        ("SubmitForm", PDActionSubmitForm),
        ("Thread", PDActionThread),
        ("GoToE", PDActionEmbeddedGoTo),
    ],
)
def test_create_action_dispatches_each_subtype(sub_type, expected_cls):
    action = PDActionFactory.create_action(_make(sub_type))
    assert isinstance(action, expected_cls)
    assert action.get_sub_type() == sub_type


def test_create_action_null_dictionary_returns_none():
    assert PDActionFactory.create_action(None) is None


def test_create_action_missing_subtype_returns_none():
    # /S is missing — upstream's `getNameAsString(COSName.S)` returns null,
    # the switch default branch leaves `retval = null`.
    d = COSDictionary()
    assert PDActionFactory.create_action(d) is None


def test_create_action_unknown_subtype_returns_none():
    # /S = /Foo — falls through every branch of the switch.
    assert PDActionFactory.create_action(_make("Foo")) is None


def test_create_action_sub_type_constants_match_factory():
    # SUB_TYPE constants on each PDAction subclass must equal the dispatch
    # keys baked into PDActionFactory.create_action — upstream parity.
    assert PDActionJavaScript.SUB_TYPE == "JavaScript"
    assert PDActionGoTo.SUB_TYPE == "GoTo"
    assert PDActionLaunch.SUB_TYPE == "Launch"
    assert PDActionRemoteGoTo.SUB_TYPE == "GoToR"
    assert PDActionURI.SUB_TYPE == "URI"
    assert PDActionNamed.SUB_TYPE == "Named"
    assert PDActionSound.SUB_TYPE == "Sound"
    assert PDActionMovie.SUB_TYPE == "Movie"
    assert PDActionImportData.SUB_TYPE == "ImportData"
    assert PDActionResetForm.SUB_TYPE == "ResetForm"
    assert PDActionHide.SUB_TYPE == "Hide"
    assert PDActionSubmitForm.SUB_TYPE == "SubmitForm"
    assert PDActionThread.SUB_TYPE == "Thread"
    assert PDActionEmbeddedGoTo.SUB_TYPE == "GoToE"


def test_factory_is_utility_class():
    # Upstream marks PDActionFactory as a utility class with a private
    # no-arg constructor. The Python mirror raises TypeError on
    # instantiation.
    with pytest.raises(TypeError):
        PDActionFactory()
