"""Fuzz/parity tests for ``PDActionFactory`` dispatch, ``PDAction`` ``/Next``
chaining, ``PDActionURI`` / ``PDActionGoTo`` / ``PDActionNamed`` entries, and
``PDDestination`` resolution into the concrete page-destination subclasses.

All expectations are pinned to Apache PDFBox 3.0.7 behaviour:

* ``PDActionFactory.createAction`` switches on ``/S`` over a *fixed* set of 14
  subtypes (JavaScript, GoTo, Launch, GoToR, URI, Named, Sound, Movie,
  ImportData, ResetForm, Hide, SubmitForm, Thread, GoToE) and returns ``null``
  for everything else — including ``Trans``, ``SetOCGState``, ``Rendition``,
  ``GoTo3DView``, ``GoToDp``, ``RichMediaExecute`` and unknown names
  (``PDActionFactory.java`` lines 46-104).
* ``PDAction.getNext`` builds its list via ``PDActionFactory.createAction``, so
  a single ``/Next`` dict whose ``/S`` is unrecognised becomes ``[None]`` and an
  array keeps a ``None`` in each unrecognised slot (``PDAction.java``).
* ``PDActionURI.getURI`` decodes UTF-16 when a BOM is present, else UTF-8.
* ``PDDestination.create`` dispatches a ``COSArray`` (size > 1, item[1] a name)
  to the matching page-destination subclass, a ``COSString``/``COSName`` to a
  named destination, ``null`` to ``null``, and raises ``OSError`` otherwise.

Note on a deliberate, pre-existing pypdfbox divergence: the ``/XYZ`` /
``/FitH`` / ``/FitR`` coordinate getters return ``None`` for a missing/null slot
where upstream's ``getInt``-based getters return the ``-1`` sentinel. That
choice is established and tested elsewhere; these tests assert the pypdfbox
(``None``) contract.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
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
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageFitDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)


def _action(sub_type: str) -> COSDictionary:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), sub_type)
    return d


# ---------- PDActionFactory dispatch over /S ----------


@pytest.mark.parametrize(
    ("sub_type", "expected_cls"),
    [
        ("GoTo", PDActionGoTo),
        ("URI", PDActionURI),
        ("Launch", PDActionLaunch),
        ("GoToR", PDActionRemoteGoTo),
        ("Named", PDActionNamed),
        ("JavaScript", PDActionJavaScript),
        ("Thread", PDActionThread),
        ("Sound", PDActionSound),
        ("Movie", PDActionMovie),
        ("Hide", PDActionHide),
        ("SubmitForm", PDActionSubmitForm),
        ("ResetForm", PDActionResetForm),
        ("ImportData", PDActionImportData),
    ],
    ids=[
        "goto",
        "uri",
        "launch",
        "gotor",
        "named",
        "javascript",
        "thread",
        "sound",
        "movie",
        "hide",
        "submitform",
        "resetform",
        "importdata",
    ],
)
def test_factory_dispatches_known_subtype(sub_type: str, expected_cls: type) -> None:
    result = PDActionFactory.create_action(_action(sub_type))
    assert type(result) is expected_cls
    assert result.get_sub_type() == sub_type


def test_factory_dispatches_embedded_go_to() -> None:
    from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
        PDActionEmbeddedGoTo,
    )

    result = PDActionFactory.create_action(_action("GoToE"))
    assert type(result) is PDActionEmbeddedGoTo


@pytest.mark.parametrize(
    "sub_type",
    [
        "Trans",
        "SetOCGState",
        "Rendition",
        "GoTo3DView",
        "GoToDp",
        "RichMediaExecute",
        "Bogus",
        "goto",  # case-sensitive: lowercase is unknown
        "",
    ],
    ids=[
        "trans",
        "setocgstate",
        "rendition",
        "goto3dview",
        "gotodp",
        "richmediaexecute",
        "bogus",
        "lowercase_goto",
        "empty",
    ],
)
def test_factory_returns_none_for_unrecognised_subtype(sub_type: str) -> None:
    # Upstream's switch has no case for these → default → null.
    assert PDActionFactory.create_action(_action(sub_type)) is None


def test_factory_returns_none_for_missing_s() -> None:
    # No /S entry at all → getNameAsString returns null → null.
    assert PDActionFactory.create_action(COSDictionary()) is None


def test_factory_returns_none_for_none_input() -> None:
    assert PDActionFactory.create_action(None) is None


def test_factory_reads_s_stored_as_name() -> None:
    # /S is a COSName in conforming files; getNameAsString must read it.
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("URI"))
    assert type(PDActionFactory.create_action(d)) is PDActionURI


# ---------- /Next action chaining ----------


def test_get_next_absent_returns_none() -> None:
    assert PDActionGoTo().get_next() is None


def test_get_next_single_dict_wraps_in_one_element_list() -> None:
    base = PDActionGoTo()
    nxt = _action("URI")
    base.get_cos_object().set_item(COSName.get_pdf_name("Next"), nxt)
    chained = base.get_next()
    assert isinstance(chained, list)
    assert len(chained) == 1
    assert type(chained[0]) is PDActionURI


def test_get_next_single_unknown_dict_yields_list_with_none() -> None:
    base = PDActionGoTo()
    base.get_cos_object().set_item(COSName.get_pdf_name("Next"), _action("Trans"))
    chained = base.get_next()
    assert chained == [None]


def test_get_next_array_preserves_length_with_none_for_unknown() -> None:
    base = PDActionGoTo()
    arr = COSArray()
    arr.add(_action("URI"))
    arr.add(_action("Bogus"))  # unknown → None slot
    arr.add(_action("Named"))
    base.get_cos_object().set_item(COSName.get_pdf_name("Next"), arr)
    chained = base.get_next()
    assert len(chained) == 3
    assert type(chained[0]) is PDActionURI
    assert chained[1] is None
    assert type(chained[2]) is PDActionNamed


def test_get_next_array_non_dictionary_member_becomes_none() -> None:
    base = PDActionGoTo()
    arr = COSArray()
    arr.add(_action("GoTo"))
    arr.add(COSInteger.get(5))  # non-dict member
    base.get_cos_object().set_item(COSName.get_pdf_name("Next"), arr)
    chained = base.get_next()
    assert len(chained) == 2
    assert type(chained[0]) is PDActionGoTo
    assert chained[1] is None


def test_set_next_round_trips() -> None:
    base = PDActionGoTo()
    base.set_next([PDActionURI(), PDActionNamed()])
    chained = base.get_next()
    assert [type(a).__name__ for a in chained] == ["PDActionURI", "PDActionNamed"]


def test_set_next_none_removes_entry() -> None:
    base = PDActionGoTo()
    base.set_next([PDActionURI()])
    base.set_next(None)
    assert base.get_next() is None


# ---------- PDActionURI get/set + /IsMap ----------


def test_uri_set_get_round_trip() -> None:
    a = PDActionURI()
    a.set_uri("https://example.com/")
    assert a.get_uri() == "https://example.com/"


def test_uri_get_none_when_absent() -> None:
    assert PDActionURI().get_uri() is None


def test_uri_utf16_be_bom_decoded() -> None:
    a = PDActionURI()
    raw = b"\xfe\xff" + "http://x".encode("utf-16-be")
    a.get_cos_object().set_item(COSName.get_pdf_name("URI"), COSString(raw))
    assert a.get_uri() == "http://x"


def test_uri_plain_ascii_decoded_as_utf8() -> None:
    a = PDActionURI()
    a.get_cos_object().set_item(
        COSName.get_pdf_name("URI"), COSString(b"mailto:a@b.com")
    )
    assert a.get_uri() == "mailto:a@b.com"


def test_uri_non_cos_string_uri_returns_none() -> None:
    a = PDActionURI()
    a.get_cos_object().set_item(COSName.get_pdf_name("URI"), COSName.get_pdf_name("x"))
    assert a.get_uri() is None


def test_uri_is_map_defaults_false_and_round_trips() -> None:
    a = PDActionURI()
    assert a.get_is_map() is False
    a.set_is_map(True)
    assert a.get_is_map() is True
    assert a.should_track_mouse_position() is True


# ---------- PDActionGoTo /D destination ----------


def test_goto_destination_none_when_absent() -> None:
    assert PDActionGoTo().get_destination() is None


def test_goto_destination_named_from_cos_string() -> None:
    a = PDActionGoTo()
    a.get_cos_object().set_item(COSName.get_pdf_name("D"), COSString(b"Chapter1"))
    dest = a.get_destination()
    assert isinstance(dest, PDNamedDestination)
    assert dest.get_named_destination() == "Chapter1"


def test_goto_destination_page_array() -> None:
    a = PDActionGoTo()
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("Fit"))
    a.get_cos_object().set_item(COSName.get_pdf_name("D"), arr)
    dest = a.get_destination()
    assert isinstance(dest, PDPageFitDestination)


def test_goto_named_destination_string_accessor() -> None:
    a = PDActionGoTo()
    a.set_named_destination("Intro")
    assert a.get_named_destination() == "Intro"


# ---------- PDActionNamed /N ----------


def test_named_action_round_trip_and_predicate() -> None:
    a = PDActionNamed()
    a.set_n("NextPage")
    assert a.get_n() == "NextPage"
    assert a.is_next_page() is True
    assert a.is_standard_named_action() is True


def test_named_action_extension_name_not_standard() -> None:
    a = PDActionNamed()
    a.set_n("CustomViewerAction")
    assert a.is_standard_named_action() is False


# ---------- PDDestination.create: named vs page ----------


def test_create_none_returns_none() -> None:
    assert PDDestination.create(None) is None


def test_create_cos_string_is_named() -> None:
    dest = PDDestination.create(COSString(b"Dest1"))
    assert isinstance(dest, PDNamedDestination)
    assert dest.get_named_destination() == "Dest1"


def test_create_cos_name_is_named() -> None:
    dest = PDDestination.create(COSName.get_pdf_name("Dest2"))
    assert isinstance(dest, PDNamedDestination)
    assert dest.get_named_destination() == "Dest2"
    assert dest.is_name_form() is True


@pytest.mark.parametrize(
    ("type_name", "expected_cls"),
    [
        ("Fit", PDPageFitDestination),
        ("FitB", PDPageFitDestination),
        ("FitH", PDPageFitWidthDestination),
        ("FitBH", PDPageFitWidthDestination),
        ("FitV", PDPageFitHeightDestination),
        ("FitBV", PDPageFitHeightDestination),
        ("FitR", PDPageFitRectangleDestination),
        ("XYZ", PDPageXYZDestination),
    ],
    ids=["fit", "fitb", "fith", "fitbh", "fitv", "fitbv", "fitr", "xyz"],
)
def test_create_page_destination_by_type_name(
    type_name: str, expected_cls: type
) -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name(type_name))
    dest = PDDestination.create(arr)
    assert type(dest) is expected_cls
    assert dest.get_type() == type_name


def test_create_unknown_type_name_raises() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("FitNope"))
    with pytest.raises(OSError):
        PDDestination.create(arr)


def test_create_short_array_raises() -> None:
    # size <= 1 falls through the upstream chain to the final OSError.
    arr = COSArray()
    arr.add(COSInteger.get(0))
    with pytest.raises(OSError):
        PDDestination.create(arr)


def test_create_array_item1_not_name_raises() -> None:
    # item[1] not a COSName → not a page dest, not a string/name → OSError.
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSInteger.get(5))
    with pytest.raises(OSError):
        PDDestination.create(arr)


# ---------- XYZ coordinate parsing (left/top/zoom) ----------


def _xyz(left, top, zoom) -> PDPageXYZDestination:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("XYZ"))
    for v in (left, top, zoom):
        arr.add(COSNull.NULL if v is None else COSFloat(float(v)))
    return PDPageXYZDestination(arr)


def test_xyz_parses_left_top_zoom() -> None:
    d = _xyz(72.0, 540.0, 1.5)
    assert d.get_left() == 72.0
    assert d.get_top() == 540.0
    assert d.get_zoom() == 1.5


def test_xyz_null_slots_return_none() -> None:
    d = _xyz(None, None, None)
    assert d.get_left() is None
    assert d.get_top() is None
    assert d.get_zoom() is None


def test_xyz_zoom_zero_is_a_written_value_not_unset() -> None:
    # Zoom 0 means "retain current zoom" but it is still an explicit slot
    # value: upstream stores it verbatim and getZoom() returns 0.0.
    d = _xyz(10.0, 20.0, 0.0)
    assert d.get_zoom() == 0.0
    assert d.is_zoom_unset() is False


def test_xyz_short_array_left_top_zoom_unset() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("XYZ"))
    d = PDPageXYZDestination(arr)
    assert d.get_left() is None
    assert d.get_top() is None
    assert d.get_zoom() is None


# ---------- FitR rectangle coords ----------


def test_fitr_parses_four_edges() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("FitR"))
    arr.add(COSFloat(1.0))  # left
    arr.add(COSFloat(2.0))  # bottom
    arr.add(COSFloat(3.0))  # right
    arr.add(COSFloat(4.0))  # top
    d = PDPageFitRectangleDestination(arr)
    assert d.get_left() == 1.0
    assert d.get_bottom() == 2.0
    assert d.get_right() == 3.0
    assert d.get_top() == 4.0
    assert d.get_rect() == (1.0, 2.0, 3.0, 4.0)


def test_fitr_missing_edge_is_none() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("FitR"))
    arr.add(COSFloat(1.0))
    arr.add(COSNull.NULL)
    arr.add(COSFloat(3.0))
    # top slot omitted entirely (short array)
    d = PDPageFitRectangleDestination(arr)
    assert d.get_left() == 1.0
    assert d.get_bottom() is None
    assert d.get_right() == 3.0
    assert d.get_top() is None


# ---------- FitH (PDPageFitWidthDestination) top ----------


def test_fith_parses_top() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("FitH"))
    arr.add(COSFloat(700.0))
    d = PDPageFitWidthDestination(arr)
    assert d.get_top() == 700.0
    assert d.is_bounded() is False


def test_fitbh_is_bounded_variant() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("FitBH"))
    arr.add(COSFloat(700.0))
    d = PDPageFitWidthDestination(arr)
    assert d.is_bounded() is True
    assert d.get_top() == 700.0


# ---------- FitV (PDPageFitHeightDestination) left ----------


def test_fitv_parses_left() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("FitV"))
    arr.add(COSFloat(50.0))
    d = PDPageFitHeightDestination(arr)
    assert d.get_left() == 50.0
    assert d.is_bounded() is False


# ---------- page number / page object retrieval ----------


def test_retrieve_page_number_from_integer_slot() -> None:
    arr = COSArray()
    arr.add(COSInteger.get(7))
    arr.add(COSName.get_pdf_name("Fit"))
    d = PDPageFitDestination(arr)
    assert d.get_page_number() == 7
    assert d.retrieve_page_number() == 7
    assert d.has_page_number() is True
    assert d.has_page() is False


def test_page_object_slot_returns_dictionary() -> None:
    page = COSDictionary()
    page.set_name(COSName.TYPE, "Page")
    arr = COSArray()
    arr.add(page)
    arr.add(COSName.get_pdf_name("XYZ"))
    d = PDPageXYZDestination(arr)
    assert d.get_page() is page
    assert d.has_page() is True
    assert d.has_page_number() is False
    # No owning page tree / document context → -1.
    assert d.retrieve_page_number() == -1


def test_page_number_minus_one_when_slot_not_numeric() -> None:
    d = PDPageFitDestination(
        COSArray([COSNull.NULL, COSName.get_pdf_name("Fit")])
    )
    assert d.get_page_number() == -1
    assert d.find_page_number() == -1


# ---------- PDAction.create (base dispatch incl. unknown → PDActionUnknown) ----------


def test_pd_action_create_unknown_returns_unknown_wrapper() -> None:
    from pypdfbox.pdmodel.interactive.action.pd_action_unknown import PDActionUnknown

    # PDAction.create (distinct from the factory) wraps unknown /S in
    # PDActionUnknown rather than returning None.
    result = PDAction.create(_action("Bogus"))
    assert type(result) is PDActionUnknown


def test_pd_action_create_trans_is_known_to_base_create() -> None:
    from pypdfbox.pdmodel.interactive.action.pd_action_transition import (
        PDActionTransition,
    )

    # Trans is unknown to the factory but known to PDAction.create.
    result = PDAction.create(_action("Trans"))
    assert type(result) is PDActionTransition
