"""Tests for the ``ri`` (set rendering intent) operator and its
:class:`PDFRenderer` pass-through.

PDF 32000-1 §8.6.5.8: the ``ri`` operator sets the colour rendering
intent in the graphics state. The four standard intents are:

* ``AbsoluteColorimetric`` — exact device colorimetry, no adjustments.
* ``RelativeColorimetric`` — adjust white point, preserve in-gamut hues.
* ``Saturation`` — preserve vividness, sacrifice colorimetric accuracy.
* ``Perceptual`` — pleasing rendition for typical scenes (default).

The lite renderer logs and ignores the intent (no ICC pipeline), but
the operator must still be dispatched successfully, validated for
operand shape, and exposed via the typed accessor. These tests pin
that contract.
"""
from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import (
    MissingOperandException,
    Operator,
)
from pypdfbox.contentstream.operator.state.set_rendering_intent import (
    SetRenderingIntent,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer


def _make_doc(width: float = 50.0, height: float = 50.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _set_contents(page: PDPage, ops: bytes) -> None:
    contents = COSStream()
    contents.set_raw_data(ops)
    page.get_cos_object().set_item(COSName.CONTENTS, contents)


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 12,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


# ---------------------------------------------------------------------------
# operator surface
# ---------------------------------------------------------------------------


def test_set_rendering_intent_empty_operands_raises() -> None:
    op = Operator.get_operator("ri")
    with pytest.raises(MissingOperandException):
        SetRenderingIntent().process(op, [])


def test_set_rendering_intent_non_name_operand_silently_skips() -> None:
    """Upstream's ``instanceof COSName`` guard silently returns when the
    first operand isn't a name."""
    op = Operator.get_operator("ri")
    # First operand is an integer — should be silently dropped, not raise.
    SetRenderingIntent().process(op, [COSInteger.get(1)])


def test_set_rendering_intent_processes_each_standard_name() -> None:
    op = Operator.get_operator("ri")
    proc = SetRenderingIntent()
    for name in (
        "AbsoluteColorimetric",
        "RelativeColorimetric",
        "Saturation",
        "Perceptual",
    ):
        # No exception → operator dispatched successfully.
        proc.process(op, [COSName.get_pdf_name(name)])


def test_get_intent_name_returns_first_name() -> None:
    name = COSName.get_pdf_name("Saturation")
    assert SetRenderingIntent.get_intent_name([name]) is name


def test_get_intent_name_handles_empty_or_non_name() -> None:
    assert SetRenderingIntent.get_intent_name([]) is None
    assert SetRenderingIntent.get_intent_name([COSInteger.get(0)]) is None
    assert SetRenderingIntent.get_intent_name([COSFloat(1.5)]) is None


def test_get_intent_name_unknown_name_is_returned_verbatim() -> None:
    """The typed accessor must not validate against the well-known list —
    that's downstream's job (lite renderer logs & ignores)."""
    bogus = COSName.get_pdf_name("FooBar")
    assert SetRenderingIntent.get_intent_name([bogus]) is bogus


# ---------------------------------------------------------------------------
# integration via PDFRenderer
# ---------------------------------------------------------------------------


def test_renderer_passes_through_absolute_colorimetric_intent() -> None:
    """``/AbsoluteColorimetric ri`` mid-stream must not crash the
    renderer; the page should still render as if the intent op was a
    no-op (because the lite renderer doesn't implement ICC remapping)."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"/AbsoluteColorimetric ri\n"
        b"1 0 0 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # PIL y flipped: PDF (5..35, 5..35) → PIL (5..35, 15..45).
    inside = img.getpixel((20, 25))
    assert _is_close(inside, (255, 0, 0), tol=20), inside


def test_renderer_passes_through_perceptual_intent() -> None:
    doc, page = _make_doc()
    _set_contents(
        page,
        b"/Perceptual ri\n"
        b"0 1 0 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
    )
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((20, 25))
    assert _is_close(inside, (0, 255, 0), tol=20), inside


def test_renderer_passes_through_relative_colorimetric_intent() -> None:
    doc, page = _make_doc()
    _set_contents(
        page,
        b"/RelativeColorimetric ri\n"
        b"0 0 1 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
    )
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((20, 25))
    assert _is_close(inside, (0, 0, 255), tol=20), inside


def test_renderer_passes_through_saturation_intent() -> None:
    doc, page = _make_doc()
    _set_contents(
        page,
        b"/Saturation ri\n"
        b"1 1 0 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
    )
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((20, 25))
    assert _is_close(inside, (255, 255, 0), tol=20), inside


def test_renderer_unknown_intent_name_does_not_crash() -> None:
    """A bogus intent name must be silently dispatched (the operator
    processor doesn't validate the name; the renderer logs at debug)."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"/FooBarIntent ri\n"
        b"1 0 1 rg\n"
        b"5 5 30 30 re\n"
        b"f\n",
    )
    # Render should still produce a fully formed image with the fill.
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((20, 25))
    assert _is_close(inside, (255, 0, 255), tol=20), inside


def test_renderer_intent_between_fills_does_not_corrupt_state() -> None:
    """An intent op set between two fills should not alter the second
    fill's outcome — both red and blue rectangles must be visible."""
    doc, page = _make_doc(60.0, 30.0)
    _set_contents(
        page,
        b"1 0 0 rg\n5 5 10 20 re\nf\n"
        b"/Perceptual ri\n"
        b"0 0 1 rg\n30 5 10 20 re\nf\n",
    )
    img = PDFRenderer(doc).render_image(0)
    # PIL y flipped: PDF y=5..25 → PIL y=5..25.
    red = img.getpixel((10, 15))
    blue = img.getpixel((35, 15))
    assert _is_close(red, (255, 0, 0), tol=20), red
    assert _is_close(blue, (0, 0, 255), tol=20), blue


def test_renderer_multiple_intent_changes_are_idempotent() -> None:
    """Three consecutive ``ri`` ops with the same intent — the renderer
    must handle the redundancy gracefully."""
    doc, page = _make_doc()
    _set_contents(
        page,
        b"/Perceptual ri\n"
        b"/Perceptual ri\n"
        b"/Perceptual ri\n"
        b"0.5 0.5 0.5 rg\n"
        b"5 5 30 30 re\nf\n",
    )
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((20, 25))
    # ~50% grey
    assert 100 <= inside[0] <= 160, inside
    assert 100 <= inside[1] <= 160, inside


def test_renderer_intent_inside_form_xobject_is_scoped() -> None:
    """An intent op inside a Form XObject must not leak out to the
    parent graphics state at ``Q`` (q/Q wraps the form invocation; the
    PDF spec puts /RenderingIntent in the GS so it's saved/restored)."""
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
    from pypdfbox.pdmodel.pd_resources import PDResources

    doc, page = _make_doc(50.0, 50.0)
    form_stream = COSStream()
    form_stream.set_raw_data(
        b"/Saturation ri\n"
        b"1 0 0 rg\n5 5 20 20 re\nf\n"
    )
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0.0, 0.0, 50.0, 50.0))

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("F0"),
        form.get_cos_object(),
    )
    # Page-level contents: invoke the form within q/Q, then paint a
    # green rect (which should NOT be affected by the inner intent).
    _set_contents(
        page,
        b"q\n/F0 Do\nQ\n"
        b"0 1 0 rg\n25 25 20 20 re\nf\n",
    )
    img = PDFRenderer(doc).render_image(0)
    inside_form = img.getpixel((10, 35))
    inside_outer = img.getpixel((30, 15))
    assert _is_close(inside_form, (255, 0, 0), tol=20), inside_form
    assert _is_close(inside_outer, (0, 255, 0), tol=20), inside_outer
