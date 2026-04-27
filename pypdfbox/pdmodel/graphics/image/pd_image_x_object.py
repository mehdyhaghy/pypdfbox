from __future__ import annotations

import io
import logging
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, BinaryIO

from PIL import Image

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSFloat, COSInteger, COSName, COSStream
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.graphics.color import PDColorSpace
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject

_LOG = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
    from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList

_IMAGE: COSName = COSName.get_pdf_name("Image")
_WIDTH: COSName = COSName.get_pdf_name("Width")
_HEIGHT: COSName = COSName.get_pdf_name("Height")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_BPC: COSName = COSName.get_pdf_name("BPC")
_COLORSPACE: COSName = COSName.get_pdf_name("ColorSpace")
_CS: COSName = COSName.get_pdf_name("CS")
_FILTER: COSName = COSName.FILTER  # type: ignore[attr-defined]
_MASK: COSName = COSName.get_pdf_name("Mask")
_SMASK: COSName = COSName.get_pdf_name("SMask")
_DECODE: COSName = COSName.get_pdf_name("Decode")
_INTERPOLATE: COSName = COSName.get_pdf_name("Interpolate")
_IMAGE_MASK: COSName = COSName.get_pdf_name("ImageMask")
_STRUCT_PARENT: COSName = COSName.get_pdf_name("StructParent")
_METADATA: COSName = COSName.METADATA  # type: ignore[attr-defined]
_OC: COSName = COSName.get_pdf_name("OC")


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

    # ---------- /Mask (explicit-mask Image XObject) ----------

    def get_mask(self) -> PDImageXObject | None:
        """Return the explicit-mask ``/Mask`` Image XObject when ``/Mask`` is
        a stream. When ``/Mask`` is a COSArray (color-key mask) this returns
        ``None`` — use :meth:`get_color_key_mask` for that form.

        Mirrors upstream ``PDImageXObject.getMask()``.
        """
        value = self.get_cos_object().get_dictionary_object(_MASK)
        if isinstance(value, COSStream):
            return PDImageXObject(value)
        return None

    def set_mask(self, value: PDImageXObject | None) -> None:
        """Set ``/Mask`` to an explicit-mask Image XObject (stream form).
        Pass ``None`` to remove the entry. Removes any previous color-key
        ``/Mask`` array as well — only one form may be present at a time."""
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_MASK)
            return
        cos.set_item(_MASK, value.get_cos_object())

    # ---------- /Mask (color-key mask) ----------

    def get_color_key_mask(self) -> list[int] | None:
        """Return the ``/Mask`` color-key range list when ``/Mask`` is a
        COSArray of ``[min1 max1 min2 max2 ...]`` integers; returns ``None``
        when ``/Mask`` is absent or carries an explicit-mask stream.

        Mirrors upstream ``PDImageXObject.getColorKeyMask()``.
        """
        value = self.get_cos_object().get_dictionary_object(_MASK)
        if not isinstance(value, COSArray):
            return None
        out: list[int] = []
        for item in value:
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(int(item.value))
            else:
                # Per spec entries are integers; bail out rather than guess.
                return None
        return out

    def set_color_key_mask(self, values: Iterable[int] | None) -> None:
        """Replace ``/Mask`` with a color-key mask COSArray of integers.
        Pass ``None`` to remove the entry."""
        cos = self.get_cos_object()
        if values is None:
            cos.remove_item(_MASK)
            return
        array = COSArray()
        for v in values:
            array.add(COSInteger.get(int(v)))
        cos.set_item(_MASK, array)

    # ---------- /SMask ----------

    def get_soft_mask(self) -> PDImageXObject | None:
        """Return the ``/SMask`` soft-mask Image XObject, or ``None``."""
        value = self.get_cos_object().get_dictionary_object(_SMASK)
        if isinstance(value, COSStream):
            return PDImageXObject(value)
        return None

    def set_soft_mask(self, value: PDImageXObject | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_SMASK)
            return
        cos.set_item(_SMASK, value.get_cos_object())

    # ---------- /Decode ----------

    def get_decode(self) -> list[float] | None:
        """``/Decode`` color-component min/max pairs, or ``None`` when absent."""
        value = self.get_cos_object().get_dictionary_object(_DECODE)
        if not isinstance(value, COSArray):
            return None
        return value.to_float_array()

    def set_decode(self, values: Iterable[float] | None) -> None:
        cos = self.get_cos_object()
        if values is None:
            cos.remove_item(_DECODE)
            return
        array = COSArray()
        for v in values:
            array.add(COSFloat(float(v)))
        cos.set_item(_DECODE, array)

    # ---------- /Interpolate ----------

    def is_interpolate(self) -> bool:
        """``/Interpolate`` flag; default ``False`` per PDF 32000-1 Table 89."""
        return self.get_cos_object().get_boolean(_INTERPOLATE, False)

    def set_interpolate(self, value: bool) -> None:
        self.get_cos_object().set_boolean(_INTERPOLATE, bool(value))

    # ---------- /ImageMask ----------

    def is_image_mask(self) -> bool:
        """``/ImageMask`` flag; default ``False`` per PDF 32000-1 Table 89."""
        return self.get_cos_object().get_boolean(_IMAGE_MASK, False)

    def set_image_mask(self, value: bool) -> None:
        self.get_cos_object().set_boolean(_IMAGE_MASK, bool(value))

    # ---------- stencil (upstream PDImage interface aliases) ----------

    def is_stencil(self) -> bool:
        """Whether this is a stencil mask. Mirrors upstream
        ``PDImage.isStencil()`` which reads ``/ImageMask``."""
        return self.is_image_mask()

    def set_stencil(self, is_stencil: bool) -> None:
        """Mark this image as a stencil mask. Mirrors upstream
        ``PDImage.setStencil(boolean)`` which writes ``/ImageMask``."""
        self.set_image_mask(is_stencil)

    # ---------- /StructParent ----------

    def get_struct_parent(self) -> int:
        """``/StructParent`` integer key into the structure parent tree;
        default ``-1`` when absent (mirrors upstream)."""
        return self.get_cos_object().get_int(_STRUCT_PARENT, -1)

    def set_struct_parent(self, value: int) -> None:
        self.get_cos_object().set_int(_STRUCT_PARENT, int(value))

    # ---------- /Metadata ----------

    def get_metadata(self) -> PDMetadata | None:
        """Typed ``/Metadata`` XMP wrapper; ``None`` when absent."""
        # Local import to avoid an import cycle with PDMetadata's PDDocument
        # dependency at package import time.
        from pypdfbox.pdmodel.common.pd_metadata import PDMetadata  # noqa: PLC0415

        value = self.get_cos_object().get_dictionary_object(_METADATA)
        if isinstance(value, COSStream):
            return PDMetadata(value)
        return None

    def set_metadata(self, value: PDMetadata | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_METADATA)
            return
        cos.set_item(_METADATA, value.get_cos_object())

    # ---------- /OC ----------

    def get_oc(self) -> PDPropertyList | None:
        """Typed ``/OC`` optional content membership; ``None`` when absent
        or carries an unrecognised /Type."""
        # Local import to avoid an import cycle with the optionalcontent
        # subpackage (which itself imports image-cluster types in places).
        from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList  # noqa: PLC0415

        value = self.get_cos_object().get_dictionary_object(_OC)
        if isinstance(value, COSDictionary):
            return PDPropertyList.create(value)
        return None

    def set_oc(self, value: PDPropertyList | None) -> None:
        cos = self.get_cos_object()
        if value is None:
            cos.remove_item(_OC)
            return
        cos.set_item(_OC, value.get_cos_object())

    # ---------- PIL image helper ----------

    def to_pil_image(self) -> Image.Image | None:
        """Best-effort conversion to a PIL image.

        Supports DCT/JPX payloads via Pillow and raw 8-bit DeviceRGB,
        DeviceGray, ``Separation``, and ``DeviceN`` rasters. ``Separation``
        and ``DeviceN`` evaluate the colour space's tint transform via
        :class:`PDFunction` and forward the result to the alternate
        colour space (typically DeviceCMYK or DeviceRGB) before
        compositing into sRGB.

        More complex PDF image features such as decode arrays, masks,
        Indexed expansion, and non-8bpc samples remain rendering-cluster
        work and return ``None`` here.
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
        if color_space_name in ("Separation", "DeviceN"):
            return _decode_devicen_to_rgb(
                color_space, data, width, height
            )
        return None


def _decode_devicen_to_rgb(
    color_space: PDColorSpace,
    data: bytes,
    width: int,
    height: int,
) -> Image.Image | None:
    """Decode an 8-bit DeviceN/Separation raster into an sRGB PIL image.

    For each pixel, reads ``n`` tint bytes (one per colorant), normalises
    each to ``[0, 1]``, and forwards through the colour space's ``to_rgb``
    helper (which evaluates the tint transform and converts via the
    alternate colour space). Falls back to a luminance-only display
    when any step fails — emitted at debug level rather than raising
    so a single bad pixel cannot abort decoding of the whole page.
    """
    n = color_space.get_number_of_components()
    if n <= 0:
        _LOG.debug(
            "DeviceN/Separation image: zero components, falling back to luminance"
        )
        return _luminance_fallback(data, width, height, max(1, n))
    expected = width * height * n
    if len(data) < expected:
        _LOG.debug(
            "DeviceN/Separation image: short raster (%d < %d), aborting",
            len(data), expected,
        )
        return None
    cs_to_rgb = getattr(color_space, "to_rgb", None)
    if cs_to_rgb is None:
        _LOG.debug(
            "DeviceN/Separation image: %r has no to_rgb(), falling back to luminance",
            color_space.get_name(),
        )
        return _luminance_fallback(data, width, height, n)

    out = bytearray(width * height * 3)
    cache: dict[tuple[int, ...], tuple[int, int, int]] = {}
    fallback_used = False
    for pixel in range(width * height):
        offset = pixel * n
        sample = tuple(data[offset : offset + n])
        rgb = cache.get(sample)
        if rgb is None:
            try:
                components = [b / 255.0 for b in sample]
                triple = cs_to_rgb(components)
            except Exception:  # noqa: BLE001 - defensive: any eval/alt-space failure
                triple = None
            if triple is None:
                fallback_used = True
                # Per-pixel luminance fallback: average the tint bytes.
                avg = sum(sample) // n if n > 0 else 0
                rgb = (avg, avg, avg)
            else:
                r, g, b = triple
                rgb = (
                    int(round(_clamp01(r) * 255.0)),
                    int(round(_clamp01(g) * 255.0)),
                    int(round(_clamp01(b) * 255.0)),
                )
            cache[sample] = rgb
        out_offset = pixel * 3
        out[out_offset] = rgb[0]
        out[out_offset + 1] = rgb[1]
        out[out_offset + 2] = rgb[2]
    if fallback_used:
        _LOG.debug(
            "DeviceN/Separation image: tint transform failed for one or more "
            "samples; affected pixels rendered as luminance"
        )
    return Image.frombytes("RGB", (width, height), bytes(out))


def _luminance_fallback(
    data: bytes, width: int, height: int, n: int
) -> Image.Image | None:
    """Render an N-component raster as a grayscale image by averaging
    the per-pixel tint bytes. Used only when the tint transform cannot
    be evaluated."""
    expected = width * height * n
    if len(data) < expected:
        return None
    if n == 1:
        return Image.frombytes(
            "L", (width, height), data[:expected]
        ).convert("RGB")
    out = bytearray(width * height)
    for pixel in range(width * height):
        offset = pixel * n
        out[pixel] = sum(data[offset : offset + n]) // n
    return Image.frombytes("L", (width, height), bytes(out)).convert("RGB")


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value
