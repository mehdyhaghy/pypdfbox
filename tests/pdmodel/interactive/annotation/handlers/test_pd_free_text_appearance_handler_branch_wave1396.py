"""Wave 1396 branch-coverage tests for ``PDFreeTextAppearanceHandler``.

Targets the False-branch arrows for the AcroForm/font-resolution
short-circuits in
``pypdfbox/pdmodel/interactive/annotation/handlers/pd_free_text_appearance_handler.py``:

* 439->452 — no acro_form on the catalog
* 441->452 — acro_form has no callable ``get_default_resources``
* 443->452 — ``get_default_resources()`` returns ``None``
* 445->452 — default resources has no callable ``get_font``
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.interactive.annotation.handlers.pd_free_text_appearance_handler import (
    PDFreeTextAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def _make_handler(document: PDDocument | None = None) -> PDFreeTextAppearanceHandler:
    annot = PDAnnotationFreeText()
    return PDFreeTextAppearanceHandler(annot, document=document)


def test_resolve_font_with_no_document_returns_default() -> None:
    """No document → fall through to default font.

    Closes the False arm of ``self._document is not None`` at line 436.
    Also exercises the path that doesn't pass through the AcroForm
    pyramid, so it does not consume branch 439 etc — sanity baseline.
    """
    handler = _make_handler()
    font = handler._resolve_font()  # noqa: SLF001
    assert font is not None


def test_resolve_font_when_no_acroform_returns_default() -> None:
    """Document with no AcroForm → fall through to default font.

    Closes the False arm at line 439 (``acro_form is not None``).
    """
    with PDDocument() as document:
        # Default catalog has no /AcroForm.
        handler = _make_handler(document)
        font = handler._resolve_font()  # noqa: SLF001
        assert font is not None


def test_resolve_font_when_acroform_lacks_get_default_resources() -> None:
    """AcroForm missing ``get_default_resources`` → fall through.

    Closes the False arm at line 441 (``callable(resources_getter)``).
    """
    with PDDocument() as document:
        # Plant a fake acro_form on the catalog that doesn't have
        # get_default_resources at all.
        class FakeAcroForm:
            # No get_default_resources attribute.
            def get_cos_object(self) -> Any:
                from pypdfbox.cos import COSDictionary as _D
                return _D()

        # Monkey-patch the catalog's get_acro_form to return our fake.
        catalog = document.get_document_catalog()
        catalog.get_acro_form = lambda: FakeAcroForm()  # type: ignore[method-assign]
        handler = _make_handler(document)
        font = handler._resolve_font()  # noqa: SLF001
        assert font is not None


def test_resolve_font_when_default_resources_is_none() -> None:
    """``get_default_resources`` returning ``None`` → fall through.

    Closes the False arm at line 443 (``default_resources is not None``).
    """
    with PDDocument() as document:
        class FakeAcroForm:
            def get_default_resources(self) -> None:
                return None

            def get_cos_object(self) -> Any:
                from pypdfbox.cos import COSDictionary as _D
                return _D()

        catalog = document.get_document_catalog()
        catalog.get_acro_form = lambda: FakeAcroForm()  # type: ignore[method-assign]
        handler = _make_handler(document)
        font = handler._resolve_font()  # noqa: SLF001
        assert font is not None


def test_resolve_font_when_resources_lacks_get_font() -> None:
    """Default resources missing ``get_font`` → fall through.

    Closes the False arm at line 445 (``callable(font_getter)``).
    """
    with PDDocument() as document:
        class FakeDefaultResources:
            # No get_font attribute.
            pass

        class FakeAcroForm:
            def get_default_resources(self) -> Any:
                return FakeDefaultResources()

            def get_cos_object(self) -> Any:
                from pypdfbox.cos import COSDictionary as _D
                return _D()

        catalog = document.get_document_catalog()
        catalog.get_acro_form = lambda: FakeAcroForm()  # type: ignore[method-assign]
        handler = _make_handler(document)
        font = handler._resolve_font()  # noqa: SLF001
        assert font is not None


def test_extract_font_details_no_da_no_document_uses_defaults() -> None:
    """No /DA, no document → defaults are used.

    Exercises the early-exit at line 345 with both upstream branches
    skipped (no document fallback).
    """
    annot = PDAnnotationFreeText()
    handler = PDFreeTextAppearanceHandler(annot, document=None)
    handler.extract_font_details(annot)
    assert handler._font_size == handler.DEFAULT_FONT_SIZE  # noqa: SLF001
    assert handler._font_name == handler.DEFAULT_FONT_NAME  # noqa: SLF001


def test_extract_font_details_no_acroform_uses_defaults() -> None:
    """No /DA, document but no acro_form → defaults.

    Closes the False arm of ``acro_form is not None`` at line 341.
    """
    with PDDocument() as document:
        annot = PDAnnotationFreeText()
        handler = PDFreeTextAppearanceHandler(annot, document=document)
        handler.extract_font_details(annot)
        assert handler._font_size == handler.DEFAULT_FONT_SIZE  # noqa: SLF001


def test_extract_font_details_acroform_lacks_get_default_appearance() -> None:
    """AcroForm missing ``get_default_appearance`` → defaults.

    Closes the False arm of ``callable(getter)`` at line 343.
    """
    with PDDocument() as document:
        class FakeAcroForm:
            # No get_default_appearance attribute.
            pass

        document.get_document_catalog().get_acro_form = (  # type: ignore[method-assign]
            lambda: FakeAcroForm()
        )
        annot = PDAnnotationFreeText()
        handler = PDFreeTextAppearanceHandler(annot, document=document)
        handler.extract_font_details(annot)
        assert handler._font_size == handler.DEFAULT_FONT_SIZE  # noqa: SLF001


def test_extract_font_details_da_without_tf_keeps_defaults() -> None:
    """/DA with no Tf operator → font_arguments is None, keep defaults.

    Closes the False arm of ``font_arguments is not None`` at line 351.
    """
    annot = PDAnnotationFreeText()
    # DA with just a color op, no Tf
    annot.set_default_appearance("0 g")
    handler = PDFreeTextAppearanceHandler(annot, document=None)
    handler.extract_font_details(annot)
    assert handler._font_size == handler.DEFAULT_FONT_SIZE  # noqa: SLF001
    assert handler._font_name == handler.DEFAULT_FONT_NAME  # noqa: SLF001
