from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSName,
    COSStream,
)

from .common.pd_stream import PDStream
from .font.pd_font import PDFont
from .graphics.form.pd_form_x_object import PDFormXObject
from .graphics.image.pd_image_x_object import PDImageXObject
from .graphics.pd_x_object import PDXObject
from .pd_page import PDPage
from .pd_resources import PDResources

if TYPE_CHECKING:
    from .pd_document import PDDocument


_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")
_X_OBJECT: COSName = COSName.get_pdf_name("XObject")


class PDPageContentStream:
    """High-level PDF content-stream writer. Mirrors
    ``org.apache.pdfbox.pdmodel.PDPageContentStream`` (the lite surface —
    upstream's class is ~1500 lines; we ship the operators most commonly
    needed for new-content generation).

    Two construction shapes match upstream:

    - ``PDPageContentStream(document, page)`` — append a fresh content
      stream to ``page`` (does not overwrite — for parity convenience the
      lite surface always *appends* so callers can layer content on
      existing pages without losing pre-existing operators).
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
    ) -> None:
        self._document = document
        self._closed: bool = False
        self._buffer: bytearray = bytearray()
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
            # Append the new stream to the page's /Contents (matches
            # upstream's APPEND mode, which is the safer default for the
            # lite surface).
            self._attach_to_page(source_page, self._target_stream)
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
    def _attach_to_page(page: PDPage, new_stream: COSStream) -> None:
        """Append ``new_stream`` to ``page``'s /Contents.

        - No /Contents yet → set the new stream as /Contents directly.
        - /Contents is already a stream → wrap [old, new] into a COSArray.
        - /Contents is already an array → append.
        """
        page_dict = page.get_cos_object()
        existing = page_dict.get_dictionary_object(_CONTENTS)
        if existing is None:
            page_dict.set_item(_CONTENTS, new_stream)
            return
        if isinstance(existing, COSArray):
            existing.add(new_stream)
            return
        # Single existing stream — promote to array.
        arr = COSArray()
        arr.add(existing)
        arr.add(new_stream)
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
        # Commit the buffered bytes — set_raw_data replaces the body.
        self._target_stream.set_raw_data(bytes(self._buffer))

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

    def close_path(self) -> None:
        self._write_operator(b"h")

    def stroke(self) -> None:
        self._write_operator(b"S")

    def close_and_stroke(self) -> None:
        self._write_operator(b"s")

    def fill(self) -> None:
        self._write_operator(b"f")

    def fill_and_stroke(self) -> None:
        self._write_operator(b"B")

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

    def show_text(self, text: str) -> None:
        """Emit ``(text) Tj``. The text is PDF-escaped (literal form for
        ASCII, hex form for any non-ASCII byte).

        Note: the *font*'s encode step is a font-cluster #4+ concern.
        Upstream calls ``font.encode(text)``; the lite surface here
        encodes the Python ``str`` as Latin-1 when possible (which matches
        the WinAnsi standard 14-font mapping for ASCII) and falls back to
        UTF-16BE hex form for non-Latin-1 input.
        """
        try:
            data = text.encode("latin-1")
            ascii_safe = all(b < 0x80 and b not in (0x0D, 0x0A) for b in data)
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
        self._buffer.append(0x20)
        self._write_operator(b"Tj")

    def new_line_at_offset(self, tx: float, ty: float) -> None:
        self._write_operands(tx, ty)
        self._write_operator(b"Td")

    def new_line(self) -> None:
        self._write_operator(b"T*")

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

    def set_horizontal_scaling(self, scaling: float) -> None:
        self._write_operands(scaling)
        self._write_operator(b"Tz")

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

    # ------------------------------------------------------------------
    # XObject
    # ------------------------------------------------------------------

    def draw_image(
        self,
        image: PDImageXObject,
        x: float,
        y: float,
        width: float | None = None,
        height: float | None = None,
    ) -> None:
        """Emit ``q <w> 0 0 <h> <x> <y> cm /<key> Do Q``.

        When ``width``/``height`` are omitted we use the image's intrinsic
        ``/Width`` and ``/Height`` (matching upstream's
        ``drawImage(PDImageXObject, float, float)`` overload).
        """
        if not isinstance(image, PDImageXObject):
            raise TypeError(
                f"PDPageContentStream.draw_image expects PDImageXObject; got "
                f"{type(image).__name__}"
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


__all__ = ["PDPageContentStream"]
