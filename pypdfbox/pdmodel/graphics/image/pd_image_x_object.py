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
_SMASK_IN_DATA: COSName = COSName.get_pdf_name("SMaskInData")
_DCT_DECODE: COSName = COSName.get_pdf_name("DCTDecode")
_JPX_DECODE: COSName = COSName.get_pdf_name("JPXDecode")
_CCITTFAX_DECODE: COSName = COSName.get_pdf_name("CCITTFaxDecode")
_FLATE_DECODE: COSName = COSName.get_pdf_name("FlateDecode")
_LZW_DECODE: COSName = COSName.get_pdf_name("LZWDecode")
_RUN_LENGTH_DECODE: COSName = COSName.get_pdf_name("RunLengthDecode")
_JBIG2_DECODE: COSName = COSName.get_pdf_name("JBIG2Decode")
_MATTE: COSName = COSName.get_pdf_name("Matte")
_DCT: COSName = COSName.get_pdf_name("DCT")
_JPX: COSName = COSName.get_pdf_name("JPX")
_CCF: COSName = COSName.get_pdf_name("CCF")
_FL: COSName = COSName.get_pdf_name("Fl")
_LZW: COSName = COSName.get_pdf_name("LZW")
_RL: COSName = COSName.get_pdf_name("RL")

# Public ``/Subtype /Image`` constant. Mirrors upstream's reliance on
# ``COSName.IMAGE`` for ``/Subtype`` checks across the image cluster, and
# lets callers identify Image XObjects without re-deriving the name.
SUBTYPE_IMAGE: COSName = _IMAGE


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

    # ---------- factory helpers ----------

    @staticmethod
    def create_thumbnail(cos_stream: COSStream) -> PDImageXObject:
        """Create a thumbnail Image XObject from ``cos_stream``. Mirrors
        upstream ``PDImageXObject.createThumbnail(COSStream)``: thumbnails
        are special — any non-null ``/Subtype`` is treated as ``/Image``,
        so this wraps the stream in a :class:`PDStream` and constructs the
        XObject directly. The construction stamps ``/Type /XObject`` and
        ``/Subtype /Image`` on the underlying dictionary."""
        return PDImageXObject(PDStream(cos_stream))

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

        Stencil masks always report ``1`` regardless of the dictionary
        entry — mirrors upstream ``PDImageXObject.getBitsPerComponent``
        which short-circuits via ``isStencil()`` before reading the
        dictionary. Returns ``-1`` when neither ``/BitsPerComponent``
        nor ``/BPC`` is present on a non-stencil image.
        """
        if self.is_stencil():
            return 1
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
        value = self.get_color_space_cos_object()
        if value is not None:
            return PDColorSpace.create(value)
        if self.is_stencil():
            from pypdfbox.pdmodel.graphics.color import PDDeviceGray  # noqa: PLC0415

            return PDDeviceGray.INSTANCE
        return None

    def set_color_space(self, name: PDColorSpace | COSName | str | None) -> None:
        cos = self.get_cos_object()
        if name is None:
            self.clear_color_space()
            return
        if isinstance(name, PDColorSpace):
            value = name.get_cos_object()
        else:
            value = name if isinstance(name, COSName) else COSName.get_pdf_name(name)
        if value is not None:
            cos.set_item(_COLORSPACE, value)

    def clear_color_space(self) -> None:
        """Remove both long and short color-space entries. No-op if absent."""
        cos = self.get_cos_object()
        cos.remove_item(_COLORSPACE)
        cos.remove_item(_CS)

    # ---------- /Filter ----------

    def get_filter(self) -> COSName | COSArray | None:
        """Raw ``/Filter`` value — single name, array, or ``None``.
        Mirrors upstream's ``getCOSObject().getFilter()`` access pattern.
        For a *normalized list*, use ``get_stream().get_filters()``."""
        value = self.get_cos_object().get_dictionary_object(_FILTER)
        if isinstance(value, (COSName, COSArray)):
            return value
        return None

    # ---------- decoded bytes ----------

    def create_input_stream(
        self,
        stop_filters: Sequence[str | COSName] | None = None,
    ) -> BinaryIO:
        """Decoded body. Delegates to ``PDStream.create_input_stream`` so
        the same stop-filter semantics apply (e.g. images stop at
        ``DCTDecode`` to keep JPEG bytes intact for downstream encoders)."""
        return self.get_stream().create_input_stream(stop_filters)

    def is_empty(self) -> bool:
        """Return ``True`` when the underlying stream has no raw data."""
        cos = self.get_cos_object()
        return isinstance(cos, COSStream) and cos.get_length() == 0

    def get_suffix(self) -> str | None:
        """Return the conventional file suffix implied by the image filters.

        Mirrors upstream ``PDImageXObject.getSuffix()``: no filter and
        lossless PDF filters are treated as PNG-exportable image data,
        JPEG/JPEG2000/CCITT/JBIG2 filters use their native suffixes, and
        unsupported filters return ``None``.
        """
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return None
        filters = cos.get_filter_list()
        if not filters:
            return "png"
        if _has_named_filter(filters, _DCT_DECODE, _DCT):
            return "jpg"
        if _has_named_filter(filters, _JPX_DECODE, _JPX):
            return "jpx"
        if _has_named_filter(filters, _CCITTFAX_DECODE, _CCF):
            return "tiff"
        if _has_named_filter(
            filters,
            _FLATE_DECODE,
            _FL,
            _LZW_DECODE,
            _LZW,
            _RUN_LENGTH_DECODE,
            _RL,
        ):
            return "png"
        if _JBIG2_DECODE in filters:
            return "jb2"
        _LOG.warning("get_suffix() returns None, filters: %s", filters)
        return None

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
            self.clear_mask()
            return
        cos.set_item(_MASK, value.get_cos_object())

    def clear_mask(self) -> None:
        """Remove ``/Mask``. No-op if absent."""
        self.get_cos_object().remove_item(_MASK)

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

    def get_color_key_mask_array(self) -> COSArray | None:
        """Return the raw ``/Mask`` ``COSArray`` when the entry is the
        color-key form (``[min1 max1 ...]``), or ``None`` otherwise.

        Mirrors upstream ``PDImageXObject.getColorKeyMask()`` which returns
        the underlying ``COSArray`` directly. Use :meth:`get_color_key_mask`
        for the decoded ``list[int]`` form."""
        value = self.get_cos_object().get_dictionary_object(_MASK)
        if isinstance(value, COSArray):
            return value
        return None

    def set_color_key_mask(self, values: Iterable[int] | None) -> None:
        """Replace ``/Mask`` with a color-key mask COSArray of integers.
        Pass ``None`` to remove the entry."""
        cos = self.get_cos_object()
        if values is None:
            self.clear_mask()
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
            self.clear_soft_mask()
            return
        cos.set_item(_SMASK, value.get_cos_object())

    def clear_soft_mask(self) -> None:
        """Remove ``/SMask``. No-op if absent."""
        self.get_cos_object().remove_item(_SMASK)

    # ---------- /SMaskInData (JPEG2000-only optional hint) ----------

    def get_smask_in_data(self) -> int:
        """``/SMaskInData`` integer (one of ``0``, ``1``, ``2``); default
        ``0`` per PDF 32000-1 Table 89. Only meaningful for JPXDecode
        images. Mirrors upstream ``PDImageXObject.getSMaskInData()``."""
        return self.get_cos_object().get_int(_SMASK_IN_DATA, 0)

    def set_smask_in_data(self, value: int) -> None:
        """Set ``/SMaskInData`` (must be ``0``, ``1``, or ``2`` per spec).
        Mirrors upstream ``PDImageXObject.setSMaskInData(int)``."""
        if value not in (0, 1, 2):
            raise ValueError(
                f"/SMaskInData must be 0, 1, or 2 (PDF 32000-1 Table 89); got {value!r}"
            )
        self.get_cos_object().set_int(_SMASK_IN_DATA, int(value))

    # ---------- /Decode ----------

    def get_decode(self) -> list[float] | None:
        """``/Decode`` color-component min/max pairs, or ``None`` when absent."""
        value = self.get_cos_object().get_dictionary_object(_DECODE)
        return _numeric_array_to_floats(value)

    def get_decode_array(self) -> COSArray | None:
        """Return the raw ``/Decode`` ``COSArray`` (or ``None`` when
        absent or not an array). Mirrors upstream
        ``PDImageXObject.getDecode()`` which returns the underlying
        ``COSArray`` directly. Use :meth:`get_decode` for the decoded
        ``list[float]`` form."""
        value = self.get_cos_object().get_dictionary_object(_DECODE)
        if isinstance(value, COSArray):
            return value
        return None

    def set_decode(self, values: Iterable[float] | None) -> None:
        cos = self.get_cos_object()
        if values is None:
            self.clear_decode()
            return
        array = COSArray()
        for v in values:
            array.add(COSFloat(float(v)))
        cos.set_item(_DECODE, array)

    def set_decode_array(self, decode: COSArray | None) -> None:
        """Set ``/Decode`` to a pre-built ``COSArray``. Mirrors upstream
        ``PDImageXObject.setDecode(COSArray)`` exactly — pass ``None`` to
        remove the entry. Use :meth:`set_decode` for the float-iterable
        convenience form."""
        cos = self.get_cos_object()
        if decode is None:
            self.clear_decode()
            return
        cos.set_item(_DECODE, decode)

    def clear_decode(self) -> None:
        """Remove ``/Decode``. No-op if absent."""
        self.get_cos_object().remove_item(_DECODE)

    # ---------- /Matte (soft-mask only) ----------

    def get_matte(self) -> list[float] | None:
        """Return the soft-mask ``/Matte`` array as a ``list[float]``,
        or ``None`` when absent or not a COSArray.

        ``/Matte`` is only meaningful on soft-mask Image XObjects (see
        PDF 32000-1 §11.6.5.3); on a regular image it will normally be
        absent. Mirrors upstream's private ``extractMatte`` reader, which
        reads ``COSName.MATTE`` from the soft-mask's COS object via
        ``COSArray.toFloatArray``."""
        value = self.get_cos_object().get_dictionary_object(_MATTE)
        return _numeric_array_to_floats(value)

    def get_matte_array(self) -> COSArray | None:
        """Return the raw ``/Matte`` ``COSArray`` (or ``None``). Use
        :meth:`get_matte` for the decoded ``list[float]`` form."""
        value = self.get_cos_object().get_dictionary_object(_MATTE)
        if isinstance(value, COSArray):
            return value
        return None

    def set_matte(self, values: Iterable[float] | None) -> None:
        """Set ``/Matte`` to a list of float matte components. Pass
        ``None`` to remove the entry. ``/Matte`` is only meaningful on
        soft-mask Image XObjects."""
        cos = self.get_cos_object()
        if values is None:
            self.clear_matte()
            return
        array = COSArray()
        for v in values:
            array.add(COSFloat(float(v)))
        cos.set_item(_MATTE, array)

    def clear_matte(self) -> None:
        """Remove ``/Matte``. No-op if absent."""
        self.get_cos_object().remove_item(_MATTE)

    # ---------- /Interpolate ----------

    def is_interpolate(self) -> bool:
        """``/Interpolate`` flag; default ``False`` per PDF 32000-1 Table 89."""
        return self.get_cos_object().get_boolean(_INTERPOLATE, False)

    def get_interpolate(self) -> bool:
        """Mechanical mirror of upstream ``PDImage.getInterpolate()``;
        identical to :meth:`is_interpolate`."""
        return self.is_interpolate()

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
            self.clear_metadata()
            return
        cos.set_item(_METADATA, value.get_cos_object())

    def clear_metadata(self) -> None:
        """Remove ``/Metadata``. No-op if absent."""
        self.get_cos_object().remove_item(_METADATA)

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
            self.clear_optional_content()
            return
        cos.set_item(_OC, value.get_cos_object())

    # Mechanical aliases mirroring upstream
    # ``PDImageXObject.getOptionalContent()`` / ``setOptionalContent()``
    # — the longer-named accessors are the ones used in the upstream
    # public API; ``get_oc`` / ``set_oc`` remain for the short COS-key
    # form.
    def get_optional_content(self) -> PDPropertyList | None:
        """Typed ``/OC`` optional content membership; mirrors upstream
        ``PDImageXObject.getOptionalContent()``."""
        return self.get_oc()

    def set_optional_content(self, value: PDPropertyList | None) -> None:
        """Mirrors upstream ``PDImageXObject.setOptionalContent()``."""
        self.set_oc(value)

    def clear_oc(self) -> None:
        """Remove ``/OC``. No-op if absent."""
        self.clear_optional_content()

    def clear_optional_content(self) -> None:
        """Remove ``/OC`` optional-content membership. No-op if absent."""
        self.get_cos_object().remove_item(_OC)

    # ---------- presence predicates ----------

    def has_mask(self) -> bool:
        """Return ``True`` when the dictionary carries any ``/Mask``
        entry — explicit-mask stream or color-key array."""
        return self.get_cos_object().get_dictionary_object(_MASK) is not None

    def has_explicit_mask(self) -> bool:
        """Return ``True`` when ``/Mask`` is an explicit-mask Image
        XObject (stream form)."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_MASK), COSStream
        )

    def has_color_key_mask(self) -> bool:
        """Return ``True`` when ``/Mask`` is a valid color-key array."""
        return self.get_color_key_mask() is not None

    def has_soft_mask(self) -> bool:
        """Return ``True`` when ``/SMask`` is a stream."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_SMASK), COSStream
        )

    def has_color_space(self) -> bool:
        """Return ``True`` when ``/ColorSpace`` (or short ``/CS``) is set."""
        return self.get_color_space_cos_object() is not None

    def has_metadata(self) -> bool:
        """Return ``True`` when ``/Metadata`` is a stream."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_METADATA), COSStream
        )

    def has_optional_content(self) -> bool:
        """Return ``True`` when ``/OC`` carries an optional-content
        dictionary."""
        return isinstance(
            self.get_cos_object().get_dictionary_object(_OC), COSDictionary
        )

    def has_decode(self) -> bool:
        """Return ``True`` when ``/Decode`` is a numeric COSArray."""
        return self.get_decode() is not None

    def has_matte(self) -> bool:
        """Return ``True`` when ``/Matte`` is a numeric COSArray. Only
        meaningful on soft-mask Image XObjects."""
        return self.get_matte() is not None

    # ---------- filter-type predicates ----------

    def _has_filter(self, filter_name: COSName) -> bool:
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return False
        return filter_name in cos.get_filter_list()

    def is_jpeg(self) -> bool:
        """Return ``True`` when the filter chain contains ``/DCTDecode``."""
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return False
        return _has_named_filter(cos.get_filter_list(), _DCT_DECODE, _DCT)

    def is_jpx(self) -> bool:
        """Return ``True`` when the filter chain contains ``/JPXDecode``."""
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return False
        return _has_named_filter(cos.get_filter_list(), _JPX_DECODE, _JPX)

    def is_jbig2(self) -> bool:
        """Return ``True`` when the filter chain contains ``/JBIG2Decode``."""
        return self._has_filter(_JBIG2_DECODE)

    def is_ccittfax(self) -> bool:
        """Return ``True`` when the filter chain contains ``/CCITTFaxDecode``."""
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return False
        return _has_named_filter(cos.get_filter_list(), _CCITTFAX_DECODE, _CCF)

    # ---------- PIL image helper ----------

    def to_pil_image(self) -> Image.Image | None:
        """Best-effort conversion to a PIL image.

        Supports DCT/JPX payloads via Pillow and raw 8-bit DeviceRGB,
        DeviceGray, DeviceCMYK, ``Separation``, and ``DeviceN`` rasters.
        ``Separation`` and ``DeviceN`` evaluate the colour space's tint
        transform via :class:`PDFunction` and forward the result to the
        alternate colour space (typically DeviceCMYK or DeviceRGB)
        before compositing into sRGB.

        Raw DeviceGray rasters support 1/2/4/8/16 bits per
        component, while Indexed rasters support 1/2/4/8 bits per
        component; raw 8-bit DeviceRGB and DeviceCMYK rasters apply
        simple component-wise ``/Decode`` arrays. More complex PDF image
        features such as masks, multi-component 16-bit samples, and
        non-device color models remain rendering-cluster work and
        return ``None`` here.
        """
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return None
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return None

        filter_names = {item.name for item in cos.get_filter_list()}
        if "DCTDecode" in filter_names or "DCT" in filter_names:
            with self.create_input_stream(stop_filters=["DCTDecode", "DCT"]) as src:
                return Image.open(io.BytesIO(src.read())).convert("RGB")
        if "JPXDecode" in filter_names or "JPX" in filter_names:
            with self.create_input_stream(stop_filters=["JPXDecode", "JPX"]) as src:
                return Image.open(io.BytesIO(src.read())).convert("RGB")

        bpc = self.get_bits_per_component()
        color_space = self.get_color_space()
        color_space_name = color_space.get_name() if color_space is not None else None
        sub_byte = bpc in (1, 2, 4)
        if bpc not in (8, -1) and not (
            (sub_byte and color_space_name in ("DeviceGray", "Indexed"))
            or (bpc == 16 and color_space_name == "DeviceGray")
        ):
            return None
        with self.create_input_stream() as src:
            data = src.read()
        rgb_len = width * height * 3
        gray_len = width * height
        pixel_count = width * height
        decode = self.get_decode()
        if color_space_name == "DeviceRGB" or (
            color_space_name is None and len(data) >= rgb_len
        ):
            if len(data) < rgb_len:
                return None
            decoded = _apply_decode_to_8bit_samples(
                data[:rgb_len], pixel_count, 3, decode
            )
            if decoded is None:
                return None
            return Image.frombytes("RGB", (width, height), decoded)
        if color_space_name == "DeviceGray":
            if sub_byte:
                samples = _unpack_sub_byte_samples(data, width, height, bpc)
                if samples is None:
                    return None
            elif bpc == 16:
                samples = _unpack_16bit_samples(data, width, height)
                if samples is None:
                    return None
            else:
                if len(data) < gray_len:
                    return None
                samples = data[:gray_len]
            decoded = _apply_decode_to_8bit_samples(
                samples,
                pixel_count,
                1,
                decode,
                bpc=bpc if sub_byte or bpc == 16 else 8,
            )
            if decoded is None:
                return None
            return Image.frombytes("L", (width, height), decoded).convert("RGB")
        if color_space_name == "DeviceCMYK" and color_space is not None:
            cmyk_len = width * height * 4
            if len(data) < cmyk_len:
                return None
            decoded = _apply_decode_to_8bit_samples(
                data[:cmyk_len], pixel_count, 4, decode
            )
            if decoded is None:
                return None
            return color_space.to_rgb_image(decoded, width, height)
        if color_space_name == "Indexed" and color_space is not None:
            if sub_byte:
                samples = _unpack_sub_byte_samples(data, width, height, bpc)
                if samples is None:
                    return None
                decoded = _apply_decode_to_indexed_samples(
                    samples, pixel_count, decode, bpc=bpc
                )
            else:
                if len(data) < pixel_count:
                    return None
                decoded = _apply_decode_to_indexed_samples(
                    data[:pixel_count], pixel_count, decode, bpc=8
                )
            if decoded is None:
                return None
            return color_space.to_rgb_image(decoded, width, height)
        if color_space_name in ("Separation", "DeviceN") and color_space is not None:
            return _decode_devicen_to_rgb(
                color_space, data, width, height
            )
        return None


def _apply_decode_to_8bit_samples(
    data: Sequence[int],
    pixel_count: int,
    components: int,
    decode: Sequence[float] | None,
    *,
    bpc: int = 8,
) -> bytes | None:
    expected = pixel_count * components
    if len(data) < expected:
        return None
    if decode is None and bpc == 8:
        return data[:expected]
    if decode is None:
        decode = [0.0, 1.0] * components
    elif len(decode) != components * 2:
        return None

    max_sample = float((1 << int(bpc)) - 1)
    if max_sample <= 0.0:
        return None

    out = bytearray(expected)
    for i in range(expected):
        component = i % components
        dmin = decode[component * 2]
        dmax = decode[component * 2 + 1]
        value = dmin + (data[i] / max_sample) * (dmax - dmin)
        out[i] = int(round(_clamp01(value) * 255.0))
    return bytes(out)


def _apply_decode_to_indexed_samples(
    data: bytes,
    pixel_count: int,
    decode: Sequence[float] | None,
    *,
    bpc: int = 8,
) -> bytes | None:
    if len(data) < pixel_count:
        return None
    if decode is None:
        return data[:pixel_count]
    if len(decode) != 2:
        return None

    max_sample = float((1 << int(bpc)) - 1)
    if max_sample <= 0.0:
        return None
    dmin = decode[0]
    dmax = decode[1]
    out = bytearray(pixel_count)
    for i in range(pixel_count):
        value = dmin + (data[i] / max_sample) * (dmax - dmin)
        out[i] = int(round(_clamp(value, 0.0, 255.0)))
    return bytes(out)


def _apply_decode_to_8bit_indexed_samples(
    data: bytes,
    pixel_count: int,
    decode: Sequence[float] | None,
) -> bytes | None:
    return _apply_decode_to_indexed_samples(data, pixel_count, decode, bpc=8)


def _unpack_sub_byte_samples(
    data: bytes,
    width: int,
    height: int,
    bpc: int,
    components: int = 1,
) -> bytes | None:
    if bpc not in (1, 2, 4) or components <= 0:
        return None
    row_samples = int(width) * int(components)
    row_bits = row_samples * int(bpc)
    row_bytes = (row_bits + 7) // 8
    expected = row_bytes * int(height)
    if len(data) < expected:
        return None

    mask = (1 << int(bpc)) - 1
    out = bytearray(row_samples * int(height))
    for y in range(int(height)):
        row_offset = y * row_bytes
        out_offset = y * row_samples
        for sample_index in range(row_samples):
            bit_index = sample_index * int(bpc)
            byte = data[row_offset + (bit_index // 8)]
            shift = 8 - int(bpc) - (bit_index % 8)
            out[out_offset + sample_index] = (byte >> shift) & mask
    return bytes(out)


def _unpack_16bit_samples(
    data: bytes,
    width: int,
    height: int,
    components: int = 1,
) -> list[int] | None:
    sample_count = int(width) * int(height) * int(components)
    expected = sample_count * 2
    if len(data) < expected:
        return None

    out: list[int] = []
    for sample_index in range(sample_count):
        offset = sample_index * 2
        out.append((data[offset] << 8) | data[offset + 1])
    return out


def _numeric_array_to_floats(value: COSBase | None) -> list[float] | None:
    if not isinstance(value, COSArray):
        return None
    out: list[float] = []
    for item in value:
        if not isinstance(item, (COSInteger, COSFloat)):
            return None
        out.append(float(item.value))
    return out


def _has_named_filter(filters: Iterable[COSName], *names: COSName) -> bool:
    return any(filter_name in names for filter_name in filters)


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


def _clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value
