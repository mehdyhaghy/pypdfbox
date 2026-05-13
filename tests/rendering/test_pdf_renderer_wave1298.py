"""Wave 1298 — ``PDFRenderer.render_image`` / ``render_image_with_dpi``
parity with upstream's four-arg
``renderImage(int, float, ImageType, RenderDestination)`` overload.

The renderer now accepts a ``destination=`` kwarg that threads straight
into the ``PageDrawerParameters`` built for this render. ``None`` defers
to the renderer-level default (``set_default_destination``); a non-None
value is honoured *for this render only* without mutating the default,
matching upstream's per-call ``RenderDestination`` argument.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer, RenderDestination


def _make_doc() -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, 50.0, 50.0)))
    return doc


class _SpyRenderer(PDFRenderer):
    """Capture the ``destination`` propagated into ``PageDrawerParameters``."""

    seen: list[RenderDestination]

    def __init__(self, document: PDDocument) -> None:
        super().__init__(document)
        self.seen = []

    def create_page_drawer(self, parameters: Any) -> Any:  # type: ignore[override]
        self.seen.append(parameters.get_destination())
        return super().create_page_drawer(parameters)


# ---------------------------------------------------------------------------
# render_image_with_dpi — destination kwarg
# ---------------------------------------------------------------------------


def test_render_image_with_dpi_accepts_destination_enum() -> None:
    """Passing a ``RenderDestination`` enum threads it into the
    PageDrawerParameters for this render."""
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        renderer.render_image_with_dpi(
            0, dpi=72.0, destination=RenderDestination.PRINT
        )
        assert renderer.seen == [RenderDestination.PRINT]
    finally:
        doc.close()


def test_render_image_with_dpi_accepts_destination_string() -> None:
    """Bare string aliases mirror the renderer-level setter behaviour."""
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        renderer.render_image_with_dpi(0, dpi=72.0, destination="Export")
        assert renderer.seen == [RenderDestination.EXPORT]
    finally:
        doc.close()


def test_render_image_with_dpi_destination_none_uses_default() -> None:
    """``destination=None`` (the default) falls back to whatever the
    renderer-level ``set_default_destination`` configured — which is
    ``View`` out of the box."""
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        renderer.render_image_with_dpi(0, dpi=72.0)
        assert renderer.seen == [RenderDestination.VIEW]
    finally:
        doc.close()


def test_render_image_with_dpi_destination_does_not_mutate_default() -> None:
    """The per-call destination must NOT mutate the renderer-level
    default — that's the whole point of having both a setter and a
    kwarg (upstream behaves the same way: the four-arg overload threads
    ``destination`` straight into PageDrawerParameters and never touches
    ``defaultDestination``)."""
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        # Lock in EXPORT as the renderer-level default.
        renderer.set_default_destination(RenderDestination.EXPORT)
        renderer.render_image_with_dpi(
            0, dpi=72.0, destination=RenderDestination.PRINT
        )
        # Per-call PRINT was honoured for that render…
        assert renderer.seen == [RenderDestination.PRINT]
        # …but the renderer-level default is still EXPORT.
        assert renderer.get_default_destination() == "Export"
        # A subsequent default-call resolves to EXPORT, confirming
        # state didn't leak.
        renderer.render_image_with_dpi(0, dpi=72.0)
        assert renderer.seen == [
            RenderDestination.PRINT,
            RenderDestination.EXPORT,
        ]
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# render_image — destination kwarg threads through render_image_with_dpi
# ---------------------------------------------------------------------------


def test_render_image_forwards_destination_to_render_image_with_dpi() -> None:
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        renderer.render_image(0, scale=1.0, destination=RenderDestination.PRINT)
        assert renderer.seen == [RenderDestination.PRINT]
    finally:
        doc.close()


def test_render_image_destination_string_round_trip() -> None:
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        renderer.render_image(0, scale=1.0, destination="View")
        assert renderer.seen == [RenderDestination.VIEW]
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Java-style aliases honour the kwarg too
# ---------------------------------------------------------------------------


def test_render_image_java_alias_accepts_destination() -> None:
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        renderer.renderImage(0, scale=1.0, destination=RenderDestination.PRINT)
        assert renderer.seen == [RenderDestination.PRINT]
    finally:
        doc.close()


def test_render_image_with_dpi_java_alias_accepts_destination() -> None:
    doc = _make_doc()
    try:
        renderer = _SpyRenderer(doc)
        renderer.renderImageWithDPI(
            0, dpi=72.0, destination=RenderDestination.EXPORT
        )
        assert renderer.seen == [RenderDestination.EXPORT]
    finally:
        doc.close()
