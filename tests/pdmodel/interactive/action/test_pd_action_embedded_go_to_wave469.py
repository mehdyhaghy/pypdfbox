from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.open_mode import OpenMode
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)

_D = COSName.get_pdf_name("D")
_F = COSName.get_pdf_name("F")
_NEW_WINDOW = COSName.get_pdf_name("NewWindow")
_S = COSName.get_pdf_name("S")
_T = COSName.get_pdf_name("T")


def test_wave469_presence_predicates_track_clear_methods() -> None:
    action = PDActionEmbeddedGoTo()
    assert action.is_valid() is True
    assert action.is_empty() is True

    fs = PDComplexFileSpecification()
    fs.set_file("attachments/child.pdf")
    destination = PDPageFitDestination()
    destination.set_page_number(2)
    target = PDTargetDirectory()
    target.set_target_filename("child.pdf")

    action.set_file(fs)
    action.set_destination(destination)
    action.set_target_directory(target)
    action.set_open_in_new_window(True)

    assert action.has_file() is True
    assert action.has_destination() is True
    assert action.has_target_directory() is True
    assert action.has_new_window() is True
    assert action.is_open_in_new_window() is True
    assert action.is_empty() is False

    action.clear_file()
    action.clear_destination()
    action.clear_target_directory()
    action.clear_new_window()

    assert action.get_file() is None
    assert action.get_destination() is None
    assert action.get_target_directory() is None
    assert action.has_new_window() is False
    assert action.is_open_in_user_preference() is True
    assert action.is_empty() is True


def test_wave469_open_mode_setter_preserves_tristate_semantics() -> None:
    action = PDActionEmbeddedGoTo()
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE

    action.set_open_in_new_window(OpenMode.SAME_WINDOW)
    assert action.get_open_in_new_window() is False
    assert action.get_open_in_new_window_mode() is OpenMode.SAME_WINDOW
    assert action.is_open_in_same_window() is True
    assert action.get_cos_object().contains_key(_NEW_WINDOW)

    action.set_open_in_new_window(OpenMode.NEW_WINDOW)
    assert action.get_open_in_new_window() is True
    assert action.get_open_in_new_window_mode() is OpenMode.NEW_WINDOW

    action.set_open_in_new_window(OpenMode.USER_PREFERENCE)
    assert not action.get_cos_object().contains_key(_NEW_WINDOW)
    assert action.get_open_in_new_window() is False
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE

    action.set_open_in_new_window(True)
    action.set_open_in_new_window(None)
    assert action.get_open_in_new_window_mode() is OpenMode.USER_PREFERENCE


def test_wave469_non_dictionary_target_reports_absent_but_preserves_raw_entry() -> None:
    action = PDActionEmbeddedGoTo()
    action.get_cos_object().set_item(_T, COSString("not a target dictionary"))

    assert action.get_target() is None
    assert action.has_target() is False
    assert action.has_target_directory() is False
    assert action.get_cos_object().get_dictionary_object(_T) is not None


def test_wave469_set_target_accepts_raw_cos_dictionary() -> None:
    raw_target = COSDictionary()
    raw_target.set_name("R", "P")
    raw_target.set_string("N", "parent.pdf")
    action = PDActionEmbeddedGoTo()

    action.set_target(raw_target)

    target = action.get_target_directory()
    assert target is not None
    assert target.get_cos_object() is raw_target
    rel = target.get_relationship()
    assert rel is not None and rel.get_name() == "P"
    assert target.get_target_filename() == "parent.pdf"


def test_wave469_walk_to_target_collects_nested_snapshot_values() -> None:
    root = PDTargetDirectory()
    root.set_target_filename("child.pdf")
    root.set_page_number(4)
    root.set_annotation_number(1)

    nested = PDTargetDirectory()
    nested.set_relationship("P")
    nested.set_target_filename("parent.pdf")
    nested.set_named_destination("chapter-2")
    root.set_target_directory(nested)

    action = PDActionEmbeddedGoTo()
    action.set_target_directory(root)

    steps = action.walk_to_target()

    assert [step.relationship for step in steps] == ["C", "P"]
    assert steps[0].target_filename == "child.pdf"
    assert steps[0].page_number == 4
    assert steps[0].named_destination is None
    assert steps[0].annotation_number == 1
    assert steps[1].target_filename == "parent.pdf"
    assert steps[1].page_number is None
    assert steps[1].named_destination == "chapter-2"
    assert steps[1].annotation_number is None


def test_wave469_null_setters_remove_backing_entries() -> None:
    action = PDActionEmbeddedGoTo()
    fs = PDComplexFileSpecification()
    fs.set_file("payload.pdf")
    action.set_file(fs)
    action.set_d(PDNamedDestination("Dest"))
    action.set_target(PDTargetDirectory())
    action.set_new_window(False)

    action.set_file(None)
    action.set_d(None)
    action.set_target(None)
    action.clear_new_window()

    cos = action.get_cos_object()
    assert not cos.contains_key(_F)
    assert not cos.contains_key(_D)
    assert not cos.contains_key(_T)
    assert not cos.contains_key(_NEW_WINDOW)


def test_wave469_is_valid_reflects_wrapped_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "GoToR")

    assert PDActionEmbeddedGoTo(raw).is_valid() is False
