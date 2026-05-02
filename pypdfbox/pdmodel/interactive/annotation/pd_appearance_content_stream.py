from __future__ import annotations

from collections.abc import Sequence
from typing import BinaryIO

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_resources import PDResources

from .pd_appearance_stream import PDAppearanceStream
from .pd_border_style_dictionary import PDBorderStyleDictionary


class PDAppearanceContentStream(PDPageContentStream):
    """Provides the ability to write to an appearance content stream.
    Mirrors ``org.apache.pdfbox.pdmodel.PDAppearanceContentStream``
    (note: upstream lives under ``pdmodel`` directly, not under
    ``interactive.annotation`` — this lite port keeps it next to
    :class:`PDAppearanceStream` to preserve cohesion).

    Three constructor shapes match upstream:

    - ``PDAppearanceContentStream(appearance)`` — write a fresh,
      uncompressed content stream into ``appearance``'s body.
    - ``PDAppearanceContentStream(appearance, compress=True)`` —
      same but with the body Flate-encoded on flush.
    - ``PDAppearanceContentStream(appearance, output_stream=...)`` —
      caller supplies a pre-opened binary output stream (used by the
      compressed-overload upstream and by callers that want a custom
      filter chain). The writer then routes operator bytes through it
      on close.

    The class extends :class:`PDPageContentStream` (the lite surface
    matches upstream's ``PDAbstractContentStream`` parent) and adds the
    annotation-specific helpers ``set_stroking_color_on_demand``,
    ``set_non_stroking_color_on_demand``, ``set_stroking_color`` /
    ``set_non_stroking_color`` (component-array form), ``set_border_line``,
    ``set_line_width_on_demand`` and ``draw_shape``.
    """

    def __init__(
        self,
        appearance: PDAppearanceStream,
        compress: bool | None = None,
        output_stream: BinaryIO | None = None,
    ) -> None:
        if not isinstance(appearance, PDAppearanceStream):
            raise TypeError(
                "PDAppearanceContentStream requires a PDAppearanceStream; got "
                f"{type(appearance).__name__}"
            )
        # Bypass PDPageContentStream's PDPage/PDFormXObject branching —
        # PDAppearanceStream isn't a PDFormXObject in the lite port. We
        # populate the same attributes the parent uses so all inherited
        # operator helpers (move_to, set_font, draw_image, ...) work.
        self._document = None  # upstream passes null too
        self._closed = False
        self._buffer = bytearray()
        self._reset_context = False
        self._in_text_mode = False

        self._appearance = appearance
        self._target_stream = appearance.get_stream()

        # Resources: reuse the appearance's existing /Resources if present;
        # otherwise create a fresh one and attach. Mirrors upstream's
        # ``appearance.getResources()`` falling back via
        # ``PDAbstractContentStream`` on first use.
        existing = appearance.get_resources()
        if existing is None:
            self._resources = PDResources()
            appearance.set_resources(self._resources)
        else:
            self._resources = existing

        # Custom output_stream short-circuits compression handling.
        self._external_output: BinaryIO | None = output_stream
        # ``compress=True`` selects FlateDecode at flush time. The
        # external-output branch ignores ``compress`` because the caller
        # owns the filter chain.
        self._compress = bool(compress) and output_stream is None

    # ------------------------------------------------------------------
    # lifecycle — overridden to support the explicit-output-stream path
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Flush the buffered operator bytes.

        - With an external ``output_stream``, write the buffered bytes
          to it and close it (the caller-provided stream is responsible
          for committing back into the underlying COSStream — that's
          how ``COSStream.create_output_stream(...)`` works).
        - With ``compress=True``, route bytes through a FlateDecode
          encoding stream.
        - Otherwise commit the bytes verbatim via ``set_raw_data``.
        """
        if self._closed:
            return
        self._closed = True
        data = bytes(self._buffer)
        if self._external_output is not None:
            try:
                self._external_output.write(data)
            finally:
                self._external_output.close()
            return
        if self._compress:
            with self._target_stream.create_output_stream(
                COSName.FLATE_DECODE  # type: ignore[attr-defined]
            ) as out:
                out.write(data)
        else:
            self._target_stream.set_raw_data(data)

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------

    def get_appearance(self) -> PDAppearanceStream:
        """Return the appearance stream this writer targets."""
        return self._appearance

    def get_resources(self) -> PDResources:
        """Return the ``/Resources`` dictionary the writer is binding font
        + xobject names against. Mirrors upstream's
        ``PDAbstractContentStream.getResources`` accessor — we override
        here because the lite-port appearance writer bypasses the parent
        constructor."""
        return self._resources

    def is_compress(self) -> bool:
        """Return whether the writer will Flate-encode the content stream
        on close. Returns ``False`` when an external output stream was
        supplied (the caller owns the filter chain in that case)."""
        return self._compress

    # ------------------------------------------------------------------
    # color — "on demand" helpers
    # ------------------------------------------------------------------

    def set_stroking_color_on_demand(self, color: PDColor | None) -> bool:
        """Emit the stroking-color operator only when ``color`` is non-null
        and has at least one component. Returns ``True`` on emit."""
        if color is None:
            return False
        components = color.get_components()
        if len(components) == 0:
            return False
        self.set_stroking_color(components)
        return True

    def set_non_stroking_color_on_demand(self, color: PDColor | None) -> bool:
        """Emit the non-stroking-color operator only when ``color`` is
        non-null and has at least one component. Returns ``True`` on emit."""
        if color is None:
            return False
        components = color.get_components()
        if len(components) == 0:
            return False
        self.set_non_stroking_color(components)
        return True

    # ------------------------------------------------------------------
    # color — component-array form
    # ------------------------------------------------------------------

    def set_stroking_color(self, components: Sequence[float]) -> None:
        """Emit ``c1 c2 ... cN <op>`` where the operator is selected by
        component count (``G`` for 1, ``RG`` for 3, ``K`` for 4). Other
        component counts are silently ignored (matches upstream's
        ``default: break``)."""
        for value in components:
            self._write_operands(float(value))
        n = len(components)
        if n == 1:
            self._write_operator(b"G")
        elif n == 3:
            self._write_operator(b"RG")
        elif n == 4:
            self._write_operator(b"K")
        # else: silently no-op (matches upstream)

    def set_non_stroking_color(self, components: Sequence[float]) -> None:
        """Emit the non-stroking equivalent of :meth:`set_stroking_color`
        (``g`` / ``rg`` / ``k``)."""
        for value in components:
            self._write_operands(float(value))
        n = len(components)
        if n == 1:
            self._write_operator(b"g")
        elif n == 3:
            self._write_operator(b"rg")
        elif n == 4:
            self._write_operator(b"k")
        # else: silently no-op (matches upstream)

    # ------------------------------------------------------------------
    # border / line-width helpers
    # ------------------------------------------------------------------

    def set_border_line(
        self,
        line_width: float,
        bs: PDBorderStyleDictionary | None,
        border: COSArray | None,
    ) -> None:
        """Convenience for annotations: sets the line dash style and width.

        - When ``bs`` is non-null, has a ``/D`` entry, and its style is
          ``"D"`` (dashed), emit the dash pattern from
          :meth:`PDBorderStyleDictionary.get_dash_style`.
        - When ``bs`` is null and ``border`` has more than 3 entries,
          treat ``border[3]`` as the dash array (or fall back to a
          1-element invisible-dash array per PDFBOX-5266 if ``border[3]``
          is malformed).
        - Always emit ``set_line_width_on_demand(line_width)`` last.
        """
        if (
            bs is not None
            and bs.get_cos_object().contains_key(COSName.get_pdf_name("D"))
            and bs.get_style() == PDBorderStyleDictionary.STYLE_DASHED
        ):
            dash = bs.get_dash_style()
            if dash is not None:
                self.set_dash_pattern(list(dash.get_dash_array()), 0)
        elif bs is None and border is not None and border.size() > 3:
            entry = border.get_object(3)
            if isinstance(entry, COSArray):
                self.set_dash_pattern(list(entry.to_float_array()), 0)
            else:
                # PDFBOX-5266: invalid dash array, be invisible
                self.set_dash_pattern([0.0], 0)
        self.set_line_width_on_demand(line_width)

    def set_line_width_on_demand(self, line_width: float) -> None:
        """Emit the line-width operator only when ``line_width`` differs
        from 1 by more than 1e-6. Acrobat skips the operator for the
        default width, so we do too."""
        if abs(float(line_width) - 1.0) >= 1e-6:
            self.set_line_width(float(line_width))

    # ------------------------------------------------------------------
    # shape painting
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


__all__ = ["PDAppearanceContentStream"]
