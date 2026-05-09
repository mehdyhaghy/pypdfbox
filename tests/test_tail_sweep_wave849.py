from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
)
from pypdfbox.pdmodel.interactive.pagenavigation.pd_thread import PDThread
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition import PDTransition
from pypdfbox.pdmodel.interactive.pagenavigation.pd_transition_direction import (
    PDTransitionDirection,
)
from pypdfbox.pdmodel.pd_developer_extension import PDDeveloperExtension
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_wave849_cid_to_gid_map_defaults_to_identity_when_absent() -> None:
    font = PDCIDFont()

    assert font.is_identity_cid_to_gid_map() is True


def test_wave849_transition_direction_falls_back_for_unparseable_cos_value() -> None:
    transition = PDTransition()
    transition.get_cos_object().set_item(COSName.get_pdf_name("Di"), COSString("bad"))

    assert transition.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT


def test_wave849_pd_thread_equality_short_circuits_same_wrapper() -> None:
    thread = PDThread()

    assert thread == thread


def test_wave849_developer_extension_cos_dictionary_alias_returns_wrapped_dict() -> None:
    dictionary = COSDictionary()
    extension = PDDeveloperExtension(dictionary)

    assert extension.get_cos_dictionary() is dictionary


def test_wave849_rectangle_repr_includes_normalized_float_coordinates() -> None:
    rect = PDRectangle(1, 2, 3, 4)

    assert repr(rect) == "PDRectangle(1.0, 2.0, 3.0, 4.0)"


def test_wave849_destination_unset_predicates_handle_short_arrays() -> None:
    assert PDPageFitHeightDestination(COSArray()).is_left_unset() is True
    assert PDPageFitWidthDestination(COSArray()).is_top_unset() is True
    assert PDPageFitRectangleDestination(COSArray()).is_right_unset() is True
