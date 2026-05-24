"""Wave 1391 — regressions: rotated AcroForm widget appearances paint
off-page, and unembedded Standard 14 fonts with ``/Encoding``
``/Differences`` overlays drop every glyph to ``.notdef``.

Two distinct root causes were exposed by the wave-1390 visual battery
on ``tests/fixtures/pdmodel/interactive/form/AcroFormsRotation.pdf``:

1. **Matrix-order bug in ``PDFRenderer._render_annotation``.**
   The historical call ``_matmul(a_matrix, m_appear)`` means "apply
   ``a_matrix`` first, then ``m_appear``" — but upstream PDFBox does
   ``Matrix.concatenate(a, matrix)`` which is ``matrix.multiply(a)``
   — "apply ``matrix`` first, then ``a``". For widgets with rotated
   appearances (``/MK /R 90`` and ``/R 180``) the swapped order
   pushed the painted region thousands of points off the page, so 12
   of 16 widgets on each page of ``AcroFormsRotation.pdf`` rendered
   as completely blank. Fix: swap the args to
   ``_matmul(m_appear, a_matrix)``.

2. **Base-less ``DictionaryEncoding`` for unembedded Standard 14
   fonts.** ``PDSimpleFont.get_encoding_typed()`` builds a
   :class:`DictionaryEncoding` *without* a base encoding when
   ``/Encoding`` is a COSDictionary (the upstream Type 3 mode). For
   regular Type 1 fonts with ``/Differences`` (no ``/BaseEncoding``)
   that drops every code outside the differences table to
   ``.notdef``, so ``PDType1Font.get_glyph_width`` and
   ``get_glyph_path`` returned 0 / ``[]`` and the renderer painted
   nothing. The full :meth:`PDSimpleFont.read_encoding` resolution
   path passes ``is_non_symbolic`` / ``built_in`` to
   :class:`DictionaryEncoding` so the base resolves to
   :class:`StandardEncoding`, but rewiring ``get_encoding_typed`` to
   delegate there broke an existing test that pins the
   base-less behaviour
   (``test_simple_font_standard14_false_for_dictionary_encoding_without_base``).
   Wave-1391 fix: narrowly patch the Standard 14 fall-through path in
   ``PDType1Font.get_glyph_width`` / ``get_glyph_path`` so a
   ``.notdef`` result from a base-less ``DictionaryEncoding`` retries
   through the family's default PostScript encoding (Symbol /
   ZapfDingbats / Standard). Leaves ``get_encoding_typed`` and
   ``is_standard_14`` untouched.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.rendering.pdf_renderer import PDFRenderer

_ACROFORM_ROTATION = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
    / "AcroFormsRotation.pdf"
)
_TRANSITIONS = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "pagenavigation"
    / "transitions_test.pdf"
)


def _fraction_non_white(doc: PDDocument, page_index: int, dpi: int = 72) -> float:
    """Render ``page_index`` at ``dpi`` and return the fraction of
    non-pure-white RGB pixels (any channel below 250)."""
    renderer = PDFRenderer(doc)
    img = renderer.render_image_with_dpi(page_index, dpi)
    arr = np.array(img.convert("RGB"))
    total = arr.shape[0] * arr.shape[1]
    if total == 0:
        return 0.0
    non_white = int(np.sum(np.any(arr < 250, axis=-1)))
    return non_white / total


@pytest.mark.skipif(
    not _ACROFORM_ROTATION.exists(),
    reason="AcroFormsRotation.pdf fixture missing",
)
def test_acroforms_rotation_page0_widgets_paint() -> None:
    """Page 1 of ``AcroFormsRotation.pdf`` has 16 widget annotations
    arranged in four rotation orientations (0 / 90 / 180 / 270). Before
    the wave-1391 fix the renderer painted only ~0.78% of the pixels
    (just borders for the four R=0 widgets): the rotated-widget
    appearances landed off-page because the appearance matrix was
    composed in the wrong order, and the inner field-value text never
    painted because the unembedded Helvetica's ``/Differences``
    encoding overlay dropped every glyph to ``.notdef``.

    The 5% threshold is calibrated against ``pdftocairo`` (~4.72%) —
    we expect to be within ±0.5% of that reference now that both bugs
    are fixed.
    """
    with PDDocument.load(_ACROFORM_ROTATION) as doc:
        fraction = _fraction_non_white(doc, 0)
    assert fraction >= 0.05, (
        f"AcroFormsRotation page 0 rendered with only {fraction * 100:.3f}% "
        "non-white pixels — widget appearances are dropping content again."
    )


@pytest.mark.skipif(
    not _ACROFORM_ROTATION.exists(),
    reason="AcroFormsRotation.pdf fixture missing",
)
def test_acroforms_rotation_page1_widgets_paint() -> None:
    """Page 2 has ``/Rotate 90`` plus the same 16-widget grid. Once
    the appearance matrix composition is correct and the encoding
    fall-through covers the unembedded Helvetica, the widget borders
    and inner text paint just as densely as page 1. The page-level
    ``/Rotate`` canvas swap (separate concern — pypdfbox currently
    emits the un-rotated canvas) is *not* enforced here.
    """
    with PDDocument.load(_ACROFORM_ROTATION) as doc:
        fraction = _fraction_non_white(doc, 1)
    assert fraction >= 0.05, (
        f"AcroFormsRotation page 1 rendered with only {fraction * 100:.3f}% "
        "non-white pixels — widget appearances are dropping content again."
    )


@pytest.mark.skipif(
    not _TRANSITIONS.exists(), reason="transitions_test.pdf fixture missing"
)
@pytest.mark.parametrize("page_index", [0, 1, 2])
def test_transitions_test_each_page_paints_text(page_index: int) -> None:
    """``transitions_test.pdf`` is a Sejda-produced 3-slide deck whose
    page content streams contain a single ``Tj`` each:
    ``(First Page)`` / ``(Second Page)`` / ``(Third Page)`` painted in
    Helvetica-Bold 12pt at (100, 700). The non-white pixel count is
    inherently tiny (~0.07-0.09%, matching ``pdftocairo`` exactly) —
    there is no other content on these pages, so we cannot enforce a
    high non-white-fraction threshold without inventing pixels.
    Instead we assert that the text *renders at all* (>=100 non-white
    pixels) — a regression that drops the text entirely (e.g. an
    encoding bug that nukes the Helvetica-Bold ``/WinAnsiEncoding``
    fall-through) would be caught here.
    """
    with PDDocument.load(_TRANSITIONS) as doc:
        renderer = PDFRenderer(doc)
        img = renderer.render_image_with_dpi(page_index, 72)
    arr = np.array(img.convert("RGB"))
    non_white = int(np.sum(np.any(arr < 250, axis=-1)))
    assert non_white >= 100, (
        f"transitions_test page {page_index} rendered only {non_white} "
        "non-white pixels — the slide text was dropped."
    )


def test_dictionary_encoding_baseless_falls_through_to_standard_for_helv() -> None:
    """White-box: an unembedded Type 1 ``/Helvetica`` whose
    ``/Encoding`` is a base-less COSDictionary (``/Differences``-only)
    must still resolve every Standard 14 glyph width via the AFM
    fallback. Before the wave-1391 fix the lookup returned 0.0 for
    every code outside the differences overlay because
    :meth:`DictionaryEncoding.get_name` returned ``.notdef`` — the
    bug that nuked field-value text in AcroForm widget appearances.

    The fix narrowly patches
    :meth:`PDType1Font.get_glyph_width` / ``get_glyph_path`` to retry
    via the family's default PostScript encoding when the typed
    encoding is a base-less ``DictionaryEncoding``.
    """
    from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    encoding_dict = COSDictionary()
    encoding_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Encoding"))
    # Differences re-map only code 24; everything else should
    # fall through to StandardEncoding.
    differences = COSArray()
    differences.add(COSInteger.get(24))
    differences.add(COSName.get_pdf_name("breve"))
    encoding_dict.set_item(COSName.get_pdf_name("Differences"), differences)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
    )
    font_dict.set_item(COSName.get_pdf_name("Encoding"), encoding_dict)
    font = PDType1Font(font_dict)

    # Code 116 = 't' in StandardEncoding; the /Differences overlay
    # only touches code 24, so the lookup must fall through to the
    # base encoding via the wave-1391 retry path.
    assert font.get_glyph_width(116) == 278.0, (
        "Helvetica with base-less /Differences should still resolve 't' "
        "through StandardEncoding — got 0, meaning the encoding "
        "fall-through is broken."
    )
    # Smoke: 'L', 'o', 'r', 'e', 'm', ' ' (letters used in the
    # widget's Lorem ipsum field value) should all resolve too.
    for code in b"Lorem ":
        assert font.get_glyph_width(code) > 0, (
            f"code {code} ({chr(code)!r}) had zero width — encoding "
            "fall-through is still broken."
        )
    # And the same code must produce a non-empty glyph path so the
    # renderer actually paints something.
    assert len(font.get_glyph_path(116)) > 0, (
        "Helvetica 't' has empty glyph path — the get_glyph_path "
        "fall-through is broken."
    )


def test_render_annotation_matrix_order_matches_upstream() -> None:
    """White-box: ``_render_annotation`` must compose the appearance
    matrix as ``_matmul(m_appear, a_matrix)`` (apply ``m_appear``
    first, then ``a_matrix``) — matching upstream's
    ``Matrix.concatenate(a, matrix)`` which is defined as
    ``matrix.multiply(a)``. The historical
    ``_matmul(a_matrix, m_appear)`` (apply ``a_matrix`` first then
    ``m_appear``) silently broke rotated widgets: for a widget with
    ``/MK /R 90`` and a 90° appearance matrix the composition placed
    the bbox corners hundreds of points outside the page.
    """
    import inspect

    src = inspect.getsource(PDFRenderer._render_annotation)
    # Strip comment lines so we don't match the historical-broken
    # form quoted in the explanatory docstring above the call.
    code_lines = [
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    ]
    code_text = "\n".join(code_lines)
    assert "_matmul(m_appear, a_matrix)" in code_text, (
        "_render_annotation no longer composes the appearance matrix in "
        "the upstream-faithful order — rotated widgets will paint "
        "off-page again."
    )
    assert "_matmul(a_matrix, m_appear)" not in code_text, (
        "_render_annotation still composes the appearance matrix in "
        "the wrong (apply-translate-before-rotate) order — rotated "
        "widgets will paint off-page."
    )
