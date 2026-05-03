"""Wave 268 round-out — fill in the remaining cold gaps on
:class:`PDActionEmbeddedGoTo` so it matches the parity surface already
present on :class:`PDActionRemoteGoTo`: ``has_new_window``,
``clear_file`` / ``clear_destination`` / ``clear_target`` /
``clear_target_directory`` / ``clear_new_window``, and ``is_empty``."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)

_F = COSName.get_pdf_name("F")
_D = COSName.D  # type: ignore[attr-defined]
_T = COSName.get_pdf_name("T")
_NEW_WINDOW = COSName.get_pdf_name("NewWindow")


# ---------- has_new_window ----------


def test_has_new_window_false_when_absent_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    assert a.has_new_window() is False


def test_has_new_window_true_when_explicit_true_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    a.set_new_window(True)
    assert a.has_new_window() is True


def test_has_new_window_true_when_explicit_false_wave268() -> None:
    """``has_new_window`` reports presence, not value — explicit ``false``
    is also "present"."""
    a = PDActionEmbeddedGoTo()
    a.set_new_window(False)
    assert a.has_new_window() is True


# ---------- clear_* ----------


def test_clear_file_removes_entry_wave268() -> None:
    d = COSDictionary()
    d.set_string(_F, "embedded.pdf")
    a = PDActionEmbeddedGoTo(d)
    assert a.has_file() is True
    a.clear_file()
    assert a.has_file() is False
    assert d.get_dictionary_object(_F) is None


def test_clear_destination_removes_entry_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    dest.set_page_number(0)  # int form satisfies GoToE constraint
    a.set_destination(dest)
    assert a.has_destination() is True
    a.clear_destination()
    assert a.has_destination() is False


def test_clear_target_removes_entry_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    a.set_target(PDTargetDirectory())
    assert a.has_target() is True
    a.clear_target()
    assert a.has_target() is False


def test_clear_target_directory_alias_wave268() -> None:
    """Spec-named ``clear_target_directory`` mirrors ``clear_target``."""
    a = PDActionEmbeddedGoTo()
    a.set_target(PDTargetDirectory())
    assert a.has_target_directory() is True
    a.clear_target_directory()
    assert a.has_target_directory() is False


def test_clear_new_window_removes_entry_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    a.set_new_window(True)
    assert a.has_new_window() is True
    a.clear_new_window()
    assert a.has_new_window() is False


# ---------- is_empty ----------


def test_is_empty_default_wave268() -> None:
    """Fresh action has ``/S = GoToE`` only — no F/D/T/NewWindow yet."""
    a = PDActionEmbeddedGoTo()
    assert a.is_empty() is True


def test_is_empty_false_with_file_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    d = a.get_cos_object()
    d.set_string(_F, "embedded.pdf")
    assert a.is_empty() is False


def test_is_empty_false_with_destination_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    dest = PDPageFitDestination()
    dest.set_page_number(2)
    a.set_destination(dest)
    assert a.is_empty() is False


def test_is_empty_false_with_target_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    a.set_target(PDTargetDirectory())
    assert a.is_empty() is False


def test_is_empty_false_with_new_window_wave268() -> None:
    a = PDActionEmbeddedGoTo()
    a.set_new_window(False)  # even explicit-false counts as "present"
    assert a.is_empty() is False


def test_is_empty_true_after_clear_all_wave268() -> None:
    """Round-trip: setting then clearing every field returns ``is_empty``."""
    a = PDActionEmbeddedGoTo()
    a.get_cos_object().set_string(_F, "x.pdf")
    dest = PDPageFitDestination()
    dest.set_page_number(0)
    a.set_destination(dest)
    a.set_target(PDTargetDirectory())
    a.set_new_window(True)
    assert a.is_empty() is False

    a.clear_file()
    a.clear_destination()
    a.clear_target()
    a.clear_new_window()
    assert a.is_empty() is True
