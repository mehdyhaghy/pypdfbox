from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
    from pypdfbox.pdmodel.pd_resources import PDResources

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_METADATA: COSName = COSName.METADATA  # type: ignore[attr-defined]
_XOBJECT: COSName = COSName.get_pdf_name("XObject")
_GROUP: COSName = COSName.get_pdf_name("Group")
_S: COSName = COSName.get_pdf_name("S")
_TRANSPARENCY: COSName = COSName.get_pdf_name("Transparency")


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

    @staticmethod
    def create_x_object(
        base: COSBase | None,
        resources: PDResources | None = None,
    ) -> PDXObject | None:
        """Build the typed ``PDXObject`` for ``base``. Mirrors upstream
        ``PDXObject.createXObject(COSBase, PDResources)``.

        - ``None`` → ``None`` (matches upstream's ``TODO throw an
          exception?`` placeholder which currently returns ``null``).
        - ``COSStream`` with ``/Subtype /Image`` → :class:`PDImageXObject`.
        - ``COSStream`` with ``/Subtype /Form`` → :class:`PDFormXObject`,
          or :class:`PDTransparencyGroup` when the form has a
          ``/Group /S /Transparency`` entry. (The transparency-group form
          subclass is not yet ported — when absent we fall back to the
          plain :class:`PDFormXObject` which still exposes the group dict
          via :meth:`PDFormXObject.get_group_attributes`.)
        - any other ``COSStream`` /Subtype value → ``OSError`` with the
          subtype reproduced verbatim (matches upstream's
          ``IOException("Invalid XObject Subtype: ...")``).
        - non-stream ``base`` → ``OSError`` (mirrors upstream's
          ``IOException("Unexpected object type: ...")``).
        """
        if base is None:
            return None
        if not isinstance(base, COSStream):
            raise OSError(
                f"Unexpected object type: {type(base).__name__}"
            )
        # Local imports — cluster boundary, avoids a circular import at
        # module load (graphics → form/image which themselves import
        # PDXObject).
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
            PDFormXObject,
        )
        from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
            PDImageXObject,
        )

        subtype = base.get_name(_SUBTYPE)
        if subtype == "Image":
            return PDImageXObject(base)
        if subtype == "Form":
            # When the form carries /Group /S /Transparency, upstream
            # returns a PDTransparencyGroup. Until that subclass is
            # ported, return a plain PDFormXObject — the transparency
            # group attributes are still discoverable via
            # ``get_group_attributes()``.
            return PDFormXObject(base)
        if subtype == "PS":
            # PDPostScriptXObject is not yet ported; surface this as the
            # same OSError shape upstream uses for the general invalid
            # subtype branch so callers get a deterministic failure.
            raise OSError("PDPostScriptXObject is not yet supported")
        raise OSError(f"Invalid XObject Subtype: {subtype}")

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

    def get_sub_type(self) -> str | None:
        """Mechanical snake_case translation of upstream ``getSubType()``
        (camelCase → snake_case treats the second capital ``T`` as a word
        boundary). Identical to :meth:`get_subtype`; both spellings are
        kept live so call sites that follow either convention compile."""
        return self.get_subtype()

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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PDXObject):
            return NotImplemented
        return self._stream.get_cos_object() is other._stream.get_cos_object()

    def __hash__(self) -> int:
        return id(self._stream.get_cos_object())

    def __repr__(self) -> str:
        return f"{type(self).__name__}(subtype={self.get_subtype()!r})"
