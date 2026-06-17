from __future__ import annotations

import io
import logging
import math
import os
from collections.abc import Iterable, Sequence
from pathlib import Path
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
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_resources import PDResources

    from .pd_image import PDImage

_IMAGE: COSName = COSName.get_pdf_name("Image")
_WIDTH: COSName = COSName.get_pdf_name("Width")
_HEIGHT: COSName = COSName.get_pdf_name("Height")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_BPC: COSName = COSName.get_pdf_name("BPC")
_COLORSPACE: COSName = COSName.get_pdf_name("ColorSpace")
_CS: COSName = COSName.get_pdf_name("CS")

# Sentinel for "no full-region render cached yet" — upstream initialises
# ``cachedImageSubsampling = Integer.MAX_VALUE`` so the first full-region
# render at any subsampling level populates the cache.
_CACHED_IMAGE_SUBSAMPLING_UNSET: int = 2**31 - 1
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

    def __init__(
        self,
        stream: PDStream | COSStream,
        resources: PDResources | None = None,
    ) -> None:
        super().__init__(stream, _IMAGE)
        # Mirror upstream ``PDImageXObject(PDStream, PDResources)``: keep the
        # owning page ``/Resources`` so :meth:`get_color_space` can resolve a
        # *named* ``/ColorSpace`` against the page's ``/Resources/ColorSpace``
        # subdictionary and consult the document-level ResourceCache for
        # indirect colour-space references (PDF 32000-1 §8.9.5.2). ``None`` is
        # the legacy default — callers that wrap a stream directly (masks,
        # thumbnails, factory output) pass no resources, matching upstream's
        # ``resources = null`` constructors.
        self._resources: PDResources | None = resources
        # Per-instance decoded-image cache, mirroring upstream's
        # ``SoftReference<BufferedImage> cachedImage`` +
        # ``int cachedImageSubsampling = Integer.MAX_VALUE`` pair — only
        # full-region renders are cached, preferring the lowest subsampling
        # seen (lower subsampling = higher quality), and :meth:`set_color_space`
        # invalidates the cache. A plain reference replaces the SoftReference
        # (no GC-driven eviction; see :class:`DefaultResourceCache` for the
        # same deliberate deviation).
        self._cached_image: Image.Image | None = None
        self._cached_image_subsampling: int = _CACHED_IMAGE_SUBSAMPLING_UNSET
        # Per-instance typed colour-space cache, mirroring upstream's
        # ``private PDColorSpace colorSpace`` field — built once on the first
        # :meth:`get_color_space` call and reset by :meth:`set_color_space`.
        self._color_space: PDColorSpace | None = None

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

    @staticmethod
    def create_from_file(image_path: str | os.PathLike[str], doc: PDDocument) -> PDImageXObject:
        """Create a ``PDImageXObject`` from an image file path. Mirrors
        upstream ``PDImageXObject.createFromFile(String, PDDocument)``
        (Java line 191), which delegates to
        :meth:`create_from_file_by_extension`."""
        return PDImageXObject.create_from_file_by_extension(Path(image_path), doc)

    @staticmethod
    def create_from_file_by_extension(
        file: str | os.PathLike[str], doc: PDDocument
    ) -> PDImageXObject:
        """Create a ``PDImageXObject`` from an image file. Format is
        determined from the file-name suffix. Mirrors upstream
        ``PDImageXObject.createFromFileByExtension(File, PDDocument)``
        (Java line 217). Supported suffixes: ``jpg``/``jpeg``,
        ``tif``/``tiff``, ``gif``, ``bmp``, ``png``.

        Library-first: PNG/GIF/BMP route through Pillow + the lossless
        factory; TIFF routes through CCITTFactory (with PNG fallback);
        JPEG routes through JPEGFactory.
        """
        from pypdfbox.pdmodel.graphics.image.ccitt_factory import CCITTFactory  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.image.jpeg_factory import JPEGFactory  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.image.lossless_factory import (
            LosslessFactory,  # noqa: PLC0415
        )

        path = Path(file)
        name = path.name
        if "." not in name:
            raise ValueError(f"Image type not supported: {name}")
        ext = name.rsplit(".", 1)[1].lower()
        if ext in ("jpg", "jpeg"):
            with path.open("rb") as fh:
                return JPEGFactory.create_from_stream(doc, fh)
        if ext in ("tif", "tiff"):
            try:
                return CCITTFactory.create_from_file(doc, path)
            except OSError as ex:
                _LOG.debug("Reading as TIFF failed, setting fileType to PNG: %s", ex)
                ext = "png"
        if ext in ("gif", "bmp", "png"):
            with Image.open(path) as bim:
                bim.load()
                return LosslessFactory.create_from_image(doc, bim)
        raise ValueError(f"Image type not supported: {name}")

    @staticmethod
    def create_from_file_by_content(
        file: str | os.PathLike[str], doc: PDDocument
    ) -> PDImageXObject:
        """Create a ``PDImageXObject`` from an image file. Format is
        determined from the file's content (magic bytes), not its
        extension. Mirrors upstream
        ``PDImageXObject.createFromFileByContent(File, PDDocument)``
        (Java line 277). Supported types: JPEG, TIFF, GIF, BMP, PNG.
        """
        path = Path(file)
        try:
            with path.open("rb") as fh:
                head = fh.read(16)
        except OSError as exc:
            raise OSError(f"Could not determine file type: {path.name}") from exc
        file_type = _detect_file_type(head)
        if file_type is None:
            raise ValueError(f"Image type not supported: {path.name}")
        with path.open("rb") as fh:
            data = fh.read()
        return PDImageXObject.create_from_byte_array(doc, data, path.name)

    @staticmethod
    def create_from_byte_array(
        document: PDDocument,
        byte_array: bytes | bytearray | memoryview,
        name: str | None = None,
        custom_factory: object | None = None,
    ) -> PDImageXObject:
        """Create a ``PDImageXObject`` from raw image bytes. Format is
        determined from the file content. Mirrors upstream
        ``PDImageXObject.createFromByteArray(PDDocument, byte[], String)``
        and the four-arg overload accepting a ``CustomFactory``
        (Java lines 345 and 366).

        ``custom_factory`` is accepted for upstream signature parity. If
        non-null and supplied for BMP/GIF/PNG inputs, it must expose
        ``create_from_byte_array(document, byte_array)`` and is preferred
        over the default Pillow + ``LosslessFactory`` path.
        """
        from pypdfbox.pdmodel.graphics.image.ccitt_factory import CCITTFactory  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.image.jpeg_factory import JPEGFactory  # noqa: PLC0415
        from pypdfbox.pdmodel.graphics.image.lossless_factory import (
            LosslessFactory,  # noqa: PLC0415
        )

        if not isinstance(byte_array, (bytes, bytearray, memoryview)):
            raise TypeError(
                f"byte_array must be bytes-like; got {type(byte_array).__name__}"
            )
        data = bytes(byte_array)
        file_type = _detect_file_type(data)
        if file_type is None:
            raise ValueError(f"Image type not supported: {name}")

        if file_type == "JPEG":
            return JPEGFactory.create_from_byte_array(document, data)
        if file_type == "TIFF":
            try:
                return CCITTFactory.create_from_byte_array(document, data)
            except OSError as ex:
                _LOG.debug("Reading as TIFF failed, setting fileType to PNG: %s", ex)
                file_type = "PNG"
        if file_type in ("BMP", "GIF", "PNG"):
            if custom_factory is not None:
                return custom_factory.create_from_byte_array(document, data)  # type: ignore[union-attr]
            with Image.open(io.BytesIO(data)) as bim:
                bim.load()
                return LosslessFactory.create_from_image(document, bim)
        raise ValueError(f"Image type {file_type} not supported: {name}")

    @staticmethod
    def create_raw_stream(document: PDDocument, raw_input: BinaryIO) -> COSStream:
        """Create a ``COSStream`` from already-encoded (raw) bytes.
        Mirrors upstream's private static
        ``PDImageXObject.createRawStream(PDDocument, InputStream)``
        (Java line 170)."""
        cos_doc = document.get_document()
        stream = cos_doc.create_cos_stream()
        with stream.create_raw_output_stream() as output:
            chunk = raw_input.read()
            if isinstance(chunk, (bytes, bytearray, memoryview)):
                output.write(bytes(chunk))
        return stream

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
        """Typed ``/ColorSpace`` wrapper, or ``None`` when absent/unsupported.

        Mirrors upstream ``PDImageXObject.getColorSpace()``: the *raw*
        ``/ColorSpace`` (falling back to ``/CS``) item is handed to
        :meth:`PDColorSpace.create` together with this image's owning
        ``/Resources`` (the value passed to the constructor). Threading
        ``resources`` lets a bare-name colour space resolve against the
        page's ``/Resources/ColorSpace`` subdictionary (PDF 32000-1
        §8.9.5.2) and lets an indirect colour-space reference hit the
        document-level ResourceCache instead of re-parsing on every call —
        the behaviour that was dropped when the constructor lost its
        ``resources`` parameter (DEFERRED.md, wave 1485). The typed wrapper
        is cached per instance (upstream's ``private PDColorSpace
        colorSpace`` field) — repeated calls return the same object until
        :meth:`set_color_space` resets it."""
        if self._color_space is not None:
            return self._color_space
        # Raw item (may be a COSObject indirect ref) — upstream uses
        # getCOSObject().getItem(COLORSPACE, CS); create() unwraps it and,
        # given resources, consults/populates the colour-space cache
        # (PDFBOX-4022).
        value = self.get_cos_object().get_item(_COLORSPACE, _CS)
        if value is not None:
            self._color_space = PDColorSpace.create(value, self._resources)
            return self._color_space
        if self.is_stencil():
            from pypdfbox.pdmodel.graphics.color import PDDeviceGray  # noqa: PLC0415

            self._color_space = PDDeviceGray.INSTANCE
            return self._color_space
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
        # Upstream ``setColorSpace`` resets both per-instance caches
        # (``colorSpace = null; cachedImage = null;``).
        self._color_space = None
        self._cached_image = None
        self._cached_image_subsampling = _CACHED_IMAGE_SUBSAMPLING_UNSET

    def clear_color_space(self) -> None:
        """Remove both long and short color-space entries. No-op if absent."""
        cos = self.get_cos_object()
        cos.remove_item(_COLORSPACE)
        cos.remove_item(_CS)
        self._color_space = None
        self._cached_image = None
        self._cached_image_subsampling = _CACHED_IMAGE_SUBSAMPLING_UNSET

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

    # ---------- rendering surface (mirrors upstream getImage / opaque /
    # stencil / raw raster) ----------

    def get_image(
        self,
        region: tuple[int, int, int, int] | None = None,
        subsampling: int = 1,
    ) -> Image.Image | None:
        """Return a fully-decoded image with any soft/stencil/color-key mask
        composited as the alpha channel. Mirrors upstream
        ``PDImageXObject.getImage()`` and the parameterised overload
        ``getImage(Rectangle, int)`` (Java lines 463 and 472), which return
        an ARGB ``BufferedImage`` once a ``/SMask`` or ``/Mask`` is present.

        Library-first: Pillow handles the actual sample decoding via
        :meth:`to_pil_image`. ``region`` is a ``(x, y, w, h)`` tuple and
        is applied via :meth:`PIL.Image.Image.crop`. ``subsampling`` is
        applied via :meth:`PIL.Image.Image.resize` with nearest-neighbour
        sampling (matches upstream's per-pixel-row-skip semantics for the
        common case ``subsampling >= 1``).

        Mask handling mirrors upstream's ``getImage`` ordering: a ``/SMask``
        (PDF 32000-1 §8.9.5.4) takes precedence and becomes the alpha plane;
        otherwise an explicit-mask ``/Mask`` stencil (§8.9.6.3) or a
        color-key ``/Mask`` range (§8.9.6.4) is applied. The mask plane is
        upscaled to the base image's dimensions when its own dimensions
        differ and its own ``/Decode`` array is honoured (delegated to
        :meth:`to_pil_image`). When no mask is present the opaque raster is
        returned unchanged.
        """
        # Upstream caches full-region renders only, returning the cached
        # raster when the same subsampling level is requested again
        # (``region == null && subsampling == cachedImageSubsampling``).
        if (
            region is None
            and subsampling == self._cached_image_subsampling
            and self._cached_image is not None
        ):
            return self._cached_image
        image = self.to_pil_image()
        if image is None:
            return None
        image = self._apply_image_masks(image)
        if region is not None:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))
        if subsampling > 1:
            image = image.resize(
                (max(1, image.width // subsampling), max(1, image.height // subsampling)),
                Image.NEAREST,
            )
        if region is None and subsampling <= self._cached_image_subsampling:
            # Only cache full-image renders, and prefer lower subsampling
            # frequency: lower subsampling means higher quality and longer
            # render times (upstream Java lines 514-519).
            self._cached_image_subsampling = subsampling
            self._cached_image = image
        return image

    def _apply_image_masks(self, image: Image.Image) -> Image.Image:
        """Composite this image's ``/SMask`` or ``/Mask`` into ``image`` as
        alpha, returning an RGBA image when a mask is present (else ``image``
        unchanged). Mirrors the mask precedence in upstream ``getImage`` —
        ``/SMask`` first, then explicit-mask ``/Mask`` stream, then color-key
        ``/Mask`` array. Each step is best-effort: a mask that fails to decode
        leaves the opaque raster in place rather than raising.

        Upstream ordering (``PDImageXObject.getImage`` → ``applyMask``, Java
        lines 487-512): ``getRGBImage`` does bake a color-key ``/Mask`` array
        into the base ARGB alpha, but when a ``/SMask`` (or stencil ``/Mask``)
        is also present ``applyMask`` then **overwrites band 3 (alpha) outright**
        with the mask samples (``raster.setSamples(...,3,samples)``, Java line
        679) — it does NOT multiply with the color-key alpha. So a color-key
        ``/Mask`` array has no net effect when ``/SMask`` is present: the SMask
        wins and the color-key is discarded. Verified against the 3.0.7 live
        oracle (``test_color_key_mask_smask_oracle.py``). Hence the precedence
        below mirrors upstream exactly — ``/SMask`` first (color-key skipped),
        then explicit-stencil ``/Mask``, then a standalone color-key array."""
        soft_mask = None
        try:
            soft_mask = self.get_soft_mask()
        except Exception:  # noqa: BLE001 - best-effort; opaque raster on failure
            soft_mask = None
        if soft_mask is not None:
            # /SMask replaces the alpha band wholesale (Java applyMask line 679),
            # so the color-key array is discarded — do not apply it here.
            return _apply_soft_mask(image, soft_mask, self)

        explicit_mask = None
        try:
            explicit_mask = self.get_mask()
        except Exception:  # noqa: BLE001
            explicit_mask = None
        if explicit_mask is not None:
            # Stencil /Mask likewise replaces band 3 (Java line 663/679),
            # discarding any color-key array.
            return _apply_explicit_mask(image, explicit_mask)

        color_key = None
        try:
            color_key = self.get_color_key_mask()
        except Exception:  # noqa: BLE001
            color_key = None
        if color_key:
            return _apply_color_key_mask(image, color_key, self)
        return image

    def get_opaque_image(
        self,
        region: tuple[int, int, int, int] | None = None,
        subsampling: int = 1,
    ) -> Image.Image | None:
        """Return the opaque image (raster without any mask applied). If
        this Image XObject is itself a mask, the buffered image carries
        the raw mask. Mirrors upstream ``PDImageXObject.getOpaqueImage()``
        and the parameterised overload (Java lines 585 and 603).

        Unlike :meth:`get_image` this NEVER composites ``/SMask`` /
        ``/Mask`` into the raster — it returns the colour samples alone,
        matching upstream's ``getOpaqueImage`` (which decodes the raster
        without the alpha-mask step). ``region`` / ``subsampling`` are
        applied identically to :meth:`get_image`."""
        image = self.to_pil_image()
        if image is None:
            return None
        if region is not None:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))
        if subsampling > 1:
            image = image.resize(
                (max(1, image.width // subsampling), max(1, image.height // subsampling)),
                Image.NEAREST,
            )
        return image

    def get_stencil_image(self, paint: object) -> Image.Image | None:
        """Return a stencil-painted image. Mirrors upstream
        ``PDImageXObject.getStencilImage(Paint)`` (Java line 569).

        Stencil painting (mapping the 1-bit mask onto an arbitrary
        ``Paint``) is rendering-cluster territory. We honour upstream's
        type contract — raises if not actually a stencil — and otherwise
        return the underlying 1-bit mask via :meth:`to_pil_image` so
        callers get something usable."""
        if not self.is_stencil():
            raise ValueError("Image is not a stencil")
        del paint  # paint compositing is rendering-cluster work
        return self.to_pil_image()

    def get_raw_image(self) -> Image.Image | None:
        """Return the *raw* image without colour-space conversion to
        sRGB. Mirrors upstream ``PDImageXObject.getRawImage()`` (Java
        line 526). Today's implementation reuses :meth:`to_pil_image`
        and returns ``None`` when raw-raster decoding is not yet
        supported for the image's colour space."""
        return self.to_pil_image()

    def get_raw_raster(self) -> bytes | None:
        """Return the *raw* sample bytes for this image (no colour-space
        conversion). Mirrors upstream
        ``PDImageXObject.getRawRaster()`` (Java line 532) which returns
        a ``WritableRaster``; we expose the byte array directly because
        Python has no equivalent to ``java.awt.image.WritableRaster``.
        ``None`` when the underlying COS object is not a stream."""
        cos = self.get_cos_object()
        if not isinstance(cos, COSStream):
            return None
        with self.create_input_stream() as src:
            return src.read()

    def extract_matte(self, soft_mask: PDImageXObject) -> list[float] | None:
        """Extract the matte color from a softmask, converted to sRGB.
        Mirrors upstream's private
        ``PDImageXObject.extractMatte(PDImageXObject)`` (Java line 544).

        Returns ``None`` when ``/Matte`` is absent or shorter than the
        image's colour-space component count. Otherwise the matte values
        are forwarded through this image's colour space's
        ``to_rgb(components)`` transform when one is available; when the
        colour space cannot be resolved or carries no ``to_rgb``, the
        raw matte values are returned untouched."""
        matte = soft_mask.get_matte()
        if matte is None:
            return None
        color_space = self.get_color_space()
        if color_space is None:
            return matte
        n = color_space.get_number_of_components()
        if len(matte) < n:
            _LOG.error("Image /Matte entry not long enough for colorspace, skipped")
            return None
        cs_to_rgb = getattr(color_space, "to_rgb", None)
        if cs_to_rgb is None:
            return matte
        try:
            rgb = cs_to_rgb(list(matte[:n]))
        except Exception:  # noqa: BLE001
            return matte
        if rgb is None:
            return matte
        return [float(c) for c in rgb]

    def init_jpx_values(self) -> None:
        """Refresh ``/Width``, ``/Height``, ``/BitsPerComponent``, and
        ``/ColorSpace`` from a JPX-decoded payload's intrinsic values.
        Mirrors upstream's private ``PDImageXObject.initJPXValues()``
        (Java line 736).

        The JPX-decoder integration this requires (returning a
        ``DecodeResult`` with embedded colour-space and SMask metadata)
        is rendering-cluster work that has not yet been ported. The
        method is provided as an API-parity stub so callers that wire
        their own JPX decoder do not have to subclass to add it."""
        return None

    def apply_mask(
        self,
        image: Image.Image,
        mask: Image.Image | None,
        interpolate_mask: bool,
        is_soft: bool,
        matte: Sequence[float] | None,
    ) -> Image.Image:
        """Composite ``mask`` into ``image`` as alpha. Mirrors upstream's
        private ``PDImageXObject.applyMask`` (Java line 619).

        Library-first: when ``mask`` is ``None`` we return ``image``
        unmodified (matches upstream's first branch). The full Q16.15
        matte fixed-point compositing path is rendering-cluster work and
        is not exercised here — the simple mask path uses Pillow's
        ``putalpha`` (or alpha inversion for stencil masks)."""
        del interpolate_mask, matte  # rendering-cluster fidelity, not yet exercised
        if mask is None:
            return image
        target = image.convert("RGBA")
        alpha = mask.convert("L").resize(target.size, Image.NEAREST)
        if not is_soft:
            alpha = Image.eval(alpha, lambda v: 255 - v)
        target.putalpha(alpha)
        return target

    @staticmethod
    def scale_image(
        image: Image.Image,
        width: int,
        height: int,
        mode: str,
        interpolate: bool,
    ) -> Image.Image:
        """High-quality image scaling. Mirrors upstream's private static
        ``PDImageXObject.scaleImage`` (Java line 768). Pillow handles
        the actual resampling — bicubic when ``interpolate`` is set,
        nearest-neighbour otherwise. ``mode`` is a PIL mode string
        (``"L"``, ``"RGBA"``, …)."""
        scaled = image.resize(
            (int(width), int(height)),
            Image.BICUBIC if interpolate else Image.NEAREST,
        )
        if scaled.mode != mode:
            scaled = scaled.convert(mode)
        return scaled

    @staticmethod
    def clamp_color(color: int) -> int:
        """Clamp a colour component to ``[0, 255]``. Mirrors upstream's
        private static ``PDImageXObject.clampColor`` (Java line 731)."""
        if color < 0:
            return 0
        if color > 255:
            return 255
        return color

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
        return decode_pdimage_to_pil(self, filter_names)


def decode_pdimage_to_pil(
    pd_image: PDImage, filter_names: set[str]
) -> Image.Image | None:
    """Decode any :class:`PDImage` (XObject *or* inline image) to a PIL image.

    Shared raster-decode core for :meth:`PDImageXObject.to_pil_image` and
    :meth:`PDInlineImage.to_pil_image`. Operates purely through the
    :class:`PDImage` accessor surface (``get_width`` / ``get_height`` /
    ``get_bits_per_component`` / ``get_color_space`` / ``get_decode`` /
    ``create_input_stream``) so both image shapes share one decode path —
    inline images previously had a stripped-down decoder that returned
    ``None`` for Indexed, DeviceCMYK, sub-byte and 16-bit rasters.

    ``filter_names`` is the resolved set of filter names (long *and* short
    forms) so DCT/JPX payloads can be handed straight to Pillow.

    Supports DCT/JPX payloads via Pillow and raw DeviceRGB, DeviceGray
    (1/2/4/8/16 bpc), DeviceCMYK, Indexed (1/2/4/8 bpc), ``Separation`` and
    ``DeviceN`` rasters. Masks, multi-component 16-bit samples and other
    non-device colour models remain rendering-cluster work and return
    ``None``.
    """
    width = pd_image.get_width()
    height = pd_image.get_height()
    if width <= 0 or height <= 0:
        return None

    if "DCTDecode" in filter_names or "DCT" in filter_names:
        with pd_image.create_input_stream(stop_filters=["DCTDecode", "DCT"]) as src:
            jpeg = Image.open(io.BytesIO(src.read()))
            jpeg.load()
        return _dct_jpeg_to_rgb(pd_image, jpeg, width, height)
    if "JPXDecode" in filter_names or "JPX" in filter_names:
        with pd_image.create_input_stream(stop_filters=["JPXDecode", "JPX"]) as src:
            return Image.open(io.BytesIO(src.read())).convert("RGB")

    bpc = pd_image.get_bits_per_component()
    # PDImageXObject.get_color_space returns None when absent; PDInlineImage
    # raises OSError for a missing/unsupported /CS. Treat both as "unknown"
    # so the colour-space-less raster falls through to the byte-length
    # heuristic below rather than propagating the error.
    try:
        color_space = pd_image.get_color_space()
    except OSError:
        color_space = None
    color_space_name = color_space.get_name() if color_space is not None else None
    sub_byte = bpc in (1, 2, 4)
    if bpc not in (8, -1) and not (
        (sub_byte and color_space_name in ("DeviceGray", "Indexed"))
        or (bpc == 16 and color_space_name in ("DeviceGray", "DeviceRGB"))
    ):
        return None
    with pd_image.create_input_stream() as src:
        data = src.read()
    rgb_len = width * height * 3
    gray_len = width * height
    pixel_count = width * height
    # ``get_decode`` returns ``list[float]`` on PDImageXObject but a raw
    # ``COSArray`` on PDInlineImage — normalise to a float list so the
    # decode-array math below is uniform across both image shapes.
    decode = pd_image.get_decode()
    if isinstance(decode, COSArray):
        decode = _numeric_array_to_floats(decode)
    if color_space_name == "DeviceRGB" or (
        color_space_name is None and len(data) >= rgb_len
    ):
        if bpc == 16:
            # Big-endian 16-bit samples, three per pixel. PDFBox reads the
            # 16-bit raster and down-shifts to 8-bit for rendering; the
            # decode-array math below reproduces that scaling (raw / 65535
            # * 255) exactly.
            samples = _unpack_16bit_samples(data, width, height, components=3)
            if samples is None:
                return None
            decoded = _apply_decode_to_8bit_samples(
                samples, pixel_count, 3, decode, bpc=16
            )
            if decoded is None:
                return None
            return Image.frombytes("RGB", (width, height), decoded)
        if len(data) < rgb_len:
            return None
        decoded = _apply_decode_to_8bit_samples(data[:rgb_len], pixel_count, 3, decode)
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
        decoded = _apply_decode_to_8bit_samples(data[:cmyk_len], pixel_count, 4, decode)
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
    if color_space_name == "Lab" and color_space is not None:
        lab_len = width * height * 3
        if len(data) < lab_len:
            return None
        # Mirrors upstream ``PDLab.toRGBImage(WritableRaster)``: the colour
        # space consumes the *raw* 8-bit samples and performs its own
        # L*a*b* scaling (0..255 -> L*=0..100, a*/b*=minA+t*deltaA), so no
        # /Decode-array pre-pass is applied here — the Lab toRGBImage loop
        # is the decode.
        return color_space.to_rgb_image(data[:lab_len], width, height)
    if color_space_name in ("Separation", "DeviceN") and color_space is not None:
        n = color_space.get_number_of_components()
        decoded = _apply_devicen_decode(data, width, height, n, decode)
        if decoded is None:
            return None
        return _decode_devicen_to_rgb(color_space, decoded, width, height)
    if color_space_name == "ICCBased" and color_space is not None:
        # ICCBased (PDF §8.6.5.5): /N ∈ {1, 3, 4} gives the component count.
        # Mirrors upstream ``PDImageXObject.getImage()`` handing the raw 8-bpc
        # raster to ``PDICCBased.toRGBImage(raster)``, which converts through
        # the embedded ICC profile (or, on an unparseable/LUT-less profile,
        # the /Alternate fallback). The raw samples are decoded N-channels-
        # per-pixel with the component-wise /Decode array applied, then handed
        # to the colour space's bulk ``to_rgb_image`` — identical pipeline to
        # the DeviceCMYK/DeviceRGB/DeviceGray branches above, but keyed off the
        # ICC profile's /N rather than a device-space name.
        components = color_space.get_number_of_components()
        if components not in (1, 3, 4):
            return None
        needed = pixel_count * components
        if len(data) < needed:
            return None
        decoded = _apply_decode_to_8bit_samples(
            data[:needed], pixel_count, components, decode
        )
        if decoded is None:
            return None
        return color_space.to_rgb_image(decoded, width, height)
    return None


def _apply_soft_mask(
    image: Image.Image, smask: PDImageXObject, base: PDImageXObject
) -> Image.Image:
    """Return ``image`` (RGBA) with the ``/SMask`` Image XObject composited as
    the alpha channel (PDF 32000-1 §8.9.5.4).

    The soft mask is decoded as grayscale via :meth:`to_pil_image` (which
    honours its own ``/Decode`` array and ``BitsPerComponent`` ≠ 8), reduced
    to a single luminance channel, and upscaled to the base image's
    dimensions when its own dimensions differ. When the soft mask carries a
    ``/Matte`` array the base colours were pre-blended against it and are
    un-pre-multiplied (``c = m + (c' - m) / alpha``) — mirroring upstream
    ``PDImageXObject.applyMask``. Any decode failure returns ``image``
    unchanged."""
    try:
        mask_image = smask.to_pil_image()
    except Exception:  # noqa: BLE001 - best-effort; opaque raster on failure
        return image
    if mask_image is None:
        return image
    if mask_image.mode != "L":
        mask_image = mask_image.convert("L")
    if mask_image.size != image.size:
        # Upstream ``applyMask`` scales the mask via ``scaleImage`` honouring
        # the soft mask's own ``/Interpolate`` flag (default ``false`` → hard
        # per-sample selection, i.e. nearest-neighbour). Only interpolate when
        # the SMask explicitly requests it.
        try:
            interpolate = bool(smask.get_interpolate())
        except Exception:  # noqa: BLE001
            interpolate = False
        resample = Image.BICUBIC if interpolate else Image.NEAREST
        mask_image = mask_image.resize(image.size, resample)
    rgba = image.convert("RGBA")
    # Upstream applyMask (Java line 679) overwrites the alpha band wholesale
    # with the SMask samples, so any pre-existing color-key alpha is discarded
    # — putalpha (replace, not multiply) matches that exactly.
    rgba.putalpha(mask_image)
    return _unpremultiply_matte(rgba, mask_image, base, smask)


def _unpremultiply_matte(
    rgba: Image.Image,
    alpha: Image.Image,
    base: PDImageXObject,
    smask: PDImageXObject,
) -> Image.Image:
    """Un-pre-multiply the soft mask's ``/Matte`` colour out of ``rgba``.

    When the soft mask declares ``/Matte`` (PDF §11.6.5.3) the base colour
    ``c'`` was stored pre-blended against the matte ``m``; the true colour is
    recovered as ``c = m + (c' - m) / alpha``. Pixels with alpha 0 are left
    untouched and every recovered component is clamped to ``[0, 255]``. An
    absent matte (or any resolution failure) returns ``rgba`` unchanged."""
    try:
        matte = base.extract_matte(smask)
    except Exception:  # noqa: BLE001 - best-effort
        return rgba
    if not matte or len(matte) < 3:
        return rgba
    m = [max(0.0, min(255.0, float(c) * 255.0)) for c in matte[:3]]
    px = rgba.load()
    apx = alpha.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            a = apx[x, y]
            if a == 0:
                continue
            r, g, b, _ = px[x, y]
            scale = 255.0 / a
            nr = m[0] + (r - m[0]) * scale
            ng = m[1] + (g - m[1]) * scale
            nb = m[2] + (b - m[2]) * scale
            px[x, y] = (
                0 if nr < 0 else 255 if nr > 255 else int(round(nr)),
                0 if ng < 0 else 255 if ng > 255 else int(round(ng)),
                0 if nb < 0 else 255 if nb > 255 else int(round(nb)),
                a,
            )
    return rgba


def _apply_explicit_mask(image: Image.Image, mask: PDImageXObject) -> Image.Image:
    """Return ``image`` (RGBA) with an explicit-mask ``/Mask`` 1-bit stencil
    applied as alpha (PDF 32000-1 §8.9.6.3).

    A stencil sample of ``1`` masks the pixel out (transparent), a sample of
    ``0`` paints it (opaque); a ``/Decode [1 0]`` on the mask reverses that
    polarity. The mask is decoded to a 1-component plane, scaled to the base
    image's dimensions with nearest-neighbour sampling (the spec's per-sample
    selection — no bilinear blur of the stencil edge), and applied as alpha.
    Any decode failure returns ``image`` unchanged."""
    try:
        mw = int(mask.get_width())
        mh = int(mask.get_height())
        if mw <= 0 or mh <= 0:
            return image
        with mask.create_input_stream() as src:
            data = src.read()
        samples = _unpack_sub_byte_samples(data, mw, mh, 1)
        if samples is None:
            return image
    except Exception:  # noqa: BLE001 - best-effort; opaque raster on failure
        return image

    try:
        decode = mask.get_decode()
    except Exception:  # noqa: BLE001
        decode = None
    masked_sample = 1
    if decode is not None and len(decode) >= 2 and decode[0] > decode[1]:
        masked_sample = 0

    alpha_bytes = bytearray(mw * mh)
    for i, s in enumerate(samples):
        alpha_bytes[i] = 0 if s == masked_sample else 255
    alpha = Image.frombytes("L", (mw, mh), bytes(alpha_bytes))
    if alpha.size != image.size:
        alpha = alpha.resize(image.size, Image.NEAREST)
    rgba = image.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def _apply_color_key_mask(
    image: Image.Image,
    ranges: Sequence[int],
    pd_image: PDImage,
) -> Image.Image:
    """Return ``image`` (RGBA) with a color-key ``/Mask`` range applied as
    alpha (PDF 32000-1 §8.9.6.4).

    ``ranges`` is ``[min1 max1 min2 max2 ...]`` over the **raw colour-component
    sample values** in the image's native colour space — one inclusive pair
    per component. A pixel is masked out (alpha 0) iff every raw component
    sample falls inside its pair. This mirrors upstream
    ``SampledImageReader.applyColorKeyMask`` / the spec's "before any further
    colour conversion" rule: the comparison is against the integer samples in
    ``[0, 2**bpc - 1]`` (after ``/Decode`` sample-index remap for the index of
    an Indexed image, but before the colour lookup / device conversion), NOT
    against the converted sRGB pixels. So a DeviceGray image keys on its single
    gray sample (``[min max]``), a DeviceCMYK image on its four CMYK samples,
    and an Indexed image on the palette index (``[min max]``).

    A mask whose pair-count does not match the image's component count, an odd
    or too-short range, or a raster we cannot read back as raw samples leaves
    ``image`` unchanged (best-effort — never raise)."""
    if len(ranges) < 2 or len(ranges) % 2 != 0:
        return image
    components = len(ranges) // 2

    samples = _read_color_key_samples(pd_image, components)
    if samples is None:
        # Fall back to the sRGB-pixel comparison for the 3-component RGB case
        # (raw samples already equal the displayed RGB there); otherwise leave
        # the raster opaque rather than key on the wrong colour space.
        if components != 3:
            return image
        samples = _rgb_pixels_as_samples(image)
        if samples is None:
            return image

    width, height = image.size
    if len(samples) < width * height * components:
        return image

    rgba = image.convert("RGBA")
    apx = rgba.load()
    pair_lo = ranges[0::2]
    pair_hi = ranges[1::2]
    pixel = 0
    for y in range(height):
        for x in range(width):
            base = pixel * components
            keyed = True
            for c in range(components):
                s = samples[base + c]
                if not (pair_lo[c] <= s <= pair_hi[c]):
                    keyed = False
                    break
            if keyed:
                r, g, b, _ = apx[x, y]
                apx[x, y] = (r, g, b, 0)
            pixel += 1
    return rgba


def _rgb_pixels_as_samples(image: Image.Image) -> list[int]:
    """Flatten an image's sRGB pixels into interleaved R,G,B sample values —
    the raw-sample stand-in for a 3-component DeviceRGB color-key when the
    native raster is unavailable."""
    return list(image.convert("RGB").tobytes())


def _read_color_key_samples(
    pd_image: PDImage, components: int
) -> list[int] | None:
    """Read the raw, interleaved per-component sample values for ``pd_image``
    in its native colour space, ``components`` per pixel, row-major.

    Used only for color-key ``/Mask`` evaluation (PDF §8.9.6.4), which compares
    the **raw integer samples** in ``[0, 2**bpc - 1]`` — not the converted
    sRGB pixels — against the range pairs (also expressed in raw-sample units).
    Handles raw DeviceGray (1/2/4/8/16 bpc), Indexed (1/2/4/8 bpc, the palette
    index itself, with its ``/Decode`` index remap honoured), DeviceRGB and
    DeviceCMYK (8-bit). Returns ``None`` for filtered payloads (DCT/JPX) or any
    colour-space / bit-depth combination whose raw samples we cannot
    reconstruct — the caller then leaves the raster opaque (or falls back to
    the sRGB-pixel path for plain RGB)."""
    cos = pd_image.get_cos_object()
    if not isinstance(cos, COSStream):
        return None
    filter_names = {item.name for item in cos.get_filter_list()}
    if filter_names & {"DCTDecode", "DCT", "JPXDecode", "JPX"}:
        return None

    width = pd_image.get_width()
    height = pd_image.get_height()
    if width <= 0 or height <= 0:
        return None
    pixel_count = width * height

    try:
        color_space = pd_image.get_color_space()
    except OSError:
        color_space = None
    cs_name = color_space.get_name() if color_space is not None else None
    if cs_name not in ("DeviceGray", "DeviceRGB", "DeviceCMYK", "Indexed"):
        return None
    if color_space is not None and color_space.get_number_of_components() != components:
        return None

    bpc = pd_image.get_bits_per_component()
    with pd_image.create_input_stream() as src:
        data = src.read()

    if cs_name == "Indexed":
        if bpc in (1, 2, 4):
            samples = _unpack_sub_byte_samples(data, width, height, bpc)
        elif bpc in (8, -1):
            samples = data[:pixel_count] if len(data) >= pixel_count else None
        else:
            return None
        if samples is None:
            return None
        return _apply_color_key_index_decode(
            list(samples), pixel_count, pd_image, bpc
        )

    if cs_name == "DeviceGray":
        if bpc in (1, 2, 4):
            samples = _unpack_sub_byte_samples(data, width, height, bpc)
            return list(samples) if samples is not None else None
        if bpc == 16:
            return _unpack_16bit_samples(data, width, height)
        return list(data[:pixel_count]) if len(data) >= pixel_count else None

    # DeviceRGB / DeviceCMYK — raw 8-bit interleaved samples only.
    if bpc not in (8, -1):
        return None
    needed = pixel_count * components
    return list(data[:needed]) if len(data) >= needed else None


def _apply_color_key_index_decode(
    samples: list[int], pixel_count: int, pd_image: PDImage, bpc: int
) -> list[int]:
    """Map raw Indexed samples through any ``/Decode`` index remap to the
    palette-index values the color-key range is expressed against. With no
    ``/Decode`` the raw index is used unchanged; the comparison is against the
    integer index, not the looked-up colour (PDF §8.9.6.4)."""
    decode = pd_image.get_decode()
    if isinstance(decode, COSArray):
        decode = _numeric_array_to_floats(decode)
    if not decode or len(decode) != 2:
        return samples[:pixel_count]
    max_sample = float((1 << int(bpc if bpc in (1, 2, 4) else 8)) - 1)
    if max_sample <= 0.0:
        return samples[:pixel_count]
    dmin, dmax = decode[0], decode[1]
    return [
        int(round(_clamp(dmin + (samples[i] / max_sample) * (dmax - dmin), 0.0, 255.0)))
        for i in range(pixel_count)
    ]


def _dct_jpeg_to_rgb(
    pd_image: PDImage, jpeg: Image.Image, width: int, height: int
) -> Image.Image | None:
    """Colour-transform a decoded ``/DCTDecode`` JPEG into an sRGB image.

    Mirrors how PDFBox finishes a JPEG decode: the libjpeg raster is handed
    to the *PDF* colour pipeline (the resolved ``/ColorSpace`` transform),
    not the codec's own built-in RGB conversion.

    For grayscale and YCbCr-RGB JPEGs the two paths coincide, so we keep the
    fast ``Image.convert("RGB")`` route. For a **CMYK / YCCK JPEG carrying
    the Adobe APP14 transform marker** they must not: that is the classic
    inverted-CMYK trap. Adobe stores CMYK in JPEG inverted (255 = ink-off),
    but Pillow's JPEG reader already re-inverts on load (``tobytes()`` hands
    back conventional ``0 = ink-off`` samples), so the PDF ``/Decode
    [1 0 1 0 1 0 1 0]`` array that ``JPEGFactory`` attaches has *already*
    been accounted for by the codec — re-applying it would double-invert.
    The remaining divergence from Pillow's ``convert("RGB")`` is only the
    CMYK->RGB transform itself: Pillow runs LittleCMS with a bundled profile
    we do not control, while every other DeviceCMYK raster in pypdfbox goes
    through :meth:`PDDeviceCMYK.to_rgb_image` (a deterministic subtractive
    transform, by design — see that class's docstring). Routing the JPEG's
    CMYK samples through the same ``/DeviceCMYK`` space keeps the JPEG path
    consistent with the raw-CMYK path and platform/Pillow-version stable.

    The residual luminance gap against Java PDFBox on CMYK JPEGs is the
    known subtractive-vs-``CGATS001Compat-v2-micro.icc`` colour-cluster
    divergence, not a polarity error (polarity matches exactly).
    """
    if jpeg.mode != "CMYK":
        return jpeg.convert("RGB")

    try:
        color_space = pd_image.get_color_space()
    except OSError:
        color_space = None
    # A non-CMYK PDF colour space over a CMYK codestream is exotic; defer to
    # Pillow rather than guess.
    if color_space is None or color_space.get_name() != "DeviceCMYK":
        return jpeg.convert("RGB")

    samples = jpeg.tobytes()  # interleaved C,M,Y,K bytes, codec (un-inverted) order
    pixel_count = width * height
    cmyk_len = pixel_count * 4
    if len(samples) < cmyk_len:
        return jpeg.convert("RGB")

    return color_space.to_rgb_image(samples[:cmyk_len], width, height)


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
        # The decoded value is a *palette index*. Upstream resolves it with
        # ``Math.round`` (round-half-UP), the same rule
        # ``PDIndexed.toRGB``/``to_rgb`` uses (``math.floor(v + 0.5)``). Python's
        # built-in ``round`` is banker's rounding (round-half-to-even), so a
        # half-integer index from a fractional ``/Decode`` (e.g. ``[0 7.5]`` on a
        # 4-bit image: sample 1 -> index 0.5) would dereference a *different*
        # palette slot than PDFBox (Python ``round(0.5)==0`` vs Java
        # ``Math.round(0.5)==1``). Mirror Java exactly so the image-raster index
        # path agrees with the scalar ``PDIndexed.to_rgb`` path.
        out[i] = int(math.floor(_clamp(value, 0.0, 255.0) + 0.5))
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


def _apply_devicen_decode(
    data: bytes,
    width: int,
    height: int,
    components: int,
    decode: Sequence[float] | None,
) -> bytes | None:
    """Apply the ``/Decode`` array to a raw 8-bit Separation/DeviceN raster
    (PDF 32000-1 §8.9.5.2), returning interleaved 8-bit tint samples scaled
    into the decoded ``[decode_min, decode_max]`` range per component.

    Mirrors upstream ``SampledImageReader`` which maps every raw sample
    through ``decode[2c] + sample / maxVal * (decode[2c+1] - decode[2c])``
    *before* the colour space's tint transform runs. The default decode for a
    Separation/DeviceN component is ``[0 1]`` (identity over the 8-bit range),
    so an absent or default decode passes the raster through unchanged; an
    inverted ``[1 0]`` decode flips the tint (raw 0 → tint 1.0), which the
    downstream :func:`_decode_devicen_to_rgb` (dividing each byte by 255)
    then feeds to the tint transform — reproducing PDFBox's reversed ramp.

    Returns ``None`` on a short raster or a ``/Decode`` array whose length
    does not match ``components * 2`` (the caller then aborts the decode)."""
    if components <= 0:
        return None
    expected = width * height * components
    if len(data) < expected:
        return None
    if decode is None:
        return data[:expected]
    if len(decode) != components * 2:
        return None
    # Skip the work when the decode is the per-component identity [0 1 ...].
    if all(
        decode[2 * c] == 0.0 and decode[2 * c + 1] == 1.0 for c in range(components)
    ):
        return data[:expected]

    out = bytearray(expected)
    for i in range(expected):
        component = i % components
        dmin = decode[component * 2]
        dmax = decode[component * 2 + 1]
        value = dmin + (data[i] / 255.0) * (dmax - dmin)
        out[i] = int(round(_clamp01(value) * 255.0))
    return bytes(out)


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


def _detect_file_type(head: bytes) -> str | None:
    """Sniff the image format from the leading bytes. Mirrors upstream's
    ``FileTypeDetector.detectFileType`` for the subset of formats
    ``PDImageXObject.createFromByteArray`` supports.

    Returns the upstream ``FileType`` name (``"JPEG"``, ``"TIFF"``,
    ``"PNG"``, ``"GIF"``, ``"BMP"``) or ``None`` when no match is
    found.
    """
    if len(head) < 4:
        return None
    if head[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if head[:2] == b"BM":
        return "BMP"
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        return "TIFF"
    return None
