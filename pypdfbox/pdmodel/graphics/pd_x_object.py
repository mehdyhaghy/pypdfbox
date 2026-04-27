from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.pd_metadata import PDMetadata

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_METADATA: COSName = COSName.METADATA  # type: ignore[attr-defined]
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

    def get_subtype(self) -> str | None:
        """Return the ``/Subtype`` name as a ``str`` (e.g. ``"Image"``,
        ``"Form"``, ``"PS"``) or ``None`` when absent. Mirrors upstream
        ``getSubType()``."""
        return self.get_cos_object().get_name(_SUBTYPE)

    def get_metadata(self) -> PDMetadata | None:
        """Typed ``/Metadata`` XMP wrapper; ``None`` when absent. Mirrors
        upstream ``getMetadata()``."""
        # Local import to avoid an import cycle with PDMetadata's
        # PDDocument dependency at package import time.
        from pypdfbox.pdmodel.common.pd_metadata import PDMetadata  # noqa: PLC0415

        value = self.get_cos_object().get_dictionary_object(_METADATA)
        if isinstance(value, COSStream):
            return PDMetadata(value)
        return None

    def set_metadata(self, value: PDMetadata | None) -> None:
        """Set or clear ``/Metadata``. Mirrors upstream ``setMetadata()``."""
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_METADATA)
            return
        cos.set_item(_METADATA, value.get_cos_object())
