from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_resource_cache import PDResourceCache


class PDTransparencyGroup(PDFormXObject):
    """
    A transparency-group form XObject. Mirrors
    ``org.apache.pdfbox.pdmodel.graphics.form.PDTransparencyGroup``.

    Subclass of :class:`PDFormXObject` returned by the XObject factory
    when a ``/Subtype /Form`` stream carries a ``/Group`` entry whose
    ``/S`` is ``/Transparency`` (PDF 32000-1 §11.6.6). The class adds
    no new keys — it exists so callers can dispatch on type to
    distinguish a transparency-group form from a plain form X-Object,
    matching upstream.
    """

    def __init__(
        self,
        stream: PDStream | COSStream | PDDocument,
        cache: PDResourceCache | None = None,
    ) -> None:
        # All four upstream constructors ultimately hand off to the parent
        # ``PDFormXObject`` constructor — ``PDTransparencyGroup`` carries no
        # additional state. Mirror that here while keeping the same overload
        # surface as :class:`PDFormXObject` (PDStream / COSStream / PDDocument
        # plus an optional resource cache).
        super().__init__(stream, cache=cache)
