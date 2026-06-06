from __future__ import annotations

from typing import TYPE_CHECKING

from .pd_abstract_content_stream import PDAbstractContentStream
from .pd_page_content_stream import PDPageContentStream
from .pd_resources import PDResources

if TYPE_CHECKING:
    from .graphics.form.pd_form_x_object import PDFormXObject


class PDFormContentStream(PDPageContentStream):
    """Content-stream writer for a form XObject body. Mirrors
    ``org.apache.pdfbox.pdmodel.PDFormContentStream``.

    Upstream's class is a thin three-line subclass of
    ``PDAbstractContentStream`` whose only job is to wire the writer to the
    form's content-stream output and the form's ``/Resources``
    (PDFormContentStream.java:36-39). The pypdfbox buffered operator
    machinery lives in :class:`PDPageContentStream`; this subclass reuses
    it but pins the fractional-digit count to the shared base's ``4``
    (matching upstream's ``PDAbstractContentStream`` parent rather than the
    page writer's ``5``) and seeds ``/Resources`` from the form exactly as
    the Java constructor does via ``form.getResources()``.
    """

    def __init__(self, form: PDFormXObject) -> None:
        # Local import to avoid a top-level cycle through the form package.
        from .graphics.form.pd_form_x_object import PDFormXObject

        if not isinstance(form, PDFormXObject):
            raise TypeError(
                "PDFormContentStream requires a PDFormXObject; got "
                f"{type(form).__name__}"
            )
        # Reuse the PDFormXObject branch of the parent constructor, which
        # sets ``_target_stream`` to the form's COSStream and ``_resources``
        # to the form's /Resources (creating one when absent). ``document``
        # is ``None`` — upstream's ctor passes null too.
        super().__init__(None, form)  # type: ignore[arg-type]
        # Upstream's PDFormContentStream extends PDAbstractContentStream, so
        # numeric operands emit at most 4 fractional digits (not the page
        # writer's 5).
        self._max_fraction_digits = (
            PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS
        )
        self._form = form

    def get_resources(self) -> PDResources:
        """Return the form's ``/Resources`` dictionary the writer binds
        names against."""
        return self._resources


__all__ = ["PDFormContentStream"]
