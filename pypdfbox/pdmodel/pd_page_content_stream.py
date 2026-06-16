from __future__ import annotations

import importlib
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
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
_EXT_G_STATE: COSName = COSName.get_pdf_name("ExtGState")
_PATTERN: COSName = COSName.get_pdf_name("Pattern")
_SHADING: COSName = COSName.get_pdf_name("Shading")
_DEVICE_COLOR_SPACES: frozenset[str] = frozenset(
    {"DeviceGray", "DeviceRGB", "DeviceCMYK"}
)


class AppendMode(Enum):
    """How a page-targeted content stream is attached to existing contents."""

    OVERWRITE = "OVERWRITE"
    APPEND = "APPEND"
    PREPEND = "PREPEND"

    def is_overwrite(self) -> bool:
        """``True`` if this mode is :attr:`OVERWRITE`. Mirrors upstream's
        ``AppendMode.isOverwrite()``."""
        return self is AppendMode.OVERWRITE

    def is_prepend(self) -> bool:
        """``True`` if this mode is :attr:`PREPEND`. Mirrors upstream's
        ``AppendMode.isPrepend()``."""
        return self is AppendMode.PREPEND


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
    exit. Numeric operands are formatted with up to 5 decimal places
    (matching upstream ``setMaximumFractionDigits(5)``) with trailing
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
        # Maximum fractional digits for numeric operands. Upstream's
        # ``PDPageContentStream`` constructor calls
        # ``setMaximumFractionDigits(5)`` (Java) while the shared
        # ``PDAbstractContentStream`` base — used by the appearance / form /
        # pattern writers — leaves it at 4. Subclasses (notably
        # :class:`PDAppearanceContentStream`) override this to match their
        # upstream parent's digit count.
        self._max_fraction_digits: int = _MAX_FRACTION_DIGITS
        # Whether we've started a text block (BT) — used purely as a
        # convenience for users; we don't enforce strict state machines
        # here (upstream tracks ``inTextMode`` for sanity-check exceptions
        # but the lite surface keeps it advisory).
        self._in_text_mode: bool = False

        # Resolve the destination COSStream + the resource dictionary
        # we'll attach fonts/XObjects/etc. to.
        if isinstance(source_page, PDPage):
            self._target_stream: COSStream = COSStream()
            # Resources: reuse the resolved /Resources if present, including
            # inherited page-tree resources. Creating a direct page resources
            # dictionary when a parent already supplies one would shadow that
            # parent and can break existing content streams.
            existing = source_page.get_inherited_cos_object(
                COSName.RESOURCES  # type: ignore[attr-defined]
            )
            if isinstance(existing, COSDictionary):
                self._resources = PDResources(existing)
            else:
                self._resources = PDResources()
                source_page.set_resources(self._resources)
            mode = _coerce_append_mode(append_mode)
            needs_context_restore = self._attach_to_page(
                source_page,
                self._target_stream,
                mode,
                self._reset_context,
            )
            if needs_context_restore:
                self.restore_graphics_state()
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
        reset_context: bool = False,
    ) -> bool:
        """Attach ``new_stream`` to ``page``'s /Contents.

        - No /Contents yet → set the new stream as /Contents directly.
        - OVERWRITE → replace /Contents with the new stream.
        - APPEND → stream becomes the last content stream.
        - PREPEND → stream becomes the first content stream.

        When ``reset_context`` is true while preserving existing content,
        mirror upstream PDFBox's constructor behavior: prefix the existing
        content with ``q`` and start the new stream with ``Q`` so graphics
        state changes from previous streams do not leak into appended
        operators.
        """
        page_dict = page.get_cos_object()
        existing = page_dict.get_dictionary_object(_CONTENTS)
        if existing is None or append_mode is AppendMode.OVERWRITE:
            page_dict.set_item(_CONTENTS, new_stream)
            return False
        if isinstance(existing, COSArray):
            arr = existing
            if append_mode is AppendMode.APPEND:
                arr.add(new_stream)
            else:
                arr.add_at(0, new_stream)
        else:
            # Single existing stream — promote to array.
            arr = COSArray()
            if append_mode is AppendMode.APPEND:
                arr.add(existing)
                arr.add(new_stream)
            else:
                arr.add(new_stream)
                arr.add(existing)
        if reset_context:
            prefix = COSStream()
            prefix.set_raw_data(b"q\n")
            arr.add_at(0, prefix)
        page_dict.set_item(_CONTENTS, arr)
        return reset_context

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

    def _require_outside_text_block(self, op: str) -> None:
        """Reject ``op`` if currently inside a ``BT``/``ET`` block.

        Mirrors upstream's ``IllegalStateException`` guard ("Error: <op> is
        not allowed within a text block.") used by every path-construction,
        path-painting, clipping, transform, save/restore, and shading
        operator on :class:`PDAbstractContentStream`.
        """
        if self._in_text_mode:
            raise RuntimeError(
                f"Error: {op} is not allowed within a text block (BT/ET)."
            )

    def _require_inside_text_block(self, op: str) -> None:
        """Reject ``op`` if not currently inside a ``BT``/``ET`` block.

        Mirrors upstream's ``IllegalStateException`` guard ("Error: must
        call beginText() before <op>") used by ``newLine``,
        ``newLineAtOffset``, and ``setTextMatrix`` on
        :class:`PDAbstractContentStream`.
        """
        if not self._in_text_mode:
            raise RuntimeError(
                f"Error: must call begin_text() before {op}."
            )

    def move_to(self, x: float, y: float) -> None:
        self._require_outside_text_block("move_to")
        self._write_operands(x, y)
        self._write_operator(b"m")

    def line_to(self, x: float, y: float) -> None:
        self._require_outside_text_block("line_to")
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
        self._require_outside_text_block("curve_to")
        self._write_operands(x1, y1, x2, y2, x3, y3)
        self._write_operator(b"c")

    def curve_to_1(self, x2: float, y2: float, x3: float, y3: float) -> None:
        """Emit ``v`` — Bezier curve from current point with control points
        (current, x2,y2) ending at x3,y3."""
        self._require_outside_text_block("curve_to_1")
        self._write_operands(x2, y2, x3, y3)
        self._write_operator(b"v")

    def curve_to_2(self, x1: float, y1: float, x3: float, y3: float) -> None:
        """Emit ``y`` — Bezier curve with control points (x1,y1, x3,y3)
        ending at x3,y3."""
        self._require_outside_text_block("curve_to_2")
        self._write_operands(x1, y1, x3, y3)
        self._write_operator(b"y")

    def curve_to2(self, x2: float, y2: float, x3: float, y3: float) -> None:
        """Alias for :meth:`curve_to_1` matching upstream's ``curveTo2``
        Java method name (emits the ``v`` operator — current point is the
        first Bezier control point)."""
        self.curve_to_1(x2, y2, x3, y3)

    def curve_to1(self, x1: float, y1: float, x3: float, y3: float) -> None:
        """Alias for :meth:`curve_to_2` matching upstream's ``curveTo1``
        Java method name (emits the ``y`` operator — final point is the
        second Bezier control point)."""
        self.curve_to_2(x1, y1, x3, y3)

    def close_path(self) -> None:
        self._require_outside_text_block("close_path")
        self._write_operator(b"h")

    def stroke(self) -> None:
        self._require_outside_text_block("stroke")
        self._write_operator(b"S")

    def close_and_stroke(self) -> None:
        self._require_outside_text_block("close_and_stroke")
        self._write_operator(b"s")

    def fill(self) -> None:
        self._require_outside_text_block("fill")
        self._write_operator(b"f")

    def fill_even_odd(self) -> None:
        """Emit ``f*`` — fill using the even-odd rule."""
        self._require_outside_text_block("fill_even_odd")
        self._write_operator(b"f*")

    def fill_and_stroke(self) -> None:
        self._require_outside_text_block("fill_and_stroke")
        self._write_operator(b"B")

    def fill_and_stroke_even_odd(self) -> None:
        """Emit ``B*`` — fill (even-odd) and stroke."""
        self._require_outside_text_block("fill_and_stroke_even_odd")
        self._write_operator(b"B*")

    def close_fill_and_stroke(self) -> None:
        """Emit ``b`` — close, fill (non-zero), and stroke."""
        self._require_outside_text_block("close_fill_and_stroke")
        self._write_operator(b"b")

    def close_fill_and_stroke_even_odd(self) -> None:
        """Emit ``b*`` — close, fill (even-odd), and stroke."""
        self._require_outside_text_block("close_fill_and_stroke_even_odd")
        self._write_operator(b"b*")

    def clip_path(self) -> None:
        """Emit ``W`` — set the clipping path using the non-zero winding
        rule. Must be followed by a path-painting or ``n`` operator."""
        self._require_outside_text_block("clip_path")
        self._write_operator(b"W")

    def clip_path_even_odd(self) -> None:
        """Emit ``W*`` — set the clipping path using the even-odd rule."""
        self._require_outside_text_block("clip_path_even_odd")
        self._write_operator(b"W*")

    def clip(self) -> None:
        """Emit ``W n`` — intersect clipping path (non-zero) and end the
        path. Mirrors upstream's ``clip()``, which writes the clip
        operator followed by the no-op path terminator so the path is
        consumed without painting."""
        self._require_outside_text_block("clip")
        self._write_operator(b"W")
        self._write_operator(b"n")

    def clip_even_odd(self) -> None:
        """Emit ``W* n`` — intersect clipping path (even-odd) and end the
        path. Mirrors upstream's ``clipEvenOdd()``."""
        self._require_outside_text_block("clip_even_odd")
        self._write_operator(b"W*")
        self._write_operator(b"n")

    def clip_non_zero_rule(self) -> None:
        """Alias for :meth:`clip` — PDFBox legacy spelling (the
        ``clipPath(int rule)`` overload accepted ``PathIterator.WIND_NON_ZERO``).
        Use this when porting code that disambiguated by rule name."""
        self.clip()

    def clip_even_odd_rule(self) -> None:
        """Alias for :meth:`clip_even_odd` — PDFBox legacy spelling (the
        ``clipPath(int rule)`` overload accepted ``PathIterator.WIND_EVEN_ODD``).
        Use this when porting code that disambiguated by rule name."""
        self.clip_even_odd()

    def end_path(self) -> None:
        """Emit ``n`` — end the path without filling or stroking. Used
        after a clipping operator (``W``/``W*``) or to discard a path."""
        self._require_outside_text_block("end_path")
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

    def close_and_fill_and_stroke(self) -> None:
        """Alias for :meth:`close_fill_and_stroke` matching upstream's
        ``closeAndFillAndStroke`` Java method name."""
        self.close_fill_and_stroke()

    def close_and_fill_and_stroke_even_odd(self) -> None:
        """Alias for :meth:`close_fill_and_stroke_even_odd` matching
        upstream's ``closeAndFillAndStrokeEvenOdd`` Java method name."""
        self.close_fill_and_stroke_even_odd()

    def add_rect(self, x: float, y: float, width: float, height: float) -> None:
        self._require_outside_text_block("add_rect")
        self._write_operands(x, y, width, height)
        self._write_operator(b"re")

    # ------------------------------------------------------------------
    # color
    # ------------------------------------------------------------------

    def set_stroking_color_rgb(self, r: float, g: float, b: float) -> None:
        """Emit ``r g b RG`` — set the DeviceRGB stroking color.

        ``r``/``g``/``b`` must be in ``0..1``; out-of-range values raise
        :class:`ValueError`, matching upstream's
        ``IllegalArgumentException`` from ``setStrokingColor(float, float,
        float)``.
        """
        if (
            _is_outside_one_interval(r)
            or _is_outside_one_interval(g)
            or _is_outside_one_interval(b)
        ):
            raise ValueError(
                "Parameters must be within 0..1, but are "
                f"({r:.2f},{g:.2f},{b:.2f})"
            )
        self._write_operands(r, g, b)
        self._write_operator(b"RG")

    def set_non_stroking_color_rgb(self, r: float, g: float, b: float) -> None:
        """Emit ``r g b rg`` — set the DeviceRGB non-stroking color.

        ``r``/``g``/``b`` must be in ``0..1``; out-of-range values raise
        :class:`ValueError`, matching upstream's
        ``IllegalArgumentException``.
        """
        if (
            _is_outside_one_interval(r)
            or _is_outside_one_interval(g)
            or _is_outside_one_interval(b)
        ):
            raise ValueError(
                "Parameters must be within 0..1, but are "
                f"({r:.2f},{g:.2f},{b:.2f})"
            )
        self._write_operands(r, g, b)
        self._write_operator(b"rg")

    def set_stroking_color_gray(self, gray: float) -> None:
        """Emit ``gray G`` — set the DeviceGray stroking color.

        ``gray`` must be in ``0..1``; out-of-range values raise
        :class:`ValueError`, matching upstream's
        ``IllegalArgumentException``.
        """
        if _is_outside_one_interval(gray):
            raise ValueError(
                f"Parameter must be within 0..1, but is {gray}"
            )
        self._write_operands(gray)
        self._write_operator(b"G")

    def set_non_stroking_color_gray(self, gray: float) -> None:
        """Emit ``gray g`` — set the DeviceGray non-stroking color.

        ``gray`` must be in ``0..1``; out-of-range values raise
        :class:`ValueError`.
        """
        if _is_outside_one_interval(gray):
            raise ValueError(
                f"Parameter must be within 0..1, but is {gray}"
            )
        self._write_operands(gray)
        self._write_operator(b"g")

    def set_stroking_color_cmyk(
        self, c: float, m: float, y: float, k: float
    ) -> None:
        """Emit ``c m y k K`` — set the DeviceCMYK stroking color.

        Each component must be in ``0..1``; out-of-range values raise
        :class:`ValueError`, matching upstream's
        ``IllegalArgumentException``.
        """
        if (
            _is_outside_one_interval(c)
            or _is_outside_one_interval(m)
            or _is_outside_one_interval(y)
            or _is_outside_one_interval(k)
        ):
            raise ValueError(
                "Parameters must be within 0..1, but are "
                f"({c:.2f},{m:.2f},{y:.2f},{k:.2f})"
            )
        self._write_operands(c, m, y, k)
        self._write_operator(b"K")

    def set_non_stroking_color_cmyk(
        self, c: float, m: float, y: float, k: float
    ) -> None:
        """Emit ``c m y k k`` — set the DeviceCMYK non-stroking color.

        Each component must be in ``0..1``; out-of-range values raise
        :class:`ValueError`.
        """
        if (
            _is_outside_one_interval(c)
            or _is_outside_one_interval(m)
            or _is_outside_one_interval(y)
            or _is_outside_one_interval(k)
        ):
            raise ValueError(
                "Parameters must be within 0..1, but are "
                f"({c:.2f},{m:.2f},{y:.2f},{k:.2f})"
            )
        self._write_operands(c, m, y, k)
        self._write_operator(b"k")

    def set_stroking_color_rgb_int(self, r: int, g: int, b: int) -> None:
        """Emit ``r g b RG`` — set the DeviceRGB stroking color from
        8-bit integer components.

        Each of ``r``, ``g``, ``b`` must be in ``0..255``; out-of-range
        values raise :class:`ValueError`. Mirrors upstream's
        ``setStrokingColor(java.awt.Color)``, which extracts the AWT
        color's 0..255 RGB triple, normalizes by 255, and forwards to
        the float-form ``setStrokingColor(r, g, b)``.
        """
        ri, gi, bi = int(r), int(g), int(b)
        if (
            _is_outside_255_interval(ri)
            or _is_outside_255_interval(gi)
            or _is_outside_255_interval(bi)
        ):
            raise ValueError(
                "Parameters must be within 0..255, but are "
                f"({r},{g},{b})"
            )
        self.set_stroking_color_rgb(ri / 255.0, gi / 255.0, bi / 255.0)

    def set_non_stroking_color_rgb_int(
        self, r: int, g: int, b: int
    ) -> None:
        """Emit ``r g b rg`` — non-stroking variant of
        :meth:`set_stroking_color_rgb_int`. Components are 8-bit integers
        in ``0..255``.

        Mirrors upstream's ``setNonStrokingColor(java.awt.Color)``.
        """
        ri, gi, bi = int(r), int(g), int(b)
        if (
            _is_outside_255_interval(ri)
            or _is_outside_255_interval(gi)
            or _is_outside_255_interval(bi)
        ):
            raise ValueError(
                "Parameters must be within 0..255, but are "
                f"({r},{g},{b})"
            )
        self.set_non_stroking_color_rgb(ri / 255.0, gi / 255.0, bi / 255.0)

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
        # Mirrors upstream ``PDAbstractContentStream.setStrokingColor(PDColor)``
        # / ``setNonStrokingColor(PDColor)`` (Java lines 661 / 781). Upstream
        # never takes the device-shorthand path (``RG``/``G``/``K``) for a
        # PDColor: it always writes the color-space name + ``CS``/``cs`` (when
        # the color-space stack top differs), then the components, then
        # ``SCN``/``scn`` for Pattern / Separation / DeviceN / ICCBased and
        # ``SC``/``sc`` for everything else (including the device spaces).
        cs = color.get_color_space()
        components = color.get_components()
        pattern_name = color.get_pattern_name()

        # Color-space stack: upstream ``PDAbstractContentStream`` tracks one
        # per stroking/non-stroking channel so a repeat ``setStrokingColor``
        # of the same space skips the ``CS`` operator. This lite
        # ``PDPageContentStream`` has no such parent state, so track it
        # locally (lazily initialised) to reproduce the byte-for-byte output.
        attr = (
            "_pd_color_cs_stroking" if stroking else "_pd_color_cs_non_stroking"
        )
        current_cs = getattr(self, attr, None)
        if current_cs is not cs:
            self._write_name(self._resource_key_for_color_space(cs))
            self._buffer.append(0x20)
            self._write_operator(b"CS" if stroking else b"cs")
            setattr(self, attr, cs)

        for value in components:
            self._write_operands(float(value))
        if self._is_scn_color_space(cs):
            if pattern_name is not None:
                self._write_name(pattern_name)
                self._buffer.append(0x20)
            self._write_operator(b"SCN" if stroking else b"scn")
        else:
            self._write_operator(b"SC" if stroking else b"sc")

    @staticmethod
    def _is_scn_color_space(color_space: Any) -> bool:
        """Mirrors the ``instanceof PDPattern | PDSeparation | PDDeviceN |
        PDICCBased`` check that selects ``SCN``/``scn`` over ``SC``/``sc`` in
        upstream ``setStrokingColor``/``setNonStrokingColor`` (Java lines
        685 / 805)."""
        from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
        from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
        from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern
        from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation

        return isinstance(
            color_space, (PDPattern, PDSeparation, PDDeviceN, PDICCBased)
        )

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
        """Emit ``<cap> J`` — set the line cap style.

        ``cap`` must be 0 (butt), 1 (round), or 2 (projecting square),
        matching PDF 32000-1 §8.4.3.3. Values outside that range raise
        :class:`ValueError`, mirroring upstream's
        ``IllegalArgumentException`` from ``setLineCapStyle``.
        """
        c = int(cap)
        if not 0 <= c <= 2:
            raise ValueError(
                f"unknown value for line cap style: {cap!r} (expected 0..2)"
            )
        self._write_operands(c)
        self._write_operator(b"J")

    def set_line_join_style(self, join: int) -> None:
        """Emit ``<join> j`` — set the line join style.

        ``join`` must be 0 (miter), 1 (round), or 2 (bevel), matching PDF
        32000-1 §8.4.3.4. Values outside that range raise
        :class:`ValueError`, mirroring upstream's
        ``IllegalArgumentException`` from ``setLineJoinStyle``.
        """
        j = int(join)
        if not 0 <= j <= 2:
            raise ValueError(
                f"unknown value for line join style: {join!r} (expected 0..2)"
            )
        self._write_operands(j)
        self._write_operator(b"j")

    def set_miter_limit(self, miter: float) -> None:
        """Emit ``<miter> M`` — set the miter limit.

        ``miter`` must be strictly positive — Acrobat Reader will not
        render content with a non-positive miter limit. Values ``<= 0``
        raise :class:`ValueError`, mirroring upstream's
        ``IllegalArgumentException`` from ``setMiterLimit``.
        """
        m = float(miter)
        if m <= 0.0:
            raise ValueError(
                f"miter limit <= 0 is invalid and will not render in "
                f"Acrobat Reader; got {miter!r}"
            )
        self._write_operands(m)
        self._write_operator(b"M")

    def set_dash_pattern(self, dash: list[float], phase: float) -> None:
        """Emit ``[a b c ... ] phase d`` — set the dash pattern.

        Each array element is written as a numeric operand *followed by a
        space* (upstream's ``setLineDashPattern`` calls ``writeOperand`` per
        element, and ``writeOperand`` always appends a space), so a
        two-element pattern serialises as ``[3 2 ]`` — note the trailing
        space inside the bracket. An empty pattern serialises as ``[]``.
        """
        self._buffer.append(0x5B)  # [
        for v in dash:
            self._buffer.extend(_format_number(v, self._max_fraction_digits))
            self._buffer.append(0x20)
        self._buffer.append(0x5D)  # ]
        self._buffer.append(0x20)
        self._write_operands(phase)
        self._write_operator(b"d")

    def set_line_dash_pattern(
        self, pattern: list[float], phase: float
    ) -> None:
        """Alias for :meth:`set_dash_pattern` matching upstream's
        ``setLineDashPattern`` Java method name."""
        self.set_dash_pattern(pattern, phase)

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
        """Emit ``BT`` — begin a text object.

        Raises :class:`RuntimeError` when already inside a text block,
        mirroring upstream's ``IllegalStateException`` ("Error: Nested
        beginText() calls are not allowed.") from
        ``PDAbstractContentStream.beginText``.
        """
        if self._in_text_mode:
            raise RuntimeError(
                "Nested begin_text() calls are not allowed."
            )
        self._write_operator(b"BT")
        self._in_text_mode = True

    def end_text(self) -> None:
        """Emit ``ET`` — end the current text object.

        Raises :class:`RuntimeError` when not currently inside a text
        block, mirroring upstream's ``IllegalStateException`` ("Error: You
        must call beginText() before calling endText.") from
        ``PDAbstractContentStream.endText``.
        """
        if not self._in_text_mode:
            raise RuntimeError(
                "end_text() requires a matching begin_text() call first."
            )
        self._write_operator(b"ET")
        self._in_text_mode = False

    def is_in_text_mode(self) -> bool:
        """Return whether the writer is currently inside a text block
        (between ``BT`` and ``ET``).

        Exposes the upstream protected ``inTextMode`` field as a public
        predicate so callers and tests can branch on text-mode state
        without poking at the private attribute.
        """
        return self._in_text_mode

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
        self._require_inside_text_block("new_line_at_offset")
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
        self._require_inside_text_block("move_text_position_and_set_leading")
        self._write_operands(x, y)
        self._write_operator(b"TD")

    def new_line(self) -> None:
        self._require_inside_text_block("new_line")
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
                self._buffer.extend(
                    _format_number(item, self._max_fraction_digits)
                )
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

        Raises :class:`RuntimeError` when called outside a text block,
        mirroring upstream's ``IllegalStateException`` ("Error: must call
        beginText() before setTextMatrix") from
        ``PDAbstractContentStream.setTextMatrix``.
        """
        self._require_inside_text_block("set_text_matrix")
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

    def set_text_rendering_mode(self, mode: int | Any) -> None:
        """Emit ``<mode> Tr`` — set the text rendering mode (0-7).

        Accepts either an ``int`` (0..7) or a
        :class:`pypdfbox.pdmodel.graphics.state.RenderingMode` enum
        member. Mirrors upstream's ``setRenderingMode(RenderingMode)`` —
        the int form is the legacy spelling. Out-of-range integers raise
        :class:`ValueError`.
        """
        from pypdfbox.pdmodel.graphics.state.rendering_mode import (  # noqa: PLC0415
            RenderingMode,
        )

        m = mode.int_value() if isinstance(mode, RenderingMode) else int(mode)
        if not 0 <= m <= 7:
            raise ValueError(
                f"text rendering mode must be in 0..7; got {mode!r}"
            )
        self._write_operands(m)
        self._write_operator(b"Tr")

    def set_rendering_mode(self, mode: int | Any) -> None:
        """Alias for :meth:`set_text_rendering_mode` matching upstream's
        ``setRenderingMode`` Java method name. Accepts ``int`` or
        :class:`RenderingMode`."""
        self.set_text_rendering_mode(mode)

    # ------------------------------------------------------------------
    # graphics state
    # ------------------------------------------------------------------

    def save_graphics_state(self) -> None:
        self._require_outside_text_block("save_graphics_state")
        self._write_operator(b"q")

    def restore_graphics_state(self) -> None:
        self._require_outside_text_block("restore_graphics_state")
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
        self._require_outside_text_block("transform")
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

    def set_graphics_state_parameters(self, ext_g_state: Any) -> None:
        """Emit ``/<key> gs`` — apply a :class:`PDExtendedGraphicsState`.

        Auto-registers ``ext_g_state`` under ``/Resources/ExtGState`` (key
        ``GS<n>``) when not already present. Mirrors upstream's
        ``setGraphicsStateParameters`` (Java) /
        ``set_graphics_state_parameters`` (port).
        """
        key = self._resource_key_for_ext_g_state(ext_g_state)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"gs")

    # ------------------------------------------------------------------
    # ExtGState convenience setters — each builds (or fetches) a small
    # ExtGState carrying just the relevant key, registers it under
    # /Resources/ExtGState, and emits ``/<key> gs``. Mirrors upstream's
    # ``setStrokingAlphaConstant``/``setNonStrokingAlphaConstant``/
    # ``setBlendMode`` / Soft-mask convenience helpers.
    # ------------------------------------------------------------------

    def set_stroking_alpha_constant(self, alpha: float) -> None:
        """Emit ``/<key> gs`` with an ExtGState carrying ``/CA``."""
        ext = self._build_ext_g_state(stroking_alpha=float(alpha))
        self.set_graphics_state_parameters(ext)

    def set_non_stroking_alpha_constant(self, alpha: float) -> None:
        """Emit ``/<key> gs`` with an ExtGState carrying ``/ca``."""
        ext = self._build_ext_g_state(non_stroking_alpha=float(alpha))
        self.set_graphics_state_parameters(ext)

    def set_blend_mode(self, blend_mode: Any) -> None:
        """Emit ``/<key> gs`` with an ExtGState carrying ``/BM``.

        Accepts a :class:`pypdfbox.pdmodel.graphics.blend_mode.BlendMode`,
        a :class:`COSName`, or a ``str`` blend-mode name.
        """
        ext = self._build_ext_g_state(blend_mode=blend_mode)
        self.set_graphics_state_parameters(ext)

    def set_softmask(self, soft_mask: Any) -> None:
        """Emit ``/<key> gs`` with an ExtGState carrying ``/SMask``.

        ``soft_mask`` may be a :class:`PDSoftMask`, a :class:`COSDictionary`
        (taken as the SMask dict directly), or ``None`` to write the
        ``/None`` literal that disables masking.
        """
        ext = self._build_ext_g_state(soft_mask=soft_mask)
        self.set_graphics_state_parameters(ext)

    # alias: upstream method name is ``setSoftMask`` (camelCase) — keep
    # both spellings so callers porting from PDFBox find either.
    def set_soft_mask(self, soft_mask: Any) -> None:
        """Alias for :meth:`set_softmask` matching upstream's
        ``setSoftMask`` Java method name."""
        self.set_softmask(soft_mask)

    @staticmethod
    def _build_ext_g_state(
        *,
        stroking_alpha: float | None = None,
        non_stroking_alpha: float | None = None,
        blend_mode: Any = None,
        soft_mask: Any = None,
    ) -> Any:
        """Construct a fresh :class:`PDExtendedGraphicsState` carrying
        only the keys explicitly passed. Lazy-imports the class to keep
        the writer's module-load cost down."""
        from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
            PDExtendedGraphicsState,
        )

        ext = PDExtendedGraphicsState()
        if stroking_alpha is not None:
            ext.set_stroking_alpha_constant(stroking_alpha)
        if non_stroking_alpha is not None:
            ext.set_non_stroking_alpha_constant(non_stroking_alpha)
        if blend_mode is not None:
            ext.set_blend_mode(blend_mode)
        if soft_mask is not None:
            ext.get_cos_object().set_item(
                COSName.get_pdf_name("SMask"),
                soft_mask.get_cos_object()
                if hasattr(soft_mask, "get_cos_object")
                else soft_mask,
            )
        return ext

    # ------------------------------------------------------------------
    # pattern / shading colour
    # ------------------------------------------------------------------

    def set_stroking_color_pattern(self, pattern: Any) -> None:
        """Emit ``/Pattern CS /<key> SCN`` — set the stroking colour to a
        :class:`PDAbstractPattern`. Mirrors upstream's
        ``setStrokingColor(PDAbstractPattern)``."""
        self._set_color_pattern(pattern, stroking=True)

    def set_non_stroking_color_pattern(self, pattern: Any) -> None:
        """Emit ``/Pattern cs /<key> scn`` — non-stroking variant of
        :meth:`set_stroking_color_pattern`."""
        self._set_color_pattern(pattern, stroking=False)

    # alias: shorter spelling matching the agent-task targets.
    def set_pattern_stroke(self, pattern: Any) -> None:
        """Alias for :meth:`set_stroking_color_pattern`."""
        self.set_stroking_color_pattern(pattern)

    def set_pattern_fill(self, pattern: Any) -> None:
        """Alias for :meth:`set_non_stroking_color_pattern`."""
        self.set_non_stroking_color_pattern(pattern)

    def set_stroking_pattern(
        self,
        pattern: Any,
        color_components: list[float] | tuple[float, ...] | None = None,
    ) -> None:
        """Emit ``/Pattern CS [<components> ]/<key> SCN`` — set the
        stroking colour to a :class:`PDAbstractPattern`.

        ``color_components`` is the optional list of underlying-colour-space
        components for an *uncolored* tiling pattern (PDF 32000-1 §8.7.3.3).
        When provided, the components are emitted before the pattern name.
        For coloured patterns and shading patterns omit the argument.

        Mirrors upstream's ``setStrokingColor(PDColor)`` behaviour for the
        Pattern colour-space branch, exposed here directly so callers don't
        need to construct a PDColor first.
        """
        self._set_color_pattern(
            pattern, color_components=color_components, stroking=True
        )

    def set_non_stroking_pattern(
        self,
        pattern: Any,
        color_components: list[float] | tuple[float, ...] | None = None,
    ) -> None:
        """Emit ``/Pattern cs [<components> ]/<key> scn`` — non-stroking
        variant of :meth:`set_stroking_pattern`."""
        self._set_color_pattern(
            pattern, color_components=color_components, stroking=False
        )

    def _set_color_pattern(
        self,
        pattern: Any,
        *,
        color_components: list[float] | tuple[float, ...] | None = None,
        stroking: bool,
    ) -> None:
        # Emit /Pattern (CS or cs).
        pattern_cs_name = COSName.get_pdf_name("Pattern")
        self._write_name(pattern_cs_name)
        self._buffer.append(0x20)
        self._write_operator(b"CS" if stroking else b"cs")
        # Optional underlying-colour-space components for uncolored tiling
        # patterns. Emit them as bare numeric operands in front of the
        # pattern name, mirroring upstream's
        # ``for (float value : color.getComponents()) writeOperand(value)``.
        if color_components is not None:
            for value in color_components:
                self._write_operands(float(value))
        # Register the pattern under /Resources/Pattern and emit its key.
        key = self._resource_key_for_pattern(pattern)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"SCN" if stroking else b"scn")

    def shading_fill(self, shading: Any) -> None:
        """Emit ``/<key> sh`` — paint the shape and colour shading from a
        :class:`PDShading`. Mirrors upstream's ``shadingFill``.

        Raises :class:`RuntimeError` when called inside a text block,
        mirroring upstream's ``IllegalStateException``.
        """
        self._require_outside_text_block("shading_fill")
        key = self._resource_key_for_shading(shading)
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"sh")

    # ------------------------------------------------------------------
    # shape painting (line-width-aware operator dispatch)
    # ------------------------------------------------------------------

    def draw_shape(
        self,
        line_width: float,
        has_stroke: bool,
        has_fill: bool,
    ) -> None:
        """Emit the path-painting operator selected from ``line_width``,
        ``has_stroke``, and ``has_fill``:

        - very thin lines (``line_width < 1e-6``) suppress the stroke;
        - fill + stroke -> ``B``;
        - stroke only -> ``S``;
        - fill only -> ``f``;
        - neither -> ``n`` (end path without painting).

        Matches the helper of the same name on
        :class:`PDAppearanceContentStream`.
        """
        resolved_has_stroke = bool(has_stroke)
        if float(line_width) < 1e-6:
            resolved_has_stroke = False
        if has_fill and resolved_has_stroke:
            self.fill_and_stroke()
        elif resolved_has_stroke:
            self.stroke()
        elif has_fill:
            self.fill()
        else:
            self._write_operator(b"n")

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
        if isinstance(x, (tuple, list)):
            raise TypeError(
                "draw_image transform_matrix overload does not accept y, "
                "width, or height"
            )
        x_pos = float(x)
        y_pos = float(y)

        if width is None:
            width = float(image.get_width())
        if height is None:
            height = float(image.get_height())
        key = self._resource_key_for_xobject(image)
        self.save_graphics_state()
        self.transform(width, 0, 0, height, x_pos, y_pos)
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
        jpeg_factory: Any | None = None
        lossless_factory: Any | None = None
        try:
            jpeg_module = importlib.import_module(
                "pypdfbox.pdmodel.graphics.image.jpeg_factory"
            )
            jpeg_factory = getattr(jpeg_module, "JPEGFactory", None)
        except ImportError:
            pass
        try:
            lossless_module = importlib.import_module(
                "pypdfbox.pdmodel.graphics.image.lossless_factory"
            )
            lossless_factory = getattr(lossless_module, "LosslessFactory", None)
        except ImportError:
            pass

        # Even if the modules import, the symbols themselves may be
        # missing (test stubs, partial installs). Treat that as the
        # same "not available" condition.
        jpeg = (
            getattr(jpeg_factory, "create_from_byte_array", None)
            if jpeg_factory is not None
            else None
        )
        lossless = (
            getattr(lossless_factory, "create_from_image", None)
            if lossless_factory is not None
            else None
        )

        if jpeg is None and lossless is None:
            raise NotImplementedError(
                "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
            )

        from pathlib import Path as _Path
        pil_image_mod: Any | None = None
        pil_image_type: Any | None = None
        try:
            pil_image_mod = importlib.import_module("PIL.Image")
            pil_image_type = getattr(pil_image_mod, "Image", None)
        except ImportError:
            pass

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
                return cast("PDImageXObject", jpeg(document, path.read_bytes()))
            if lossless is None or pil_image_mod is None:
                raise NotImplementedError(
                    "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                )
            with pil_image_mod.open(path) as src:
                src.load()
                return cast("PDImageXObject", lossless(document, src))

        # bytes → sniff JPEG SOI marker; otherwise hand off to Pillow
        # then the lossless factory.
        if isinstance(image, (bytes, bytearray)):
            data = bytes(image)
            if data[:2] == b"\xff\xd8":
                if jpeg is None:
                    raise NotImplementedError(
                        "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                    )
                return cast("PDImageXObject", jpeg(document, data))
            if lossless is None or pil_image_mod is None:
                raise NotImplementedError(
                    "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                )
            import io as _io
            with pil_image_mod.open(_io.BytesIO(data)) as src:
                src.load()
                return cast("PDImageXObject", lossless(document, src))

        # Pillow Image → always decode via the lossless factory.
        if pil_image_type is not None and isinstance(image, pil_image_type):
            if lossless is None:
                raise NotImplementedError(
                    "install JPEGFactory/LosslessFactory or pass a PDImageXObject"
                )
            return cast("PDImageXObject", lossless(document, image))

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
        """Emit ``/<key> Do`` — draw ``form_xobject`` on the current page.

        At the origin (``x == 0`` and ``y == 0``) this matches upstream's
        ``drawForm(PDFormXObject)`` exactly: a bare ``/<key> Do`` with **no**
        surrounding ``q`` / ``cm`` / ``Q`` (the caller controls the graphics
        state). Upstream's ``drawForm`` takes no position argument; the ``x`` /
        ``y`` parameters here are a pypdfbox convenience extension — when either
        is non-zero a ``q 1 0 0 1 <x> <y> cm`` … ``Q`` wrapper is emitted so
        the placement translate is self-contained.

        Raises :class:`RuntimeError` when called inside a text block
        (between ``BT`` / ``ET``) — matches upstream's
        ``IllegalStateException`` from ``drawForm``.
        """
        if not isinstance(form_xobject, PDFormXObject):
            raise TypeError(
                f"PDPageContentStream.draw_form expects PDFormXObject; got "
                f"{type(form_xobject).__name__}"
            )
        if self._in_text_mode:
            raise RuntimeError(
                "draw_form is not allowed within a text block (BT/ET)."
            )
        key = self._resource_key_for_xobject(form_xobject)
        if x != 0.0 or y != 0.0:
            # pypdfbox convenience placement: self-contained translate.
            self.save_graphics_state()
            self.transform(1, 0, 0, 1, x, y)
            self._write_name(key)
            self._buffer.append(0x20)
            self._write_operator(b"Do")
            self.restore_graphics_state()
            return
        # Upstream parity: bare ``/<key> Do`` at the origin, no q/cm/Q.
        self._write_name(key)
        self._buffer.append(0x20)
        self._write_operator(b"Do")

    # ------------------------------------------------------------------
    # marked content (tagged-PDF authoring)
    # ------------------------------------------------------------------

    def begin_marked_content(self, tag: COSName | str) -> None:
        """Emit ``/<tag> BMC``."""
        self._write_name(_to_cos_name(tag))
        self._buffer.append(0x20)
        self._write_operator(b"BMC")

    def begin_marked_content_with_mcid(
        self,
        tag: COSName | str,
        mcid: int,
    ) -> None:
        """Emit ``/<tag> <</MCID <mcid>>> BDC``.

        Mirrors upstream's ``beginMarkedContent(COSName tag, int mcid)``
        overload — used by tagged-PDF authoring to associate a marked
        content sequence with an entry in the structure tree without
        registering a property list under ``/Resources/Properties``.

        Raises :class:`ValueError` when ``mcid`` is negative, matching
        upstream's ``IllegalArgumentException``.
        """
        n = int(mcid)
        if n < 0:
            raise ValueError(f"mcid should not be negative; got {mcid!r}")
        self._write_name(_to_cos_name(tag))
        self._buffer.append(0x20)
        self._buffer.extend(b"<</MCID ")
        self._buffer.extend(str(n).encode("ascii"))
        self._buffer.extend(b">> ")
        self._write_operator(b"BDC")

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

    def set_marked_content_point(self, tag: COSName | str) -> None:
        """Alias for :meth:`add_marked_content_point` matching upstream's
        ``setMarkedContentPoint`` Java method name."""
        self.add_marked_content_point(tag)

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

    def set_marked_content_point_with_properties(
        self,
        tag: COSName | str,
        property_list: PDPropertyList | COSName | str,
    ) -> None:
        """Alias for :meth:`add_marked_content_point_with_dict` matching
        upstream's ``setMarkedContentPointWithProperties`` Java method
        name."""
        self.add_marked_content_point_with_dict(tag, property_list)

    # ------------------------------------------------------------------
    # raw byte / comment writers
    # ------------------------------------------------------------------

    def add_comment(self, comment: str) -> None:
        """Emit ``%<comment>\\n`` — write a PDF comment line.

        Mirrors upstream's ``addComment(String comment)``. The argument is
        encoded as US-ASCII; embedded newlines are rejected with
        :class:`ValueError` because the next line would otherwise be
        parsed as ordinary content-stream tokens.
        """
        if "\n" in comment or "\r" in comment:
            raise ValueError("comment should not include a newline")
        self._buffer.append(0x25)  # %
        self._buffer.extend(comment.encode("ascii"))
        self._buffer.append(0x0A)

    def append_raw_commands(self, data: str | bytes | bytearray | int | float) -> None:
        """Append raw bytes to the content stream verbatim.

        Mirrors upstream's deprecated ``appendRawCommands`` overloads
        (``String``, ``byte[]``, ``int``, ``float``, ``double``). Use of
        this method is discouraged — prefer the typed operator methods on
        this class. Provided for porting parity with PDFBox callers.

        - ``str`` → encoded as US-ASCII and appended.
        - ``bytes`` / ``bytearray`` → appended verbatim.
        - ``int`` / ``float`` → formatted as a numeric operand (4-decimal
          format, trailing-zero trim, trailing space) matching upstream's
          ``writeOperand`` overloads.
        """
        if isinstance(data, bool):
            raise TypeError("append_raw_commands does not accept bool")
        if isinstance(data, (bytes, bytearray)):
            self._buffer.extend(bytes(data))
        elif isinstance(data, str):
            self._buffer.extend(data.encode("ascii"))
        elif isinstance(data, (int, float)):
            self._write_operands(data)
        else:
            raise TypeError(
                "append_raw_commands expects str, bytes, int, or float; "
                f"got {type(data).__name__}"
            )

    # ------------------------------------------------------------------
    # resource key allocation
    # ------------------------------------------------------------------

    def _resource_key_for_font(self, font: PDFont) -> COSName:
        """Return the /Resources/Font key for ``font``, allocating a new
        ``F<n>`` slot if necessary."""
        font_cos = font.get_cos_object()
        sub = self._resources.get_cos_object().get_dictionary_object(_FONT)
        if isinstance(sub, COSDictionary):
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is font_cos:
                    return key
        return self._resources.add(_FONT, font_cos)

    def _resource_key_for_xobject(self, xobject: PDXObject) -> COSName:
        x_cos = xobject.get_cos_object()
        sub = self._resources.get_cos_object().get_dictionary_object(_X_OBJECT)
        if isinstance(sub, COSDictionary):
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
        if isinstance(sub, COSDictionary):
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
        if isinstance(sub, COSDictionary):
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is prop_cos:
                    return key
        return self._resources.add(_PROPERTIES, prop_cos)

    def _resource_key_for_ext_g_state(self, ext_g_state: Any) -> COSName:
        """Return the /Resources/ExtGState key for ``ext_g_state``,
        allocating a new ``gs<n>`` slot when necessary. Reuses an
        existing slot when the same COSDictionary is already registered."""
        ext_cos = ext_g_state.get_cos_object()
        sub = self._resources.get_cos_object().get_dictionary_object(
            _EXT_G_STATE
        )
        if isinstance(sub, COSDictionary):
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is ext_cos:
                    return key
        return self._resources.add(_EXT_G_STATE, ext_cos)

    def _resource_key_for_pattern(self, pattern: Any) -> COSName:
        """Return the /Resources/Pattern key for ``pattern``, allocating
        a new ``p<n>`` slot when necessary. ``pattern`` may be a
        :class:`PDAbstractPattern` (or any object exposing
        ``get_cos_object``) — accepts a raw :class:`COSDictionary` for
        callers porting tests that pre-built the dictionary."""
        from pypdfbox.cos import COSDictionary  # noqa: PLC0415

        pat_cos = (
            pattern.get_cos_object()
            if hasattr(pattern, "get_cos_object")
            else pattern
        )
        if not isinstance(pat_cos, COSDictionary):
            raise TypeError(
                "set_(non_)stroking_color_pattern expects a PDAbstractPattern "
                f"or COSDictionary; got {type(pattern).__name__}"
            )
        sub = self._resources.get_cos_object().get_dictionary_object(_PATTERN)
        if isinstance(sub, COSDictionary):
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is pat_cos:
                    return key
        return self._resources.add(_PATTERN, pat_cos)

    def _resource_key_for_shading(self, shading: Any) -> COSName:
        """Return the /Resources/Shading key for ``shading``, allocating
        a new ``sh<n>`` slot when necessary."""
        from pypdfbox.cos import COSDictionary  # noqa: PLC0415

        sh_cos = (
            shading.get_cos_object()
            if hasattr(shading, "get_cos_object")
            else shading
        )
        if not isinstance(sh_cos, COSDictionary) and not isinstance(
            sh_cos, COSStream
        ):
            raise TypeError(
                "shading_fill expects a PDShading or COSDictionary/COSStream; "
                f"got {type(shading).__name__}"
            )
        sub = self._resources.get_cos_object().get_dictionary_object(_SHADING)
        if isinstance(sub, COSDictionary):
            for key in sub.key_set():
                if sub.get_dictionary_object(key) is sh_cos:
                    return key
        return self._resources.add(_SHADING, sh_cos)

    # ------------------------------------------------------------------
    # low-level emit helpers
    # ------------------------------------------------------------------

    def _write_operator(self, op: bytes) -> None:
        self._buffer.extend(op)
        self._buffer.append(0x0A)

    def _write_operands(self, *values: float) -> None:
        for v in values:
            self._buffer.extend(_format_number(v, self._max_fraction_digits))
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


_FAST_PATH_LIMIT: float = 9.223372e18
_MAX_FRACTION_DIGITS: int = 5
_POWER_OF_TENS: tuple[int, ...] = (1, 10, 100, 1000, 10000, 100000)


def _format_number(value: float, max_fraction_digits: int = _MAX_FRACTION_DIGITS) -> bytes:
    """Format a numeric operand byte-for-byte like upstream PDFBox's
    ``PDAbstractContentStream.writeOperand(float)``.

    Upstream routes every numeric operand through ``float`` (the Java drawing
    API signatures are all ``float``) and formats it with
    ``NumberFormatUtil.formatFloatFast(value, maxFractionDigits, buffer)``.
    ``PDPageContentStream``'s constructor sets ``maxFractionDigits = 5`` while
    the shared ``PDAbstractContentStream`` constructor (used by appearance /
    form / pattern streams) sets ``maxFractionDigits = 4``;
    ``setMaximumFractionDigits`` may change it at runtime. The digit count is
    therefore a parameter here (default 5 for the page writer's call sites).

    ``formatFloatFast`` is **not** equivalent to ``format(f, ".Nf")`` on the
    Python ``float`` (a 64-bit double): two divergences matter for byte parity:

    1. **float32 narrowing.** The operand is a Java 32-bit ``float``, so its
       decimal expansion is taken from the *single-precision* value. e.g.
       ``12345.6789f`` is ``12345.6787109375`` and (at 5 digits) formats as
       ``12345.67871``, not ``12345.6789``.
    2. **truncating half-up on the narrowed fraction.** ``formatFloatFast``
       computes ``frac = (long)((|f| - trunc(f)) * 10**N + 0.5)`` — a half-up
       round of the *float32* fractional part. Because the float32 value of a
       decimal literal like ``0.000005`` is ``4.99999987e-06``, the ``+0.5``
       only reaches ``0.9999…`` and truncates to ``0`` (upstream emits ``0``),
       whereas a float64 ``.5f`` format would emit ``0.00001``.

    This function reproduces both. Whole-number operands keep their integer
    spelling (no ``.0``), matching ``NumberFormat`` on integral values, and
    negative zero is preserved (``-0``) exactly as upstream's buffer writer
    leaves the leading ``'-'`` before a zero integer part.

    When ``max_fraction_digits`` exceeds ``MAX_FRACTION_DIGITS`` (5), upstream's
    ``formatFloatFast`` returns ``-1`` and the caller falls back to
    ``NumberFormat.format((double) real)`` — Locale.US grouping-off HALF_EVEN
    rounding of the float32 value widened to a double. We reproduce that with
    :func:`round` (Python's banker's rounding is HALF_EVEN) on the widened
    value.

    Non-finite values (``inf`` / ``-inf`` / ``nan``) raise :class:`ValueError`,
    mirroring upstream's ``writeOperand(float)`` ``IllegalArgumentException``
    guard ("X is not a finite number")."""
    import math as _math  # noqa: PLC0415
    import struct as _struct  # noqa: PLC0415

    # Python ``int`` operands print via the integer path (NumberFormat.format
    # on a long), with no float narrowing — Python ints are unbounded so the
    # exact decimal is correct.
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value).encode("ascii")

    f64 = float(value)
    if not _math.isfinite(f64):
        raise ValueError(f"{value!r} is not a finite number")

    n = max(0, int(max_fraction_digits))

    # Narrow to a Java 32-bit float — this is the value upstream's drawing API
    # actually formats.
    f = _struct.unpack("f", _struct.pack("f", f64))[0]

    # Fallback range: upstream's ``formatFloatFast`` returns -1 (forcing the
    # ``NumberFormat.format((double) real)`` path) when the magnitude exceeds
    # Long.MAX_VALUE or the requested digit count exceeds MAX_FRACTION_DIGITS
    # (5). NumberFormat is Locale.US, grouping off, default HALF_EVEN.
    if abs(f) > _FAST_PATH_LIMIT or n > _MAX_FRACTION_DIGITS:
        rounded = round(f, n) if n > 0 else round(f)
        text = format(float(rounded), f".{n}f").rstrip("0").rstrip(".")
        return (text or "0").encode("ascii")

    integer = int(f)  # truncation toward zero, like Java's (long) cast
    sign = ""
    if f < 0.0:
        sign = "-"
        integer = -integer
    power = _POWER_OF_TENS[n]
    scaled = int((abs(f) - float(integer)) * power + 0.5)
    if scaled >= power:
        integer += 1
        scaled -= power
    text = sign + str(integer)
    if scaled > 0 and n > 0:
        frac = str(scaled).rjust(n, "0").rstrip("0")
        text = f"{text}.{frac}"
    return text.encode("ascii")


def _is_outside_one_interval(val: float) -> bool:
    """Return ``True`` if ``val`` is outside the closed ``[0, 1]`` range.

    Mirrors upstream's private ``isOutsideOneInterval(double)`` guard
    used by the DeviceGray/RGB/CMYK setters before they write operands.
    """
    return val < 0.0 or val > 1.0


def _is_outside_255_interval(val: int) -> bool:
    """Return ``True`` if ``val`` is outside the closed ``[0, 255]``
    integer range.

    Mirrors upstream's protected ``isOutside255Interval(int)`` helper —
    used when converting an AWT-style 8-bit color triple (``0..255``)
    into the PDF 32000-1 normalized ``0..1`` representation.
    """
    return val < 0 or val > 255


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
