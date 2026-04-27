from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)

if TYPE_CHECKING:
    from .pd_field import PDField

_LOG = logging.getLogger(__name__)

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_RECT: COSName = COSName.get_pdf_name("Rect")
_DA: COSName = COSName.get_pdf_name("DA")
_V: COSName = COSName.get_pdf_name("V")
_TYPE: COSName = COSName.get_pdf_name("Type")
_XOBJECT: COSName = COSName.get_pdf_name("XObject")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_FORM: COSName = COSName.get_pdf_name("Form")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_RESOURCES: COSName = COSName.get_pdf_name("Resources")
_FORM_TYPE: COSName = COSName.get_pdf_name("FormType")


def _parse_default_appearance(
    da: str | None,
) -> tuple[str | None, float, tuple[float, ...] | None]:
    """Parse a ``/DA`` default-appearance string into ``(font_name, size, color)``.

    The ``/DA`` string is a sequence of content-stream operators. We look
    only for the two operators that appearance generation cares about:

    - ``/<font-name> <size> Tf`` — selects font + size.
    - ``g`` / ``rg`` / ``k`` — selects non-stroking color (1, 3, or 4
      components respectively).

    Returns ``(font_name, size, color_components)`` with ``font_name = None``
    when the string omits a ``Tf`` operator (caller falls back to Helvetica),
    ``size = 0.0`` when omitted (caller picks an auto-size), and
    ``color = None`` when no color operator was present (caller defaults
    to black).

    The lite parser is intentionally simple — it splits on whitespace and
    walks tokens. Upstream uses a proper content-stream parser
    (``COSStreamParser``), which is overkill for the operator subset that
    affects flat-text appearance.
    """
    if not da:
        return (None, 0.0, None)
    tokens = da.split()
    font_name: str | None = None
    size: float = 0.0
    color: tuple[float, ...] | None = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "Tf" and i >= 2:
            name_tok = tokens[i - 2]
            size_tok = tokens[i - 1]
            if name_tok.startswith("/"):
                font_name = name_tok[1:]
            try:
                size = float(size_tok)
            except ValueError:
                size = 0.0
        elif tok == "g" and i >= 1:
            try:
                color = (float(tokens[i - 1]),)
            except ValueError:
                pass
        elif tok == "rg" and i >= 3:
            try:
                color = (
                    float(tokens[i - 3]),
                    float(tokens[i - 2]),
                    float(tokens[i - 1]),
                )
            except ValueError:
                pass
        elif tok == "k" and i >= 4:
            try:
                color = (
                    float(tokens[i - 4]),
                    float(tokens[i - 3]),
                    float(tokens[i - 2]),
                    float(tokens[i - 1]),
                )
            except ValueError:
                pass
        i += 1

    return (font_name, size, color)


def _rect_from_cos(value: COSBase | None) -> tuple[float, float, float, float] | None:
    """Pull a ``/Rect`` array off a widget annotation as four floats."""
    if not isinstance(value, COSArray) or value.size() < 4:
        return None
    nums: list[float] = []
    for i in range(4):
        entry = value.get_object(i)
        if isinstance(entry, (COSFloat, COSInteger)):
            nums.append(float(entry.value))
        else:
            return None
    llx, lly, urx, ury = nums
    # Normalize so width / height are non-negative — matches PDRectangle.from_cos_array.
    if urx < llx:
        llx, urx = urx, llx
    if ury < lly:
        lly, ury = ury, lly
    return (llx, lly, urx, ury)


class PDAppearanceGenerator:
    """Lite port of upstream ``AppearanceGeneratorHelper`` — generates a
    *flat* normal appearance for a text field's widgets.

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.form.AppearanceGenerator``
    (the static facade) and ``AppearanceGeneratorHelper`` (the worker
    that actually composes the content stream). The lite scope is the
    text-field flat-text path:

    1. Pull each widget's ``/Rect`` to size the appearance ``/BBox``.
    2. Parse the field's ``/DA`` (font name, font size, non-stroking color).
    3. Emit a content stream that draws the field's ``/V`` value as a
       single line of flat text positioned roughly center-left within
       the widget rect.
    4. Install the resulting :class:`PDAppearanceStream` as the widget's
       ``/AP /N`` (normal appearance).

    **Deferred:** button (``/Btn``) on/off state appearances, choice
    field (``/Ch``) list/combo rendering, signature field (``/Sig``)
    visual signature appearances, multi-line / comb / quadding
    layout, font-substitution fallbacks for non-Standard-14 ``/DA``
    fonts, ``/MK`` border/background painting, rich-text (``/RV``)
    rendering. Every one of those goes through ``apply_change()`` /
    ``construct_appearances()`` upstream and stays a no-op in the lite
    surface — see ``CHANGES.md``.
    """

    DEFAULT_FONT_SIZE: float = 12.0
    AUTO_FONT_SIZE_MIN: float = 4.0
    AUTO_FONT_SIZE_MAX: float = 12.0

    def __init__(self, default_appearance: str | None = None) -> None:
        """``default_appearance`` is an optional override used when the
        field carries no ``/DA`` of its own and the inheritable walk also
        returns nothing. Falls back to ``"/Helv 0 Tf 0 g"``."""
        self._default_appearance_override = default_appearance

    # ------------------------------------------------------------------
    # public surface
    # ------------------------------------------------------------------

    def generate(self, field: PDField) -> None:
        """Regenerate the ``/AP /N`` normal appearance of every widget on
        ``field``. Only PDF text fields (``/FT /Tx``) are handled in the
        lite port — non-text fields log a debug message and are skipped.
        """
        from .pd_text_field import PDTextField

        if not isinstance(field, PDTextField):
            _LOG.debug(
                "PDAppearanceGenerator.generate: skipping %s — only "
                "PDTextField appearance regeneration is implemented "
                "(button / choice / signature deferred)",
                type(field).__name__,
            )
            return

        value = field.get_value() or ""
        da = field.get_default_appearance() or self._default_appearance_override
        font_name, font_size, color = _parse_default_appearance(da)

        for widget in field.get_widgets():
            self._regenerate_widget(widget, value, font_name, font_size, color)

    # ------------------------------------------------------------------
    # widget-level regeneration
    # ------------------------------------------------------------------

    def _regenerate_widget(
        self,
        widget: object,
        value: str,
        font_name: str | None,
        font_size: float,
        color: tuple[float, ...] | None,
    ) -> None:
        widget_cos = widget.get_cos_object()  # type: ignore[attr-defined]
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            _LOG.debug(
                "PDAppearanceGenerator: widget has no /Rect, skipping "
                "appearance regeneration"
            )
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            _LOG.debug(
                "PDAppearanceGenerator: widget /Rect is degenerate "
                "(%s x %s), skipping",
                width,
                height,
            )
            return

        # Build a fresh form-XObject COSStream for the appearance body.
        appearance_cos = COSStream()
        appearance_cos.set_item(_TYPE, _XOBJECT)
        appearance_cos.set_item(_SUBTYPE, _FORM)
        appearance_cos.set_int(_FORM_TYPE, 1)
        bbox = COSArray(
            [
                COSFloat(0.0),
                COSFloat(0.0),
                COSFloat(width),
                COSFloat(height),
            ]
        )
        appearance_cos.set_item(_BBOX, bbox)
        appearance_stream = PDAppearanceStream(appearance_cos)

        # Resolve the font + size. ``font_size = 0`` is the "auto-size" tag
        # in the /DA spec — pick a sane value clamped to widget height
        # (auto-sizing rule per upstream: line height ~ 1.15 * size).
        font = self._resolve_font(font_name)
        resolved_size = font_size
        if resolved_size <= 0.0:
            resolved_size = self._auto_size(height)

        # Emit content stream:
        #   /Tx BMC                  marked-content section
        #   q                        save graphics state
        #   1 1 width-2 height-2 re W n  clip to interior
        #   BT
        #     <color>                 non-stroking color
        #     /<font-key> <size> Tf
        #     <x> <y> Td
        #     (<value>) Tj
        #   ET
        #   Q
        #   EMC
        with PDAppearanceContentStream(appearance_stream) as cs:
            # /Tx BMC marked-content tag — Acrobat looks for this on form
            # field appearance streams.
            cs._buffer.extend(b"/Tx BMC\n")  # type: ignore[attr-defined]
            cs.save_graphics_state()
            # Light interior clip (1pt margin all around) so the value
            # never bleeds over the widget border.
            interior_w = max(0.0, width - 2.0)
            interior_h = max(0.0, height - 2.0)
            if interior_w > 0.0 and interior_h > 0.0:
                cs.add_rect(1.0, 1.0, interior_w, interior_h)
                cs._write_operator(b"W")  # type: ignore[attr-defined]
                cs._write_operator(b"n")  # type: ignore[attr-defined]
            cs.begin_text()
            if color is not None:
                cs.set_non_stroking_color(color)
            cs.set_font(font, resolved_size)
            # Position text: small left padding, vertically roughly
            # centered using a 1.15 line-height heuristic.
            x = 2.0
            y = max(2.0, (height - resolved_size) / 2.0)
            cs.new_line_at_offset(x, y)
            if value:
                cs.show_text(value)
            cs.end_text()
            cs.restore_graphics_state()
            cs._buffer.extend(b"EMC\n")  # type: ignore[attr-defined]

        # Wire the new appearance into the widget annotation as /AP /N.
        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            ap_dict = PDAppearanceDictionary(ap_value)
        else:
            ap_dict = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict.get_cos_object())
        ap_dict.set_normal_appearance(appearance_stream)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_font(font_name: str | None) -> PDFont:
        """Return a :class:`PDFont` for ``font_name``.

        The /DA font key is a /Resources/Font dict alias (e.g. ``Helv``).
        Resolving it to a fully-qualified font dictionary requires walking
        the AcroForm /DR resource tree, which is wider than the lite scope.
        Instead we map the alias to a Standard 14 font when we recognise
        it (``Helv`` -> Helvetica, ``HeBo`` -> Helvetica-Bold, ``TiRo`` ->
        Times-Roman, ``CoRo`` -> Courier, ``ZaDb`` -> ZapfDingbats) and
        fall back to Helvetica otherwise. Callers who rely on a custom
        embedded font in their /DA are deferred — see ``CHANGES.md``.
        """
        if font_name:
            mapped = {
                "Helv": Standard14Fonts.HELVETICA,
                "HeBo": Standard14Fonts.HELVETICA_BOLD,
                "HeIt": Standard14Fonts.HELVETICA_OBLIQUE,
                "HeBI": Standard14Fonts.HELVETICA_BOLD_OBLIQUE,
                "TiRo": "Times-Roman",
                "TiBo": "Times-Bold",
                "TiIt": "Times-Italic",
                "TiBI": "Times-BoldItalic",
                "CoRo": "Courier",
                "CoBo": "Courier-Bold",
                "CoIt": "Courier-Oblique",
                "CoBI": "Courier-BoldOblique",
                "Symb": "Symbol",
                "ZaDb": "ZapfDingbats",
            }.get(font_name, font_name)
            if Standard14Fonts.get_mapped_font_name(mapped) is not None:
                return PDFontFactory.create_default_font(mapped)
        return PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)

    @classmethod
    def _auto_size(cls, height: float) -> float:
        """Pick an auto-size font size from a widget rect height.

        Upstream's ``calculateFontSize`` is iterative (it shrinks the size
        until the value fits the rect width); the lite port uses a
        constant heuristic — 0.7 of the height clamped to
        ``[AUTO_FONT_SIZE_MIN, AUTO_FONT_SIZE_MAX]``.
        """
        candidate = height * 0.7
        return max(
            cls.AUTO_FONT_SIZE_MIN,
            min(cls.AUTO_FONT_SIZE_MAX, candidate),
        )


__all__ = ["PDAppearanceGenerator"]
