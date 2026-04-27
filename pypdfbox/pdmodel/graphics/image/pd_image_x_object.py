from __future__ import annotations

import io
from collections.abc import Sequence
from typing import BinaryIO

from PIL import Image

from pypdfbox.cos import COSArray, COSBase, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color import PDColorSpace
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

    Cluster #3 shipped only the *metadata + raw filter pipeline* surface.
    The current surface adds typed color-space resolution through
    ``PDColorSpace.create`` plus a small PIL helper for the raw/JPEG image
    forms already supported by the dependency stack.

    Existing stream metadata APIs are preserved: ``/Width``, ``/Height``,
    ``/BitsPerComponent`` (and short alias ``/BPC``), raw ``/ColorSpace``
    access through ``get_color_space_cos_object``, the ``/Filter`` chain,
    and ``create_input_stream`` over the decoded body via ``PDStream``.
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

    def get_color_space_cos_object(self) -> COSBase | None:
        """Raw ``/ColorSpace`` value, falling back to the short ``/CS`` alias."""
        cos = self.get_cos_object()
        value = cos.get_dictionary_object(_COLORSPACE)
        if value is None:
            value = cos.get_dictionary_object(_CS)
        return value

    def get_color_space(self) -> PDColorSpace | None:
        """Typed ``/ColorSpace`` wrapper, or ``None`` when absent/unsupported."""
        return PDColorSpace.create(self.get_color_space_cos_object())

    def set_color_space(self, name: PDColorSpace | COSName | str | None) -> None:
        cos = self.get_cos_object()
        if name is None:
            cos.remove_item(_COLORSPACE)
            return
        if isinstance(name, PDColorSpace):
            value = name.get_cos_object()
        else:
            value = name if isinstance(name, COSName) else COSName.get_pdf_name(name)
        if value is not None:
            cos.set_item(_COLORSPACE, value)

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

    # ---------- PIL image helper ----------

    def to_pil_image(self) -> Image.Image | None:
        """Best-effort conversion to a PIL image.

        Supports DCT/JPX payloads via Pillow and raw 8-bit DeviceRGB or
        DeviceGray rasters. More complex PDF image features such as decode
        arrays, masks, Indexed expansion, and non-8bpc samples remain
        rendering-cluster work and return ``None`` here.
        """
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return None
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return None

        filter_names = {item.name for item in cos.get_filter_list()}
        if "DCTDecode" in filter_names:
            with self.create_input_stream(stop_filters=["DCTDecode"]) as src:
                return Image.open(io.BytesIO(src.read())).convert("RGB")
        if "JPXDecode" in filter_names:
            with self.create_input_stream(stop_filters=["JPXDecode"]) as src:
                return Image.open(io.BytesIO(src.read())).convert("RGB")

        bpc = self.get_bits_per_component()
        if bpc not in (8, -1):
            return None
        color_space = self.get_color_space()
        color_space_name = color_space.get_name() if color_space is not None else None
        with self.create_input_stream() as src:
            data = src.read()
        rgb_len = width * height * 3
        gray_len = width * height
        if color_space_name == "DeviceRGB" or (
            color_space_name is None and len(data) >= rgb_len
        ):
            if len(data) < rgb_len:
                return None
            return Image.frombytes("RGB", (width, height), data[:rgb_len])
        if color_space_name == "DeviceGray":
            if len(data) < gray_len:
                return None
            return Image.frombytes("L", (width, height), data[:gray_len]).convert("RGB")
        return None
