from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.interactive.action import (
    PDAction,
    PDActionGoTo,
    PDActionURI,
)
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageFitDestination,
    PDPageXYZDestination,
)


# ---------------------------------------------------------------- /Dest typed


def test_destination_default_none() -> None:
    ann = PDAnnotationLink()
    assert ann.get_destination() is None


def test_destination_explicit_array_round_trip() -> None:
    ann = PDAnnotationLink()
    dest = PDPageXYZDestination()
    dest.set_page_number(2)
    dest.set_left(10)
    dest.set_top(20)
    ann.set_destination(dest)
    rt = ann.get_destination()
    assert isinstance(rt, PDPageXYZDestination)
    assert rt.get_page_number() == 2
    assert rt.get_left() == 10
    assert rt.get_top() == 20


def test_destination_named_via_pd_destination_round_trip() -> None:
    ann = PDAnnotationLink()
    named = PDNamedDestination("toc")
    ann.set_destination(named)
    rt = ann.get_destination()
    assert isinstance(rt, PDNamedDestination)
    assert rt.get_named_destination() == "toc"


def test_destination_named_from_string_round_trip() -> None:
    ann = PDAnnotationLink()
    ann.set_destination("Chapter1")
    rt = ann.get_destination()
    assert isinstance(rt, PDNamedDestination)
    assert rt.get_named_destination() == "Chapter1"


def test_destination_named_from_cos_name_round_trip() -> None:
    ann = PDAnnotationLink()
    ann.set_destination(COSName.get_pdf_name("AppendixA"))
    rt = ann.get_destination()
    assert isinstance(rt, PDNamedDestination)
    assert rt.get_named_destination() == "AppendixA"


def test_destination_named_from_cos_string_round_trip() -> None:
    ann = PDAnnotationLink()
    ann.set_destination(COSString("Foreword"))
    rt = ann.get_destination()
    assert isinstance(rt, PDNamedDestination)
    assert rt.get_named_destination() == "Foreword"


def test_destination_clear() -> None:
    ann = PDAnnotationLink()
    ann.set_destination("intro")
    ann.set_destination(None)
    assert ann.get_destination() is None
    assert ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Dest")) is None


def test_destination_typed_dispatch_matches_pd_destination_create() -> None:
    """Typed dispatch should be functionally equivalent to ``PDDestination.create``
    on the raw stored value."""
    ann = PDAnnotationLink()
    dest = PDPageFitDestination()
    dest.set_page_number(7)
    ann.set_destination(dest)
    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Dest"))
    rt_typed = ann.get_destination()
    rt_factory = PDDestination.create(raw)
    assert isinstance(rt_typed, PDPageFitDestination)
    assert isinstance(rt_factory, PDPageFitDestination)
    assert rt_typed.get_cos_object() is rt_factory.get_cos_object()


# ---------------------------------------------------------------- /H highlight


def test_highlight_mode_default_invert() -> None:
    ann = PDAnnotationLink()
    assert ann.get_highlight_mode() == "I"
    assert ann.get_highlight_mode() == PDAnnotationLink.HIGHLIGHT_MODE_INVERT


@pytest.mark.parametrize(
    "constant,expected",
    [
        (PDAnnotationLink.HIGHLIGHT_MODE_NONE, "N"),
        (PDAnnotationLink.HIGHLIGHT_MODE_INVERT, "I"),
        (PDAnnotationLink.HIGHLIGHT_MODE_OUTLINE, "O"),
        (PDAnnotationLink.HIGHLIGHT_MODE_PUSH, "P"),
    ],
)
def test_highlight_mode_constants_round_trip(constant: str, expected: str) -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode(constant)
    assert ann.get_highlight_mode() == expected
    assert ann.get_cos_object().get_name(COSName.get_pdf_name("H")) == expected


def test_highlight_mode_clear_returns_default() -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode(PDAnnotationLink.HIGHLIGHT_MODE_PUSH)
    ann.set_highlight_mode(None)
    assert ann.get_highlight_mode() == PDAnnotationLink.HIGHLIGHT_MODE_INVERT
    assert ann.get_cos_object().get_name(COSName.get_pdf_name("H")) is None


# ---------------------------------------------------------------- /QuadPoints


def test_quad_points_default_none() -> None:
    ann = PDAnnotationLink()
    assert ann.get_quad_points() is None


def test_quad_points_round_trip_list() -> None:
    ann = PDAnnotationLink()
    qp = [0.0, 0.0, 100.0, 0.0, 0.0, 50.0, 100.0, 50.0]
    ann.set_quad_points(qp)
    rt = ann.get_quad_points()
    assert rt == qp
    assert isinstance(rt, list)
    assert all(isinstance(v, float) for v in rt)


def test_quad_points_round_trip_tuple() -> None:
    ann = PDAnnotationLink()
    qp = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0)
    ann.set_quad_points(qp)
    rt = ann.get_quad_points()
    assert rt == list(qp)


def test_quad_points_persisted_as_cos_array_of_cos_floats() -> None:
    ann = PDAnnotationLink()
    ann.set_quad_points([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5])
    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("QuadPoints"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 8
    for entry in raw:
        assert isinstance(entry, COSFloat)


def test_quad_points_clear() -> None:
    ann = PDAnnotationLink()
    ann.set_quad_points([0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    ann.set_quad_points(None)
    assert ann.get_quad_points() is None
    assert ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("QuadPoints")) is None


def test_quad_points_accepts_cos_array_directly() -> None:
    ann = PDAnnotationLink()
    qp = COSArray.of_cos_floats([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    ann.set_quad_points(qp)
    rt = ann.get_quad_points()
    assert rt == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]


# ---------------------------------------------------------------- /PA preview


def test_p_a_default_none() -> None:
    ann = PDAnnotationLink()
    assert ann.get_p_a() is None


def test_p_a_round_trip() -> None:
    ann = PDAnnotationLink()
    preview = PDActionURI()
    preview.set_uri("https://preview.test")
    ann.set_p_a(preview)
    rt = ann.get_p_a()
    assert isinstance(rt, PDActionURI)
    assert rt.get_uri() == "https://preview.test"


def test_p_a_clear() -> None:
    ann = PDAnnotationLink()
    ann.set_p_a(PDActionURI())
    ann.set_p_a(None)
    assert ann.get_p_a() is None
    assert ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("PA")) is None


def test_p_a_accepts_raw_cos_dictionary() -> None:
    ann = PDAnnotationLink()
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("Action"))  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("S"), "URI")
    raw.set_string(COSName.get_pdf_name("URI"), "https://raw.test")
    ann.set_p_a(raw)
    rt = ann.get_p_a()
    assert isinstance(rt, PDActionURI)
    assert rt.get_uri() == "https://raw.test"


def test_p_a_independent_of_a() -> None:
    """``/A`` and ``/PA`` are independent slots — setting one does not
    leak into the other."""
    ann = PDAnnotationLink()
    main = PDActionGoTo()
    main.set_destination("toc")
    preview = PDActionURI()
    preview.set_uri("https://preview.test")
    ann.set_action(main)
    ann.set_p_a(preview)
    assert isinstance(ann.get_action(), PDActionGoTo)
    assert isinstance(ann.get_p_a(), PDActionURI)


# ---------------------------------------------------------------- /A → URL helper


def test_get_url_uri_when_action_is_uri() -> None:
    ann = PDAnnotationLink()
    action = PDActionURI()
    action.set_uri("https://example.test/path?q=1")
    ann.set_action(action)
    assert ann.get_url_uri() == "https://example.test/path?q=1"


def test_get_url_uri_returns_none_when_no_action() -> None:
    ann = PDAnnotationLink()
    assert ann.get_url_uri() is None


def test_get_url_uri_returns_none_when_action_is_not_uri() -> None:
    ann = PDAnnotationLink()
    goto = PDActionGoTo()
    goto.set_destination("Chapter1")
    ann.set_action(goto)
    assert ann.get_url_uri() is None


def test_get_url_uri_returns_none_for_uri_action_without_uri_entry() -> None:
    ann = PDAnnotationLink()
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("Action"))  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("S"), "URI")
    ann.set_action(raw)
    assert ann.get_url_uri() is None


def test_get_url_uri_via_raw_dict_subtype() -> None:
    """``get_url_uri`` should not require a typed ``PDActionURI`` —
    it inspects the raw ``/A`` dictionary's ``/S`` and ``/URI``."""
    ann = PDAnnotationLink()
    raw = COSDictionary()
    raw.set_item(COSName.TYPE, COSName.get_pdf_name("Action"))  # type: ignore[attr-defined]
    raw.set_name(COSName.get_pdf_name("S"), "URI")
    raw.set_string(COSName.get_pdf_name("URI"), "https://raw-url.test")
    ann.set_action(raw)
    assert ann.get_url_uri() == "https://raw-url.test"


# ---------------------------------------------------------------- typed action factories


def test_get_action_dispatches_via_pd_action_factory() -> None:
    """``get_action`` should return the concrete ``PDAction`` subclass for
    the stored ``/A`` ``/S`` subtype, mirroring upstream factory dispatch."""
    ann = PDAnnotationLink()
    ann.set_action(PDActionURI())
    rt = ann.get_action()
    assert isinstance(rt, PDActionURI)
    assert isinstance(rt, PDAction)


# ---------------------------------------------------------------- /PA upstream-named aliases


def test_get_previous_uri_default_none() -> None:
    """``get_previous_uri`` mirrors upstream ``getPreviousURI()`` —
    returns ``None`` when ``/PA`` is absent."""
    ann = PDAnnotationLink()
    assert ann.get_previous_uri() is None


def test_set_previous_uri_round_trip() -> None:
    """``set_previous_uri`` mirrors upstream ``setPreviousURI(PDActionURI)``
    and writes the action under ``/PA``."""
    ann = PDAnnotationLink()
    action = PDActionURI()
    action.set_uri("https://prev.test")
    ann.set_previous_uri(action)
    rt = ann.get_previous_uri()
    assert isinstance(rt, PDActionURI)
    assert rt.get_uri() == "https://prev.test"


def test_previous_uri_alias_writes_same_pa_entry() -> None:
    """``set_previous_uri`` and ``set_p_a`` must write the same ``/PA``
    entry — they are simply different names for the same accessor."""
    ann_a = PDAnnotationLink()
    ann_b = PDAnnotationLink()
    action_a = PDActionURI()
    action_a.set_uri("https://a.test")
    action_b = PDActionURI()
    action_b.set_uri("https://a.test")
    ann_a.set_p_a(action_a)
    ann_b.set_previous_uri(action_b)
    assert (
        ann_a.get_cos_object().get_dictionary_object(  # type: ignore[attr-defined]
            COSName.get_pdf_name("PA")
        )
        is not None
    )
    assert (
        ann_b.get_cos_object().get_dictionary_object(  # type: ignore[attr-defined]
            COSName.get_pdf_name("PA")
        )
        is not None
    )
    # Cross-read: setter via one name, getter via the other.
    assert ann_a.get_previous_uri() is not None
    assert ann_b.get_p_a() is not None


def test_previous_uri_clear_via_alias() -> None:
    ann = PDAnnotationLink()
    ann.set_previous_uri(PDActionURI())
    ann.set_previous_uri(None)
    assert ann.get_previous_uri() is None
    assert ann.get_p_a() is None
