"""Upstream-parity port for ``PDActionGoTo``.

Mirrors ``PDActionGoTo.java`` (PDFBox 3.0.x). Upstream ships no JUnit
test for the GoTo wrapper — this module ports the source's behavioural
contract: SUB_TYPE stamp, /D destination dispatch (array vs name vs
string), and the IllegalArgumentException raised when a page destination
points at a non-page element.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_xyz_destination import (
    PDPageXYZDestination,
)

_S = COSName.get_pdf_name("S")
_D = COSName.get_pdf_name("D")


def test_default_constructor_stamps_subtype():
    action = PDActionGoTo()
    assert action.get_sub_type() == "GoTo"
    assert action.get_cos_object().get_name(_S) == "GoTo"


def test_get_destination_returns_none_when_missing():
    action = PDActionGoTo()
    assert action.get_destination() is None


def test_set_destination_to_page_fit_dest_writes_array():
    # Upstream: setDestination for a PDPageDestination unwraps the COSArray
    # and writes it directly to /D.
    action = PDActionGoTo()
    dest = PDPageFitDestination()
    # Page slot empty → seed with a dummy page dict so the validation
    # branch in setDestination accepts the destination.
    page = COSDictionary()
    page.set_name(COSName.get_pdf_name("Type"), "Page")
    dest.set_page(page)
    action.set_destination(dest)
    payload = action.get_cos_object().get_dictionary_object(_D)
    assert isinstance(payload, COSArray)


def test_set_destination_rejects_non_page_dict_first_element():
    # Upstream raises IllegalArgumentException when the destination's
    # backing array has a non-COSDictionary first element. Python mirrors
    # this with ValueError.
    action = PDActionGoTo()
    dest = PDPageXYZDestination()
    # Replace the page slot with a COSInteger — invalid.
    dest.get_cos_object().set(0, COSInteger.get(42))
    with pytest.raises(ValueError, match="page dictionary"):
        action.set_destination(dest)


def test_set_destination_with_named_destination_string():
    # /D may be a string (named destination). Upstream stores via
    # ``setItem`` of the raw string; pypdfbox uses set_string. Either way
    # the round-trip recovers the name. getDestination dispatches the
    # string form through PDDestination.create → PDNamedDestination
    # (PDActionGoTo.java line 66-69), matching upstream exactly.
    action = PDActionGoTo()
    action.set_destination("Chapter1")
    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "Chapter1"


def test_set_destination_with_cos_array_passthrough():
    # Raw COSArray for /D — explicit page-target form per spec.
    action = PDActionGoTo()
    page = COSDictionary()
    page.set_name(COSName.get_pdf_name("Type"), "Page")
    arr = COSArray([page, COSName.get_pdf_name("Fit")])
    action.set_d(arr)
    payload = action.get_cos_object().get_dictionary_object(_D)
    assert payload is arr


def test_set_destination_none_removes_entry():
    action = PDActionGoTo()
    action.set_destination("Foo")
    resolved = action.get_destination()
    assert isinstance(resolved, PDNamedDestination)
    assert resolved.get_named_destination() == "Foo"
    action.set_destination(None)
    assert action.get_destination() is None


def test_sub_type_constant_equals_go_to():
    assert PDActionGoTo.SUB_TYPE == "GoTo"
