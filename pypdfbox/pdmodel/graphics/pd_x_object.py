from __future__ import annotations

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_XOBJECT: COSName = COSName.get_pdf_name("XObject")


class PDXObject:
    """
    Abstract external object (``/Type /XObject``). Mirrors
    ``org.apache.pdfbox.pdmodel.graphics.PDXObject``.

    Concrete subtypes — ``PDFormXObject`` (/Subtype /Form),
    ``PDImageXObject`` (/Subtype /Image), and (later) ``PDPostScriptXObject``
    — extend this class. The ``createXObject`` factory dispatch lives in
    ``pypdfbox.pdmodel.pd_resources.PDResources.get_x_object`` (the only
    place dispatch is currently exercised).
    """

    def __init__(
        self,
        stream: PDStream | COSStream,
        subtype: COSName,
    ) -> None:
        if isinstance(stream, COSStream):
            self._stream = PDStream(stream)
        elif isinstance(stream, PDStream):
            self._stream = stream
        else:
            raise TypeError(
                f"PDXObject expects PDStream or COSStream; got {type(stream).__name__}"
            )
        # Mirror upstream: stamp /Type /XObject and /Subtype on the underlying dict.
        cos = self._stream.get_cos_object()
        cos.set_item(_TYPE, _XOBJECT)
        cos.set_item(_SUBTYPE, subtype)

    def get_cos_object(self) -> COSStream:
        return self._stream.get_cos_object()

    def get_stream(self) -> PDStream:
        return self._stream
