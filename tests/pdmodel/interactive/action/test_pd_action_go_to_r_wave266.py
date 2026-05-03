"""Wave 266 round-out tests for :class:`PDActionRemoteGoTo`.

Covers the new ``has_*`` / ``clear_*`` / ``is_empty`` / ``is_valid``
predicates that round out the upstream-parity surface (mirroring the
matching cluster on :class:`PDActionEmbeddedGoTo`).
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action import PDActionRemoteGoTo
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)

_F: COSName = COSName.get_pdf_name("F")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_NEW_WINDOW: COSName = COSName.get_pdf_name("NewWindow")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_S: COSName = COSName.get_pdf_name("S")


# ---- SUB_TYPE constant + defaults -----------------------------------------


def test_sub_type_constant_value() -> None:
    """The SUB_TYPE class constant is the spec-mandated ``"GoToR"``."""
    assert PDActionRemoteGoTo.SUB_TYPE == "GoToR"


def test_default_constructor_sets_type_action_and_s_gotor() -> None:
    """A fresh action carries both ``/Type /Action`` and ``/S /GoToR``."""
    action = PDActionRemoteGoTo()
    assert action.get_cos_object().get_name(_TYPE) == "Action"
    assert action.get_cos_object().get_name(_S) == "GoToR"
    assert action.get_sub_type() == PDActionRemoteGoTo.SUB_TYPE


def test_dict_constructor_does_not_overwrite_existing_subtype() -> None:
    """Mirrors upstream: the dict-arg constructor wraps verbatim."""
    raw = COSDictionary()
    raw.set_name(_S, "Custom")
    action = PDActionRemoteGoTo(raw)
    assert action.get_sub_type() == "Custom"


# ---- has_* predicates -----------------------------------------------------


def test_has_file_false_when_absent() -> None:
    action = PDActionRemoteGoTo()
    assert action.has_file() is False


def test_has_file_true_for_string_form() -> None:
    action = PDActionRemoteGoTo()
    action.set_file("other.pdf")
    assert action.has_file() is True


def test_has_file_true_for_filespec_form() -> None:
    action = PDActionRemoteGoTo()
    fs = PDSimpleFileSpecification()
    fs.set_file("attached.pdf")
    action.set_file_specification(fs)
    assert action.has_file() is True


def test_has_destination_false_when_absent() -> None:
    action = PDActionRemoteGoTo()
    assert action.has_destination() is False


def test_has_destination_true_for_named_destination() -> None:
    action = PDActionRemoteGoTo()
    action.set_destination("Chapter9")
    assert action.has_destination() is True


def test_has_destination_true_for_explicit_destination() -> None:
    action = PDActionRemoteGoTo()
    dest = PDPageXYZDestination()
    dest.set_page_number(3)
    action.set_destination(dest)
    assert action.has_destination() is True


def test_has_new_window_false_when_absent() -> None:
    action = PDActionRemoteGoTo()
    assert action.has_new_window() is False


def test_has_new_window_true_when_set_true() -> None:
    action = PDActionRemoteGoTo()
    action.set_new_window(True)
    assert action.has_new_window() is True


def test_has_new_window_true_when_set_false() -> None:
    """Presence is independent of value — explicit ``false`` still counts."""
    action = PDActionRemoteGoTo()
    action.set_new_window(False)
    assert action.has_new_window() is True


# ---- clear_* removers -----------------------------------------------------


def test_clear_file_removes_f() -> None:
    action = PDActionRemoteGoTo()
    action.set_file("foo.pdf")
    assert action.has_file() is True

    action.clear_file()
    assert action.has_file() is False
    assert action.get_file() is None


def test_clear_file_idempotent_when_absent() -> None:
    action = PDActionRemoteGoTo()
    action.clear_file()  # no-op
    assert action.has_file() is False


def test_clear_destination_removes_d() -> None:
    action = PDActionRemoteGoTo()
    action.set_destination("Chapter1")
    assert action.has_destination() is True

    action.clear_destination()
    assert action.has_destination() is False
    assert action.get_destination() is None


def test_clear_new_window_removes_entry() -> None:
    action = PDActionRemoteGoTo()
    action.set_new_window(True)
    assert action.has_new_window() is True

    action.clear_new_window()
    assert action.has_new_window() is False
    assert action.get_open_in_new_window() is OpenMode.USER_PREFERENCE


# ---- is_empty -------------------------------------------------------------


def test_is_empty_true_for_fresh_action() -> None:
    action = PDActionRemoteGoTo()
    assert action.is_empty() is True


def test_is_empty_false_when_only_file_present() -> None:
    action = PDActionRemoteGoTo()
    action.set_file("doc.pdf")
    assert action.is_empty() is False


def test_is_empty_false_when_only_destination_present() -> None:
    action = PDActionRemoteGoTo()
    action.set_destination("Chapter1")
    assert action.is_empty() is False


def test_is_empty_false_when_only_new_window_present() -> None:
    action = PDActionRemoteGoTo()
    action.set_new_window(True)
    assert action.is_empty() is False


def test_is_empty_true_after_clearing_all_entries() -> None:
    action = PDActionRemoteGoTo()
    action.set_file("doc.pdf")
    action.set_destination("Chapter9")
    action.set_new_window(True)
    assert action.is_empty() is False

    action.clear_file()
    action.clear_destination()
    action.clear_new_window()
    assert action.is_empty() is True


# ---- is_valid -------------------------------------------------------------


def test_is_valid_true_for_fresh_action() -> None:
    action = PDActionRemoteGoTo()
    assert action.is_valid() is True


def test_is_valid_false_when_subtype_overridden() -> None:
    action = PDActionRemoteGoTo()
    action.set_sub_type("GoTo")
    assert action.is_valid() is False
