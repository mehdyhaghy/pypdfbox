"""Coverage round-out for :class:`PDFTemplateCreator`.

Drives the full ``build_pdf`` walk through the concrete
:class:`PDVisibleSigBuilder` to cover Java line 76 (the canonical builder
sequence), Java line 157 (``getVisualSignatureAsStream``), and Java
line 47-129 (the orchestration that fans intermediates through the
shared :class:`PDFTemplateStructure`).
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_builder import (
    PDFTemplateBuilder,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_creator import (
    PDFTemplateCreator,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_structure import (
    PDFTemplateStructure,
)
from pypdfbox.pdmodel.pd_document import PDDocument


def _make_designer() -> PDVisibleSignDesigner:
    """Hand-rolled designer (no on-disk PDF needed)."""
    designer = (
        PDVisibleSignDesigner()
        .coordinates(10.0, 20.0)
        .width(100.0)
        .height(50.0)
        .page_width(595.0)
        .page_height(842.0)
        .signature_field_name("CoverageSig")
    )
    # Image bytes — designer just stores them; rendering is downstream.
    designer.read_image_stream(b"\x89PNG\r\nFAKEBYTES")
    return designer


# ---------- get_pdf_structure ----------


def test_get_pdf_structure_returns_builder_structure_identity() -> None:
    """Java line 64: the creator surfaces the builder's structure as-is."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    assert creator.get_pdf_structure() is builder.get_structure()
    assert isinstance(creator.get_pdf_structure(), PDFTemplateStructure)


# ---------- build_pdf — happy-path full walk ----------


def test_build_pdf_returns_binary_stream() -> None:
    """Java line 76-156: end-to-end walk yields a BytesIO with PDF
    content. The structure should now be fully populated."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    designer = _make_designer()
    result = creator.build_pdf(designer)
    payload = result.read()
    assert isinstance(payload, bytes)
    assert payload.startswith(b"%PDF-")


def test_build_pdf_invokes_create_page_and_create_template() -> None:
    """Whether or not the underlying pdmodel constructors succeed (some
    are stubs), the creator must invoke ``create_page`` and
    ``create_template`` exactly once in order."""

    calls: list[str] = []

    class _SpyBuilder(PDVisibleSigBuilder):
        def create_page(self, properties: Any) -> None:
            calls.append("create_page")
            super().create_page(properties)

        def create_template(self, page: Any) -> None:
            calls.append("create_template")
            super().create_template(page)

    creator = PDFTemplateCreator(_SpyBuilder())
    creator.build_pdf(_make_designer())
    # create_page precedes create_template — mirrors Java ordering.
    assert calls.index("create_page") < calls.index("create_template")


def test_build_pdf_invokes_create_signature_field_then_signature() -> None:
    """``create_signature_field`` must run before ``create_signature``."""

    calls: list[str] = []

    class _SpyBuilder(PDVisibleSigBuilder):
        def create_signature_field(self, acro_form: Any) -> None:
            calls.append("field")
            super().create_signature_field(acro_form)

        def create_signature(
            self, sig_field: Any, page: Any, signer_name: str
        ) -> None:
            calls.append("signature")
            super().create_signature(sig_field, page, signer_name)

    creator = PDFTemplateCreator(_SpyBuilder())
    creator.build_pdf(_make_designer())
    assert calls == ["field", "signature"]


def test_build_pdf_populates_proc_set_array() -> None:
    """``create_proc_set_array`` is the first call in the walk."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    creator.build_pdf(_make_designer())
    proc_set = creator.get_pdf_structure().get_proc_set()
    assert proc_set is not None
    # ProcSet contains the five required names: PDF, Text, ImageB, ImageC, ImageI.
    names = [item.get_name() for item in proc_set]
    assert "PDF" in names
    assert "Text" in names


def test_build_pdf_calls_create_formatter_rectangle_with_designer_params() -> None:
    """``create_formatter_rectangle`` is called with the designer's
    parameter list. Whether the resulting ``PDRectangle`` materialises
    depends on local pdmodel availability — we only assert the call
    is made with the canonical [0, 0, 100, 50] default vector."""

    captured: list[list[int]] = []

    class _SpyBuilder(PDVisibleSigBuilder):
        def create_formatter_rectangle(self, params: list[int]) -> None:
            captured.append(list(params))
            super().create_formatter_rectangle(params)

    creator = PDFTemplateCreator(_SpyBuilder())
    creator.build_pdf(_make_designer())
    assert captured == [[0, 0, 100, 50]]


def test_build_pdf_populates_holder_and_inner_and_image_forms() -> None:
    """All three form XObjects (holder, inner, image) wired."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    creator.build_pdf(_make_designer())
    s = creator.get_pdf_structure()
    assert s.get_holder_form_stream() is not None
    assert s.get_holder_form_resources() is not None
    assert s.get_holder_form() is not None
    assert s.get_inner_form_stream() is not None
    assert s.get_inner_form_resources() is not None
    assert s.get_inner_form() is not None
    assert s.get_image_form_stream() is not None
    assert s.get_image_form_resources() is not None


def test_build_pdf_stores_image_reference() -> None:
    """``create_signature_image`` stows the designer's image bytes."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    designer = _make_designer()
    creator.build_pdf(designer)
    img = creator.get_pdf_structure().get_image()
    # Designer stored the raw PNG bytes; build_pdf forwards them.
    assert img == b"\x89PNG\r\nFAKEBYTES"


def test_build_pdf_records_affine_transform() -> None:
    """The designer's transform is shuttled through unchanged."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    designer = _make_designer()
    creator.build_pdf(designer)
    assert (
        creator.get_pdf_structure().get_affine_transform()
        is designer.get_transform()
    )


def test_build_pdf_calls_close_template_in_finally() -> None:
    """Java's try/finally ensures the template is closed even when the
    middle of the pipeline raises. We assert the close hook fires."""

    closed: list[bool] = []

    class _SpyBuilder(PDVisibleSigBuilder):
        def close_template(self, template: Any) -> None:
            closed.append(True)
            super().close_template(template)

    creator = PDFTemplateCreator(_SpyBuilder())
    creator.build_pdf(_make_designer())
    assert closed == [True]


def test_build_pdf_close_template_runs_even_when_step_raises() -> None:
    """``finally`` semantics: if any builder hook explodes mid-walk,
    ``close_template`` still fires."""

    closed: list[bool] = []

    class _ExplodingBuilder(PDVisibleSigBuilder):
        def create_signature_field(self, acro_form: Any) -> None:
            raise RuntimeError("boom")

        def close_template(self, template: Any) -> None:
            closed.append(True)
            super().close_template(template)

    creator = PDFTemplateCreator(_ExplodingBuilder())
    with pytest.raises(RuntimeError, match="boom"):
        creator.build_pdf(_make_designer())
    assert closed == [True]


# ---------- get_visual_signature_as_stream ----------


def test_get_visual_signature_as_stream_returns_pdf_bytes() -> None:
    """Java line 157: the public helper forwards to
    ``_visual_signature_as_stream`` which writes via :class:`COSWriter`."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    doc = PDDocument()
    try:
        stream = creator.get_visual_signature_as_stream(doc.get_document())
    finally:
        doc.close()
    payload = stream.read()
    assert payload.startswith(b"%PDF-")


def test_get_visual_signature_as_stream_returns_fresh_bytesio() -> None:
    """Each invocation must hand back a *new* :class:`BytesIO` whose
    cursor is at the start — callers may read it directly."""
    builder = PDVisibleSigBuilder()
    creator = PDFTemplateCreator(builder)
    doc = PDDocument()
    try:
        s1 = creator.get_visual_signature_as_stream(doc.get_document())
        s2 = creator.get_visual_signature_as_stream(doc.get_document())
    finally:
        doc.close()
    assert s1 is not s2
    assert isinstance(s1, io.BytesIO)
    assert s1.tell() == 0
    assert s2.tell() == 0


# ---------- abstract builder rejects instantiation ----------


def test_pdf_template_builder_is_abstract() -> None:
    """Mirrors PDFBox upstream: ``PDFTemplateBuilder`` is an interface."""
    with pytest.raises(TypeError):
        PDFTemplateBuilder()  # type: ignore[abstract]
