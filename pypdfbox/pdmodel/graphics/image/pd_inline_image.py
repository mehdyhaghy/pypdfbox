from __future__ import annotations

import io
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, BinaryIO

from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.filter.filter_factory import FilterFactory
from pypdfbox.pdmodel.graphics.color import PDColorSpace

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resources import PDResources


# Inline-image dictionary keys. Per PDF 32000-1 §8.9.7, inline images use
# short single-letter abbreviations in the BI/ID/EI dictionary; the long
# form is also accepted as a fallback (mirroring upstream's two-key
# ``getInt(short, long, default)`` lookups).
_W: COSName = COSName.get_pdf_name("W")
_WIDTH: COSName = COSName.get_pdf_name("Width")
_H: COSName = COSName.get_pdf_name("H")
_HEIGHT: COSName = COSName.get_pdf_name("Height")
_BPC: COSName = COSName.get_pdf_name("BPC")
_BITS_PER_COMPONENT: COSName = COSName.get_pdf_name("BitsPerComponent")
_CS: COSName = COSName.get_pdf_name("CS")
_COLORSPACE: COSName = COSName.get_pdf_name("ColorSpace")
_F: COSName = COSName.get_pdf_name("F")
_FILTER: COSName = COSName.get_pdf_name("Filter")
_D: COSName = COSName.get_pdf_name("D")
_DECODE: COSName = COSName.get_pdf_name("Decode")
_DP: COSName = COSName.get_pdf_name("DP")
_DECODE_PARMS: COSName = COSName.get_pdf_name("DecodeParms")
_IM: COSName = COSName.get_pdf_name("IM")
_IMAGE_MASK: COSName = COSName.get_pdf_name("ImageMask")
_I: COSName = COSName.get_pdf_name("I")
_INTERPOLATE: COSName = COSName.get_pdf_name("Interpolate")
_RGB: COSName = COSName.get_pdf_name("RGB")
_DEVICERGB: COSName = COSName.get_pdf_name("DeviceRGB")
_CMYK: COSName = COSName.get_pdf_name("CMYK")
_DEVICECMYK: COSName = COSName.get_pdf_name("DeviceCMYK")
_G: COSName = COSName.get_pdf_name("G")
_DEVICEGRAY: COSName = COSName.get_pdf_name("DeviceGray")
_INDEXED: COSName = COSName.get_pdf_name("Indexed")
_I_NAME: COSName = _I  # /I doubles as Indexed abbreviation in inline /CS

# Filter names whose presence determines the on-disk suffix.
_DCT_DECODE: str = "DCTDecode"
_DCT_DECODE_ABBREVIATION: str = "DCT"
_CCITTFAX_DECODE: str = "CCITTFaxDecode"
_CCITTFAX_DECODE_ABBREVIATION: str = "CCF"


def _two_key_int(
    parameters: COSDictionary,
    short: COSName,
    long: COSName,
    default: int,
) -> int:
    """Read an integer entry from ``parameters``, preferring the short
    abbreviation but falling back to the long form. Mirrors upstream's
    ``COSDictionary#getInt(firstKey, secondKey, default)``.
    """
    if parameters.contains_key(short):
        return parameters.get_int(short, default)
    return parameters.get_int(long, default)


def _two_key_boolean(
    parameters: COSDictionary,
    short: COSName,
    long: COSName,
    default: bool,
) -> bool:
    """Two-key boolean lookup mirroring upstream
    ``COSDictionary#getBoolean(firstKey, secondKey, default)``."""
    if parameters.contains_key(short):
        return parameters.get_boolean(short, default)
    return parameters.get_boolean(long, default)


def _two_key_object(
    parameters: COSDictionary,
    short: COSName,
    long: COSName,
) -> COSBase | None:
    """Two-key resolved-object lookup mirroring upstream
    ``COSDictionary#getDictionaryObject(firstKey, secondKey)``."""
    value = parameters.get_dictionary_object(short)
    if value is not None:
        return value
    return parameters.get_dictionary_object(long)


def _remove_two_key(parameters: COSDictionary, short: COSName, long: COSName) -> None:
    parameters.remove_item(short)
    parameters.remove_item(long)


def _numeric_array_to_floats(value: COSBase | None) -> list[float] | None:
    if not isinstance(value, COSArray):
        return None
    out: list[float] = []
    for item in value:
        if not isinstance(item, (COSInteger, COSFloat)):
            return None
        out.append(float(item.value))
    return out


class PDInlineImage:
    """An inline image object embedded directly within a content stream
    via the ``BI``/``ID``/``EI`` operator triplet (PDF 32000-1 §8.9.7).

    Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage``.

    The constructor takes the inline-image *parameters dictionary* (the
    keys/values between ``BI`` and ``ID``), the *raw encoded bytes*
    (between ``ID`` and ``EI``), and the surrounding page ``PDResources``
    used to resolve named color spaces. The constructor decodes the data
    eagerly through the filter chain so that ``get_data`` and the
    no-argument ``create_input_stream`` are zero-cost on subsequent
    calls; this matches the upstream eager-decode behavior, where inline
    images are typically tiny (PDF spec discourages payloads above 4KB).
    """

    def __init__(
        self,
        parameters: COSDictionary,
        data: bytes,
        resources: PDResources | None,
    ) -> None:
        self._parameters: COSDictionary = parameters
        self._resources: PDResources | None = resources
        self._raw_data: bytes = bytes(data)

        decoded: bytes = self._raw_data
        last_result_params: COSDictionary | None = None
        filters = self.get_filters()
        if filters:
            current_in: bytes = self._raw_data
            for index, name in enumerate(filters):
                src = io.BytesIO(current_in)
                dst = io.BytesIO()
                filter_obj = FilterFactory.INSTANCE.get_filter(name)
                result = filter_obj.decode(src, dst, parameters, index)
                last_result_params = (
                    result.parameters if result is not None else None
                )
                current_in = dst.getvalue()
            decoded = current_in
        self._decoded_data: bytes = decoded

        # Repair parameters with any decode-time mutations (e.g. CCITT
        # /Columns added by the decoder). Mirrors upstream's
        # ``parameters.addAll(decodeResult.getParameters())`` step.
        if last_result_params is not None and last_result_params is not parameters:
            parameters.add_all(last_result_params)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSDictionary:
        return self._parameters

    def get_resources(self) -> PDResources | None:
        """The page-level ``PDResources`` passed at construction time.
        Used internally to resolve named color spaces in inline-image
        ``/CS`` arrays. Mirrors the upstream private ``resources`` field
        — upstream does not expose a public getter, but pypdfbox exposes
        one for parity-test introspection.
        """
        return self._resources

    # ---------- /W /Width ----------

    def get_width(self) -> int:
        return _two_key_int(self._parameters, _W, _WIDTH, -1)

    def set_width(self, width: int) -> None:
        self._parameters.set_int(_W, int(width))

    # ---------- /H /Height ----------

    def get_height(self) -> int:
        return _two_key_int(self._parameters, _H, _HEIGHT, -1)

    def set_height(self, height: int) -> None:
        self._parameters.set_int(_H, int(height))

    # ---------- /BPC /BitsPerComponent ----------

    def get_bits_per_component(self) -> int:
        if self.is_stencil():
            return 1
        return _two_key_int(self._parameters, _BPC, _BITS_PER_COMPONENT, -1)

    def set_bits_per_component(self, bits_per_component: int) -> None:
        self._parameters.set_int(_BPC, int(bits_per_component))

    # ---------- /CS /ColorSpace ----------

    def to_long_name(self, cs: COSBase) -> COSBase:
        """Expand single-letter inline color-space abbreviations
        (``/G`` → ``/DeviceGray``, ``/RGB`` → ``/DeviceRGB``,
        ``/CMYK`` → ``/DeviceCMYK``); other values pass through. Mirrors
        upstream ``PDInlineImage#toLongName`` (Java line 151) — package-private
        in upstream, exposed here as protected for parity-test introspection.
        """
        if isinstance(cs, COSName):
            if cs == _RGB:
                return _DEVICERGB
            if cs == _CMYK:
                return _DEVICECMYK
            if cs == _G:
                return _DEVICEGRAY
        return cs

    # Private alias retained for backward compatibility with existing
    # call sites; ``to_long_name`` is the parity-matched public surface.
    _to_long_name = to_long_name

    def get_color_space_cos_object(self) -> COSBase | None:
        """Raw ``/CS`` (or long-form ``/ColorSpace`` fallback) value —
        the underlying ``COSName`` or ``COSArray`` — without resolving
        through :class:`PDColorSpace`. Mirrors
        :meth:`PDImageXObject.get_color_space_cos_object`. Returns
        ``None`` when neither key is present. Useful for callers that
        want to inspect the COS shape (e.g. to detect ``/I`` /
        ``/Indexed`` arrays) before paying the resolution cost.
        """
        return _two_key_object(self._parameters, _CS, _COLORSPACE)

    def get_color_space(self) -> PDColorSpace:
        cs = _two_key_object(self._parameters, _CS, _COLORSPACE)
        if cs is not None:
            return self.create_color_space(cs)
        if self.is_stencil():
            # Stencil-mask color space must be gray; it is often missing.
            from pypdfbox.pdmodel.graphics.color import PDDeviceGray  # noqa: PLC0415

            return PDDeviceGray.INSTANCE
        # An image without a color space is always broken.
        raise OSError("could not determine inline image color space")

    def create_color_space(self, cs: COSBase) -> PDColorSpace:
        """Resolve an inline-image ``/CS`` value into a :class:`PDColorSpace`.
        Mirrors upstream ``PDInlineImage#createColorSpace`` (Java line 168) —
        package-private in upstream, exposed here as protected for parity
        with the test surface.
        """
        if isinstance(cs, COSName):
            resolved = PDColorSpace.create(self._to_long_name(cs), self._resources)
            if resolved is None:
                raise OSError(
                    f"unsupported inline image color space name: {cs.get_name()!r}"
                )
            return resolved

        if isinstance(cs, COSArray) and cs.size() > 1:
            cs_type = cs.get(0)
            if cs_type in (_I_NAME, _INDEXED):
                # Rebuild the array with long-form ``/Indexed`` head and
                # long-form base color-space name so PDColorSpace.create
                # picks up the standard branch.
                dst = COSArray()
                dst.add_all(list(cs))
                dst.set(0, _INDEXED)
                base = cs.get(1)
                if base is not None:
                    dst.set(1, self._to_long_name(base))
                resolved = PDColorSpace.create(dst, self._resources)
                if resolved is None:
                    raise OSError("unsupported indexed color space in inline image")
                return resolved
            # Separation / DeviceN / ICCBased / Lab / CalGray / CalRGB —
            # PDColorSpace.create handles all of these directly when the
            # head is the long-form name. Inline images reach this path
            # for ``[/Separation ...]`` and ``[/DeviceN ...]`` rasters
            # whose tint transforms compose to RGB via the alternate CS.
            if isinstance(cs_type, COSName) and cs_type.get_name() in (
                "Separation",
                "DeviceN",
                "ICCBased",
                "Lab",
                "CalGray",
                "CalRGB",
                "Pattern",
            ):
                resolved = PDColorSpace.create(cs, self._resources)
                if resolved is None:
                    raise OSError(
                        f"unsupported inline image color space: {cs_type.get_name()!r}"
                    )
                return resolved
            raise OSError(
                f"Illegal type of inline image color space: {cs_type!r}"
            )

        raise OSError(f"Illegal type of object for inline image color space: {cs!r}")

    # Private alias retained for backward compatibility with existing
    # call sites; ``create_color_space`` is the parity-matched public surface.
    _create_color_space = create_color_space

    def set_color_space(self, color_space: PDColorSpace | None) -> None:
        if color_space is None:
            self.clear_color_space()
            return
        base = color_space.get_cos_object()
        if base is None:
            # Device color spaces have no array form — fall back to /CS /Name.
            base = COSName.get_pdf_name(color_space.get_name())
        self._parameters.set_item(_CS, base)

    def clear_color_space(self) -> None:
        """Remove both ``/CS`` and ``/ColorSpace``. No-op if absent."""
        _remove_two_key(self._parameters, _CS, _COLORSPACE)

    # ---------- /F /Filter ----------

    def get_filter_cos_object(self) -> COSBase | None:
        """Raw ``/F`` (or long-form ``/Filter`` fallback) value — a
        single ``COSName``, a ``COSArray`` of names, or ``None`` when
        absent. Mirrors :meth:`PDImageXObject.get_filter`. Use
        :meth:`get_filters` for the normalised ``list[str]`` form.
        """
        return _two_key_object(self._parameters, _F, _FILTER)

    def has_filters(self) -> bool:
        """``True`` when ``/F`` (or ``/Filter``) carries at least one
        filter name. Convenience predicate parallel to
        :meth:`PDImageXObject` callers that want to short-circuit
        without building the filter-name list."""
        value = _two_key_object(self._parameters, _F, _FILTER)
        if isinstance(value, COSName):
            return True
        if isinstance(value, COSArray):
            return any(isinstance(item, COSName) for item in value)
        return False

    def get_filters(self) -> list[str]:
        """A (possibly empty) list of filter names applied to the raw
        data. Names are returned verbatim — both long forms (``/FlateDecode``)
        and short abbreviations (``/Fl``) are preserved so callers can
        distinguish them; ``FilterFactory.get_filter`` resolves both.
        """
        filters = _two_key_object(self._parameters, _F, _FILTER)
        if isinstance(filters, COSName):
            return [filters.get_name()]
        if isinstance(filters, COSArray):
            out: list[str] = []
            for item in filters:
                if isinstance(item, COSName):
                    out.append(item.get_name())
            return out
        return []

    def set_filters(self, filters: Sequence[str] | None) -> None:
        if filters is None:
            self.clear_filters()
            return
        array = COSArray()
        for name in filters:
            array.add(COSName.get_pdf_name(name))
        self._parameters.set_item(_F, array)

    def clear_filters(self) -> None:
        """Remove both ``/F`` and ``/Filter``. No-op if absent."""
        _remove_two_key(self._parameters, _F, _FILTER)

    # ---------- /D /Decode ----------

    def get_decode(self) -> COSArray | None:
        decode = _two_key_object(self._parameters, _D, _DECODE)
        if isinstance(decode, COSArray):
            return decode
        return None

    def set_decode(self, decode: COSArray | Iterable[float] | None) -> None:
        if decode is None:
            self.clear_decode()
            return
        if isinstance(decode, COSArray):
            self._parameters.set_item(_D, decode)
            return
        array = COSArray()
        for v in decode:
            array.add(COSFloat(float(v)))
        self._parameters.set_item(_D, array)

    def clear_decode(self) -> None:
        """Remove both ``/D`` and ``/Decode``. No-op if absent."""
        _remove_two_key(self._parameters, _D, _DECODE)

    # ---------- /IM /ImageMask ----------

    def is_stencil(self) -> bool:
        """Whether this is a stencil mask. Mirrors upstream
        ``PDImage#isStencil()`` which reads ``/IM`` (or ``/ImageMask``)."""
        return _two_key_boolean(self._parameters, _IM, _IMAGE_MASK, False)

    def set_stencil(self, is_stencil: bool) -> None:
        """Mark this inline image as a stencil mask. Mirrors upstream
        ``PDImage#setStencil(boolean)`` which writes ``/IM``."""
        self._parameters.set_boolean(_IM, bool(is_stencil))

    # Convenience aliases — upstream ``PDImage`` exposes the same
    # ``isStencil`` / ``setStencil`` surface on every implementation.
    def is_image_mask(self) -> bool:
        return self.is_stencil()

    def set_image_mask(self, value: bool) -> None:
        self.set_stencil(value)

    # ---------- /I /Interpolate ----------

    def get_interpolate(self) -> bool:
        return _two_key_boolean(self._parameters, _I, _INTERPOLATE, False)

    def is_interpolate(self) -> bool:
        """Alias of :meth:`get_interpolate` matching the ``isXxx`` boolean
        convention used by :class:`PDImageXObject` for the same flag."""
        return self.get_interpolate()

    def set_interpolate(self, value: bool) -> None:
        self._parameters.set_boolean(_I, bool(value))

    # ---------- /Mask color-key range (color-key only — no stream form) ----------

    def get_color_key_mask(self) -> list[int] | None:
        """Return the ``/Mask`` color-key range list when ``/Mask`` is a
        ``COSArray`` of ``[min1 max1 min2 max2 ...]`` integers; ``None``
        otherwise. Inline images cannot use the explicit-mask stream form
        (no XObject indirection inside a content stream), so only the
        color-key form is meaningful here.
        """
        value = self._parameters.get_dictionary_object("Mask")
        if not isinstance(value, COSArray):
            return None
        out: list[int] = []
        for item in value:
            if isinstance(item, (COSInteger, COSFloat)):
                out.append(int(item.value))
            else:
                return None
        return out

    def get_color_key_mask_array(self) -> COSArray | None:
        """Return the raw ``/Mask`` ``COSArray`` (color-key form) or
        ``None`` when absent or not an array. Mirrors the upstream
        ``PDImageXObject.getColorKeyMask()`` shape — useful when callers
        need to inspect or mutate the underlying COS objects directly.
        Use :meth:`get_color_key_mask` for the decoded ``list[int]``
        form."""
        value = self._parameters.get_dictionary_object("Mask")
        if isinstance(value, COSArray):
            return value
        return None

    # ---------- /D /Decode helpers ----------

    def get_decode_as_floats(self) -> list[float] | None:
        """Decoded ``/Decode`` array as a list of floats, or ``None`` when
        absent or not an array. Convenience parallel to
        :meth:`PDImageXObject.get_decode` so callers can read decode pairs
        without hand-walking the ``COSArray`` returned by
        :meth:`get_decode`."""
        return _numeric_array_to_floats(self.get_decode())

    # ---------- decoded bytes / stream surface ----------

    def get_data(self) -> bytes:
        """Decoded inline-image bytes. Mirrors upstream
        ``PDInlineImage#getData()``."""
        return self._decoded_data

    # Upstream PDImage interface alias — the XObject form exposes the
    # same accessor under ``getStream`` / ``createInputStream``; mirror
    # both surfaces so callers can use either name.
    def get_stream(self) -> bytes:
        """Raw (still-encoded) inline-image bytes — the contents between
        ``ID`` and ``EI`` before any filter pipeline. Use
        :meth:`get_data` for the decoded form."""
        return self._raw_data

    def is_empty(self) -> bool:
        return len(self._decoded_data) == 0

    def create_input_stream(
        self,
        stop_filters: Sequence[str | COSName] | None = None,
    ) -> BinaryIO:
        """Decoded body as a fresh ``BinaryIO``. With ``stop_filters``,
        decoding halts once a filter whose name appears in the list is
        about to run (matching upstream behavior — used by callers that
        want to keep e.g. JPEG payloads encoded for downstream encoders).
        """
        if stop_filters is None:
            return io.BytesIO(self._decoded_data)
        stops = {
            (s.get_name() if isinstance(s, COSName) else s) for s in stop_filters
        }
        filters = self.get_filters()
        current = self._raw_data
        for index, name in enumerate(filters):
            if name in stops:
                break
            filter_obj = FilterFactory.INSTANCE.get_filter(name)
            src = io.BytesIO(current)
            dst = io.BytesIO()
            filter_obj.decode(src, dst, self._parameters, index)
            current = dst.getvalue()
        return io.BytesIO(current)

    # ---------- suffix predicates ----------

    def is_jpeg(self) -> bool:
        """``True`` when this inline image carries a ``DCTDecode``
        (or short-form ``DCT``) filter — the JPEG payload form. Parallel
        to :meth:`get_suffix` returning ``"jpg"`` but cheaper because no
        suffix dispatch is needed."""
        filters = self.get_filters()
        return _DCT_DECODE in filters or _DCT_DECODE_ABBREVIATION in filters

    def is_ccitt(self) -> bool:
        """``True`` when this inline image carries a ``CCITTFaxDecode``
        (or short-form ``CCF``) filter — the fax/T.6 payload form.
        Parallel to :meth:`get_suffix` returning ``"tiff"``."""
        filters = self.get_filters()
        return (
            _CCITTFAX_DECODE in filters
            or _CCITTFAX_DECODE_ABBREVIATION in filters
        )

    # ---------- suffix ----------

    def get_suffix(self) -> str:
        """Return the on-disk suffix for this image type (``"png"``,
        ``"jpg"``, ``"tiff"``). Mirrors upstream ``PDInlineImage#getSuffix``.

        JPX and JBIG2 do not exist for inline images per PDF 32000-1
        §8.9.7, so this helper covers only the inline-eligible filters.
        """
        filters = self.get_filters()
        if not filters:
            return "png"
        if _DCT_DECODE in filters or _DCT_DECODE_ABBREVIATION in filters:
            return "jpg"
        if _CCITTFAX_DECODE in filters or _CCITTFAX_DECODE_ABBREVIATION in filters:
            return "tiff"
        return "png"

    # ---------- PIL helper (mirrors PDImageXObject.to_pil_image) ----------

    def to_pil_image(self) -> Image.Image | None:
        """Best-effort conversion to a PIL image — same scope as
        :meth:`PDImageXObject.to_pil_image`: DCT/JPX payloads via Pillow
        and raw 8-bit DeviceGray/DeviceRGB rasters. Stencil masks,
        Indexed expansion, decode arrays and non-8bpc samples are
        rendering-cluster work and return ``None`` here.
        """
        width = self.get_width()
        height = self.get_height()
        if width <= 0 or height <= 0:
            return None

        filters = self.get_filters()
        if _DCT_DECODE in filters or _DCT_DECODE_ABBREVIATION in filters:
            with self.create_input_stream(
                stop_filters=[_DCT_DECODE, _DCT_DECODE_ABBREVIATION]
            ) as src:
                return Image.open(io.BytesIO(src.read())).convert("RGB")
        if "JPXDecode" in filters or "JPX" in filters:
            with self.create_input_stream(stop_filters=["JPXDecode", "JPX"]) as src:
                return Image.open(io.BytesIO(src.read())).convert("RGB")

        bpc = self.get_bits_per_component()
        if bpc not in (8, -1):
            return None

        try:
            color_space = self.get_color_space()
        except OSError:
            color_space = None
        color_space_name = color_space.get_name() if color_space is not None else None
        data = self._decoded_data
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
        if color_space_name in ("Separation", "DeviceN") and color_space is not None:
            from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (  # noqa: PLC0415
                _decode_devicen_to_rgb,
            )

            return _decode_devicen_to_rgb(color_space, data, width, height)
        return None

    # ---------- rendering surface (mirrors upstream getImage / stencil /
    # raw raster — Java lines 353, 359, 365, 371, 377) ----------

    def get_image(
        self,
        region: tuple[int, int, int, int] | None = None,
        subsampling: int = 1,
    ) -> Image.Image | None:
        """Return a fully-decoded image. Mirrors upstream
        ``PDInlineImage#getImage()`` and the parameterised overload
        ``getImage(Rectangle, int)`` (Java lines 353 and 359).

        Library-first: Pillow handles sample decoding via
        :meth:`to_pil_image`. ``region`` is a ``(x, y, w, h)`` tuple and
        is applied via :meth:`PIL.Image.Image.crop`. ``subsampling`` is
        applied via :meth:`PIL.Image.Image.resize` with nearest-neighbour
        sampling (matches upstream's per-pixel-row-skip semantics for the
        common case ``subsampling >= 1``).

        Stencil masks, decode-array inversion and non-8bpc rasters are
        rendering-cluster work and currently fall through to ``None`` —
        same scope as :meth:`PDImageXObject.get_image`.
        """
        image = self.to_pil_image()
        if image is None:
            return None
        if region is not None:
            x, y, w, h = region
            image = image.crop((x, y, x + w, y + h))
        if subsampling > 1:
            image = image.resize(
                (
                    max(1, image.width // subsampling),
                    max(1, image.height // subsampling),
                ),
                Image.NEAREST,
            )
        return image

    def get_stencil_image(self, paint: object) -> Image.Image | None:
        """Return a stencil-painted image. Mirrors upstream
        ``PDInlineImage#getStencilImage(Paint)`` (Java line 377).

        Honours upstream's contract — raises ``ValueError`` (the Pythonic
        analogue of ``IllegalStateException``) when the inline image is
        not actually a stencil. The underlying 1-bit mask is returned via
        :meth:`to_pil_image`; mapping the stencil onto an arbitrary
        ``paint`` is rendering-cluster territory."""
        if not self.is_stencil():
            raise ValueError("Image is not a stencil")
        del paint  # paint compositing is rendering-cluster work
        return self.to_pil_image()

    def get_raw_image(self) -> Image.Image | None:
        """Return the *raw* image without colour-space conversion to
        sRGB. Mirrors upstream ``PDInlineImage#getRawImage()`` (Java
        line 371). Today's implementation reuses :meth:`to_pil_image`
        and returns ``None`` when raw-raster decoding is not yet
        supported for the image's colour space."""
        return self.to_pil_image()

    def get_raw_raster(self) -> bytes:
        """Return the *raw* sample bytes for this inline image (no
        colour-space conversion). Mirrors upstream
        ``PDInlineImage#getRawRaster()`` (Java line 365), which returns
        a ``WritableRaster``; we expose the byte array directly because
        Python has no equivalent to ``java.awt.image.WritableRaster``.
        For inline images the decoded payload is already buffered, so
        this aliases :meth:`get_data`."""
        return self._decoded_data


__all__ = ["PDInlineImage"]
