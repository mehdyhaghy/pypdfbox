from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSName,
    COSStream,
)

from .font.pd_font import PDFont
from .graphics.form.pd_form_x_object import PDFormXObject
from .graphics.image.pd_image_x_object import PDImageXObject
from .graphics.pd_property_list import PDPropertyList
from .graphics.pd_x_object import PDXObject
from .pd_page import PDPage
from .pd_resources import PDResources

if TYPE_CHECKING:
    from .pd_document import PDDocument


_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_X_OBJECT: COSName = COSName.get_pdf_name("XObject")
_PROPERTIES: COSName = COSName.get_pdf_name("Properties")
_COLOR_SPACE: COSName = COSName.get_pdf_name("ColorSpace")
_DEVICE_COLOR_SPACES: frozenset[str] = frozenset(
    {"DeviceGray", "DeviceRGB", "DeviceCMYK"}
)


class AppendMode(Enum):
    """How a page-targeted content stream is attached to existing contents."""

    OVERWRITE = "OVERWRITE"
    APPEND = "APPEND"
    PREPEND = "PREPEND"


class PDPageContentStream:
    """High-level PDF content-stream writer. Mirrors
    ``org.apache.pdfbox.pdmodel.PDPageContentStream`` (the lite surface —
    upstream's class is ~1500 lines; we ship the operators most commonly
    needed for new-content generation).

    Two construction shapes match upstream:

    - ``PDPageContentStream(document, page[, append_mode[, compress]])`` —
      write a fresh content stream to ``page``. ``append_mode`` mirrors
      upstream's ``AppendMode`` values: ``OVERWRITE`` (default), ``APPEND``,
      or ``PREPEND``.
    - ``PDPageContentStream(document, form_xobject)`` — write into the
      form XObject's body stream (replaces any existing body).

    The writer buffers operators into a ``bytearray`` and flushes them
    into the underlying ``COSStream`` on ``close()`` / context-manager
    exit. Numeric operands are formatted with up to 4 decimal places
    (matching upstream ``setMaximumFractionDigits(4)``) with trailing
    zeros trimmed.
    """

    def __init__(
        self,
        document: PDDocument,
        source_page: PDPage | PDFormXObject | None = None,
        append_mode: AppendMode | str | bool | None = None,
        compress: bool = False,
        reset_context: bool = False,
    ) -> None:
        self._document = document
        self._closed: bool = False
        self._buffer: bytearray = bytearray()
        self._compress = bool(compress)
        self._reset_context = bool(reset_context)
        # Whether we've started a text block (BT) — used purely as a
        # convenience for users; we don't enforce strict state machines
        # here (upstream tracks ``inTextMode`` for sanity-check exceptions
        # but the lite surface keeps it advisory).
        self._in_text_mode: bool = False

        # Resolve the destination COSStream + the resource dictionary
        # we'll attach fonts/XObjects/etc. to.
        if isinstance(source_page, PDPage):
            self._target_stream: COSStream = COSStream()
            # Resources: reuse the page's existing /Resources if present;
            # otherwise create a fresh one and attach. Mirrors upstream's
            # ``sourcePage.getResources() != null ? ... : new PDResources()``.
            existing = source_page.get_cos_object().get_dictionary_object(
                COSName.RESOURCES  # type: ignore[attr-defined]
            )
            if existing is not None:
                self._resources = source_page.get_resources()
            else:
                self._resources = PDResources()
                source_page.set_resources(self._resources)
            mode = _coerce_append_mode(append_mode)
            self._attach_to_page(source_page, self._target_stream, mode)
        elif isinstance(source_page, PDFormXObject):
            self._target_stream = source_page.get_cos_object()
            existing_res = source_page.get_resources()
            if existing_res is None:
                self._resources = PDResources()
                source_page.set_resources(self._resources)
            else:
                self._resources = existing_res
        elif source_page is None:
            raise TypeError(
                "PDPageContentStream requires a PDPage or PDFormXObject"
            )
        else:
            raise TypeError(
                f"PDPageContentStream second arg must be PDPage or PDFormXObject; "
                f"got {type(source_page).__name__}"
            )

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _attach_to_page(
        page: PDPage,
        new_stream: COSStream,
        append_mode: AppendMode,
    ) -> None:
        """Attach ``new_stream`` to ``page``'s /Contents.

        - No /Contents yet → set the new stream as /Contents directly.
        - OVERWRITE → replace /Contents with the new stream.
        - APPEND → stream becomes the last content stream.
        - PREPEND → stream becomes the first content stream.
        """
        page_dict = page.get_cos_object()
        existing = page_dict.get_dictionary_object(_CONTENTS)
        if existing is None or append_mode is AppendMode.OVERWRITE:
            page_dict.set_item(_CONTENTS, new_stream)
            return
        if isinstance(existing, COSArray):
            if append_mode is AppendMode.APPEND:
                existing.add(new_stream)
            else:
                existing.add_at(0, new_stream)
            return
        # Single existing stream — promote to array.
        arr = COSArray()
        if append_mode is AppendMode.APPEND:
            arr.add(existing)
            arr.add(new_stream)
        else:
            arr.add(new_stream)
            arr.add(existing)
        page_dict.set_item(_CONTENTS, arr)

    # ------------------------------------------------------------------
    # context manager / lifecycle
    # ------------------------------------------------------------------

    def __enter__(self) -> PDPageContentStream:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Flush the buffered operator bytes into the underlying COSStream."""
        if self._closed:
            return
        self._closed = True
        data = bytes(self._buffer)
        if self._compress:
            with self._target_stream.create_output_stream(
                COSName.FLATE_DECODE  # type: ignore[attr-defined]
            ) as out:
                out.write(data)
        else:
            # Commit the buffered bytes — set_raw_data replaces the body.
            self._target_stream.set_raw_data(data)

    # ------------------------------------------------------------------
    # accessors used by tests + parity with upstream
    # ------------------------------------------------------------------

    def get_resources(self) -> PDResources:
        return self._resources

    def get_target_stream(self) -> COSStream:
        """Return the underlying COSStream the writer flushes into.

        Not present in upstream (which exposes the OutputStream directly
        via the protected base class). Useful for tests.
        """
        return self._target_stream

    # ------------------------------------------------------------------
    # path drawing
    # ------------------------------------------------------------------

    def move_to(self, x: float, y: float) -> None:
        self._write_operands(x, y)
        self._write_operator(b"m")

    def line_to(self, x: float, y: float) -> None:
        self._write_operands(x, y)
        self._write_operator(b"l")

    def curve_to(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        self._write_operands(x1, y1, x2, y2, x3, y3)
        self._write_operator(b"c")

    def curve_to_1(self, x2: float, y2: float, x3: float, y3: float) -> None:
        """Emit ``v`` — Bezier curve from current point with control points
        (current, x2,y2) ending at x3,y3."""
        self._write_operands(x2, y2, x3, y3)
        self._write_operator(b"v")

    def curve_to_2(self, x1: float, y1: float, x3: float, y3: float) -> None:
        """Emit ``y`` — Bezier curve with control points (x1,y1, x3,y3)
        ending at x3,y3."""
        self._write_operands(x1, y1, x3, y3)
        self._write_operator(b"y")

    def close_path(self) -> None:
        self._write_operator(b"h")

    def stroke(self) -> None:
        self._write_operator(b"S")

    def close_and_stroke(self) -> None:
        self._write_operator(b"s")

    def fill(self) -> None:
        self._write_operator(b"f")

    def fill_even_odd(self) -> None:
        """Emit ``f*`` — fill using the even-odd rule."""
        self._write_operator(b"f*")

    def fill_and_stroke(self) -> None:
        self._write_operator(b"B")

    def fill_and_stroke_even_odd(self) -> None:
        """Emit ``B*`` — fill (even-odd) and stroke."""
        self._write_operator(b"B*")

    def close_fill_and_stroke(self) -> None:
        """Emit ``b`` — close, fill (non-zero), and stroke."""
        self._write_operator(b"b")

    def close_fill_and_stroke_even_odd(self) -> None:
        """Emit ``b*`` — close, fill (even-odd), and stroke."""
        self._write_operator(b"b*")

    def clip_path(self) -> None:
        """Emit ``W`` — set the clipping path using the non-zero winding
        rule. Must be followed by a path-painting or ``n`` operator."""
        self._write_operator(b"W")

    def clip_path_even_odd(self) -> None:
        """Emit ``W*`` — set the clipping path using the even-odd rule."""
        self._write_operator(b"W*")

    def clip(self) -> None:
        """Emit ``W n`` — intersect clipping path (non-zero) and end the
        path. Mirrors upstream's ``clip()``, which writes the clip
        operator followed by the no-op path terminator so the path is
        consumed without painting."""
        self._write_operator(b"W")
        self._write_operator(b"n")

    def clip_even_odd(self) -> None:
        """Emit ``W* n`` — intersect clipping path (even-odd) and end the
        path. Mirrors upstream's ``clipEvenOdd()``."""
        self._write_operator(b"W*")
        self._write_operator(b"n")

    def end_path(self) -> None:
        """Emit ``n`` — end the path without filling or stroking. Used
        after a clipping operator (``W``/``W*``) or to discard a path."""
        self._write_operator(b"n")

    # Alias spelling matching upstream's ``fillEvenOddAndStroke`` Java
    # method name (current ``fill_and_stroke_even_odd`` keeps working).
    def fill_even_odd_and_stroke(self) -> None:
        """Alias for :meth:`fill_and_stroke_even_odd` matching upstream's
        ``fillEvenOddAndStroke`` ordering."""
        self.fill_and_stroke_even_odd()

    def close_fill_even_odd_and_stroke(self) -> None:
        """Alias for :meth:`close_fill_and_stroke_even_odd` matching
        upstream's ``closeFillEvenOddAndStroke`` ordering."""
        self.close_fill_and_stroke_even_odd()

    def add_rect(self, x: float, y: float, width: float, height: float) -> None:
        self._write_operands(x, y, width, height)
        self._write_operator(b"re")

    # ------------------------------------------------------------------
    # color
    # ------------------------------------------------------------------

    def set_stroking_color_rgb(self, r: float, g: float, b: float) -> None:
        self._write_operands(r, g, b)
        self._write_operator(b"RG")

    def set_non_stroking_color_rgb(self, r: float, g: float, b: float) -> None:
        self._write_operands(r, g, b)
        self._write_operator(b"rg")

    def set_stroking_color_gray(self, gray: float) -> None:
        self._write_operands(gray)
        self._write_operator(b"G")

    def set_non_stroking_color_gray(self, gray: float) -> None:
        self._write_operands(gray)
        self._write_operator(b"g")

    def set_stroking_color_cmyk(
        self, c: float, m: float, y: float, k: float
    ) -> None:
        self._write_operands(c, m, y, k)
        self._write_operator(b"K")

    def set_non_stroking_color_cmyk(
        self, c: float, m: float, y: float, k: float
    ) -> None:
        self._write_operands(c, m, y, k)
        self._write_operator(b"k")

    # ---- polymorphic set_stroking_color / set_non_stroking_color ----

    def set_stroking_color(self, *args: Any) -> None:
        """Polymorphic stroking-color setter mirroring upstream's
        ``setStrokingColor`` overloads:

        - ``set_stroking_color(gray)`` → ``<g> G``
        - ``set_stroking_color(r, g, b)`` → ``<r> <g> <b> RG``
        - ``set_stroking_color(c, m, y, k)`` → ``<c> <m> <y> <k> K``
        - ``set_stroking_color(PDColor)`` → components followed by ``SCN``
          (or the device equivalent ``G``/``RG``/``K`` when the color
          space is a device color space).

        The PDColor overload writes the pattern name (when present) after
        the numeric components, matching upstream's behaviour for
        Pattern color spaces.
        """
        self._set_color(args, stroking=True)

    def set_non_stroking_color(self, *args: Any) -> None:
        """Polymorphic non-stroking-color setter — see
        :meth:`set_stroking_color` for the overload menu. Emits the
        lowercase variants (``g``, ``rg``, ``k``, ``scn``)."""
        self._set_color(args, stroking=False)

    def _set_color(self, args: tuple[Any, ...], *, stroking: bool) -> None:
        # Single-argument forms: PDColor or scalar gray.
        if len(args) == 1:
            arg = args[0]
            from pypdfbox.pdmodel.graphics.color.pd_color import PDColor

            if isinstance(arg, PDColor):
                self._emit_pd_color(arg, stroking=stroking)
                return
            if isinstance(arg, (int, float)) and not isinstance(arg, bool):
                if stroking:
                    self.set_stroking_color_gray(float(arg))
                else:
                    self.set_non_stroking_color_gray(float(arg))
                return
            raise TypeError(
                "set_(non_)stroking_color expects PDColor or numeric "
                f"components; got {type(arg).__name__}"
            )
        if len(args) == 3:
            r, g, b = (float(v) for v in args)
            if stroking:
                self.set_stroking_color_rgb(r, g, b)
            else:
                self.set_non_stroking_color_rgb(r, g, b)
            return
        if len(args) == 4:
            c, m, y, k = (float(v) for v in args)
            if stroking:
                self.set_stroking_color_cmyk(c, m, y, k)
            else:
                self.set_non_stroking_color_cmyk(c, m, y, k)
            return
        raise TypeError(
            "set_(non_)stroking_color expects 1 (PDColor or gray), 3 (rgb), "
            f"or 4 (cmyk) arguments; got {len(args)}"
        )

    def _emit_pd_color(self, color: Any, *, stroking: bool) -> None:
        cs = color.get_color_space()
        cs_name = cs.get_name() if cs is not None else None
        components = color.get_components()
        pattern_name = color.get_pattern_name()

        # Device color spaces use the dedicated single-byte operators.
        if cs_name == "DeviceGray" and pattern_name is None:
            if stroking:
                self.set_stroking_color_gray(components[0])
            else:
                self.set_non_stroking_color_gray(components[0])
            return
        if cs_name == "DeviceRGB" and pattern_name is None:
            if stroking:
                self.set_stroking_color_rgb(*components[:3])
            else:
                self.set_non_stroking_color_rgb(*components[:3])
            return
        if cs_name == "DeviceCMYK" and pattern_name is None:
            if stroking:
                self.set_stroking_color_cmyk(*components[:4])
            else:
                self.set_non_stroking_color_cmyk(*components[:4])
            return

        # Non-device or pattern: emit components (and optional pattern
        # name) followed by SCN / scn.
        for value in components:
            self._write_operands(float(value))
        if pattern_name is not None:
            self._write_name(pattern_name)
            self._buffer.append(0x20)
        self._write_operator(b"SCN" if stroking else b"scn")

    def set_stroking_color_space(self, color_space: Any) -> None:
        """Emit ``/<key> CS`` — set the stroking color space.

        Device color spaces (DeviceGray/RGB/CMYK) are emitted by their
        well-known names without registering a resource entry; named
        spaces like ICCBased / Indexed / Lab / Pattern are registered
        under ``/Resources/ColorSpace`` (key ``Cs<n>``) if not already
        present, then referenced by that key.
        """
        key = self._resource_key_for_color_space(color_space)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"CS")

    def set_non_stroking_color_space(self, color_space: Any) -> None:
        """Emit ``/<key> cs`` — non-stroking variant of
        :meth:`set_stroking_color_space`."""
        key = self._resource_key_for_color_space(color_space)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"cs")

    # ------------------------------------------------------------------
    # line width / dash
    # ------------------------------------------------------------------

    def set_line_width(self, width: float) -> None:
        self._write_operands(width)
        self._write_operator(b"w")

    def set_line_cap_style(self, cap: int) -> None:
        self._write_operands(int(cap))
        self._write_operator(b"J")

    def set_line_join_style(self, join: int) -> None:
        self._write_operands(int(join))
        self._write_operator(b"j")

    def set_miter_limit(self, miter: float) -> None:
        self._write_operands(miter)
        self._write_operator(b"M")

    def set_dash_pattern(self, dash: list[float], phase: float) -> None:
        """Emit ``[a b c ...] phase d`` — set the dash pattern."""
        self._buffer.append(0x5B)  # [
        first = True
        for v in dash:
            if not first:
                self._buffer.append(0x20)
            self._buffer.extend(_format_number(v))
            first = False
        self._buffer.append(0x5D)  # ]
        self._buffer.append(0x20)
        self._write_operands(phase)
        self._write_operator(b"d")

    def set_rendering_intent(self, intent: str) -> None:
        """Emit ``/<intent> ri`` — set the colour rendering intent."""
        self._write_name(_to_cos_name(intent))
        self._buffer.append(0x20)
        self._write_operator(b"ri")

    def set_flatness(self, flatness: float) -> None:
        """Emit ``<value> i`` — set the flatness tolerance."""
        self._write_operands(flatness)
        self._write_operator(b"i")

    # ------------------------------------------------------------------
    # text
    # ------------------------------------------------------------------

    def begin_text(self) -> None:
        self._write_operator(b"BT")
        self._in_text_mode = True

    def end_text(self) -> None:
        self._write_operator(b"ET")
        self._in_text_mode = False

    def set_font(self, font: PDFont, size: float) -> None:
        """Emit ``/<key> <size> Tf``. Auto-registers ``font`` under the
        page's /Resources /Font dict (key "F0", "F1", ...) if absent."""
        if not isinstance(font, PDFont):
            raise TypeError(
                f"PDPageContentStream.set_font expects PDFont; got "
                f"{type(font).__name__}"
            )
        key = self._resource_key_for_font(font)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operands(size)
        self._write_operator(b"Tf")

    def show_text(self, text: str | bytes) -> None:
        """Emit ``(text) Tj``.

        ``text`` may be ``str`` (encoded via the lite latin-1/UTF-16BE
        fallback — see deferred font.encode below) or already-encoded
        ``bytes`` for callers that ran the bytes through their font's
        encoder. Bytes are emitted as a literal string when ASCII-safe,
        otherwise as hex form.

        Note: the *font*'s encode step is a font-cluster #4+ concern.
        Upstream calls ``font.encode(text)``; the lite surface here
        encodes the Python ``str`` as Latin-1 when possible (which matches
        the WinAnsi standard 14-font mapping for ASCII) and falls back to
        UTF-16BE hex form for non-Latin-1 input.
        """
        self._show_text_internal(text)
        self._buffer.append(0x20)
        self._write_operator(b"Tj")

    def _show_text_internal(self, text: str | bytes) -> None:
        """Encode ``text`` and append the PDF string literal (no operator,
        no trailing space). Mirrors upstream's ``showTextInternal``."""
        if isinstance(text, (bytes, bytearray)):
            data = bytes(text)
            ascii_safe = all(0x20 <= b < 0x80 or b == 0x09 for b in data)
        else:
            try:
                data = text.encode("latin-1")
                ascii_safe = all(0x20 <= b < 0x80 or b == 0x09 for b in data)
            except UnicodeEncodeError:
                data = text.encode("utf-16-be")
                ascii_safe = False
        if ascii_safe:
            self._buffer.append(0x28)  # (
            for b in data:
                if b in (0x28, 0x29, 0x5C):  # ( ) \
                    self._buffer.append(0x5C)
                self._buffer.append(b)
            self._buffer.append(0x29)  # )
        else:
            self._buffer.append(0x3C)  # <
            self._buffer.extend(data.hex().upper().encode("ascii"))
            self._buffer.append(0x3E)  # >

    def new_line_at_offset(self, tx: float, ty: float) -> None:
        self._write_operands(tx, ty)
        self._write_operator(b"Td")

    def move_text_position_by_amount(self, x: float, y: float) -> None:
        """Emit ``x y Td`` — move to start of next line offset by ``(x,y)``
        from start of current line. Legacy upstream alias for
        :meth:`new_line_at_offset` (kept for callers porting from PDFBox
        1.x / 2.x where this was the canonical method)."""
        self.new_line_at_offset(x, y)

    def move_text_position_and_set_leading(self, x: float, y: float) -> None:
        """Emit ``x y TD`` — move to start of next line offset by
        ``(x,y)`` and set the leading parameter to ``-y``. Equivalent to::

            -y TL
            x y Td

        but emitted as a single ``TD`` operator."""
        self._write_operands(x, y)
        self._write_operator(b"TD")

    def new_line(self) -> None:
        self._write_operator(b"T*")

    def move_to_next_line(self) -> None:
        """Emit ``T*`` — move to the start of the next line. Alias for
        :meth:`new_line` matching the upstream Java method name."""
        self.new_line()

    def move_to_next_line_show_text(self, text: str | bytes) -> None:
        """Emit ``(text) '`` — move to next line and show ``text``.
        Equivalent to ``T*`` followed by ``(text) Tj`` but emitted as a
        single ``'`` operator."""
        self._show_text_internal(text)
        self._buffer.append(0x20)
        self._write_operator(b"'")

    def set_spacings_show_text(
        self,
        word_spacing: float,
        char_spacing: float,
        text: str | bytes,
    ) -> None:
        """Emit ``aw ac (text) "`` — set word spacing to ``word_spacing``,
        character spacing to ``char_spacing``, then move to the next line
        and show ``text``. Equivalent to ``aw Tw``, ``ac Tc``, ``T*``,
        ``(text) Tj`` but emitted as a single ``"`` operator."""
        self._write_operands(word_spacing, char_spacing)
        self._show_text_internal(text)
        self._buffer.append(0x20)
        self._write_operator(b'"')

    def show_text_with_positioning(
        self,
        text_with_positioning: list[str | bytes | float | int],
    ) -> None:
        """Emit ``[ ... ] TJ`` — show one or more strings with optional
        numeric horizontal-position adjustments interleaved.

        Each item is either:

        - ``str`` / ``bytes`` — a string to show (encoded the same way
          :meth:`show_text` encodes its argument).
        - ``int`` / ``float`` — a position adjustment expressed in
          thousandths of a unit of text space (PDF 32000-1 §9.4.3).
          Positive values move the text *backwards*, i.e. tighten the
          spacing.

        Mirrors upstream's ``showTextWithPositioning(Object[])``.
        """
        if not isinstance(text_with_positioning, (list, tuple)):
            raise TypeError(
                "show_text_with_positioning expects a list/tuple of str | "
                f"float items; got {type(text_with_positioning).__name__}"
            )
        self._buffer.append(0x5B)  # [
        for item in text_with_positioning:
            if isinstance(item, (str, bytes, bytearray)):
                self._show_text_internal(item)
            elif isinstance(item, bool):
                # bool is a subclass of int — reject explicitly to match
                # upstream's IllegalArgumentException for non-string,
                # non-Float types.
                raise TypeError(
                    "show_text_with_positioning items must be str or "
                    "numeric; got bool"
                )
            elif isinstance(item, (int, float)):
                self._buffer.extend(_format_number(item))
                self._buffer.append(0x20)
            else:
                raise TypeError(
                    "show_text_with_positioning items must be str or "
                    f"numeric; got {type(item).__name__}"
                )
        self._buffer.append(0x5D)  # ]
        self._buffer.append(0x20)
        self._write_operator(b"TJ")

    def set_text_rise(self, rise: float) -> None:
        self._write_operands(rise)
        self._write_operator(b"Ts")

    def set_character_spacing(self, spacing: float) -> None:
        self._write_operands(spacing)
        self._write_operator(b"Tc")

    def set_word_spacing(self, spacing: float) -> None:
        self._write_operands(spacing)
        self._write_operator(b"Tw")

    def set_text_leading(self, leading: float) -> None:
        self._write_operands(leading)
        self._write_operator(b"TL")

    def set_leading(self, leading: float) -> None:
        """Alias for :meth:`set_text_leading` matching upstream's
        ``setLeading`` Java method name."""
        self.set_text_leading(leading)

    def set_text_matrix(
        self,
        a: float,
        b: float = 0.0,
        c: float = 0.0,
        d: float = 1.0,
        e: float = 0.0,
        f: float = 0.0,
    ) -> None:
        """Emit ``a b c d e f Tm`` — set the text matrix and the text
        line matrix.

        Accepts either the six matrix components individually, or a
        single iterable / object exposing ``get_value(row, col)`` (the
        upstream ``Matrix`` shape). The 6-tuple form mirrors
        ``setTextMatrix(Matrix)`` after Matrix has been decomposed.
        """
        if not isinstance(a, (int, float)):
            # Single non-numeric arg: treat as Matrix-like or 6-element seq.
            matrix_arg = a
            components = self._extract_matrix_components(matrix_arg)
            a, b, c, d, e, f = components
        self._write_operands(a, b, c, d, e, f)
        self._write_operator(b"Tm")

    @staticmethod
    def _extract_matrix_components(matrix: Any) -> tuple[float, ...]:
        """Decompose ``matrix`` into the six PDF affine components
        ``(a, b, c, d, e, f)``.

        Accepts:
        - An iterable (list/tuple) of length 6.
        - An object with ``get_value(row, col)`` — the pypdfbox port of
          upstream's ``org.apache.pdfbox.util.Matrix``.
        - An object with ``get_a``..``get_f`` accessor methods.
        """
        if isinstance(matrix, (list, tuple)):
            if len(matrix) != 6:
                raise ValueError(
                    "set_text_matrix iterable form requires 6 components "
                    f"(a, b, c, d, e, f); got {len(matrix)}"
                )
            return tuple(float(v) for v in matrix)
        getters = ("get_a", "get_b", "get_c", "get_d", "get_e", "get_f")
        if all(callable(getattr(matrix, name, None)) for name in getters):
            return tuple(float(getattr(matrix, name)()) for name in getters)
        get_value = getattr(matrix, "get_value", None)
        if callable(get_value):
            return (
                float(get_value(0, 0)),
                float(get_value(0, 1)),
                float(get_value(1, 0)),
                float(get_value(1, 1)),
                float(get_value(2, 0)),
                float(get_value(2, 1)),
            )
        raise TypeError(
            "set_text_matrix expects 6 numeric components, an iterable of "
            "length 6, or a Matrix-like object with get_value(row, col); "
            f"got {type(matrix).__name__}"
        )

    def set_horizontal_scaling(self, scaling: float) -> None:
        self._write_operands(scaling)
        self._write_operator(b"Tz")

    def set_text_rendering_mode(self, mode: int) -> None:
        """Emit ``<mode> Tr`` — set the text rendering mode (0-7)."""
        m = int(mode)
        if not 0 <= m <= 7:
            raise ValueError(
                f"text rendering mode must be in 0..7; got {mode!r}"
            )
        self._write_operands(m)
        self._write_operator(b"Tr")

    # ------------------------------------------------------------------
    # graphics state
    # ------------------------------------------------------------------

    def save_graphics_state(self) -> None:
        self._write_operator(b"q")

    def restore_graphics_state(self) -> None:
        self._write_operator(b"Q")

    def transform(
        self,
        a: float,
        b: float,
        c: float,
        d: float,
        e: float,
        f: float,
    ) -> None:
        self._write_operands(a, b, c, d, e, f)
        self._write_operator(b"cm")

    def concatenate_matrix(
        self,
        a: float,
        b: float,
        c: float,
        d: float,
        e: float,
        f: float,
    ) -> None:
        """Emit ``a b c d e f cm`` — alias for :meth:`transform` matching
        upstream's ``concatenate2CTM`` / ``concatenateMatrix`` naming."""
        self.transform(a, b, c, d, e, f)

    # ------------------------------------------------------------------
    # XObject
    # ------------------------------------------------------------------

    def draw_image(
        self,
        image: PDImageXObject | Any,
        x: float | tuple[float, float, float, float, float, float] | list[float] | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
    ) -> None:
        """Emit ``q <a> <b> <c> <d> <e> <f> cm /<key> Do Q`` — draw
        ``image`` on the current page.

        Mirrors upstream's three ``drawImage`` overloads:

        - ``draw_image(image, x, y)`` — draws at the image's intrinsic
          ``/Width`` × ``/Height`` (1 pt per pixel) anchored at ``(x, y)``.
          Equivalent to ``drawImage(PDImageXObject, float, float)``.
        - ``draw_image(image, x, y, width, height)`` — draws scaled to
          ``width`` × ``height`` anchored at ``(x, y)``. Equivalent to
          ``drawImage(PDImageXObject, float, float, float, float)``.
        - ``draw_image(image, transform_matrix)`` — draws using a full
          custom CTM ``(a, b, c, d, e, f)`` passed as a 6-tuple/list.
          Equivalent to ``drawImage(PDImageXObject, Matrix)``.

        ``image`` accepts a :class:`PDImageXObject` directly, or — for
        callers who haven't preassembled an XObject — a filesystem path
        (``str`` / :class:`pathlib.Path`), a Pillow ``Image.Image``, or
        raw image ``bytes``. In the latter cases we lazy-import
        ``pypdfbox.pdmodel.graphics.image.jpeg_factory.JPEGFactory`` /
        ``lossless_factory.LosslessFactory`` to build the XObject; if
        those modules aren't available a clear :class:`NotImplementedError`
        is raised.

        Raises :class:`RuntimeError` when called inside a text block
        (between ``BT`` / ``ET``) — matches upstream's
        ``IllegalStateException`` guard.
        """
        if self._in_text_mode:
            raise RuntimeError(
                "draw_image is not allowed within a text block (BT/ET)."
            )

        # Resolve the image argument to a PDImageXObject. Accept the
        # native type unchanged; otherwise route through the lazy-imported
        # factory modules.
        if not isinstance(image, PDImageXObject):
            image = self._coerce_to_image_xobject(image, self._document)

        # ``draw_image(image, transform_matrix)`` overload — the second
        # positional argument is a 6-element tuple/list of CTM components.
        if isinstance(x, (tuple, list)) and y is None and width is None and height is None:
            matrix = tuple(x)
            if len(matrix) != 6:
                raise ValueError(
                    "draw_image transform_matrix must have 6 components "
                    f"(a, b, c, d, e, f); got {len(matrix)}"
                )
            a, b_, c, d, e, f = (float(v) for v in matrix)
            key = self._resource_key_for_xobject(image)
            self.save_graphics_state()
            self.transform(a, b_, c, d, e, f)
            self._write_name(key)
            self._buffer.append(0x20)
            self._write_operator(b"Do")
            self.restore_graphics_state()
            return

        if x is None or y is None:
            raise TypeError(
                "draw_image requires either (image, x, y[, width, height]) "
                "or (image, transform_matrix)"
            )

        if width is None:
            width = float(image.get_width())
        if height is None:
            height = float(image.get_height())
        key = self._resource_key_for_xobject(image)
        self.save_graphics_state()
        self.transform(width, 0, 0, height, x, y)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"Do")
        self.restore_graphics_state()

    @staticmethod
    def _coerce_to_image_xobject(
        image: Any, document: PDDocument
    ) -> PDImageXObject:
        """Convert ``image`` (path / Pillow Image / bytes) to a
        :class:`PDImageXObject` via the JPEG/Lossless factories.

        Lazy-imports the factory modules so they remain optional at
        import time. Raises :class:`NotImplementedError` when neither
        factory is importable, with guidance for callers to install the
        factories or pass a pre-built ``PDImageXObject``.

        Routing:

        - JPEG bytes / ``.jpg`` / ``.jpeg`` paths → ``JPEGFactory.create_from_byte_array``.
        - Other paths / Pillow images / generic bytes → ``LosslessFactory.create_from_image``
          (Pillow handles PNG/GIF/BMP/etc. decoding).
        """
        # Probe-import the factories on each call; cheap (sys.modules
        # caches after the first hit) and keeps the public API surface
        # working when the factories are absent at module import.
        try:
            from pypdfbox.pdmodel.graphics.image.jpeg_factory import (  # type: ignore[import-not-found]
                JPEGFactory,
            )
        except ImportError:
            JPEGFactory = None  # type: ignore[assignment]
        try:
            from pypdfbox.pdmodel.graphics.image.lossless_factory import (  # type: ignore[import-not-found]
                LosslessFactory,
            )
        except ImportError:
            LosslessFactory = None  # type: ignore[assignment]

        # Even if the modules import, the symbols themselves may be
        # missing (test stubs, partial installs). Treat that as the
        # same "not available" condition.
        jpeg = getattr(JPEGFactory, "create_from_byte_array", None) if JPEGFactory else None
        lossless = getattr(LosslessFactory, "create_from_image", None) if LosslessFactory else None

        if jpeg is None and lossless is None:
            raise NotImplementedError(
                "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
            )

        from pathlib import Path as _Path
        try:
            from PIL.Image import Image as _PILImage  # type: ignore[import-not-found]
            from PIL import Image as _PILImageMod  # type: ignore[import-not-found]
        except ImportError:
            _PILImage = None  # type: ignore[assignment]
            _PILImageMod = None  # type: ignore[assignment]

        # Path / str → dispatch on suffix; JPEG → JPEGFactory, anything
        # else → LosslessFactory. Mirrors upstream's
        # ``PDImageXObject.createFromFileByExtension``.
        if isinstance(image, (str, _Path)):
            path = _Path(image)
            ext = path.suffix.lower().lstrip(".")
            if ext in ("jpg", "jpeg"):
                if jpeg is None:
                    raise NotImplementedError(
                        "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                    )
                return jpeg(document, path.read_bytes())
            if lossless is None or _PILImageMod is None:
                raise NotImplementedError(
                    "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                )
            with _PILImageMod.open(path) as src:
                src.load()
                return lossless(document, src)

        # bytes → sniff JPEG SOI marker; otherwise hand off to Pillow
        # then the lossless factory.
        if isinstance(image, (bytes, bytearray)):
            data = bytes(image)
            if data[:2] == b"\xff\xd8":
                if jpeg is None:
                    raise NotImplementedError(
                        "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                    )
                return jpeg(document, data)
            if lossless is None or _PILImageMod is None:
                raise NotImplementedError(
                    "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                )
            import io as _io
            with _PILImageMod.open(_io.BytesIO(data)) as src:
                src.load()
                return lossless(document, src)

        # Pillow Image → always decode via the lossless factory.
        if _PILImage is not None and isinstance(image, _PILImage):
            if lossless is None:
                raise NotImplementedError(
                    "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                )
            return lossless(document, image)

        raise TypeError(
            "PDPageContentStream.draw_image expects PDImageXObject, str, "
            f"Path, bytes, or PIL.Image.Image; got {type(image).__name__}"
        )

    def draw_form(
        self,
        form_xobject: PDFormXObject,
        x: float = 0.0,
        y: float = 0.0,
    ) -> None:
        """Emit ``q 1 0 0 1 <x> <y> cm /<key> Do Q``."""
        if not isinstance(form_xobject, PDFormXObject):
            raise TypeError(
                f"PDPageContentStream.draw_form expects PDFormXObject; got "
                f"{type(form_xobject).__name__}"
            )
        key = self._resource_key_for_xobject(form_xobject)
        self.save_graphics_state()
        if x != 0.0 or y != 0.0:
            self.transform(1, 0, 0, 1, x, y)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"Do")
        self.restore_graphics_state()

    # ------------------------------------------------------------------
    # marked content (tagged-PDF authoring)
    # ------------------------------------------------------------------

    def begin_marked_content(self, tag: COSName | str) -> None:
        """Emit ``/<tag> BMC``."""
        self._write_name(_to_cos_name(tag))
        self._buffer.append(0x20)
        self._write_operator(b"BMC")

    def begin_marked_content_with_dict(
        self,
        tag: COSName | str,
        property_list: PDPropertyList | COSName | str,
    ) -> None:
        """Emit ``/<tag> /<key> BDC``.

        ``property_list`` may be a typed :class:`PDPropertyList`, a raw
        :class:`COSName` (the key already registered under
        ``/Resources/Properties``), or a ``str`` used directly as the
        property-list key. Typed property lists are auto-registered and a
        ``MC<n>`` slot is allocated when needed.
        """
        if isinstance(property_list, PDPropertyList):
            key = self._resource_key_for_property_list(property_list)
        else:
            key = _to_cos_name(property_list)
        self._write_name(_to_cos_name(tag))
        self._buffer.append(0x20)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"BDC")

    def end_marked_content(self) -> None:
        """Emit ``EMC``."""
        self._write_operator(b"EMC")

    def add_marked_content_point(self, tag: COSName | str) -> None:
        """Emit ``/<tag> MP`` — single marked-content point."""
        self._write_name(_to_cos_name(tag))
        self._buffer.append(0x20)
        self._write_operator(b"MP")

    def add_marked_content_point_with_dict(
        self,
        tag: COSName | str,
        property_list: PDPropertyList | COSName | str,
    ) -> None:
        """Emit ``/<tag> /<key> DP`` — marked-content point with properties."""
        if isinstance(property_list, PDPropertyList):
            key = self._resource_key_for_property_list(property_list)
        else:
            key = _to_cos_name(property_list)
        self._write_name(_to_cos_name(tag))
        self._buffer.append(0x20)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"DP")

    # ------------------------------------------------------------------
    # resource key allocation
    # ------------------------------------------------------------------

    def _resource_key_for_font(self, font: PDFont) -> COSName:
        """Return the /Resources/Font key for ``font``, allocating a new
        ``F<n>`` slot if necessary."""
        font_cos = font.get_cos_object()
        sub = self._resources.get_cos_object().get_dictionary_object(_FONT)
        if sub is not None:
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is font_cos:
                    return key
        return self._resources.add(_FONT, font_cos)

    def _resource_key_for_xobject(self, xobject: PDXObject) -> COSName:
        x_cos = xobject.get_cos_object()
        sub = self._resources.get_cos_object().get_dictionary_object(_X_OBJECT)
        if sub is not None:
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is x_cos:
                    return key
        return self._resources.add_x_object(xobject)

    def _resource_key_for_color_space(self, color_space: Any) -> COSName:
        """Return the ``COSName`` to reference ``color_space`` in a
        ``CS``/``cs`` operator.

        Device color spaces are referenced by their well-known names
        (``DeviceGray``/``DeviceRGB``/``DeviceCMYK``) without a resource
        entry; named/array color spaces are registered under
        ``/Resources/ColorSpace`` (key ``Cs<n>``) when not already
        present. Mirrors upstream's ``getName(PDColorSpace)`` helper
        inside ``PDPageContentStream``.
        """
        cs_name = (
            color_space.get_name() if hasattr(color_space, "get_name") else None
        )
        if cs_name in _DEVICE_COLOR_SPACES:
            return COSName.get_pdf_name(cs_name)
        # Pattern color space without an underlying CS — emit /Pattern
        # directly (no resource entry needed for the colored form).
        cos = (
            color_space.get_cos_object()
            if hasattr(color_space, "get_cos_object")
            else None
        )
        if cs_name == "Pattern" and cos is None:
            return COSName.get_pdf_name("Pattern")
        if cos is None:
            raise TypeError(
                f"set_(non_)stroking_color_space: color space {cs_name!r} "
                "has no COS representation to register"
            )
        sub = self._resources.get_cos_object().get_dictionary_object(
            _COLOR_SPACE
        )
        if sub is not None:
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is cos:
                    return key
        return self._resources.add(_COLOR_SPACE, cos)

    def _resource_key_for_property_list(
        self, property_list: PDPropertyList
    ) -> COSName:
        """Return the /Resources/Properties key for ``property_list``,
        allocating a new ``MC<n>`` slot when necessary."""
        prop_cos = property_list.get_cos_object()
        res_dict = self._resources.get_cos_object()
        sub = res_dict.get_dictionary_object(_PROPERTIES)
        if sub is not None:
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is prop_cos:
                    return key
        return self._resources.add(_PROPERTIES, prop_cos)

    # ------------------------------------------------------------------
    # low-level emit helpers
    # ------------------------------------------------------------------

    def _write_operator(self, op: bytes) -> None:
        self._buffer.extend(op)
        self._buffer.append(0x0A)

    def _write_operands(self, *values: float) -> None:
        for v in values:
            self._buffer.extend(_format_number(v))
            self._buffer.append(0x20)

    def _write_name(self, name: COSName) -> None:
        self._buffer.append(0x2F)  # /
        # COSName names are ASCII-safe in practice for resource keys —
        # avoid the full ``#xx``-escape pass that the cos writer does.
        self._buffer.extend(name.get_name().encode("ascii"))


def _to_cos_name(name: COSName | str) -> COSName:
    if isinstance(name, COSName):
        return name
    return COSName.get_pdf_name(name)


def _format_number(value: float) -> bytes:
    """Format a numeric operand using up to 4 decimal places with trailing
    zeros stripped. Matches upstream's
    ``formatDecimal.setMaximumFractionDigits(4)``."""
    # Integers stay integer-formatted (no trailing ".0") to match upstream
    # ``NumberFormat`` behaviour on whole numbers.
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value).encode("ascii")
    f = float(value)
    if f.is_integer():
        return str(int(f)).encode("ascii")
    text = format(f, ".4f").rstrip("0").rstrip(".")
    if not text or text == "-":
        text = "0"
    return text.encode("ascii")


def _coerce_append_mode(mode: AppendMode | str | bool | None) -> AppendMode:
    if mode is None:
        return AppendMode.OVERWRITE
    if isinstance(mode, AppendMode):
        return mode
    if isinstance(mode, bool):
        return AppendMode.APPEND if mode else AppendMode.OVERWRITE
    if isinstance(mode, str):
        key = mode.upper()
        try:
            return AppendMode[key]
        except KeyError as exc:
            raise ValueError(f"unknown AppendMode: {mode!r}") from exc
    raise TypeError(
        "append_mode must be AppendMode, str, bool, or None; "
        f"got {type(mode).__name__}"
    )


PDPageContentStream.AppendMode = AppendMode  # type: ignore[attr-defined]


__all__ = ["AppendMode", "PDPageContentStream"]
