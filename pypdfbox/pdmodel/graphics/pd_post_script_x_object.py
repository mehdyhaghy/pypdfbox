from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject

_PS: COSName = COSName.get_pdf_name("PS")


class PDPostScriptXObject(PDXObject):
    """
    PostScript XObject (``/Subtype /PS``). Mirrors
    ``org.apache.pdfbox.pdmodel.graphics.PDPostScriptXObject``.

    A PostScript XObject embeds a fragment of PostScript inside a PDF
    stream. Per PDF 32000-1 §8.8.2, conforming readers may not be able to
    interpret the PostScript fragment; this class is the typed wrapper
    so the XObject factory dispatch (``PDXObject.create_x_object``)
    returns a stable, identifiable instance instead of failing.
    """

    def __init__(self, stream: COSStream) -> None:
        """Wrap the given ``COSStream`` as a PostScript XObject. The base
        :class:`PDXObject` constructor stamps ``/Type /XObject`` and
        ``/Subtype /PS`` on the underlying dictionary."""
        super().__init__(stream, _PS)
