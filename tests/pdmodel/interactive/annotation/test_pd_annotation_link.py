from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
    PDPageFitDestination,
)


def test_default_constructor_sets_link_subtype() -> None:
    ann = PDAnnotationLink()
    assert ann.get_subtype() == "Link"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Link")  # type: ignore[attr-defined]
    ann = PDAnnotationLink(d)
    assert ann.get_subtype() == "Link"


def test_action_round_trip() -> None:
    ann = PDAnnotationLink()
    action = PDActionURI()
    action.set_uri("https://example.test")
    ann.set_action(action)
    rt = ann.get_action()
    assert isinstance(rt, PDActionURI)
    assert rt.get_uri() == "https://example.test"


def test_action_default_none() -> None:
    ann = PDAnnotationLink()
    assert ann.get_action() is None


def test_action_clear() -> None:
    ann = PDAnnotationLink()
    ann.set_action(PDActionURI())
    ann.set_action(None)
    assert ann.get_action() is None


def test_destination_array_round_trip() -> None:
    ann = PDAnnotationLink()
    dest = PDPageFitDestination()
    dest.set_page_number(4)
    ann.set_destination(dest)
    rt = ann.get_destination()
    assert isinstance(rt, PDPageFitDestination)
    assert rt.get_page_number() == 4


def test_destination_named_round_trip() -> None:
    ann = PDAnnotationLink()
    dest = COSName.get_pdf_name("Chapter1")
    ann.set_destination(dest)
    rt = ann.get_destination()
    assert isinstance(rt, PDNamedDestination)
    assert rt.get_named_destination() == "Chapter1"


def test_destination_default_none() -> None:
    ann = PDAnnotationLink()
    assert ann.get_destination() is None


def test_highlight_mode_default_invert() -> None:
    ann = PDAnnotationLink()
    assert ann.get_highlight_mode() == PDAnnotationLink.HIGHLIGHT_MODE_INVERT


def test_highlight_mode_round_trip() -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode(PDAnnotationLink.HIGHLIGHT_MODE_PUSH)
    assert ann.get_highlight_mode() == "P"
    ann.set_highlight_mode(PDAnnotationLink.HIGHLIGHT_MODE_NONE)
    assert ann.get_highlight_mode() == "N"
    ann.set_highlight_mode(PDAnnotationLink.HIGHLIGHT_MODE_OUTLINE)
    assert ann.get_highlight_mode() == "O"


def test_highlight_mode_clear_returns_default() -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode("P")
    ann.set_highlight_mode(None)
    assert ann.get_highlight_mode() == PDAnnotationLink.HIGHLIGHT_MODE_INVERT


def test_border_style_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.annotation import PDBorderStyleDictionary

    ann = PDAnnotationLink()
    bs = COSDictionary()
    bs.set_name(COSName.TYPE, "Border")  # type: ignore[attr-defined]
    bs.set_int(COSName.get_pdf_name("W"), 2)
    ann.set_border_style(bs)
    resolved = ann.get_border_style()
    assert isinstance(resolved, PDBorderStyleDictionary)
    assert resolved.get_cos_object() is bs


def test_border_style_default_none() -> None:
    ann = PDAnnotationLink()
    assert ann.get_border_style() is None


def test_quad_points_round_trip() -> None:
    ann = PDAnnotationLink()
    qp = COSArray.of_cos_floats([0.0, 0.0, 100.0, 0.0, 0.0, 50.0, 100.0, 50.0])
    ann.set_quad_points(qp)
    assert ann.get_quad_points() == [0.0, 0.0, 100.0, 0.0, 0.0, 50.0, 100.0, 50.0]


def test_subtype_constant() -> None:
    assert PDAnnotationLink.SUB_TYPE == "Link"
