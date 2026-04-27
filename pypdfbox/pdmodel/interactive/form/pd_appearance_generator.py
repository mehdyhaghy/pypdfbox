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
_OFF: COSName = COSName.get_pdf_name("Off")
_YES: COSName = COSName.get_pdf_name("Yes")


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
    """Lite port of upstream ``AppearanceGeneratorHelper`` — generates
    *flat* normal appearances for AcroForm widget annotations.

    Mirrors ``org.apache.pdfbox.pdmodel.interactive.form.AppearanceGenerator``
    (the static facade) and ``AppearanceGeneratorHelper`` (the worker
    that actually composes the content stream). The lite scope covers:

    1. **Text fields (``/FT /Tx``)**: a single line of flat text, font /
       color resolved from ``/DA``.
    2. **Check boxes (``/FT /Btn`` without push/radio bits)**: a two-state
       appearance subdictionary keyed by the field's on-value name and
       ``/Off``. The on-state draws a ZapfDingbats checkmark glyph (code
       ``4``); the off-state is empty.
    3. **Radio buttons (``/FT /Btn`` with ``FLAG_RADIO``)**: same shape as
       check boxes but the on-state draws a filled circle inscribed in
       the widget rect.
    4. **Choice fields (``/FT /Ch`` — combo + list)**: the selected
       option(s) rendered as flat text in the widget area, mirroring the
       text-field path with newline-joined values.

    For each widget the generator:

    - Pulls ``/Rect`` to size the appearance ``/BBox``.
    - Parses the field's (or AcroForm's) ``/DA`` (font name, font size,
      non-stroking color).
    - Emits the per-field-type content stream into a fresh form-XObject.
    - Installs the result as the widget's ``/AP /N`` (normal appearance);
      for buttons this is the on-state-keyed subdictionary, for text
      and choice fields it's a single appearance stream.

    **Deferred:** push button (``/Btn`` with ``FLAG_PUSHBUTTON``) caption
    rendering is skipped — upstream pulls a labeled rectangle from the
    widget's ``/MK /CA`` caption entry plus optional rollover/down
    captions, which involves the appearance characteristics dictionary
    and per-state caption variants. Signature field (``/Sig``) visual
    signature appearances, multi-line / comb / quadding layout for text
    fields, font-substitution fallbacks for non-Standard-14 ``/DA`` fonts,
    ``/MK`` border / background painting, and rich-text (``/RV``) rendering
    all stay no-ops in the lite surface — see ``CHANGES.md``.
    """

    DEFAULT_FONT_SIZE: float = 12.0
    AUTO_FONT_SIZE_MIN: float = 4.0
    AUTO_FONT_SIZE_MAX: float = 12.0

    # ZapfDingbats character code for the heavy check mark glyph (a4).
    # PDF 32000-1:2008 Annex D uses code 0x34 ('4') for "a20" check.
    ZAPFDINGBATS_CHECK = b"4"

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
        ``field``. Dispatches on field type:

        - ``/Tx`` text → flat single-line text appearance.
        - ``/Btn`` check / radio → two-state on/off appearance subdict.
        - ``/Btn`` push button → skipped (caption handling deferred).
        - ``/Ch`` combo / list → flat text rendering of selected value(s).
        - ``/Sig`` signature → skipped (visual signatures deferred).
        - anything else → debug-logged and skipped.
        """
        from .pd_button import PDButton
        from .pd_check_box import PDCheckBox
        from .pd_choice import PDChoice
        from .pd_push_button import PDPushButton
        from .pd_radio_button import PDRadioButton
        from .pd_text_field import PDTextField

        if isinstance(field, PDTextField):
            self._generate_text_field(field)
            return
        if isinstance(field, PDPushButton):
            _LOG.debug(
                "PDAppearanceGenerator.generate: push-button caption "
                "appearance deferred (skipping %s)",
                field.get_fully_qualified_name(),
            )
            return
        if isinstance(field, (PDCheckBox, PDRadioButton)):
            self._generate_button(field)
            return
        if isinstance(field, PDButton):
            # Untyped /Btn (generic PDButton) — treat as check box.
            self._generate_button(field)
            return
        if isinstance(field, PDChoice):
            self._generate_choice(field)
            return
        _LOG.debug(
            "PDAppearanceGenerator.generate: skipping %s — not a "
            "supported field type (text / check / radio / choice)",
            type(field).__name__,
        )

    # ------------------------------------------------------------------
    # text field
    # ------------------------------------------------------------------

    def _generate_text_field(self, field: PDField) -> None:
        value = field.get_value() or ""  # type: ignore[attr-defined]
        da = self._resolve_default_appearance(field)
        font_name, font_size, color = _parse_default_appearance(da)
        for widget in field.get_widgets():  # type: ignore[attr-defined]
            self._regenerate_text_widget(
                widget, value, font_name, font_size, color
            )

    # ------------------------------------------------------------------
    # button (check / radio)
    # ------------------------------------------------------------------

    def _generate_button(self, field: PDField) -> None:
        """Build a two-state appearance subdictionary on each widget.

        - ``/AP /N /<on-state>`` — drawn glyph (check or filled circle).
        - ``/AP /N /Off`` — empty stream.

        The on-state name comes from the existing widget appearance dict
        when present (so re-generation preserves the upstream-chosen state
        name); otherwise we default to ``/Yes``. The widget's ``/AS`` is
        synced to either the on-state name or ``/Off`` based on the
        field's ``/V`` value.
        """
        from .pd_radio_button import PDRadioButton

        is_radio = isinstance(field, PDRadioButton)
        current_value = field.get_value()  # type: ignore[attr-defined]

        for widget in field.get_widgets():  # type: ignore[attr-defined]
            widget_cos = widget.get_cos_object()
            rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
            if rect is None:
                _LOG.debug(
                    "PDAppearanceGenerator: button widget has no /Rect, "
                    "skipping appearance regeneration"
                )
                continue
            llx, lly, urx, ury = rect
            width = urx - llx
            height = ury - lly
            if width <= 0.0 or height <= 0.0:
                continue

            on_state = self._on_state_name_for_widget(widget_cos)

            on_stream = self._build_button_on_appearance(
                width, height, is_radio
            )
            off_stream = self._build_empty_appearance(width, height)

            n_subdict = COSDictionary()
            n_subdict.set_item(
                COSName.get_pdf_name(on_state),
                on_stream.get_cos_object(),
            )
            n_subdict.set_item(_OFF, off_stream.get_cos_object())

            ap_dict = PDAppearanceDictionary()
            ap_dict.get_cos_object().set_item(_N, n_subdict)
            widget_cos.set_item(_AP, ap_dict.get_cos_object())

            # Sync /AS so the viewer renders the matching subdictionary entry.
            if current_value and current_value == on_state:
                widget_cos.set_item(
                    COSName.get_pdf_name("AS"),
                    COSName.get_pdf_name(on_state),
                )
            else:
                widget_cos.set_item(COSName.get_pdf_name("AS"), _OFF)

    def _on_state_name_for_widget(self, widget_cos: COSDictionary) -> str:
        """Return the on-state name to use for ``widget_cos``.

        Prefers the first non-Off key already present in the widget's
        ``/AP /N`` subdictionary so re-generation preserves the
        per-widget state name (matters for radio groups where each kid
        carries its own on-state). Falls back to ``"Yes"``.
        """
        ap = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap, COSDictionary):
            n = ap.get_dictionary_object(_N)
            if isinstance(n, COSDictionary):
                for key in n.key_set():
                    if key != _OFF:
                        return key.name
        return "Yes"

    def _build_button_on_appearance(
        self, width: float, height: float, is_radio: bool
    ) -> PDAppearanceStream:
        appearance_cos = self._fresh_form_xobject(width, height)
        appearance_stream = PDAppearanceStream(appearance_cos)
        with PDAppearanceContentStream(appearance_stream) as cs:
            cs.save_graphics_state()
            if is_radio:
                self._draw_radio_dot(cs, width, height)
            else:
                self._draw_check_glyph(cs, width, height)
            cs.restore_graphics_state()
        return appearance_stream

    def _build_empty_appearance(
        self, width: float, height: float
    ) -> PDAppearanceStream:
        appearance_cos = self._fresh_form_xobject(width, height)
        appearance_stream = PDAppearanceStream(appearance_cos)
        # Open + close the writer so the body is committed (an empty
        # byte string is valid — the appearance stream is just a no-op).
        with PDAppearanceContentStream(appearance_stream):
            pass
        return appearance_stream

    def _draw_check_glyph(
        self, cs: PDAppearanceContentStream, width: float, height: float
    ) -> None:
        """Draw a ZapfDingbats check mark glyph centered in the widget rect.

        Uses the resource-registered ZapfDingbats font so the encoded
        bytes ``b"4"`` map to the heavy check glyph (a20) at runtime.
        """
        font = PDFontFactory.create_default_font(Standard14Fonts.ZAPF_DINGBATS)
        # Glyph height ~ 0.7 of cap-height; pick a size that fits the rect
        # with a small margin.
        size = max(1.0, min(width, height) * 0.8)
        # ZapfDingbats glyph metrics put the check around half the em
        # square — center horizontally with a 50% nominal width estimate.
        x = (width - size * 0.5) / 2.0
        y = (height - size * 0.7) / 2.0
        cs.begin_text()
        cs.set_non_stroking_color((0.0,))
        cs.set_font(font, size)
        cs.new_line_at_offset(x, y)
        # Pass raw bytes so ``show_text`` emits ``(4) Tj`` verbatim — the
        # ZapfDingbats encoding handles the codepoint -> glyph mapping
        # at render time.
        cs.show_text(self.ZAPFDINGBATS_CHECK)
        cs.end_text()

    def _draw_radio_dot(
        self, cs: PDAppearanceContentStream, width: float, height: float
    ) -> None:
        """Draw a filled circle inscribed in the widget rect.

        Uses the standard 4-Bezier circle approximation (kappa = 0.5523)
        about the rect center with radius = 0.4 * min(width, height).
        """
        cx = width / 2.0
        cy = height / 2.0
        r = min(width, height) * 0.4
        if r <= 0.0:
            return
        k = r * 0.5522847498  # 4-cubic-Bezier circle approximation constant
        cs.set_non_stroking_color((0.0,))
        cs.move_to(cx + r, cy)
        cs.curve_to(cx + r, cy + k, cx + k, cy + r, cx, cy + r)
        cs.curve_to(cx - k, cy + r, cx - r, cy + k, cx - r, cy)
        cs.curve_to(cx - r, cy - k, cx - k, cy - r, cx, cy - r)
        cs.curve_to(cx + k, cy - r, cx + r, cy - k, cx + r, cy)
        cs.close_path()
        cs.fill()

    # ------------------------------------------------------------------
    # choice (combo / list)
    # ------------------------------------------------------------------

    def _generate_choice(self, field: PDField) -> None:
        """Render the field's selected value(s) as flat text.

        For combo boxes (single-select) and list boxes (potentially
        multi-select), the content stream is laid out the same way as a
        text field — we join the values with newlines and emit one
        ``Tj`` per line.
        """
        values = field.get_value()  # type: ignore[attr-defined]
        if isinstance(values, str):
            lines = [values] if values else []
        elif isinstance(values, list):
            lines = [v for v in values if v]
        else:
            lines = []
        da = self._resolve_default_appearance(field)
        font_name, font_size, color = _parse_default_appearance(da)
        for widget in field.get_widgets():  # type: ignore[attr-defined]
            self._regenerate_choice_widget(
                widget, lines, font_name, font_size, color
            )

    def _regenerate_choice_widget(
        self,
        widget: object,
        lines: list[str],
        font_name: str | None,
        font_size: float,
        color: tuple[float, ...] | None,
    ) -> None:
        widget_cos = widget.get_cos_object()  # type: ignore[attr-defined]
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            return

        appearance_cos = self._fresh_form_xobject(width, height)
        appearance_stream = PDAppearanceStream(appearance_cos)
        font = self._resolve_font(font_name)
        resolved_size = font_size if font_size > 0.0 else self._auto_size(height)

        with PDAppearanceContentStream(appearance_stream) as cs:
            cs._buffer.extend(b"/Tx BMC\n")  # type: ignore[attr-defined]
            cs.save_graphics_state()
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
            x = 2.0
            # Top-of-text baseline: position the first line near the top
            # of the widget so subsequent lines flow downward.
            top_y = max(2.0, height - resolved_size * 1.15)
            cs.new_line_at_offset(x, top_y)
            line_height = resolved_size * 1.15
            first = True
            for line in lines:
                if not first:
                    cs.new_line_at_offset(0.0, -line_height)
                first = False
                cs.show_text(line)
            cs.end_text()
            cs.restore_graphics_state()
            cs._buffer.extend(b"EMC\n")  # type: ignore[attr-defined]

        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            ap_dict = PDAppearanceDictionary(ap_value)
        else:
            ap_dict = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict.get_cos_object())
        ap_dict.set_normal_appearance(appearance_stream)

    # ------------------------------------------------------------------
    # widget-level regeneration (text)
    # ------------------------------------------------------------------

    def _regenerate_text_widget(
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

        appearance_cos = self._fresh_form_xobject(width, height)
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

    def _resolve_default_appearance(self, field: PDField) -> str | None:
        """Pull the field's ``/DA`` (with inheritable walk) or fall back
        to the explicit override passed to the generator constructor."""
        da: str | None = None
        getter = getattr(field, "get_default_appearance", None)
        if callable(getter):
            try:
                da = getter()
            except Exception:  # noqa: BLE001 — defensive on lite-port surface
                da = None
        if not da:
            da = self._default_appearance_override
        return da

    @staticmethod
    def _fresh_form_xobject(width: float, height: float) -> COSStream:
        """Build a fresh form-XObject COSStream sized to ``width x height``."""
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
        return appearance_cos

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
