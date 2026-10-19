"""Abstract base for the content-stream writer hierarchy.

Mirrors ``org.apache.pdfbox.pdmodel.PDAbstractContentStream``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/PDAbstractContentStream.java``).

The concrete subclass :class:`PDPageContentStream` (and its siblings
``PDAppearanceContentStream``, ``PDFormContentStream``,
``PDPatternContentStream``) inherits from this base and may override
individual operator methods. The base provides default implementations
that emit operator bytes directly to ``self._output_stream`` using the
same number-formatting rules as upstream (``setMaximumFractionDigits(4)``
in the shared base constructor, with trailing zeros trimmed).
"""

import logging
import unicodedata
from collections import deque
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, BinaryIO

from .content_stream_for_glyph_layout_interface import (
    ContentStreamForGlyphLayoutInterface,
)
from .glyphs_and_positions import GlyphsAndPositions
from .pd_page_content_stream import _format_number

if TYPE_CHECKING:
    from .glyph_layout_processor_interface import GlyphLayoutProcessorInterface
    from .pd_document import PDDocument
    from .pd_resources import PDResources

_log = logging.getLogger(__name__)

_LF = b"\n"
_SPACE = b" "


def _format_decimal(value: float, max_fraction_digits: int = 4) -> bytes:
    """Format a numeric operand byte-for-byte like upstream's
    ``PDAbstractContentStream.writeOperand(float)``.

    Upstream's shared base constructor configures the formatter via
    ``NumberFormatUtil.formatFloatFast(real, formatDecimal.getMaximumFractionDigits(), buffer)``
    with ``setMaximumFractionDigits(4)`` (Java line 112) — note this is **4**,
    not the **5** used by the concrete ``PDPageContentStream``. The operand is
    a Java 32-bit ``float``, so the decimal expansion is taken from the
    single-precision value and the fraction is half-up rounded on the narrowed
    value (see :func:`pypdfbox.pdmodel.pd_page_content_stream._format_number`
    for the full algorithm). This helper shares that implementation, only
    pinning the default digit count to the base class's 4.

    Non-finite values raise :class:`ValueError`, mirroring upstream's
    ``writeOperand(float)`` ``IllegalArgumentException`` guard."""
    return _format_number(value, max_fraction_digits)


def _java_is_whitespace(ch: str) -> bool:
    """Mirror ``java.lang.Character.isWhitespace`` for a single character.

    Java counts the Unicode space / line / paragraph separators except the
    non-breaking ones (U+00A0, U+2007, U+202F), plus the ASCII controls
    TAB, LF, VT, FF, CR and U+001C-U+001F."""
    if ch in "\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f":
        return True
    if ch in "\u00a0\u2007\u202f":
        return False
    return unicodedata.category(ch) in ("Zs", "Zl", "Zp")


def _gsub_data_for_type0(font: Any) -> Any:
    """Return the ``GsubData`` upstream's ``PDType0Font.getGsubData()`` would.

    Upstream's embedding constructor captures ``ttf.getGsubData()``; a font
    read back from a PDF (the ``COSDictionary`` constructor) carries
    ``GsubData.NO_DATA_FOUND``."""
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    if not getattr(font, "_embedded_from_font_file", False):
        return GsubData.NO_DATA_FOUND
    descendant = font.get_descendant_font()
    get_ttf = getattr(descendant, "get_true_type_font", None)
    ttf = get_ttf() if callable(get_ttf) else None
    get_gsub_data = getattr(ttf, "get_gsub_data", None)
    if not callable(get_gsub_data):
        return GsubData.NO_DATA_FOUND
    gsub_data = get_gsub_data()
    return GsubData.NO_DATA_FOUND if gsub_data is None else gsub_data


def _register_font(
    document: Any,
    font: Any,
    gsub_workers: dict[Any, Any],
    gsub_worker_factory: Any,
) -> None:
    """The font bookkeeping of upstream ``setFont`` (Java lines 180-217).

    Queues a subsetted font on the document's ``fontsToSubset`` set (so
    ``PDDocument.save`` subsets it), warns about a non-embedded
    non-Standard-14 font, and builds the per-font GSUB worker used by
    complex text layout. Shared by :class:`PDAbstractContentStream` and
    :class:`~pypdfbox.pdmodel.pd_page_content_stream.PDPageContentStream`."""
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    from .font.pd_type0_font import PDType0Font

    # keep track of fonts which are configured for subsetting
    if font.will_be_subset():
        if document is not None:
            document.get_fonts_to_subset().add(font)
        else:
            _log.warning(
                "Using the subsetted font '%s' without a PDDocument context; "
                "call subset() before saving",
                font.get_name(),
            )
    elif not font.is_embedded() and not font.is_standard14():
        _log.warning(
            "attempting to use font '%s' that isn't embedded", font.get_name()
        )

    # complex text layout
    if isinstance(font, PDType0Font):
        gsub_data = _gsub_data_for_type0(font)
        if gsub_data is not GsubData.NO_DATA_FOUND:
            gsub_workers[font] = gsub_worker_factory.get_gsub_worker(
                font.get_cmap_lookup(), gsub_data
            )
        else:
            _log.debug("No GSUB data found in font%s", font.get_name())


def _encode_text(font: Any, text: str, gsub_workers: dict[Any, Any]) -> bytes:
    """Encode ``text`` with ``font`` and record subset usage.

    The encoding half of upstream ``showTextInternal`` (Java lines 292-326):
    a ``PDType0Font`` with a GSUB worker goes through
    :func:`encode_for_gsub` (its glyph ids are pinned into the subset);
    every other font uses ``font.encode(text)``. When the font will be
    subset, each Unicode code point of ``text`` is added to the subset."""
    from .font.pd_type0_font import PDType0Font

    # complex text layout
    encoded_text: bytes | None = None
    if isinstance(font, PDType0Font):
        gsub_worker = gsub_workers.get(font)
        if gsub_worker is not None:
            glyph_ids: set[int] = set()
            encoded_text = encode_for_gsub(gsub_worker, glyph_ids, font, text)
            if font.will_be_subset():
                font.add_glyphs_to_subset(glyph_ids)

    if encoded_text is None:
        encoded_text = font.encode(text)

    # Unicode code points to keep when subsetting
    if font.will_be_subset():
        for ch in text:
            font.add_to_subset(ord(ch))
    return encoded_text


def encode_for_gsub(
    gsub_worker: Any, glyph_ids: set[int], font: Any, text: str
) -> bytes:
    """Encode ``text`` word by word through ``gsub_worker``.

    Mirrors the private ``encodeForGsub`` (Java lines 1689-1711): the text
    is split on whitespace with the separators kept
    (``StringUtil.tokenizeOnSpace``); a single whitespace token is encoded
    with ``font.encode`` and every other token goes through
    :func:`apply_gsub_rules`, whose glyph ids are added to ``glyph_ids``."""
    from pypdfbox.util.string_util import StringUtil

    out = bytearray()
    for word in StringUtil.tokenize_on_space(text):
        if word is None:
            continue
        if len(word) == 1 and _java_is_whitespace(word):
            out.extend(font.encode(word))
        else:
            glyph_ids.update(apply_gsub_rules(gsub_worker, out, font, word))
    return bytes(out)


def apply_gsub_rules(
    gsub_worker: Any, out: bytearray, font: Any, word: str
) -> list[int]:
    """Map ``word`` to glyph ids, apply GSUB, append the encoded glyphs.

    Mirrors the private ``applyGSUBRules`` (Java lines 1727-1768).

    Deviation: upstream throws ``IllegalStateException`` when the font's
    cmap has no glyph for a character. pypdfbox substitutes glyph 0
    (``.notdef``) instead, matching its documented ``PDFont.encode``
    contract (unencodable characters become CID 0 rather than raising), so
    the GSUB and plain-encode paths emit the same bytes for such text."""
    cmap_lookup = font.get_cmap_lookup()
    original_glyph_ids: list[int] = []
    # convert characters into glyphIds
    for ch in word:
        glyph_id = cmap_lookup.get_glyph_id(ord(ch))
        if glyph_id is None or glyph_id <= 0:
            _log.warning(
                "No glyph for U+%04X in font %s", ord(ch), font.get_name()
            )
            glyph_id = 0
        original_glyph_ids.append(glyph_id)

    glyph_ids_after_gsub = gsub_worker.apply_transforms(original_glyph_ids)
    for glyph_id in glyph_ids_after_gsub:
        out.extend(font.encode_glyph_id(glyph_id))
    return list(glyph_ids_after_gsub)


class PDAbstractContentStream(ContentStreamForGlyphLayoutInterface):
    """Abstract base for the content-stream writer hierarchy.

    Mirrors package-private ``org.apache.pdfbox.pdmodel.PDAbstractContentStream``
    (Java lines 77-1915). Operator emission methods write directly to
    ``self._output_stream`` so the base class is usable on its own
    (subclasses like :class:`PDPageContentStream` may override with
    buffered/optimised variants).

    Since PDFBOX-4951 upstream declares ``implements
    ContentStreamForGlyphLayoutInterface`` so an optional glyph-layout
    backend can drive it; the port mirrors that.
    """

    #: Default maximum number of fractional digits emitted for floating
    #: numeric tokens. Mirrors upstream's ``formatDecimal.setMaximumFractionDigits(4)``
    #: at Java line 112.
    DEFAULT_MAX_FRACTION_DIGITS: int = 4

    def __init__(
        self,
        document: PDDocument | None,
        output_stream: BinaryIO,
        resources: PDResources | None,
    ) -> None:
        """Configure the shared output stream + resource state.

        Mirrors upstream's package-private constructor (Java line 106).
        """
        self._document: PDDocument | None = document
        self._output_stream: BinaryIO = output_stream
        self._resources: PDResources | None = resources

        self._in_text_mode: bool = False
        self._font_stack: deque[Any] = deque()
        # PDFBOX-4951: upstream added a parallel ``Deque<Float> fontSizeStack``
        # so ``showText`` can hand the active font size to a glyph-layout
        # processor (Java line 92). Like upstream it is *not* pushed/popped by
        # ``q``/``Q`` — only ``set_font`` writes it.
        self._font_size_stack: deque[float] = deque()
        self._non_stroking_color_space_stack: deque[Any] = deque()
        self._stroking_color_space_stack: deque[Any] = deque()
        self._max_fraction_digits: int = self.DEFAULT_MAX_FRACTION_DIGITS
        # Optional pluggable text-shaping backend (PDFBOX-4951). ``None``
        # by default — upstream ships no implementation in the core
        # artifact either, and the whole show-text path behaves exactly as
        # before while it stays unset.
        self._glyph_layout_processor: GlyphLayoutProcessorInterface | None = None
        # Complex text layout: one GSUB worker per Type 0 font, built by
        # ``set_font`` (upstream ``gsubWorkers`` / ``gsubWorkerFactory``).
        self._gsub_workers: dict[Any, Any] = {}
        self._gsub_worker_factory: Any = None

    def _get_gsub_worker_factory(self) -> Any:
        if self._gsub_worker_factory is None:
            from pypdfbox.fontbox.ttf.gsub.gsub_worker_factory import (
                GsubWorkerFactory,
            )

            self._gsub_worker_factory = GsubWorkerFactory()
        return self._gsub_worker_factory

    def set_glyph_layout_processor(
        self, glyph_layout_processor: GlyphLayoutProcessorInterface | None
    ) -> None:
        """Set the glyph layout processor.

        Mirrors ``setGlyphLayoutProcessor`` (Java lines 127-130).
        """
        self._glyph_layout_processor = glyph_layout_processor

    # ---------- accessors (mirror protected getters) ----------

    @property
    def document(self) -> PDDocument | None:
        """Owning :class:`PDDocument` (may be ``None``)."""
        return self._document

    @property
    def output_stream(self) -> BinaryIO:
        """The underlying writable stream operator bytes are flushed to."""
        return self._output_stream

    @property
    def resources(self) -> PDResources | None:
        """Resource dictionary fed by this content stream's XObject /
        font / colour-space registrations."""
        return self._resources

    @property
    def in_text_mode(self) -> bool:
        """``True`` between :meth:`begin_text` and :meth:`end_text`."""
        return self._in_text_mode

    # ---------- shared protected helpers ----------

    def set_maximum_fraction_digits(self, fraction_digits_number: int) -> None:
        """Mirrors ``setMaximumFractionDigits(int)`` (Java line 122)."""
        self._max_fraction_digits = max(0, fraction_digits_number)

    def get_maximum_fraction_digits(self) -> int:
        """Return the current maximum fractional-digit count."""
        return self._max_fraction_digits

    # ------------------------------------------------------------------
    # Low-level emit helpers (mirror upstream's protected writers)
    # ------------------------------------------------------------------

    def write(self, text: str) -> None:
        """Emit raw text into the stream. Mirrors ``write(String)`` (Java line 1509)."""
        self._output_stream.write(text.encode("iso-8859-1"))

    def write_line(self) -> None:
        """Emit a newline. Mirrors ``writeLine()`` (Java line 1519)."""
        self._output_stream.write(_LF)

    def write_bytes(self, data: bytes) -> None:
        """Emit raw bytes. Mirrors ``writeBytes(byte[])`` (Java line 1530)."""
        self._output_stream.write(data)

    def write_operand(self, value: Any) -> None:
        """Emit a numeric or name operand. Mirrors the ``writeOperand``
        overloads (Java lines 1447, 1473, 1485).
        """
        from pypdfbox.cos import COSName  # local import to avoid cycles

        if isinstance(value, COSName):
            self._output_stream.write(b"/")
            self._output_stream.write(value.get_name().encode("ascii"))
            self._output_stream.write(_SPACE)
            return
        self._output_stream.write(
            _format_decimal(value, self._max_fraction_digits)
        )
        self._output_stream.write(_SPACE)

    def write_operator(self, text: str) -> None:
        """Emit an operator name followed by a newline.
        Mirrors ``writeOperator(String)`` (Java line 1497).
        """
        self._output_stream.write(text.encode("iso-8859-1"))
        self._output_stream.write(_LF)

    def write_affine_transform(self, transform: Any) -> None:
        """Emit the six components of an affine transform.
        Mirrors ``writeAffineTransform`` (Java line 1541).
        """
        # Accept either an object with ``get_matrix`` returning 6 floats,
        # or a 6-tuple of floats.
        values: tuple[float, ...]
        if hasattr(transform, "get_scale_x"):
            values = (
                transform.get_scale_x(),
                transform.get_shear_y(),
                transform.get_shear_x(),
                transform.get_scale_y(),
                transform.get_translate_x(),
                transform.get_translate_y(),
            )
        else:
            values = tuple(transform)
        for v in values:
            self.write_operand(v)

    # ------------------------------------------------------------------
    # Text-state operators
    # ------------------------------------------------------------------

    def begin_text(self) -> None:
        """Emit ``BT``. Mirrors ``beginText`` (Java line 134)."""
        if self._in_text_mode:
            raise RuntimeError("Error: Nested begin_text() calls are not allowed.")
        self.write_operator("BT")
        self._in_text_mode = True

    def end_text(self) -> None:
        """Emit ``ET``. Mirrors ``endText`` (Java line 151)."""
        if not self._in_text_mode:
            raise RuntimeError(
                "Error: You must call begin_text() before calling end_text."
            )
        self.write_operator("ET")
        self._in_text_mode = False

    def set_font(self, font: Any, font_size: float) -> None:
        """Emit ``Tf``. Mirrors ``setFont`` (Java line 184)."""
        if not self._font_stack:
            self._font_stack.append(font)
        else:
            self._font_stack.pop()
            self._font_stack.append(font)
        # PDFBOX-4951 (Java lines 196-204).
        if not self._font_size_stack:
            self._font_size_stack.append(font_size)
        else:
            self._font_size_stack.pop()
            self._font_size_stack.append(font_size)
        _register_font(
            self._document,
            font,
            self._gsub_workers,
            self._get_gsub_worker_factory(),
        )
        if self._resources is not None:
            self.write_operand(self._resources.add(font))
        self.write_operand(font_size)
        self.write_operator("Tf")

    def show_text(self, text: str | bytes) -> None:
        """Emit ``Tj``. Mirrors ``showText`` (Java lines 265-270, plus the
        PDFBOX-4951 glyph-layout-processor branch).

        ``text`` is encoded by the current font (see
        :meth:`show_text_internal`). pypdfbox extension: pre-encoded
        ``bytes`` are written as-is and never handed to a processor.

        When a glyph-layout processor has been registered (see
        :meth:`set_glyph_layout_processor`) and it claims the current font,
        the text is handed to the processor instead — it then drives
        :meth:`show_glyphs_with_positioning` / :meth:`show_glyph_codes`.
        With no processor registered (the default, and the only shape the
        core library ships) the emitted bytes are unchanged.
        """
        if not self._in_text_mode:
            raise RuntimeError("Must call begin_text() before show_text()")
        if not self._font_stack:
            raise RuntimeError("Must call set_font() before show_text()")
        if not self._font_size_stack:
            raise RuntimeError("Font is set, but fontSize is not set")
        font = self._font_stack[-1]
        processor = self._glyph_layout_processor
        if (
            processor is not None
            and isinstance(text, str)
            and processor.supports_font(font)
        ):
            font_size = self._font_size_stack[-1]
            processor.show_text(self, font, font_size, text)
            return
        self.show_text_internal(text)
        self.write(" ")
        self.write_operator("Tj")

    def show_glyph_codes(self, glyph_codes: Sequence[int]) -> None:
        """Emit ``Tj`` for raw glyph codes — only for ``PDType0Font``.

        Mirrors ``showGlyphCodes(int[])`` (Java lines 373-378).
        """
        self.write_text_pd_type0_font(glyph_codes)
        self.write(" ")
        self.write_operator("Tj")

    def write_text_pd_type0_font(self, glyph_codes: Sequence[int]) -> None:
        """Output the given glyph codes — only for ``PDType0Font``.

        Mirrors the protected ``writeTextPDType0Font(int[])``
        (Java lines 388-424).
        """
        from pypdfbox.pdfwriter.cos_writer import COSWriter
        from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

        if not self._in_text_mode:
            raise RuntimeError(
                "Must call begin_text() before write_text_pd_type0_font()"
            )
        if not self._font_stack:
            raise RuntimeError(
                "Must call set_font() before write_text_pd_type0_font()"
            )
        font = self._font_stack[-1]
        if not isinstance(font, PDType0Font):
            raise RuntimeError(
                "Must be called with current font instance of PDType0Font"
            )

        # encode glyphs, update set of used glyphs
        out = bytearray()
        glyph_ids: set[int] = set()
        for glyph_code in glyph_codes:
            out.extend(font.encode_glyph_id(glyph_code))
            if glyph_code < 0xFFFF:
                glyph_ids.add(glyph_code)
        encoded_text = bytes(out)

        # add glyphs to subset
        if font.will_be_subset():
            font.add_glyphs_to_subset(glyph_ids)
        # write encoded text and the PDF operator
        COSWriter.write_string(encoded_text, self._output_stream)

    def show_glyphs_with_positioning(
        self, glyphs_and_positions: GlyphsAndPositions
    ) -> None:
        """Emit ``TJ`` from a :class:`GlyphsAndPositions` built by a
        glyph-layout processor.

        Mirrors ``showGlyphsWithPositioning`` (Java lines 302-330). This
        method is meant to be called from within a
        ``GlyphLayoutProcessorInterface`` implementation and only for
        ``PDType0Font``.
        """
        self.write("[")
        for obj in glyphs_and_positions.to_array():
            if isinstance(obj, GlyphsAndPositions.GlyphSubList):
                self.write_text_pd_type0_font(obj.to_int_array())
            elif isinstance(obj, float):
                self.write_operand(obj)
            elif obj is None:
                raise TypeError("Argument contains null entry")
            else:
                raise ValueError(
                    "Argument must consist of array of Float and "
                    "GlyphsAndPositions.GlyphSubList types, not "
                    f"{type(obj).__name__}"
                )
        self.write("] ")
        self.write_operator("TJ")

    def show_text_internal(self, text: str | bytes) -> None:
        """Output a string using the correct encoding and subsetting.

        Mirrors the protected ``showTextInternal`` (Java lines 279-329):
        the text is encoded by the current font (through the GSUB worker
        for a Type 0 font that has one), every code point is added to the
        subset when the font will be subset, and the bytes are written with
        ``COSWriter.writeString`` (literal form for 7-bit data without
        CR/LF, hex form otherwise).

        pypdfbox extension: already-encoded ``bytes`` are written as-is
        (no encoding, no subset tracking).
        """
        from pypdfbox.pdfwriter.cos_writer import COSWriter

        if not self._in_text_mode:
            raise RuntimeError("Must call begin_text() before show_text()")
        if not self._font_stack:
            raise RuntimeError("Must call set_font() before show_text()")
        if isinstance(text, (bytes, bytearray)):
            encoded_text = bytes(text)
        else:
            encoded_text = _encode_text(
                self._font_stack[-1], text, self._gsub_workers
            )
        COSWriter.write_string(encoded_text, self._output_stream)

    def show_text_with_positioning(self, array: list[Any]) -> None:
        """Emit ``TJ``. Mirrors ``showTextWithPositioning`` (Java lines
        236-256, plus the PDFBOX-4951 up-front state guards).

        pypdfbox extensions: ``int`` adjustments are accepted alongside
        ``float``, and ``bytes`` items are written pre-encoded."""
        if not self._in_text_mode:
            raise RuntimeError(
                "Must call begin_text() before show_text_with_positioning()"
            )
        if not self._font_stack:
            raise RuntimeError(
                "Must call set_font() before show_text_with_positioning()"
            )
        self.write("[")
        for obj in array:
            if isinstance(obj, (str, bytes, bytearray)):
                self.show_text_internal(obj)
            elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
                self.write_operand(obj)
            else:
                raise ValueError(
                    "Argument must consist of array of Float and String types"
                )
        self.write("] ")
        self.write_operator("TJ")

    def set_leading(self, leading: float) -> None:
        """Emit ``TL``. Mirrors ``setLeading`` (Java line 337)."""
        self.write_operand(leading)
        self.write_operator("TL")

    def new_line(self) -> None:
        """Emit ``T*``. Mirrors ``newLine`` (Java line 349)."""
        if not self._in_text_mode:
            raise RuntimeError("Must call begin_text() before new_line()")
        self.write_operator("T*")

    def new_line_at_offset(self, tx: float, ty: float) -> None:
        """Emit ``Td``. Mirrors ``newLineAtOffset`` (Java line 367)."""
        if not self._in_text_mode:
            raise RuntimeError("Must call begin_text() before new_line_at_offset()")
        self.write_operand(tx)
        self.write_operand(ty)
        self.write_operator("Td")

    def set_text_matrix(self, matrix: Any) -> None:
        """Emit ``Tm``. Mirrors ``setTextMatrix`` (Java line 386)."""
        if not self._in_text_mode:
            raise RuntimeError("Must call begin_text() before set_text_matrix()")
        self.write_affine_transform(matrix)
        self.write_operator("Tm")

    def set_character_spacing(self, spacing: float) -> None:
        """Emit ``Tc``. Mirrors ``setCharacterSpacing`` (Java line 1609)."""
        self.write_operand(spacing)
        self.write_operator("Tc")

    def set_word_spacing(self, spacing: float) -> None:
        """Emit ``Tw``. Mirrors ``setWordSpacing`` (Java line 1628)."""
        self.write_operand(spacing)
        self.write_operator("Tw")

    def set_horizontal_scaling(self, scale: float) -> None:
        """Emit ``Tz``. Mirrors ``setHorizontalScaling`` (Java line 1641)."""
        self.write_operand(scale)
        self.write_operator("Tz")

    def set_rendering_mode(self, mode: Any) -> None:
        """Emit ``Tr``. Mirrors ``setRenderingMode`` (Java line 1654)."""
        value = mode.value if hasattr(mode, "value") else int(mode)
        self.write_operand(int(value))
        self.write_operator("Tr")

    def set_text_rise(self, rise: float) -> None:
        """Emit ``Ts``. Mirrors ``setTextRise`` (Java line 1668)."""
        self.write_operand(rise)
        self.write_operator("Ts")

    # ------------------------------------------------------------------
    # Image / form drawing
    # ------------------------------------------------------------------

    def draw_image(self, image: Any, *args: float) -> None:
        """Emit ``Do`` for an image XObject. Mirrors ``drawImage`` overloads
        (Java lines 405, 422, 449, 476, 493)."""
        x = args[0] if len(args) >= 2 else 0.0
        y = args[1] if len(args) >= 2 else 0.0
        if len(args) >= 4:
            width, height = args[2], args[3]
        else:
            try:
                width = image.get_width()
                height = image.get_height()
            except AttributeError:
                width = height = 1.0
        self.save_graphics_state()
        self.write_operand(width)
        self.write_operand(0)
        self.write_operand(0)
        self.write_operand(height)
        self.write_operand(x)
        self.write_operand(y)
        self.write_operator("cm")
        if self._resources is not None:
            name = self._resources.add(image)
            self.write_operand(name)
        self.write_operator("Do")
        self.restore_graphics_state()

    def draw_form(self, form: Any) -> None:
        """Emit ``Do`` for a form XObject. Mirrors ``drawForm`` (Java line 558)."""
        if self._resources is not None:
            self.write_operand(self._resources.add(form))
        self.write_operator("Do")

    # ------------------------------------------------------------------
    # Graphics-state operators
    # ------------------------------------------------------------------

    def transform(self, matrix: Any) -> None:
        """Emit ``cm``. Mirrors ``transform`` (Java line 578)."""
        self.write_affine_transform(matrix)
        self.write_operator("cm")

    def save_graphics_state(self) -> None:
        """Emit ``q``. Mirrors ``saveGraphicsState`` (Java line 593)."""
        if self._stroking_color_space_stack:
            self._stroking_color_space_stack.append(
                self._stroking_color_space_stack[-1]
            )
        if self._non_stroking_color_space_stack:
            self._non_stroking_color_space_stack.append(
                self._non_stroking_color_space_stack[-1]
            )
        if self._font_stack:
            self._font_stack.append(self._font_stack[-1])
        self.write_operator("q")

    def restore_graphics_state(self) -> None:
        """Emit ``Q``. Mirrors ``restoreGraphicsState`` (Java line 619)."""
        if self._stroking_color_space_stack:
            self._stroking_color_space_stack.pop()
        if self._non_stroking_color_space_stack:
            self._non_stroking_color_space_stack.pop()
        if self._font_stack:
            self._font_stack.pop()
        self.write_operator("Q")

    def get_name(self, color_space: Any) -> Any:
        """Resolve a colour-space resource name. Mirrors ``getName`` (Java line 641)."""
        name = getattr(color_space, "get_name", lambda: None)()
        from pypdfbox.cos import COSName  # local import to avoid cycles

        if name in ("DeviceGray", "DeviceRGB", "DeviceCMYK", "Pattern"):
            return COSName.get_pdf_name(name)
        if self._resources is not None:
            return self._resources.add(color_space)
        return name

    # ------------------------------------------------------------------
    # Path & rectangle operators
    # ------------------------------------------------------------------

    def add_rect(self, x: float, y: float, width: float, height: float) -> None:
        """Emit ``re``. Mirrors ``addRect`` (Java line 904)."""
        self.write_operand(x)
        self.write_operand(y)
        self.write_operand(width)
        self.write_operand(height)
        self.write_operator("re")

    def curve_to(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        """Emit ``c``. Mirrors ``curveTo`` (Java line 930)."""
        for v in (x1, y1, x2, y2, x3, y3):
            self.write_operand(v)
        self.write_operator("c")

    def curve_to2(self, x2: float, y2: float, x3: float, y3: float) -> None:
        """Emit ``v``. Mirrors ``curveTo2`` (Java line 956)."""
        for v in (x2, y2, x3, y3):
            self.write_operand(v)
        self.write_operator("v")

    def curve_to1(self, x1: float, y1: float, x3: float, y3: float) -> None:
        """Emit ``y``. Mirrors ``curveTo1`` (Java line 980)."""
        for v in (x1, y1, x3, y3):
            self.write_operand(v)
        self.write_operator("y")

    def move_to(self, x: float, y: float) -> None:
        """Emit ``m``. Mirrors ``moveTo`` (Java line 1001)."""
        self.write_operand(x)
        self.write_operand(y)
        self.write_operator("m")

    def line_to(self, x: float, y: float) -> None:
        """Emit ``l``. Mirrors ``lineTo`` (Java line 1020)."""
        self.write_operand(x)
        self.write_operand(y)
        self.write_operator("l")

    def stroke(self) -> None:
        """Emit ``S``. Mirrors ``stroke`` (Java line 1037)."""
        self.write_operator("S")

    def close_and_stroke(self) -> None:
        """Emit ``s``. Mirrors ``closeAndStroke`` (Java line 1052)."""
        self.write_operator("s")

    def fill(self) -> None:
        """Emit ``f``. Mirrors ``fill`` (Java line 1067)."""
        self.write_operator("f")

    def fill_even_odd(self) -> None:
        """Emit ``f*``. Mirrors ``fillEvenOdd`` (Java line 1082)."""
        self.write_operator("f*")

    def fill_and_stroke(self) -> None:
        """Emit ``B``. Mirrors ``fillAndStroke`` (Java line 1099)."""
        self.write_operator("B")

    def fill_and_stroke_even_odd(self) -> None:
        """Emit ``B*``. Mirrors ``fillAndStrokeEvenOdd`` (Java line 1116)."""
        self.write_operator("B*")

    def close_and_fill_and_stroke(self) -> None:
        """Emit ``b``. Mirrors ``closeAndFillAndStroke`` (Java line 1133)."""
        self.write_operator("b")

    def close_and_fill_and_stroke_even_odd(self) -> None:
        """Emit ``b*``. Mirrors ``closeAndFillAndStrokeEvenOdd`` (Java line 1150)."""
        self.write_operator("b*")

    def shading_fill(self, shading: Any) -> None:
        """Emit ``sh``. Mirrors ``shadingFill`` (Java line 1166)."""
        if self._resources is not None:
            self.write_operand(self._resources.add(shading))
        self.write_operator("sh")

    def close_path(self) -> None:
        """Emit ``h``. Mirrors ``closePath`` (Java line 1183)."""
        self.write_operator("h")

    def clip(self) -> None:
        """Emit ``W n``. Mirrors ``clip`` (Java line 1198)."""
        self.write_operator("W")
        self.write_operator("n")

    def clip_even_odd(self) -> None:
        """Emit ``W* n``. Mirrors ``clipEvenOdd`` (Java line 1216)."""
        self.write_operator("W*")
        self.write_operator("n")

    def set_line_width(self, line_width: float) -> None:
        """Emit ``w``. Mirrors ``setLineWidth`` (Java line 1234)."""
        self.write_operand(line_width)
        self.write_operator("w")

    def set_line_join_style(self, line_join_style: int) -> None:
        """Emit ``j``. Mirrors ``setLineJoinStyle`` (Java line 1247)."""
        if line_join_style not in (0, 1, 2):
            raise ValueError("Error: unknown value for line join style")
        self.write_operand(line_join_style)
        self.write_operator("j")

    def set_line_cap_style(self, line_cap_style: int) -> None:
        """Emit ``J``. Mirrors ``setLineCapStyle`` (Java line 1267)."""
        if line_cap_style not in (0, 1, 2):
            raise ValueError("Error: unknown value for line cap style")
        self.write_operand(line_cap_style)
        self.write_operator("J")

    def set_line_dash_pattern(self, pattern: list[float], phase: float) -> None:
        """Emit ``d``. Mirrors ``setLineDashPattern`` (Java line 1287)."""
        self.write("[")
        for v in pattern:
            self.write_operand(v)
        self.write("] ")
        self.write_operand(phase)
        self.write_operator("d")

    def set_miter_limit(self, miter_limit: float) -> None:
        """Emit ``M``. Mirrors ``setMiterLimit`` (Java line 1306)."""
        if miter_limit <= 0:
            raise ValueError(
                "A miter limit <= 0 is invalid and will not render in Acrobat Reader"
            )
        self.write_operand(miter_limit)
        self.write_operator("M")

    # ------------------------------------------------------------------
    # Marked-content operators
    # ------------------------------------------------------------------

    def begin_marked_content(self, tag: Any, *args: Any) -> None:
        """Emit ``BMC`` or ``BDC``. Mirrors the three ``beginMarkedContent``
        overloads (Java lines 1322, 1335, 1353)."""
        from pypdfbox.cos import COSName  # local import to avoid cycles

        cos_tag = tag if isinstance(tag, COSName) else COSName.get_pdf_name(str(tag))
        if not args:
            self.write_operand(cos_tag)
            self.write_operator("BMC")
            return
        param = args[0]
        if isinstance(param, int):
            self.write_operand(cos_tag)
            self.write("<<")
            self.write("/MCID ")
            self.write_operand(param)
            self.write(">> ")
            self.write_operator("BDC")
            return
        # PDPropertyList branch — emit the resource reference.
        if self._resources is not None:
            self.write_operand(cos_tag)
            self.write_operand(self._resources.add_property_list(param))
        else:
            self.write_operand(cos_tag)
        self.write_operator("BDC")

    def end_marked_content(self) -> None:
        """Emit ``EMC``. Mirrors ``endMarkedContent`` (Java line 1376)."""
        self.write_operator("EMC")

    def set_marked_content_point(self, tag: Any) -> None:
        """Emit ``MP``. Mirrors ``setMarkedContentPoint`` (Java line 1387)."""
        from pypdfbox.cos import COSName  # local import to avoid cycles

        cos_tag = tag if isinstance(tag, COSName) else COSName.get_pdf_name(str(tag))
        self.write_operand(cos_tag)
        self.write_operator("MP")

    def set_marked_content_point_with_properties(
        self, tag: Any, property_list: Any
    ) -> None:
        """Emit ``DP``. Mirrors ``setMarkedContentPointWithProperties`` (Java line 1400)."""
        from pypdfbox.cos import COSName  # local import to avoid cycles

        cos_tag = tag if isinstance(tag, COSName) else COSName.get_pdf_name(str(tag))
        self.write_operand(cos_tag)
        if self._resources is not None:
            self.write_operand(self._resources.add_property_list(property_list))
        self.write_operator("DP")

    def set_graphics_state_parameters(self, state: Any) -> None:
        """Emit ``gs``. Mirrors ``setGraphicsStateParameters`` (Java line 1413)."""
        if self._resources is not None:
            self.write_operand(self._resources.add_ext_g_state(state))
        self.write_operator("gs")

    def add_comment(self, comment: str) -> None:
        """Emit a ``%`` comment line. Mirrors ``addComment`` (Java line 1428)."""
        if "\r" in comment or "\n" in comment:
            raise ValueError("comment should not include a newline")
        self._output_stream.write(b"% ")
        self._output_stream.write(comment.encode("iso-8859-1"))
        self._output_stream.write(_LF)

    # ------------------------------------------------------------------
    # Colour operators (delegating to subclass-specific behaviour by
    # default — operate on raw numeric components here for parity)
    # ------------------------------------------------------------------

    def set_stroking_color(self, *args: Any) -> None:
        """Emit a stroking-colour operator (``RG``/``K``/``G``/``SC``/``SCN``).
        Mirrors the ``setStrokingColor`` overloads (Java lines 661, 701, 718,
        742, 764)."""
        self._set_color(args, stroking=True)

    def set_non_stroking_color(self, *args: Any) -> None:
        """Emit a non-stroking-colour operator (``rg``/``k``/``g``/``sc``/``scn``).
        Mirrors the ``setNonStrokingColor`` overloads (Java lines 781, 821, 838,
        861, 883)."""
        self._set_color(args, stroking=False)

    def _set_color(self, args: tuple[Any, ...], *, stroking: bool) -> None:
        if len(args) == 1:
            value = args[0]
            if isinstance(value, (int, float)):
                # single float ⇒ gray
                self._check_range_one(float(value))
                self.write_operand(float(value))
                self.write_operator("G" if stroking else "g")
                return
            # PDColor branch (best-effort delegation)
            components = getattr(value, "get_components", None)
            if components is not None:
                for c in components():
                    self.write_operand(c)
                cs = getattr(value, "get_color_space", lambda: None)()
                if cs is not None:
                    self.write_operand(self.get_name(cs))
                self.write_operator("SCN" if stroking else "scn")
                return
            raise TypeError(f"Unsupported colour argument: {type(value).__name__}")
        if len(args) == 3:
            r, g, b = (float(v) for v in args)
            for v in (r, g, b):
                self._check_range_one(v)
            for v in (r, g, b):
                self.write_operand(v)
            self.write_operator("RG" if stroking else "rg")
            return
        if len(args) == 4:
            c, m, y, k = (float(v) for v in args)
            for v in (c, m, y, k):
                self._check_range_one(v)
            for v in (c, m, y, k):
                self.write_operand(v)
            self.write_operator("K" if stroking else "k")
            return
        raise TypeError(
            f"set_{'stroking' if stroking else 'non_stroking'}_color expects "
            f"1/3/4 numeric args; got {len(args)}"
        )

    def _check_range_one(self, value: float) -> None:
        if self.is_outside_one_interval(value):
            raise ValueError(
                f"Parameters must be within 0..1, but is {value:.2f}"
            )

    def is_outside255_interval(self, val: int) -> bool:
        """Mirrors ``isOutside255Interval`` (Java line 1566)."""
        return val < 0 or val > 255

    def is_outside_one_interval(self, val: float) -> bool:
        """Mirrors ``isOutsideOneInterval`` (Java line 1571)."""
        return val < 0.0 or val > 1.0

    def set_stroking_color_space_stack(self, color_space: Any) -> None:
        """Update the stroking colour-space stack.
        Mirrors ``setStrokingColorSpaceStack`` (Java line 1576)."""
        if not self._stroking_color_space_stack:
            self._stroking_color_space_stack.append(color_space)
        else:
            self._stroking_color_space_stack.pop()
            self._stroking_color_space_stack.append(color_space)

    def set_non_stroking_color_space_stack(self, color_space: Any) -> None:
        """Update the non-stroking colour-space stack.
        Mirrors ``setNonStrokingColorSpaceStack`` (Java line 1589)."""
        if not self._non_stroking_color_space_stack:
            self._non_stroking_color_space_stack.append(color_space)
        else:
            self._non_stroking_color_space_stack.pop()
            self._non_stroking_color_space_stack.append(color_space)

    # ------------------------------------------------------------------
    # GSUB / complex-text helpers
    # ------------------------------------------------------------------

    def encode_for_gsub(
        self,
        gsub_worker: Any,
        glyph_ids: set[int],
        font: Any,
        text: str,
    ) -> bytes:
        """Mirrors the private ``encodeForGsub`` (Java line 1689); see
        :func:`encode_for_gsub`."""
        return encode_for_gsub(gsub_worker, glyph_ids, font, text)

    def apply_gsub_rules(
        self,
        gsub_worker: Any,
        out: bytearray,
        font: Any,
        word: str,
    ) -> list[int]:
        """Mirrors the private ``applyGSUBRules`` (Java line 1727); see
        :func:`apply_gsub_rules`."""
        return apply_gsub_rules(gsub_worker, out, font, word)

    # ---------- close ----------

    def close(self) -> None:
        """Close the underlying stream. Mirrors upstream's ``Closeable``
        contract (PDAbstractContentStream implements ``Closeable``)."""
        try:
            self._output_stream.close()
        except Exception:  # pragma: no cover - defensive
            _log.exception("Error closing content stream output")

    def __enter__(self) -> PDAbstractContentStream:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


__all__ = ["PDAbstractContentStream"]
