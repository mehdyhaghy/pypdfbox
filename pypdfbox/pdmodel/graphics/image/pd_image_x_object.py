from __future__ import annotations

from collections.abc import Sequence
from typing import BinaryIO

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject

_IMAGE: COSName = COSName.get_pdf_name("Image")
_WIDTH: COSName = COSName.get_pdf_name("Width")
_HEIGHT: COSName = COSName.get_pdf_name("Height")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_BPC: COSName = COSName.get_pdf_name("BPC")
_COLORSPACE: COSName = COSName.get_pdf_name("ColorSpace")
_CS: COSName = COSName.get_pdf_name("CS")
_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]


class PDImageXObject(PDXObject):
    """
    Image XObject (``/Subtype /Image``). Mirrors
    ``org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject``.

    Cluster #3 ships only the *metadata + raw filter pipeline* surface —
    actual image decoding (CCITT / JPEG / JBIG2 / JPX / lossless), color-
    space resolution, and ``BufferedImage`` rendering are deferred to
    later clusters (PRD §6.12).

    What we expose here matches the data already available without an
    image-decoding stack: ``/Width``, ``/Height``, ``/BitsPerComponent``
    (and short alias ``/BPC``), ``/ColorSpace`` (returned as the raw
    ``COSName`` or ``None`` — typed ``PDColorSpace`` lands in cluster #9),
    the ``/Filter`` chain, and ``create_input_stream`` over the decoded
    body via ``PDStream``.
    """

    def __init__(self, stream: PDStream | COSStream) -> None:
        super().__init__(stream, _IMAGE)

    # ---------- /Width, /Height ----------

    def get_width(self) -> int:
        return self.get_cos_object().get_int(_WIDTH, -1)

    def set_width(self, width: int) -> None:
        self.get_cos_object().set_int(_WIDTH, int(width))

    def get_height(self) -> int:
        return self.get_cos_object().get_int(_HEIGHT, -1)

    def set_height(self, height: int) -> None:
        self.get_cos_object().set_int(_HEIGHT, int(height))

    # ---------- /BitsPerComponent ----------

    def get_bits_per_component(self) -> int:
        """``/BitsPerComponent`` (long form first, falling back to ``/BPC``).
        Returns ``-1`` when absent."""
        cos = self.get_cos_object()
        value = cos.get_int(_BITS_PER_COMPONENT, -1)
        if value == -1:
            value = cos.get_int(_BPC, -1)
        return value

    def set_bits_per_component(self, bpc: int) -> None:
        self.get_cos_object().set_int(_BITS_PER_COMPONENT, int(bpc))

    # ---------- /ColorSpace ----------

    def get_color_space(self) -> COSName | None:
        """Cluster #3 returns the raw ``/ColorSpace`` name (or ``None``).
        The typed ``PDColorSpace`` wrapper lands with pdmodel cluster #9
        (graphics/color)."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_COLORSPACE)
        if value is None:
            value = cos.get_dictionary_object(_CS)
        if isinstance(value, COSName):
            return value
        return None

    def set_color_space(self, name: COSName | str | None) -> None:
        cos = self.get_cos_object()
        if name is None:
            cos.remove_item(_COLORSPACE)
            return
        cos.set_item(
            _COLORSPACE,
            name if isinstance(name, COSName) else COSName.get_pdf_name(name),
        )

    # ---------- /Filter ----------

    def get_filter(self) -> COSName | COSArray | None:
        """Raw ``/Filter`` value — single name, array, or ``None``.
        Mirrors upstream's ``getCOSObject().getFilter()`` access pattern.
        For a *normalized list*, use ``get_stream().get_filters()``."""
        return self.get_cos_object().get_dictionary_object(_FILTER)

    # ---------- decoded bytes ----------

    def create_input_stream(
        self,
        stop_filters: Sequence[str | COSName] | None = None,
    ) -> BinaryIO:
        """Decoded body. Delegates to ``PDStream.create_input_stream`` so
        the same stop-filter semantics apply (e.g. images stop at
        ``DCTDecode`` to keep JPEG bytes intact for downstream encoders)."""
        return self.get_stream().create_input_stream(stop_filters)
