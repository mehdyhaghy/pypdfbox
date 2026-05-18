"""Wave 1352 coverage-boost tests for :class:`pypdfbox.multipdf.Overlay`.

Closes the remaining uncovered public 1:1 upstream-named delegates:

* line 701 — ``create_combined_content_stream`` → ``_create_combined_content_stream``
* line 731 — ``overlay_page`` → ``_overlay_page``
* line 738 — ``get_layout_page`` → ``_get_layout_page``
* line 743 — ``create_adjusted_layout_page`` → ``_create_adjusted_layout_page``
* line 753 — ``create_overlay_form_x_object`` → ``_create_overlay_form_x_object``
* line 763 — ``create_overlay_stream`` → ``_create_overlay_stream``
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.multipdf import Overlay
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


def _build_base_doc(num_pages: int = 1) -> PDDocument:
    doc = PDDocument()
    for _ in range(num_pages):
        page = PDPage(PDRectangle.from_width_height(595.0, 842.0))
        doc.add_page(page)
        with PDPageContentStream(doc, page) as cs:
            cs.add_rect(50.0, 50.0, 100.0, 50.0)
            cs.stroke()
    return doc


def _build_overlay_doc() -> PDDocument:
    doc = PDDocument()
    page = PDPage(PDRectangle.from_width_height(200.0, 200.0))
    doc.add_page(page)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(20.0, 20.0, 50.0, 50.0)
        cs.fill()
    return doc


def _configured_overlay() -> tuple[Overlay, PDDocument]:
    base = _build_base_doc(num_pages=2)
    overlay_doc = _build_overlay_doc()
    overlay = Overlay()
    overlay.set_input_pdf(base)
    overlay.set_default_overlay_pdf(overlay_doc)
    overlay.load_pd_fs()
    return overlay, base


# ---------- line 701: create_combined_content_stream ----------


def test_create_combined_content_stream_delegates_to_internal() -> None:
    """The public delegate concatenates a page's /Contents (single
    COSStream) into one FlateDecode-encoded stream."""
    overlay, base = _configured_overlay()
    contents = (
        base.get_page(0)
        .get_cos_object()
        .get_dictionary_object(COSName.get_pdf_name("Contents"))
    )
    combined = overlay.create_combined_content_stream(contents)
    assert isinstance(combined, COSStream)
    with combined.create_input_stream() as src:
        body = src.read()
    assert len(body) > 0


def test_create_combined_content_stream_handles_none() -> None:
    """Passing ``None`` yields an empty COSStream (no source streams to
    concatenate)."""
    overlay, _ = _configured_overlay()
    combined = overlay.create_combined_content_stream(None)
    assert isinstance(combined, COSStream)


# ---------- line 738: get_layout_page ----------


def test_get_layout_page_returns_default_layout() -> None:
    """``get_layout_page(1, 2)`` for a doc with only a default overlay
    returns the default layout for both pages."""
    overlay, _ = _configured_overlay()
    layout1 = overlay.get_layout_page(1, 2)
    layout2 = overlay.get_layout_page(2, 2)
    # Both pages map to the same default layout instance.
    assert layout1 is not None
    assert layout2 is not None
    assert layout1 is layout2


def test_get_layout_page_unconfigured_returns_none() -> None:
    """Without any overlay configured, no layout matches."""
    overlay = Overlay()
    assert overlay.get_layout_page(1, 1) is None


# ---------- line 743: create_adjusted_layout_page ----------


def test_create_adjusted_layout_page_caches_rotation() -> None:
    """``create_adjusted_layout_page`` produces a rotated layout and
    caches it — a second call with the same rotation returns the same
    object."""
    overlay, _ = _configured_overlay()
    a = overlay.create_adjusted_layout_page(90)
    b = overlay.create_adjusted_layout_page(90)
    assert a is b
    # Rotation 0 should produce a different cached entry.
    c = overlay.create_adjusted_layout_page(180)
    assert c is not a


# ---------- line 753: create_overlay_form_x_object ----------


def test_create_overlay_form_x_object_returns_pdform_xobject() -> None:
    """Public delegate wraps the cached overlay content stream as a
    PDFormXObject with the correct /BBox + /Matrix."""
    overlay, base = _configured_overlay()
    layout = overlay.get_layout_page(1, base.get_number_of_pages())
    assert layout is not None
    cloner = Overlay._make_cloner(base)  # noqa: SLF001
    form = overlay.create_overlay_form_x_object(layout, cloner)
    assert isinstance(form, PDFormXObject)
    # /Type /XObject + /Subtype /Form must be set.
    cos = form.get_cos_object()
    assert cos.get_name(COSName.SUBTYPE) == "Form"  # type: ignore[attr-defined]


# ---------- line 763: create_overlay_stream ----------


def test_create_overlay_stream_emits_q_cm_do_q_sequence() -> None:
    """The placement stream wraps the form-XObject Do call in
    ``q\\nq\\n ... cm\\n /<id> Do Q\\nQ\\n`` (matches upstream)."""
    overlay, base = _configured_overlay()
    layout = overlay.get_layout_page(1, base.get_number_of_pages())
    assert layout is not None
    x_object_id = COSName.get_pdf_name("OL0")
    stream = overlay.create_overlay_stream(
        base.get_page(0), layout, x_object_id
    )
    assert isinstance(stream, COSStream)
    with stream.create_input_stream() as src:
        body = src.read()
    assert b"q\nq\n" in body
    assert b"/OL0 Do" in body
    assert body.endswith(b"Q\n")


# ---------- line 731: overlay_page ----------


def test_overlay_page_appends_form_do_to_content_array() -> None:
    """Public delegate registers an overlay form-XObject under ``/OL0``
    in the page's /Resources and appends a Do call into the array."""
    overlay, base = _configured_overlay()
    layout = overlay.get_layout_page(1, base.get_number_of_pages())
    assert layout is not None
    cloner = Overlay._make_cloner(base)  # noqa: SLF001
    array = COSArray()
    page = base.get_page(0)
    overlay.overlay_page(page, layout, array, cloner)
    # Exactly one entry appended (the placement stream).
    assert len(array) == 1
    # The page now has an /OL0 XObject.
    xobjs = page.get_resources().get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("XObject")
    )
    assert xobjs is not None
    key_names = [k.get_name() for k in xobjs.key_set()]  # type: ignore[attr-defined]
    assert any(k.startswith("OL") for k in key_names)
