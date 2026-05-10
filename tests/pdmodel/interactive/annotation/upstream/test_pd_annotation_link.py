"""Parity tests for ``PDAnnotationLink``.

Upstream ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
annotation/`` does not currently ship a ``PDAnnotationLinkTest.java`` —
PDFBox covers the link-annotation surface only via the rendering tests
in ``rendering/`` (which we cannot port without the appearance-handler
stack). The asserts below pin the public-API behaviours documented on
``PDAnnotationLink.java`` (PDFBox 3.0.x) so any drift in our port
surfaces immediately.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationLink,
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
)


# Upstream PDAnnotationLink.java line ~52: SUB_TYPE = "Link".
def test_default_constructor_writes_link_subtype() -> None:
    ann: PDAnnotation = PDAnnotationLink()
    assert ann.get_subtype() == PDAnnotationLink.SUB_TYPE
    assert ann.get_cos_object().get_item(COSName.TYPE) == COSName.get_pdf_name("Annot")  # type: ignore[attr-defined]


# Upstream PDAnnotationLink.java line ~80: COSDictionary constructor.
def test_dict_constructor_preserves_dict_identity() -> None:
    raw = COSDictionary()
    raw.set_name(COSName.SUBTYPE, "Link")  # type: ignore[attr-defined]
    ann = PDAnnotationLink(raw)
    assert ann.get_cos_object() is raw


# Upstream PDAnnotationLink.java line ~89: getAction / setAction.
def test_action_round_trip() -> None:
    ann = PDAnnotationLink()
    action = PDActionURI()
    action.set_uri("https://example.test")
    ann.set_action(action)
    rt = ann.get_action()
    assert isinstance(rt, PDActionURI)
    assert rt.get_uri() == "https://example.test"


# Upstream PDAnnotationLink.java line ~115: setBorderStyle / getBorderStyle.
def test_border_style_round_trip() -> None:
    ann = PDAnnotationLink()
    bs = PDBorderStyleDictionary()
    ann.set_border_style(bs)
    rt = ann.get_border_style()
    assert isinstance(rt, PDBorderStyleDictionary)
    assert rt.get_cos_object() is bs.get_cos_object()


# Upstream PDAnnotationLink.java line ~138: getDestination / setDestination.
def test_destination_round_trip() -> None:
    ann = PDAnnotationLink()
    dest = PDPageFitDestination()
    dest.set_page_number(2)
    ann.set_destination(dest)
    rt = ann.get_destination()
    assert isinstance(rt, PDPageFitDestination)
    assert rt.get_page_number() == 2


# Upstream PDAnnotationLink.java line ~158: getHighlightMode default INVERT.
def test_highlight_mode_default_invert() -> None:
    ann = PDAnnotationLink()
    assert ann.get_highlight_mode() == PDAnnotationLink.HIGHLIGHT_MODE_INVERT


# Upstream PDAnnotationLink.java line ~167: setHighlightMode.
def test_highlight_mode_round_trip() -> None:
    ann = PDAnnotationLink()
    ann.set_highlight_mode(PDAnnotationLink.HIGHLIGHT_MODE_PUSH)
    assert ann.get_highlight_mode() == "P"


# Upstream PDAnnotationLink.java line ~177: setPreviousURI / getPreviousURI.
def test_previous_uri_round_trip() -> None:
    ann = PDAnnotationLink()
    pa = PDActionURI()
    pa.set_uri("https://prev.test")
    ann.set_previous_uri(pa)
    rt = ann.get_previous_uri()
    assert isinstance(rt, PDActionURI)
    assert rt.get_uri() == "https://prev.test"


# Upstream PDAnnotationLink.java line ~196: setQuadPoints / getQuadPoints.
def test_quad_points_round_trip() -> None:
    ann = PDAnnotationLink()
    qp = [0.0, 0.0, 100.0, 0.0, 0.0, 50.0, 100.0, 50.0]
    ann.set_quad_points(qp)
    assert ann.get_quad_points() == qp


# Upstream PDAnnotationLink.java line ~209: setCustomAppearanceHandler.
def test_custom_appearance_handler_round_trip() -> None:
    ann = PDAnnotationLink()
    assert ann.get_custom_appearance_handler() is None

    class _Handler:
        def __init__(self) -> None:
            self.calls = 0

        def generate_appearance_streams(self) -> None:
            self.calls += 1

    handler = _Handler()
    ann.set_custom_appearance_handler(handler)
    assert ann.get_custom_appearance_handler() is handler
    ann.set_custom_appearance_handler(None)
    assert ann.get_custom_appearance_handler() is None


# Upstream PDAnnotationLink.java line ~215: constructAppearances() and
# line ~221: constructAppearances(PDDocument). With no custom handler the
# call must not raise; with a custom handler it must dispatch through
# generate_appearance_streams().
def test_construct_appearances_without_custom_handler_is_noop() -> None:
    ann = PDAnnotationLink()
    ann.construct_appearances()
    ann.construct_appearances(None)


def test_construct_appearances_invokes_custom_handler() -> None:
    ann = PDAnnotationLink()

    class _Handler:
        def __init__(self) -> None:
            self.calls = 0

        def generate_appearance_streams(self) -> None:
            self.calls += 1

    handler = _Handler()
    ann.set_custom_appearance_handler(handler)
    ann.construct_appearances()
    ann.construct_appearances(None)
    assert handler.calls == 2
