from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.common.pd_stream import PDStream

from .pd_color import PDColor, _clamp_unit
from .pd_color_space import PDColorSpace

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resources import PDResources

_log = logging.getLogger(__name__)

# Content-addressed caches for ICC profile parses and the sRGB transforms
# built off them. ICC profile bytes are immutable for the life of a PDF
# stream, so a SHA-256 digest is a safe key. Multiple PDFs (or multiple
# images inside a single PDF) sharing the same embedded profile reuse
# the same parsed ``ImageCmsProfile`` and ``ImageCmsTransform`` — mirrors
# upstream PDFBox's ``ICC_Profile`` / ``ICC_ColorSpace`` reuse, which
# AWT itself caches inside the Java CMM.
_PROFILE_CACHE: dict[str, Any] = {}
_TRANSFORM_CACHE: dict[tuple[str, str, str, int], Any] = {}
_SRGB_CACHE: list[Any] = []  # one-slot lazy holder for the sRGB output profile

# Mapping from ICC ``colorSpace`` 4-byte signature (header offset 16) to
# the Pillow image mode used as the CMM input mode. ICCBased colour
# spaces in PDF are constrained by §8.6.5.5 to /N ∈ {1, 3, 4}; the modes
# below are what LittleCMS2 (and therefore ``ImageCms``) expects.
_SIGNATURE_TO_MODE: dict[str, str] = {
    "RGB ": "RGB",
    "GRAY": "L",
    "CMYK": "CMYK",
    "Lab ": "LAB",
}
_N_TO_MODE: dict[int, str] = {1: "L", 3: "RGB", 4: "CMYK"}


def _clear_icc_caches() -> None:
    """Drop the module-level ICC profile + transform + sRGB caches.

    Intended for test isolation only: production code should never call
    this — the caches are content-addressed and immutable per profile,
    so they're safe to keep across the life of the process. Tests that
    monkeypatch ``ImageCms.ImageCmsProfile`` / ``ImageCms.createProfile``
    / ``ImageCms.buildTransform`` need to clear the caches between cases
    so a fake profile from one test doesn't leak into the next."""
    _PROFILE_CACHE.clear()
    _TRANSFORM_CACHE.clear()
    _SRGB_CACHE.clear()

_N: COSName = COSName.get_pdf_name("N")
_ALTERNATE: COSName = COSName.get_pdf_name("Alternate")
_RANGE: COSName = COSName.get_pdf_name("Range")
_METADATA: COSName = COSName.get_pdf_name("Metadata")

# Java ``java.awt.color.ColorSpace`` numeric constants — kept here so
# :meth:`PDICCBased.get_color_space_type` returns the same integer
# values as upstream's ``getColorSpaceType()`` without pulling in AWT.
TYPE_XYZ = 0
TYPE_LAB = 1
TYPE_LUV = 2
TYPE_YCBCR = 3
TYPE_YXY = 4
TYPE_RGB = 5
TYPE_GRAY = 6
TYPE_HSV = 7
TYPE_HLS = 8
TYPE_CMYK = 9
TYPE_CMY = 11


class PDICCBased(PDColorSpace):
    """An ICCBased color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDICCBased``.

    Array form: ``[/ICCBased <stream>]`` where the stream's dictionary
    carries ``/N`` (component count), ``/Alternate``, ``/Range``,
    ``/Metadata`` and the stream body holds the raw ICC profile bytes.

    ICC profile bytes and COS metadata are exposed directly. sRGB
    conversion uses Pillow's ICC support when available and otherwise
    falls back to ``/Alternate`` or an alternate inferred from ``/N``.
    """

    NAME: str = "ICCBased"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            stream = COSStream()
            stream.set_int(_N, 3)
            array.add(stream)
        super().__init__(array)
        self._initial_color = self._compute_initial_color()

    def _compute_initial_color(self) -> PDColor:
        """Compute the initial colour the way upstream's ``loadICCProfile``
        does, branching on whether the embedded ICC profile is parseable.

        Mirrors ``PDICCBased.loadICCProfile`` (PDFBox 3.0.7):

        * **Profile parses** (and its component count matches ``/N``):
          ``initialColor[i] = max(0, getRangeForComponent(i).getMin())`` for
          each of the ``/N`` components — for the usual 0..1 ``/Range`` that
          is all-zeros, including a four-component CMYK profile.
        * **Profile unreadable** (corrupt / absent / arity mismatch): upstream
          takes ``fallbackToAlternateColorSpace`` →
          ``initialColor = alternateColorSpace.getInitialColor()``. The
          components then come from the alternate verbatim — a DeviceCMYK
          alternate yields ``(0, 0, 0, 1)`` (K=1 black), and the count
          follows the alternate (which can differ from ``/N`` when
          ``/Alternate`` disagrees).
        * **No alternate resolvable** (invalid ``/N`` with no ``/Alternate``
          — the permissive path where upstream would have thrown): fall back
          to ``[0.0] * N``.

        pypdfbox parses the embedded profile through Pillow's ImageCms (same
        LittleCMS2 backend AWT's CMM uses), so the profile-parses branch is
        taken exactly when upstream's AWT ``ICC_Profile.getInstance`` would
        have succeeded.
        """
        if self._embedded_profile_parses():
            n = self.get_n()
            components = [max(0.0, self.get_range_for_component(i)[0])
                         for i in range(n)]
            return PDColor(components, self)
        alternate = self.get_alternate_color_space()
        if alternate is not None:
            return alternate.get_initial_color()
        n = self.get_n()
        return PDColor([0.0] * max(n, 0), self)

    def _embedded_profile_parses(self) -> bool:
        """Return ``True`` when the embedded ICC profile parses *and* its
        component count matches ``/N`` — the condition under which upstream's
        ``loadICCProfile`` keeps the AWT ``ICC_ColorSpace`` rather than
        falling back to the alternate. Mirrors upstream's parse-then-arity
        guard without throwing on failure (returns ``False`` instead)."""
        n = self.get_n()
        if n not in (1, 3, 4):
            return False
        profile_bytes = self.get_iccprofile_bytes()
        if not profile_bytes:
            return False
        if self._get_input_profile(profile_bytes) is None:
            return False
        # Profile parsed; mirror upstream's arity guard (Using N components
        # warning + alternate fallback when the profile's component count
        # disagrees with /N) by cross-checking the data-colour-space arity.
        count = self._profile_component_count(profile_bytes)
        return count is None or count == n

    @staticmethod
    def _profile_component_count(profile_bytes: bytes) -> int | None:
        """Best-effort component count of an ICC profile from its data
        colour-space signature (header bytes 16..19). Returns ``None`` when
        the signature is unrecognised or the buffer is too short."""
        if len(profile_bytes) < 20:
            return None
        sig = profile_bytes[16:20].decode("ascii", errors="replace")
        return {"GRAY": 1, "RGB ": 3, "Lab ": 3, "XYZ ": 3,
                "CMYK": 4}.get(sig)

    # ---------- factory ----------

    @staticmethod
    def create(
        icc_array: COSArray, resources: PDResources | None = None
    ) -> PDICCBased:
        """Build a ``PDICCBased`` from an ``[/ICCBased <stream>]`` array,
        consulting the supplied resources' cache when the stream slot is
        an indirect reference. Mirrors upstream
        ``PDICCBased.create(COSArray, PDResources) : PDICCBased``.

        ``icc_array`` must have at least two entries with a ``COSStream``
        in slot 1; otherwise :class:`OSError` is raised (upstream throws
        ``IOException``). When ``resources`` is provided and slot 1 is a
        ``COSObject`` (indirect reference), the resources' resource cache
        is checked first and a hit is returned directly; a miss is
        constructed and stored back in the cache.
        """
        from pypdfbox.cos.cos_object import COSObject

        PDICCBased._check_array(icc_array)
        base = icc_array.get(1)
        if isinstance(base, COSObject) and resources is not None:
            cache = resources.get_resource_cache()
            if cache is not None:
                cached = cache.get_color_space(base)
                if isinstance(cached, PDICCBased):
                    return cached
                new_space = PDICCBased(icc_array)
                cache.put_color_space(base, new_space)
                return new_space
        return PDICCBased(icc_array)

    @staticmethod
    def _check_array(icc_array: COSArray) -> None:
        """Validate the shape of an ICCBased ``COSArray``. Mirrors the
        private ``checkArray`` helper from upstream — raises ``OSError``
        (PDFBox throws ``IOException``) when the array is too short or
        the second slot is not a ``COSStream``.
        """
        if icc_array.size() < 2:
            raise OSError("ICCBased colorspace array must have two elements")
        if not isinstance(icc_array.get_object(1), COSStream):
            raise OSError(
                "ICCBased colorspace array must have a stream as second element"
            )

    @staticmethod
    def check_array(icc_array: COSArray) -> None:
        """Public alias of :meth:`_check_array`. Mirrors upstream's
        private static ``checkArray(COSArray)`` (line 134 of
        ``PDICCBased.java``) — surfaced here so callers building or
        validating an ICCBased ``COSArray`` outside the constructor can
        run the same shape check.
        """
        PDICCBased._check_array(icc_array)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return self.get_n()

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Return the default image ``/Decode`` array for this ICCBased
        color space.

        Mirrors upstream ``PDICCBased.getDefaultDecode(int)``: each
        component's decode pair comes from that component's ``/Range``
        entry, with the PDF default ``(0.0, 1.0)`` used when ``/Range``
        is absent or too short.
        """
        out: list[float] = []
        for component in range(self.get_n()):
            low, high = self.get_range_for_component(component)
            out.append(low)
            out.append(high)
        return out

    # ---------- ICCBased-specific ----------

    def _get_stream(self) -> COSStream | None:
        assert self._array is not None
        entry = self._array.get_object(1)
        if isinstance(entry, COSStream):
            return entry
        return None

    def get_pdstream(self) -> COSStream | None:
        """Return the underlying COSStream carrying the ICC profile."""
        return self._get_stream()

    def get_pd_stream(self) -> PDStream | None:
        """Return the underlying ICC profile stream wrapped as a
        :class:`PDStream`. Mirrors upstream
        ``PDICCBased.getPDStream() : PDStream``. Returns ``None`` when
        the array's second entry is not a stream."""
        stream = self._get_stream()
        if stream is None:
            return None
        return PDStream(stream)

    def get_n(self) -> int:
        """``/N`` — number of color components (1, 3, or 4). Mirrors
        upstream ``PDICCBased.getNumberOfComponents()`` /
        ``getN() : int``. Default is ``0`` (invalid) when the stream is
        absent or ``/N`` is missing — matches upstream's
        ``getInt(COSName.N, 0)``."""
        stream = self._get_stream()
        if stream is None:
            return 0
        return stream.get_int(_N, 0)

    def set_n(self, n: int) -> None:
        """Set ``/N`` (number of color components)."""
        stream = self._get_stream()
        if stream is None:
            return
        stream.set_int(_N, int(n))

    def get_alternate(self) -> PDColorSpace | None:
        stream = self._get_stream()
        if stream is None:
            return None
        alt = stream.get_dictionary_object(_ALTERNATE)
        if alt is None:
            return None
        return PDColorSpace.create(alt)

    def set_alternate(self, alternate: PDColorSpace | None) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        if alternate is None:
            stream.remove_item(_ALTERNATE)
            return
        cos = alternate.get_cos_object()
        if cos is None:
            raise TypeError("set_alternate requires a color space with a COS form")
        stream.set_item(_ALTERNATE, cos)

    def has_alternate(self) -> bool:
        """Return ``True`` when ``/Alternate`` resolves to a color space."""
        return self.get_alternate() is not None

    def clear_alternate(self) -> None:
        """Remove ``/Alternate``. No-op if the ICC stream is malformed."""
        self.set_alternate(None)

    def get_alternate_color_space(self) -> PDColorSpace | None:
        """``/Alternate`` — typed alternate color space. Mirrors upstream
        ``PDICCBased.getAlternateColorSpace() : PDColorSpace``.

        Upstream's accessor never simply returns the raw ``/Alternate``:
        when ``/Alternate`` is absent it synthesises the default alternate
        by component count (1 → DeviceGray, 3 → DeviceRGB, 4 → DeviceCMYK)
        and *throws* ``IOException`` for any other count. pypdfbox keeps
        the default-by-N synthesis but stays permissive on the invalid-N
        path (returns ``None`` instead of raising — the documented
        permissive-factory contract; see CHANGES.md "wave 1528").

        Use :meth:`get_alternate` for the literal ``/Alternate`` read
        without the default-by-N synthesis.
        """
        alt = self.get_alternate()
        if alt is not None:
            return alt
        return self.fallback_to_alternate_color_space()

    def set_alternate_color_space(self, alternate: PDColorSpace | None) -> None:
        """Upstream-named alias of :meth:`set_alternate`."""
        self.set_alternate(alternate)

    def set_alternate_color_spaces(
        self, alternates: list[PDColorSpace] | None
    ) -> None:
        """Set ``/Alternate`` from a list of color spaces. Mirrors
        upstream ``PDICCBased.setAlternateColorSpaces(List<PDColorSpace>)``.

        ``None`` clears the entry (writes a ``None`` slot — matches
        upstream's ``setItem(ALTERNATE, null)``). An empty list still
        writes an empty ``COSArray`` so the entry stays canonical.
        """
        stream = self._get_stream()
        if stream is None:
            return
        if alternates is None:
            stream.set_item(_ALTERNATE, None)
            return
        alt_array = COSArray()
        for cs in alternates:
            cos = cs.get_cos_object() if cs is not None else None
            if cos is not None:  # pragma: no branch
                # Defensive: alternates filtered for non-None entries
                # above (the inline conditional drops cs=None to cos=None
                # but every live PDColorSpace exposes a COS object).
                alt_array.add(cos)
        stream.set_item(_ALTERNATE, alt_array)

    def get_range(self) -> COSArray | None:
        stream = self._get_stream()
        if stream is None:
            return None
        entry = stream.get_dictionary_object(_RANGE)
        if isinstance(entry, COSArray):
            return entry
        return None

    def set_range(self, range_array: COSArray) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        stream.set_item(_RANGE, range_array)

    def has_range(self) -> bool:
        """Return ``True`` when ``/Range`` is present as a ``COSArray``."""
        return self.get_range() is not None

    def clear_range(self) -> None:
        """Remove ``/Range``. Components then decode as ``(0.0, 1.0)``."""
        stream = self._get_stream()
        if stream is not None:
            stream.remove_item(_RANGE)

    def get_range_for_component(self, n: int) -> tuple[float, float]:
        """Return the ``(low, high)`` pair from ``/Range`` for component
        ``n``. Mirrors upstream
        ``PDICCBased.getRangeForComponent(int) : PDRange``. Defaults to
        ``(0.0, 1.0)`` when ``/Range`` is missing or the array is too
        short for all components — mirrors PDFBox's lenient handling of
        malformed short ``/Range`` arrays."""
        rng = self.get_range()
        if rng is None or len(rng) < self.get_n() * 2:
            return (0.0, 1.0)
        low_idx = 2 * n
        high_idx = 2 * n + 1
        floats = rng.to_float_array()
        return (float(floats[low_idx]), float(floats[high_idx]))

    def set_range_for_component(self, n: int, low: float, high: float) -> None:
        """Set the ``(low, high)`` pair on ``/Range`` for component ``n``.
        Grows ``/Range`` (padding intermediate slots with the default
        ``(0.0, 1.0)``) when ``n`` is past the current end. Mirrors
        upstream ``PDICCBased.setRangeForComponent(PDRange, int)`` shape
        with positional ``low``/``high`` instead of a ``PDRange`` value
        type (we don't have a ``PDRange`` class in the lite surface)."""
        stream = self._get_stream()
        if stream is None:
            return
        rng = self.get_range()
        if rng is None:
            rng = COSArray()
            stream.set_item(_RANGE, rng)
        # Pad intermediate slots with the default (0.0, 1.0) pair so the
        # requested component index lands at a valid offset.
        required = 2 * (n + 1)
        while len(rng) < required - 2:
            rng.add(COSFloat(0.0))
            rng.add(COSFloat(1.0))
        if len(rng) < required:
            # Append the requested pair directly.
            rng.add(COSFloat(float(low)))
            rng.add(COSFloat(float(high)))
        else:
            rng.set(2 * n, COSFloat(float(low)))
            rng.set(2 * n + 1, COSFloat(float(high)))

    def get_metadata(self) -> PDMetadata | None:
        """``/Metadata`` — XMP metadata stream wrapped as
        :class:`PDMetadata`, or ``None``. Mirrors upstream
        ``PDICCBased.getMetadata() : PDMetadata``."""
        stream = self._get_stream()
        if stream is None:
            return None
        entry = stream.get_dictionary_object(_METADATA)
        if isinstance(entry, COSStream):
            return PDMetadata(entry)
        return None

    def set_metadata(self, metadata: PDMetadata | COSStream | None) -> None:
        """Set ``/Metadata`` (or remove when ``None``). Accepts a
        :class:`PDMetadata` (unwrapped to its underlying ``COSStream``)
        or a raw ``COSStream``."""
        stream = self._get_stream()
        if stream is None:
            return
        if metadata is None:
            stream.remove_item(_METADATA)
            return
        if isinstance(metadata, PDMetadata):
            stream.set_item(_METADATA, metadata.get_cos_object())
            return
        stream.set_item(_METADATA, metadata)

    def has_metadata(self) -> bool:
        """Return ``True`` when ``/Metadata`` is present as a stream."""
        return self.get_metadata() is not None

    def clear_metadata(self) -> None:
        """Remove ``/Metadata``. No-op if the ICC stream is malformed."""
        self.set_metadata(None)

    def get_iccprofile_bytes(self) -> bytes:
        """Return the decoded ICC profile body as raw bytes. Mirrors
        upstream ``PDICCBased`` accessing the underlying stream via
        ``getPDStream().createInputStream()``. Empty/absent stream →
        ``b""``."""
        pd_stream = self.get_pd_stream()
        if pd_stream is None:
            return b""
        with pd_stream.create_input_stream() as src:
            return src.read()

    # ---------- profile inspection ----------

    def _read_header_signature(self, offset: int) -> str | None:
        """Decode a 4-byte ASCII signature from the embedded ICC profile
        header at ``offset``. Returns ``None`` when the profile is absent
        or shorter than ``offset + 4`` bytes.

        Mirrors the ICC.1:2010 §7.2 header layout — bytes 12..15 carry
        the device class (table 16), bytes 16..19 the data colour space
        (table 18), and bytes 20..23 the profile connection space (PCS)
        signature. Signatures preserve trailing spaces verbatim so they
        round-trip exactly into the four-byte form expected by ICC
        consumers (e.g. ``"RGB "``, ``"Lab "``, ``"XYZ "``).
        """
        profile = self.get_iccprofile_bytes()
        if len(profile) < offset + 4:
            return None
        try:
            return profile[offset : offset + 4].decode("ascii", errors="replace")
        except UnicodeDecodeError:  # pragma: no cover — errors='replace' covers it
            return None

    def get_device_class(self) -> str | None:
        """Return the ICC profile's device-class signature (4 bytes at
        header offset 12, per ICC.1:2010 §7.2 table 16). Common values:
        ``"scnr"`` (input), ``"mntr"`` (display), ``"prtr"`` (output),
        ``"link"`` (DeviceLink), ``"spac"`` (ColorSpace), ``"abst"``
        (Abstract), ``"nmcl"`` (NamedColor). Returns ``None`` when the
        embedded profile is absent or shorter than 16 bytes.

        Note: upstream PDFBox 3.0 routes this through ``ICC_Profile.
        getProfileClass()`` and returns the AWT integer constant —
        pypdfbox enrichment surfaces the raw four-char signature so
        callers can read it without an AWT dependency."""
        return self._read_header_signature(12)

    def get_color_space_signature(self) -> str | None:
        """Return the ICC profile's data colour-space signature (4 bytes
        at header offset 16, per ICC.1:2010 §7.2 table 18). Common
        values: ``"RGB "``, ``"CMYK"``, ``"GRAY"``, ``"Lab "``,
        ``"XYZ "``. Returns ``None`` when the embedded profile is
        absent or shorter than 20 bytes.

        Note: upstream PDFBox 3.0 surfaces this through
        ``ICC_Profile.getColorSpaceType()`` as an AWT integer — see
        :meth:`get_color_space_type` for the integer form."""
        return self._read_header_signature(16)

    def get_pcs_signature(self) -> str | None:
        """Return the ICC profile-connection-space (PCS) signature
        (4 bytes at header offset 20, per ICC.1:2010 §7.2). Only two
        PCS values are legal: ``"XYZ "`` and ``"Lab "``. Returns
        ``None`` when the embedded profile is absent or shorter than
        24 bytes.

        Note: upstream PDFBox 3.0 routes this through ``ICC_Profile.
        getPCSType()`` and returns the AWT integer constant — pypdfbox
        enrichment exposes the raw signature directly."""
        return self._read_header_signature(20)

    def is_srgb(self) -> bool:
        """Return ``True`` when this ICCBased color space carries the
        embedded sRGB profile or its alternate resolves to DeviceRGB.
        Mirrors upstream ``PDICCBased.isSRGB() : boolean``.

        Detection mirrors upstream's ``is_sRGB`` private helper: the
        ICC profile header's ``deviceModel`` (bytes 84..91 of the
        128-byte profile header) is read as US-ASCII and compared to
        the literal string ``"sRGB"`` after trimming whitespace. When
        the embedded profile is unreadable, the alternate color space
        is consulted and a DeviceRGB alternate is treated as sRGB
        (matches upstream's fallback in ``loadICCProfile``).
        """
        profile = self.get_iccprofile_bytes()
        # Profile header is 128 bytes, deviceModel signature occupies
        # bytes 84..91 (icHdrModel). Need at least 91 bytes to read it.
        if len(profile) >= 91:
            try:
                device_model = profile[84:91].decode(
                    "ascii", errors="replace"
                ).strip("\x00 \t\r\n")
            except UnicodeDecodeError:
                device_model = ""
            if device_model == "sRGB":
                return True
        # Fallback: when the profile is unreadable but the alternate
        # color space is DeviceRGB, upstream's loadICCProfile flips
        # the ``isRGB`` flag — mirror that here.
        from .pd_device_rgb import PDDeviceRGB

        alternate = self.get_alternate()
        if alternate is PDDeviceRGB.INSTANCE:
            return True
        return alternate is not None and alternate.get_name() == "DeviceRGB"

    def get_color_space_type(self) -> int:
        """Return the ``java.awt.color.ColorSpace`` type integer for
        this ICCBased color space. Mirrors upstream
        ``PDICCBased.getColorSpaceType() : int``.

        When the embedded profile is readable we inspect bytes 16..19
        of the profile header (``icHdrColorSpace`` signature) to map
        common ICC color-space tags onto AWT's numeric type. Otherwise
        we fall back to ``/N``-based inference (1→GRAY, 3→RGB, 4→CMYK,
        anything else → ``-1``) — matches upstream's alternate-CS
        fallback path.
        """
        profile = self.get_iccprofile_bytes()
        # Profile header is 128 bytes; ``icHdrColorSpace`` signature
        # occupies bytes 16..19 (4-byte ASCII). Need at least 20.
        if len(profile) >= 20:
            try:
                signature = profile[16:20].decode(
                    "ascii", errors="replace"
                )
            except UnicodeDecodeError:
                signature = ""
            mapping = {
                "XYZ ": TYPE_XYZ,
                "Lab ": TYPE_LAB,
                "Luv ": TYPE_LUV,
                "YCbr": TYPE_YCBCR,
                "Yxy ": TYPE_YXY,
                "RGB ": TYPE_RGB,
                "GRAY": TYPE_GRAY,
                "HSV ": TYPE_HSV,
                "HLS ": TYPE_HLS,
                "CMYK": TYPE_CMYK,
                "CMY ": TYPE_CMY,
            }
            mapped = mapping.get(signature)
            if mapped is not None:
                return mapped
        n = self.get_n()
        if n == 1:
            return TYPE_GRAY
        if n == 3:
            return TYPE_RGB
        if n == 4:
            return TYPE_CMYK
        return -1

    @staticmethod
    def is_s_rgb(profile_bytes: bytes) -> bool:
        """Return ``True`` when ``profile_bytes`` carries the sRGB device
        model marker. Mirrors upstream's private
        ``is_sRGB(ICC_Profile) : boolean`` helper (line 246 of
        ``PDICCBased.java``).

        Reads bytes 84..91 of the 128-byte ICC profile header
        (``icHdrModel`` signature, length 7) as US-ASCII and returns
        ``True`` when the trimmed value equals ``"sRGB"``. ``False`` when
        the buffer is too short or the signature differs — matches the
        upstream behaviour that defaults to non-sRGB when the header
        can't be read.
        """
        if len(profile_bytes) < 91:
            return False
        try:
            device_model = profile_bytes[84:91].decode(
                "ascii", errors="replace"
            ).strip("\x00 \t\r\n")
        except UnicodeDecodeError:
            return False
        return device_model == "sRGB"

    @staticmethod
    def int_to_big_endian(value: int, array: bytearray, index: int) -> None:
        """Write ``value`` as a 4-byte big-endian integer into ``array``
        starting at ``index``. Mirrors upstream's private static
        ``intToBigEndian(int, byte[], int)`` (line 272 of
        ``PDICCBased.java``).

        Used by :meth:`ensure_display_profile` when patching the ICC
        header's ``deviceClass`` signature to ``scnr``/``mntr`` etc.
        Operates in place on ``array``; returns ``None``.
        """
        v = int(value) & 0xFFFFFFFF
        array[index] = (v >> 24) & 0xFF
        array[index + 1] = (v >> 16) & 0xFF
        array[index + 2] = (v >> 8) & 0xFF
        array[index + 3] = v & 0xFF

    @staticmethod
    def ensure_display_profile(profile_bytes: bytes) -> bytes:
        """Patch a non-display ICC profile to ``CLASS_DISPLAY`` when the
        rendering intent is Perceptual. Mirrors upstream's private static
        ``ensureDisplayProfile(ICC_Profile) : ICC_Profile`` (line 256 of
        ``PDICCBased.java``).

        Upstream borrows the workaround from twelvemonkeys' JPEG reader
        (PDFBOX-4114): ICC profiles whose ``deviceClass`` is something
        other than ``"mntr"`` (Display) confuse Java's CMM. When the
        rendering intent (header byte 64) is Perceptual (``0``) we
        rewrite ``deviceClass`` (header bytes 12..15) in place to the
        display signature ``"mntr"``. Otherwise the profile is returned
        unchanged — same shape as upstream.
        """
        if len(profile_bytes) < 68:
            return profile_bytes
        # ``icHdrDeviceClass`` is bytes 12..15 (4-byte ASCII signature).
        device_class = profile_bytes[12:16]
        # ``icSigDisplayClass`` = "mntr"; bail out if already display.
        if device_class == b"mntr":
            return profile_bytes
        # ``icHdrRenderingIntent`` is at byte offset 64 (4-byte BE int).
        # Perceptual = 0; keep upstream's narrow guard.
        rendering_intent = int.from_bytes(
            profile_bytes[64:68], "big", signed=False
        )
        if rendering_intent != 0:
            return profile_bytes
        patched = bytearray(profile_bytes)
        # icSigDisplayClass = ASCII "mntr" packed big-endian.
        sig = int.from_bytes(b"mntr", "big", signed=False)
        PDICCBased.int_to_big_endian(sig, patched, 12)
        return bytes(patched)

    def fallback_to_alternate_color_space(
        self, error: BaseException | None = None
    ) -> PDColorSpace | None:
        """Return the ``/Alternate`` color space (or one inferred from
        ``/N``) and surface the same shape as upstream's private
        ``fallbackToAlternateColorSpace(Exception)`` (line 226 of
        ``PDICCBased.java``).

        Upstream mutates instance state — clearing ``awtColorSpace``,
        memoising ``alternateColorSpace`` and ``initialColor``, and
        flipping ``isRGB`` when the alternate is DeviceRGB. We don't
        cache an AWT color-space adapter, so this just resolves and
        returns the alternate (the caller can pass it to
        :meth:`to_rgb`, etc.). When ``error`` is supplied it's accepted
        for surface compatibility and ignored — upstream uses it only
        for a logger warning.
        """
        from .pd_device_cmyk import PDDeviceCMYK
        from .pd_device_gray import PDDeviceGray
        from .pd_device_rgb import PDDeviceRGB

        del error  # surface-only, mirrors upstream's logger-only use
        alternate = self.get_alternate()
        if alternate is not None:
            return alternate
        n = self.get_n()
        if n == 1:
            return PDDeviceGray.INSTANCE
        if n == 3:
            return PDDeviceRGB.INSTANCE
        if n == 4:
            return PDDeviceCMYK.INSTANCE
        return None

    def load_icc_profile(self) -> bytes:
        """Materialise and lightly validate the embedded ICC profile.
        Mirrors upstream's private ``loadICCProfile()`` (line 164 of
        ``PDICCBased.java``).

        Upstream parses the profile through ``java.awt.color.ICC_Profile``
        and falls back to the alternate color space on parse failure,
        mutating private state along the way. We don't carry an AWT
        color-space cache, so this returns the profile bytes after
        running them through :meth:`ensure_display_profile` (the
        Perceptual → Display class fix-up). Returns ``b""`` when the
        underlying stream is missing — same shape as upstream's
        fallback-to-alternate path which leaves ``iccProfile`` ``None``.
        """
        profile_bytes = self.get_iccprofile_bytes()
        if not profile_bytes:
            return b""
        return self.ensure_display_profile(profile_bytes)

    def clamp_colors(
        self, components: list[float]
    ) -> list[float]:
        """Clamp ``components`` against this color space's per-component
        ``/Range`` bounds. Mirrors upstream's private
        ``clampColors(ICC_ColorSpace, float[])`` (line 299 of
        ``PDICCBased.java``).

        Upstream pulls per-component ``minValue``/``maxValue`` from the
        AWT color-space adapter; we read them from ``/Range`` (default
        ``(0.0, 1.0)``) so the result honours the same lower/upper
        bounds as upstream when the profile is well-formed and the
        ``/Range`` array matches the profile's gamut. Components beyond
        ``len(components)`` are not invented; the returned list matches
        the input length.
        """
        out: list[float] = []
        for i, value in enumerate(components):
            low, high = self.get_range_for_component(i)
            v = float(value)
            if v < low:
                v = low
            elif v > high:
                v = high
            out.append(v)
        return out

    # ---------- rendering overrides ----------

    def to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Convert an 8-bpc raster in this ICCBased color space into an
        sRGB Pillow image. Mirrors upstream
        ``PDICCBased.toRGBImage(WritableRaster)`` (line 312 of
        ``PDICCBased.java``).

        Bulk-applies the cached LittleCMS2 transform built from the
        embedded ICC profile to the entire raster in one call — matches
        upstream's ``toRGBImageAWT(raster, awtColorSpace)`` path which
        hands the raw raster to ``ICC_ColorSpace.toRGB`` rather than
        looping per pixel. When the embedded profile is unreadable
        (corrupt, unsupported channel count, e.g. a CMYK profile carrying
        no A2B0 LUT that LittleCMS refuses to build a transform from, or
        ImageCms missing) we delegate to the ``/Alternate`` color space's
        *bulk* ``to_rgb_image`` — mirroring upstream's
        ``alternateColorSpace.toRGBImage(raster)`` short-circuit when the
        AWT colour space is null (``PDICCBased.toRGBImage`` line 312). The
        alternate is resolved via :meth:`fallback_to_alternate_color_space`
        (``/Alternate`` or one inferred from ``/N`` ∈ {1, 3, 4}). Only if
        no alternate resolves do we drop to the base class's per-pixel
        loop — that path would otherwise re-attempt the already-failed ICC
        transform once per pixel (a warning storm + O(w·h) slowdown).
        """
        image = self._try_icc_to_rgb_image(raster, width, height)
        if image is not None:
            return image
        alternate = self.fallback_to_alternate_color_space()
        if alternate is not None and alternate is not self:
            return alternate.to_rgb_image(raster, width, height)
        return super().to_rgb_image(raster, width, height)

    def to_raw_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Wrap an 8-bpc raster as a Pillow image in this ICCBased color
        space's native mode when possible (1/3/4 components → ``L`` /
        ``RGB`` / ``CMYK``); falls through to :meth:`to_rgb_image`
        otherwise. Mirrors upstream
        ``PDICCBased.toRawImage(WritableRaster)`` (line 325 of
        ``PDICCBased.java``).

        Upstream short-circuits to ``alternateColorSpace.toRawImage``
        when the AWT color space is null; we route through the base
        class's ``to_raw_image`` which already prefers native modes for
        Device* spaces and falls through to RGB for everything else.
        """
        return super().to_raw_image(raster, width, height)

    # ---------- conversion ----------

    def to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Convert ``components`` through the embedded ICC profile when
        possible, falling back to the alternate color space otherwise.

        Per PDF 32000-1 §8.6.5.5: the ICC profile in the stream is the
        canonical converter; ``/Alternate`` (or one inferred from
        ``/N`` ∈ {1, 3, 4} → DeviceGray/DeviceRGB/DeviceCMYK) is a
        fallback for renderers that can't process the profile.

        We try Pillow's ``ImageCms`` first — when it's available *and*
        the embedded profile parses, we build an sRGB transform and run
        the ``components`` through it. On any error (malformed profile,
        unsupported component count) we silently fall through to the
        alternate-CS path so callers always get a valid sRGB tuple.
        """
        from .pd_device_cmyk import PDDeviceCMYK
        from .pd_device_gray import PDDeviceGray
        from .pd_device_rgb import PDDeviceRGB

        # Try ICC-based conversion first when Pillow is available.
        rgb = self._try_icc_to_rgb(components)
        if rgb is not None:
            return rgb

        alternate = self.get_alternate()
        if alternate is None:
            n = self.get_n()
            if n == 1:
                alternate = PDDeviceGray.INSTANCE
            elif n == 3:
                alternate = PDDeviceRGB.INSTANCE
            elif n == 4:
                alternate = PDDeviceCMYK.INSTANCE
            else:
                return None
        # Build a PDColor in the alternate CS and let it dispatch.
        return PDColor(components, alternate).to_rgb()

    def _resolve_in_mode(self, profile_bytes: bytes) -> str | None:
        """Pick the Pillow ``ImageCms`` input mode for the embedded ICC
        profile. Honours the profile header's data colour-space signature
        (bytes 16..19) first so v2/v4 profiles whose signature disagrees
        with the stream's ``/N`` (rare but legal — PDF can carry a 1-
        component ICCBased over a GRAY-typed profile, etc.) still feed
        LittleCMS the mode it actually wants. Falls back to ``/N`` when
        the signature is unrecognised."""
        if len(profile_bytes) >= 20:
            sig = profile_bytes[16:20].decode("ascii", errors="replace")
            mode = _SIGNATURE_TO_MODE.get(sig)
            if mode is not None:
                return mode
        return _N_TO_MODE.get(self.get_n())

    def _get_input_profile(self, profile_bytes: bytes) -> Any | None:
        """Return a cached ``ImageCmsProfile`` for ``profile_bytes``.
        Cache key is the SHA-256 of the bytes (content-addressed); two
        PDFs embedding the same profile share the same parse — mirrors
        the AWT-level ``ICC_Profile`` cache that upstream PDFBox piggy-
        backs on. Returns ``None`` when Pillow's CMM rejects the bytes."""
        try:
            from io import BytesIO

            from PIL import ImageCms
        except ImportError:  # pragma: no cover — Pillow is a hard dep
            return None
        key = hashlib.sha256(profile_bytes).hexdigest()
        cached = _PROFILE_CACHE.get(key)
        if cached is not None:
            return cached
        try:
            profile = ImageCms.ImageCmsProfile(BytesIO(profile_bytes))
        except (OSError, ValueError, ImageCms.PyCMSError) as exc:
            _log.warning(
                "ICCBased: Pillow rejected embedded profile (%d bytes): %s",
                len(profile_bytes),
                exc,
            )
            return None
        _PROFILE_CACHE[key] = profile
        return profile

    @staticmethod
    def _get_srgb_profile() -> Any | None:
        """Return the singleton sRGB output profile used for every
        ICC→sRGB conversion in this module. Built once and stashed in
        ``_SRGB_CACHE`` so the per-conversion cost is one dict lookup,
        not a fresh ``createProfile('sRGB')`` parse. Returns ``None``
        when ImageCms is unavailable (kept for surface symmetry; in
        practice Pillow ≥12.2 always provides it)."""
        if _SRGB_CACHE:
            return _SRGB_CACHE[0]
        try:
            from PIL import ImageCms
        except ImportError:  # pragma: no cover
            return None
        try:
            profile = ImageCms.createProfile("sRGB")
        except (OSError, ValueError, ImageCms.PyCMSError):
            return None
        _SRGB_CACHE.append(profile)
        return profile

    def _get_transform(
        self, profile_bytes: bytes, in_mode: str, out_mode: str = "RGB",
        intent: int = 0,
    ) -> Any | None:
        """Return a cached ``ImageCms`` transform from the embedded ICC
        profile to sRGB. Keyed on ``(sha256(profile_bytes), in_mode,
        out_mode, intent)`` so distinct render modes against the same
        profile (e.g. n-component ``to_rgb`` and bulk image) reuse the
        underlying LittleCMS LUT — same caching shape as upstream's AWT
        ``ICC_ColorSpace`` instances.

        ``intent`` follows the ICC.1:2010 §B.2 enumeration (0 =
        Perceptual, 1 = RelativeColorimetric, 2 = Saturation, 3 =
        AbsoluteColorimetric). Defaults to Perceptual (0) to match the
        PDF 32000-1 §8.6.5.5 default ``/Intent``."""
        try:
            from PIL import ImageCms
        except ImportError:  # pragma: no cover
            return None
        key = (
            hashlib.sha256(profile_bytes).hexdigest(),
            in_mode,
            out_mode,
            int(intent),
        )
        cached = _TRANSFORM_CACHE.get(key)
        if cached is not None:
            return cached
        in_profile = self._get_input_profile(profile_bytes)
        if in_profile is None:
            return None
        srgb_profile = self._get_srgb_profile()
        if srgb_profile is None:
            return None
        try:
            transform = ImageCms.buildTransform(
                in_profile, srgb_profile, in_mode, out_mode,
                renderingIntent=int(intent),
            )
        except (OSError, ValueError, ImageCms.PyCMSError) as exc:
            _log.warning(
                "ICCBased: buildTransform(%s->%s) failed: %s",
                in_mode,
                out_mode,
                exc,
            )
            return None
        _TRANSFORM_CACHE[key] = transform
        return transform

    def _try_icc_to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Attempt ICC-profile-driven conversion via Pillow's ``ImageCms``.

        Returns ``None`` (caller falls through to ``/Alternate``) when
        Pillow can't parse the embedded profile, the profile's component
        count doesn't match ``/N`` or our supported set (1/3/4), or any
        runtime error occurs while building / running the transform.
        """
        try:
            from PIL import Image, ImageCms
        except ImportError:
            return None

        profile_bytes = self.get_iccprofile_bytes()
        if not profile_bytes:
            return None

        n = self.get_n()
        if n not in (1, 3, 4):
            return None
        if len(components) < n:
            return None

        in_mode = self._resolve_in_mode(profile_bytes)
        if in_mode is None:
            return None

        if in_mode == "L":
            sample: int | tuple[int, ...] = int(
                round(_clamp_unit(components[0]) * 255.0)
            )
        else:
            sample = tuple(
                int(round(_clamp_unit(components[i]) * 255.0)) for i in range(n)
            )

        transform = self._get_transform(profile_bytes, in_mode)
        if transform is None:
            return None
        try:
            src = Image.new(in_mode, (1, 1), sample)
            dst = ImageCms.applyTransform(src, transform)
        except (OSError, ValueError, ImageCms.PyCMSError) as exc:
            _log.warning(
                "ICCBased: applyTransform single-pixel failed: %s", exc,
            )
            return None
        if dst is None:
            return None
        pixel = dst.getpixel((0, 0))
        if not isinstance(pixel, tuple) or len(pixel) < 3:
            return None
        r, g, b = pixel[:3]
        return (r / 255.0, g / 255.0, b / 255.0)

    def _try_icc_to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any | None:
        """Bulk-apply the cached LittleCMS transform to a full 8-bpc
        raster. Returns a Pillow RGB ``Image`` on success, ``None`` when
        any prerequisite is missing (Pillow not importable, profile too
        short, unsupported channel count, transform build / apply
        failure).

        Matches upstream's ``toRGBImageAWT(raster, awtColorSpace)``
        path: hand the whole raster to the CMM in one call. For an
        H×W ICC image this is orders of magnitude faster than the base
        class's per-pixel fallback, and produces identical output to
        upstream because Pillow's ImageCms and PDFBox's AWT path both
        bottom out in LittleCMS2.
        """
        try:
            from PIL import Image, ImageCms
        except ImportError:  # pragma: no cover — Pillow is a hard dep
            return None

        profile_bytes = self.get_iccprofile_bytes()
        if not profile_bytes:
            return None

        n = self.get_n()
        if n not in (1, 3, 4):
            return None
        in_mode = self._resolve_in_mode(profile_bytes)
        if in_mode is None:
            return None
        # Channels per pixel in the raster must match the profile's
        # input mode so frombytes can stride correctly.
        expected_channels = 1 if in_mode == "L" else (
            3 if in_mode == "RGB" else 4
        )
        expected = int(width) * int(height) * expected_channels
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))
        transform = self._get_transform(profile_bytes, in_mode)
        if transform is None:
            return None
        try:
            src = Image.frombytes(in_mode, (int(width), int(height)), data)
            dst = ImageCms.applyTransform(src, transform)
        except (OSError, ValueError, ImageCms.PyCMSError) as exc:
            _log.warning(
                "ICCBased: bulk applyTransform(%dx%d, %s) failed: %s",
                int(width),
                int(height),
                in_mode,
                exc,
            )
            return None
        if dst is None:
            return None
        return dst


    # ---------- string form ----------

    def __str__(self) -> str:
        """Mirrors upstream ``PDICCBased.toString``:
        ``ICCBased{numberOfComponents: <n>}``.
        """
        return f"{self.get_name()}{{numberOfComponents: {self.get_n()}}}"

    def to_string(self) -> str:
        """Return the upstream-style ``toString`` rendering. Mirrors
        upstream ``PDICCBased.toString() : String`` (line 547 of
        ``PDICCBased.java``).

        Surfaced explicitly (not just as ``__str__``) so callers porting
        from PDFBox can keep the literal ``.toString()`` invocation
        spelled snake_case without going through Python's ``str()``.
        """
        return self.__str__()


__all__ = [
    "PDICCBased",
    "TYPE_CMY",
    "TYPE_CMYK",
    "TYPE_GRAY",
    "TYPE_HLS",
    "TYPE_HSV",
    "TYPE_LAB",
    "TYPE_LUV",
    "TYPE_RGB",
    "TYPE_XYZ",
    "TYPE_YCBCR",
    "TYPE_YXY",
]
