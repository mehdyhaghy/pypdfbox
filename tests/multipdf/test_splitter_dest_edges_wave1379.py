"""Wave 1379 — Splitter destination edge-case rewrites.

Closes the DEFERRED entry "Splitter destination edge-case rewrites (full
§12.3.2.3 coverage beyond fix_destinations)" by exercising:

* Explicit fit-mode destinations (XYZ / Fit / FitH / FitV / FitR / FitB
  / FitBH / FitBV) survive an in-chunk split with coordinates preserved.
* GoToR / GoToE actions on chunk link annotations pass through untouched
  — the /F file reference is preserved verbatim because the target lives
  in a *different* document that the splitter never opens.
* Cross-chunk destinations can be opt-in retargeted via
  :meth:`Splitter.set_cross_chunk_destination_resolver` into ``/A GoToR``
  actions pointing at the sibling chunk file.
"""
from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
)
from pypdfbox.multipdf import Splitter
from pypdfbox.pdmodel.interactive.action import (
    PDActionGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    PDActionEmbeddedGoTo,
)
from pypdfbox.pdmodel.interactive.action.pd_action_remote_go_to import (
    PDActionRemoteGoTo,
)
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationLink
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageDestination,
    PDPageFitBoundingBoxDestination,
    PDPageFitBoundingBoxHeightDestination,
    PDPageFitBoundingBoxWidthDestination,
    PDPageFitDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
    PDPageXYZDestination,
)


def _make_doc(n_pages: int) -> PDDocument:
    doc = PDDocument()
    for i in range(n_pages):
        page = PDPage()
        s = COSStream()
        s.set_raw_data(b"% page " + str(i).encode("ascii") + b"\n")
        page.set_contents(s)
        doc.add_page(page)
    return doc


# ---------- explicit fit-mode preservation ----------------------------


def _xyz(page: PDPage) -> PDPageXYZDestination:
    dest = PDPageXYZDestination()
    dest.set_page(page)
    dest.set_left(50.0)
    dest.set_top(700.0)
    dest.set_zoom(1.5)
    return dest


def _fit(page: PDPage) -> PDPageFitDestination:
    dest = PDPageFitDestination()
    dest.set_page(page)
    return dest


def _fith(page: PDPage) -> PDPageFitWidthDestination:
    # /FitH top — page's top y-coordinate.
    dest = PDPageFitWidthDestination()
    dest.set_page(page)
    dest.set_top(660.0)
    return dest


def _fitv(page: PDPage) -> PDPageFitHeightDestination:
    # /FitV left — page's left x-coordinate.
    dest = PDPageFitHeightDestination()
    dest.set_page(page)
    dest.set_left(110.0)
    return dest


def _fitr(page: PDPage) -> PDPageFitRectangleDestination:
    # /FitR left bottom right top.
    dest = PDPageFitRectangleDestination()
    dest.set_page(page)
    dest.set_rect(10.0, 20.0, 200.0, 250.0)
    return dest


def _fitb(page: PDPage) -> PDPageFitBoundingBoxDestination:
    dest = PDPageFitBoundingBoxDestination()
    dest.set_page(page)
    return dest


def _fitbh(page: PDPage) -> PDPageFitBoundingBoxWidthDestination:
    dest = PDPageFitBoundingBoxWidthDestination()
    dest.set_page(page)
    dest.set_top(300.0)
    return dest


def _fitbv(page: PDPage) -> PDPageFitBoundingBoxHeightDestination:
    dest = PDPageFitBoundingBoxHeightDestination()
    dest.set_page(page)
    dest.set_left(75.0)
    return dest


@pytest.mark.parametrize(
    ("builder", "expected_type"),
    [
        (_xyz, "XYZ"),
        (_fit, "Fit"),
        (_fith, "FitH"),
        (_fitv, "FitV"),
        (_fitr, "FitR"),
        (_fitb, "FitB"),
        (_fitbh, "FitBH"),
        (_fitbv, "FitBV"),
    ],
    ids=[
        "xyz",
        "fit",
        "fith",
        "fitv",
        "fitr",
        "fitb",
        "fitbh",
        "fitbv",
    ],
)
def test_in_chunk_destination_preserves_fit_mode_and_coordinates(
    builder, expected_type
) -> None:
    """Every PDF 32000-1 §12.3.2.2 explicit-fit-mode destination survives
    an in-chunk split with the fit-type name + coordinates intact and the
    page slot rewritten to the cloned chunk page dict."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    dest = builder(src_pages[1])
    link = PDAnnotationLink()
    link.set_destination(dest)
    src_pages[0].set_annotations([link])

    chunks = Splitter().set_split_at_page(2).split(src)
    try:
        assert len(chunks) == 1
        imported_pages = list(chunks[0].get_pages())
        imported_link = imported_pages[0].get_annotations()[0]
        imported_dest = imported_link.get_destination()
        assert isinstance(imported_dest, PDPageDestination)
        array = imported_dest.get_cos_object()
        # Type name at [1] must survive verbatim.
        assert array.get(1) == COSName.get_pdf_name(expected_type)
        # Page slot at [0] must be the cloned chunk page.
        assert imported_dest.get_page() is imported_pages[1].get_cos_object()
        # Coordinates from index 2..n survive verbatim — same array length
        # as the source's destination array.
        src_array = dest.get_cos_object()
        assert array.size() == src_array.size()
        for i in range(2, src_array.size()):
            assert array.get(i) == src_array.get(i)
    finally:
        for c in chunks:
            c.close()
        src.close()


@pytest.mark.parametrize(
    "builder",
    [_xyz, _fith, _fitv, _fitr, _fitbh, _fitbv],
    ids=["xyz", "fith", "fitv", "fitr", "fitbh", "fitbv"],
)
def test_cross_chunk_destination_with_fit_coords_nulls_only_page_slot(
    builder,
) -> None:
    """When the target page lives in a different chunk, only the page
    slot at [0] is nulled — the fit-type name + coordinates are
    preserved on the cloned array so a downstream rewriter (or the
    wave-1379 resolver) can salvage them."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    dest = builder(src_pages[1])
    link = PDAnnotationLink()
    link.set_destination(dest)
    src_pages[0].set_annotations([link])

    chunks = Splitter().split(src)  # 1 page per chunk
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        imported_dest = imported_link.get_destination()
        assert isinstance(imported_dest, PDPageDestination)
        array = imported_dest.get_cos_object()
        # Page slot nulled.
        assert array.get(0) is COSNull.NULL
        # Fit name preserved.
        src_array = dest.get_cos_object()
        assert array.get(1) == src_array.get(1)
        # Coordinates preserved.
        for i in range(2, src_array.size()):
            assert array.get(i) == src_array.get(i)
    finally:
        for c in chunks:
            c.close()
        src.close()


# ---------- GoToR / GoToE pass-through --------------------------------


def test_goto_remote_action_passes_through_untouched() -> None:
    """A link with /A GoToR pointing at an *external* file is preserved
    verbatim — the splitter doesn't open or rewrite remote targets."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    action = PDActionRemoteGoTo()
    action.set_file("sibling.pdf")
    # Build an explicit /D = [3 /XYZ 50 700 1.5] payload to verify
    # cross-document destination arrays round-trip.
    remote_dest = COSArray()
    remote_dest.add(COSInteger.get(3))
    remote_dest.add(COSName.get_pdf_name("XYZ"))
    remote_dest.add(COSInteger.get(50))
    remote_dest.add(COSInteger.get(700))
    action.set_d(remote_dest)
    link = PDAnnotationLink()
    link.set_action(action)
    src_pages[0].set_annotations([link])

    chunks = Splitter().split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        imported_action = imported_link.get_action()
        assert isinstance(imported_action, PDActionRemoteGoTo)
        assert imported_action.get_file() == "sibling.pdf"
        d = imported_action.get_d()
        assert isinstance(d, COSArray)
        # Slot 0 is the integer page index in the target document and
        # MUST NOT be rewritten by fix_destinations (different /D target
        # scope from the splitter's local /D arrays).
        assert d.get(0) == COSInteger.get(3)
        assert d.get(1) == COSName.get_pdf_name("XYZ")
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_goto_embedded_action_passes_through_untouched() -> None:
    """GoToE actions (chained embedded GoTo) pass through unchanged —
    same reasoning as :func:`test_goto_remote_action_passes_through_untouched`,
    the destination scope lives in an embedded file the splitter does
    not (and cannot) introspect."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    action = PDActionEmbeddedGoTo()
    target = COSDictionary()
    target.set_name(COSName.get_pdf_name("R"), "C")
    target.set_string(COSName.get_pdf_name("N"), "attach.pdf")
    action.set_target(target)
    embedded_dest = COSArray()
    embedded_dest.add(COSInteger.get(0))
    embedded_dest.add(COSName.get_pdf_name("Fit"))
    action.get_cos_object().set_item(COSName.get_pdf_name("D"), embedded_dest)
    link = PDAnnotationLink()
    link.set_action(action)
    src_pages[0].set_annotations([link])

    chunks = Splitter().split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        imported_action = imported_link.get_action()
        assert isinstance(imported_action, PDActionEmbeddedGoTo)
        target_out = imported_action.get_target()
        assert target_out is not None
        rel = target_out.get_relationship()
        assert rel is not None and rel.get_name() == "C"
        assert target_out.get_target_filename() == "attach.pdf"
        d = imported_action.get_d()
        assert d is not None
    finally:
        for c in chunks:
            c.close()
        src.close()


# ---------- cross-chunk destination resolver --------------------------


def test_cross_chunk_resolver_default_is_none() -> None:
    sp = Splitter()
    assert sp.get_cross_chunk_destination_resolver() is None
    assert sp.has_cross_chunk_destination_resolver() is False


def test_cross_chunk_resolver_setter_round_trip_and_clear() -> None:
    sp = Splitter()
    callback: callable = lambda _dict: ("foo.pdf", 0)  # noqa: E731
    assert sp.set_cross_chunk_destination_resolver(callback) is sp
    assert sp.get_cross_chunk_destination_resolver() is callback
    assert sp.has_cross_chunk_destination_resolver() is True
    sp.set_cross_chunk_destination_resolver(None)
    assert sp.get_cross_chunk_destination_resolver() is None
    assert sp.has_cross_chunk_destination_resolver() is False


def test_cross_chunk_resolver_tuple_form_rewrites_link_to_remote_goto() -> None:
    """When a cross-chunk resolver returns ``(filename, page_index)``, the
    link's destination is rewritten as a ``/A GoToR`` action with ``/F``
    set to the filename and ``/D[0]`` set to the integer page index.
    Original fit-type name + coordinates are preserved."""
    src = _make_doc(3)
    src_pages = list(src.get_pages())
    # Link on page 0 → page 2 with /XYZ + coords.
    dest = _xyz(src_pages[2])
    link = PDAnnotationLink()
    link.set_destination(dest)
    src_pages[0].set_annotations([link])

    src_page2_dict = src_pages[2].get_cos_object()

    def resolver(target_page_dict):
        # Confirm we received the *source* dict, not a deep-copy.
        assert target_page_dict is src_page2_dict
        return ("chunk-3.pdf", 0)

    sp = Splitter().set_cross_chunk_destination_resolver(resolver)
    chunks = sp.split(src)
    try:
        # chunk[0] hosts the link; chunk[2] hosts the target — different chunks.
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        imported_action = imported_link.get_action()
        assert isinstance(imported_action, PDActionRemoteGoTo)
        assert imported_action.get_file() == "chunk-3.pdf"
        d = imported_action.get_d()
        assert isinstance(d, COSArray)
        assert d.get(0) == COSInteger.get(0)
        # Fit-type + coordinates preserved (PDPageXYZDestination stores the
        # left coordinate as a COSFloat regardless of the input type).
        assert d.get(1) == COSName.get_pdf_name("XYZ")
        left = d.get(2)
        assert float(left.float_value()) == 50.0  # type: ignore[union-attr]
        # /Dest stripped to avoid viewer ambiguity.
        assert imported_link.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("Dest")
        ) is None
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_string_form_uses_zero_page_index() -> None:
    """Returning a plain string is shorthand for ``(filename, 0)``."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    sp = Splitter().set_cross_chunk_destination_resolver(
        lambda _dict: "chunk-2.pdf"
    )
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        action = imported_link.get_action()
        assert isinstance(action, PDActionRemoteGoTo)
        assert action.get_file() == "chunk-2.pdf"
        d = action.get_d()
        assert isinstance(d, COSArray)
        assert d.get(0) == COSInteger.get(0)
        assert d.get(1) == COSName.get_pdf_name("Fit")
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_returning_none_falls_back_to_null_out() -> None:
    """When the resolver returns ``None`` the destination is nulled per the
    historical pre-1379 behaviour."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    sp = Splitter().set_cross_chunk_destination_resolver(lambda _dict: None)
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        # No GoToR injected.
        assert imported_link.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("A")
        ) is None
        dest = imported_link.get_destination()
        assert isinstance(dest, PDPageDestination)
        assert dest.get_cos_object().get(0) is COSNull.NULL
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_invalid_return_warns_and_nulls() -> None:
    """Resolver returning a value of an unsupported type falls back to
    the null-out behaviour and logs a warning."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    sp = Splitter().set_cross_chunk_destination_resolver(lambda _dict: 42)
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        dest = imported_link.get_destination()
        assert isinstance(dest, PDPageDestination)
        assert dest.get_cos_object().get(0) is COSNull.NULL
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_invalid_tuple_length_falls_back() -> None:
    """Resolver returning a tuple of unexpected length nulls out."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    sp = Splitter().set_cross_chunk_destination_resolver(
        lambda _dict: ("x.pdf",)
    )
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        dest = imported_link.get_destination()
        assert isinstance(dest, PDPageDestination)
        assert dest.get_cos_object().get(0) is COSNull.NULL
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_exception_is_caught_and_nulls_out() -> None:
    """An exception raised inside the user-supplied resolver doesn't
    bubble out of :meth:`Splitter.split` — the destination falls back to
    the null-out path."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    def boom(_dict):
        raise RuntimeError("resolver failed")

    sp = Splitter().set_cross_chunk_destination_resolver(boom)
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        dest = imported_link.get_destination()
        assert dest.get_cos_object().get(0) is COSNull.NULL
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_rewrites_a_goto_link_into_goto_r() -> None:
    """A link's ``/A`` GoTo action whose destination crosses a chunk
    boundary is rewritten into ``/A`` GoToR — overwriting the original
    GoTo on the link dict."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    action = PDActionGoTo()
    action.set_destination(_fit(src_pages[1]))
    link = PDAnnotationLink()
    link.set_action(action)
    src_pages[0].set_annotations([link])

    sp = Splitter().set_cross_chunk_destination_resolver(
        lambda _dict: ("chunk-2.pdf", 0)
    )
    chunks = sp.split(src)
    try:
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        imported_action = imported_link.get_action()
        # Note: ``/A`` got replaced — type is GoToR, not GoTo.
        assert isinstance(imported_action, PDActionRemoteGoTo)
        assert imported_action.get_file() == "chunk-2.pdf"
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_cross_chunk_resolver_keyed_by_page_dict_picks_correct_filename() -> None:
    """Resolver dispatch must be keyed by the source target page dict so
    multiple destinations can map to different chunk files."""
    src = _make_doc(3)
    src_pages = list(src.get_pages())

    link_to_p1 = PDAnnotationLink()
    link_to_p1.set_destination(_fit(src_pages[1]))
    link_to_p2 = PDAnnotationLink()
    link_to_p2.set_destination(_fit(src_pages[2]))
    src_pages[0].set_annotations([link_to_p1, link_to_p2])

    mapping = {
        id(src_pages[1].get_cos_object()): "chunk-2.pdf",
        id(src_pages[2].get_cos_object()): "chunk-3.pdf",
    }

    def resolver(target_page_dict):
        return mapping[id(target_page_dict)]

    sp = Splitter().set_cross_chunk_destination_resolver(resolver)
    chunks = sp.split(src)
    try:
        imported_annots = chunks[0].get_page(0).get_annotations()
        files = []
        for ann in imported_annots:
            action = ann.get_action()
            assert isinstance(action, PDActionRemoteGoTo)
            files.append(action.get_file())
        assert files == ["chunk-2.pdf", "chunk-3.pdf"]
    finally:
        for c in chunks:
            c.close()
        src.close()


def test_in_chunk_destination_skips_resolver_path() -> None:
    """The resolver MUST NOT be called for destinations whose target page
    lives in the same chunk — those rewrite to the cloned page dict
    directly."""
    src = _make_doc(2)
    src_pages = list(src.get_pages())
    link = PDAnnotationLink()
    link.set_destination(_fit(src_pages[1]))
    src_pages[0].set_annotations([link])

    calls = []

    def resolver(target_page_dict):
        calls.append(target_page_dict)
        return ("never.pdf", 0)

    sp = (
        Splitter()
        .set_split_at_page(2)
        .set_cross_chunk_destination_resolver(resolver)
    )
    chunks = sp.split(src)
    try:
        assert calls == []
        imported_link = chunks[0].get_page(0).get_annotations()[0]
        # No /A injected.
        assert imported_link.get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("A")
        ) is None
        dest = imported_link.get_destination()
        assert dest.get_page() is chunks[0].get_page(1).get_cos_object()
    finally:
        for c in chunks:
            c.close()
        src.close()
