"""Round-out tests for :class:`PDActionRemoteGoTo` covering:

- typed destination accessor :meth:`set_destination`
- typed file-spec accessors :meth:`get_file_specification` /
  :meth:`set_file_specification`
- ``/NewWindow`` accessors :meth:`get_new_window` / :meth:`set_new_window`
  and the upstream-spelling aliases.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSInteger, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action import PDActionRemoteGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)

_F: COSName = COSName.get_pdf_name("F")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_NEW_WINDOW: COSName = COSName.get_pdf_name("NewWindow")


def test_default_subtype_is_gotor() -> None:
    action = PDActionRemoteGoTo()
    assert action.get_sub_type() == "GoToR"


# /F ---------------------------------------------------------------------


def test_set_file_string_round_trip() -> None:
    """Backwards-compatible string path mirrors upstream ``setF(String)``."""
    action = PDActionRemoteGoTo()
    action.set_file("other.pdf")

    assert action.get_file() == "other.pdf"


def test_set_file_with_pd_file_specification_round_trip() -> None:
    action = PDActionRemoteGoTo()
    fs_in = PDSimpleFileSpecification()
    fs_in.set_file("attached.pdf")
    action.set_file(fs_in)

    fs_out = action.get_file_specification()
    assert isinstance(fs_out, PDFileSpecification)
    assert fs_out.get_file() == "attached.pdf"


def test_get_file_specification_returns_none_when_absent() -> None:
    action = PDActionRemoteGoTo()
    assert action.get_file_specification() is None


def test_set_file_specification_round_trip() -> None:
    action = PDActionRemoteGoTo()
    fs_in = PDSimpleFileSpecification()
    fs_in.set_file("file.pdf")
    action.set_file_specification(fs_in)

    fs_out = action.get_file_specification()
    assert isinstance(fs_out, PDFileSpecification)
    assert fs_out.get_file() == "file.pdf"


def test_set_file_none_removes_f() -> None:
    action = PDActionRemoteGoTo()
    action.set_file("other.pdf")
    assert action.get_cos_object().contains_key(_F)

    action.set_file(None)
    assert not action.get_cos_object().contains_key(_F)
    assert action.get_file() is None


def test_set_file_specification_none_removes_f() -> None:
    action = PDActionRemoteGoTo()
    fs = PDSimpleFileSpecification()
    fs.set_file("foo.pdf")
    action.set_file_specification(fs)
    assert action.get_cos_object().contains_key(_F)

    action.set_file_specification(None)
    assert not action.get_cos_object().contains_key(_F)


# /D — typed setter ------------------------------------------------------


def test_set_destination_with_pd_destination_round_trip() -> None:
    action = PDActionRemoteGoTo()
    dest = PDPageXYZDestination()
    dest.set_page_number(7)
    action.set_destination(dest)

    resolved = action.get_destination()
    assert isinstance(resolved, PDDestination)
    assert isinstance(resolved, PDPageXYZDestination)
    assert resolved.get_page_number() == 7


def test_set_destination_with_string_writes_named_destination() -> None:
    action = PDActionRemoteGoTo()
    action.set_destination("Chapter9")

    assert action.get_destination() == "Chapter9"
    raw = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(raw, COSString)


def test_set_destination_with_cos_array_dispatches_to_pd_destination() -> None:
    action = PDActionRemoteGoTo()
    arr = COSArray([COSInteger.get(0), COSName.get_pdf_name("XYZ")])
    action.set_destination(arr)

    resolved = action.get_destination()
    assert isinstance(resolved, PDPageXYZDestination)


def test_set_destination_none_removes_d() -> None:
    action = PDActionRemoteGoTo()
    action.set_destination("Chapter9")
    assert action.get_cos_object().contains_key(_D)

    action.set_destination(None)
    assert not action.get_cos_object().contains_key(_D)
    assert action.get_destination() is None


# /NewWindow -------------------------------------------------------------


def test_get_new_window_default_is_false_when_absent() -> None:
    action = PDActionRemoteGoTo()
    assert action.get_new_window() is False
    assert action.should_open_in_new_window() is False


def test_set_new_window_round_trips() -> None:
    action = PDActionRemoteGoTo()

    action.set_new_window(True)
    assert action.get_new_window() is True
    assert action.should_open_in_new_window() is True

    action.set_new_window(False)
    assert action.get_new_window() is False


def test_set_open_in_new_window_alias_round_trips() -> None:
    action = PDActionRemoteGoTo()

    action.set_open_in_new_window(True)
    assert action.get_new_window() is True

    action.set_open_in_new_window(False)
    assert action.get_new_window() is False


def test_new_window_stored_as_cos_boolean() -> None:
    action = PDActionRemoteGoTo()
    action.set_new_window(True)
    raw = action.get_cos_object().get_item(_NEW_WINDOW)
    assert isinstance(raw, COSBoolean)
