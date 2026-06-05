from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_rendition import (
    PDActionRendition,
)
from pypdfbox.pdmodel.interactive.action.pd_action_thread import PDActionThread
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)

_AN = COSName.get_pdf_name("AN")
_D = COSName.D  # type: ignore[attr-defined]
_F = COSName.get_pdf_name("F")
_R = COSName.get_pdf_name("R")


def test_thread_file_setter_clears_and_accepts_raw_cos_entry() -> None:
    action = PDActionThread()
    raw = COSDictionary()

    action.set_file(raw)
    assert action.get_cos_object().get_dictionary_object(_F) is raw

    action.set_file(None)
    assert not action.get_cos_object().contains_key(_F)
    assert action.get_file() is None


def test_remote_go_to_raw_d_setter_clears_entry() -> None:
    action = PDActionRemoteGoTo()
    action.set_d(COSString("chapter"))
    assert action.get_cos_object().contains_key(_D)

    action.set_d(None)
    assert not action.get_cos_object().contains_key(_D)
    assert action.get_d() is None


def test_remote_go_to_destination_raises_for_unhandled_cos_shape() -> None:
    # Upstream parity (wave 1491): get_destination delegates to
    # PDDestination.create, which raises OSError (Java IOException) for a
    # /D that is neither an array nor a name/string — here a COSInteger.
    action = PDActionRemoteGoTo()
    action.set_d(COSInteger.get(3))

    assert action.get_d() == COSInteger.get(3)
    with pytest.raises(OSError, match="can't convert to Destination"):
        action.get_destination()


def test_rendition_action_annotation_and_rendition_accept_raw_cos_entries() -> None:
    action = PDActionRendition()
    raw_annotation = COSString("not-a-dictionary")
    raw_rendition = COSString("also-not-a-dictionary")

    action.set_annotation(raw_annotation)
    action.set_rendition(raw_rendition)

    assert action.get_cos_object().get_dictionary_object(_AN) is raw_annotation
    assert action.get_cos_object().get_dictionary_object(_R) is raw_rendition
    assert action.get_annotation() is None
    assert action.get_rendition() is None
    assert action.has_annotation() is False
    assert action.has_rendition() is False


def test_go_to_accepts_non_page_destination_subclass() -> None:
    action = PDActionGoTo()
    destination = PDNamedDestination("named-target")

    action.set_destination(destination)

    raw = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(raw, COSString)
    assert raw.get_string() == "named-target"
    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "named-target"


def test_go_to_rejects_page_destination_without_page_dictionary() -> None:
    from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
        PDPageXYZDestination,
    )

    action = PDActionGoTo()
    destination = PDPageXYZDestination()
    destination.set_page_number(0)

    with pytest.raises(ValueError, match="page dictionary"):
        action.set_destination(destination)
