from __future__ import annotations

import logging
import re
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
_MK: COSName = COSName.get_pdf_name("MK")


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

    **Text fields (Wave 33+):** support multi-line (``Ff`` bit 13),
    comb (``Ff`` bit 25 — distributes the value's characters into
    ``/MaxLen`` equal-width cells), and quadding (``/Q`` 0/1/2 = left /
    centered / right alignment). Auto-line-wrap walks the value
    breaking on whitespace, advancing the baseline by ``size * 1.15``
    per line.

    **Push buttons (Wave 33+):** the widget's ``/MK /CA`` caption is
    rendered as flat text centred in the rect, with an optional border
    drawn from ``/MK /BC`` and a flat background fill from ``/MK /BG``.
    Rollover (``/RC``) and alternate / down (``/AC``) captions stay
    deferred — viewers fall back to ``/CA`` when those entries are
    absent, so the lite surface still produces a usable widget.

    **Signature fields (Wave 33+):** when the field carries a
    ``/V`` ``PDSignature``, the visual appearance is a flat box with
    the signer's ``/Name`` and ``/M`` sign date in two Helvetica-10
    lines. Sigfields without a signature value get an empty stream.

    **Deferred:** font-substitution fallbacks for non-Standard-14
    ``/DA`` fonts, rich-text (``/RV``) rendering, and a proper
    iterative auto-size for over-flowing text values stay no-ops in
    the lite surface — see ``CHANGES.md``.
    """

    DEFAULT_FONT_SIZE: float = 12.0
    AUTO_FONT_SIZE_MIN: float = 4.0
    AUTO_FONT_SIZE_MAX: float = 12.0

    # Upstream parity constants (mirror AppearanceGeneratorHelper static fields).
    # FONTSCALE — font units are 1/1000 em; multiply a unit value by
    # ``size / FONTSCALE`` to get user-space pixels.
    FONTSCALE: int = 1000
    # MINIMUM_FONT_SIZE — used by upstream's iterative auto-size to avoid
    # picking a size below 4pt; the lite-port auto-size also clamps here.
    MINIMUM_FONT_SIZE: float = 4.0
    # DEFAULT_PADDING — Acrobat's default 0.5pt padding around the field
    # bbox. The lite port uses a 1pt margin (interior_w = width - 2.0)
    # for the clip rect, but the upstream constant is preserved here so
    # callers porting from upstream code can reference it.
    DEFAULT_PADDING: float = 0.5
    # HIGHLIGHT_COLOR — Acrobat's listbox-selection highlight (sRGB).
    # Upstream value is {153/255, 193/255, 215/255} — preserved exactly.
    HIGHLIGHT_COLOR: tuple[float, float, float] = (
        153.0 / 255.0,
        193.0 / 255.0,
        215.0 / 255.0,
    )

    # Newline characters upstream's PATTERN regex matches (PDFBOX-3911):
    # CRLF, LF, VT, FF, CR, NEL (U+0085), LS (U+2028), PS (U+2029).
    # Single-line text fields collapse any of these to a single space.
    _NEWLINE_PATTERN: re.Pattern[str] = re.compile(
        "\r\n|[\n\u000B\u000C\r\u0085\u2028\u2029]"
    )

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

    def set_appearance_value(self, field: PDField, ap_value: str | None) -> None:
        """Set ``field``'s ``/V`` to ``ap_value`` and regenerate every widget's
        normal appearance.

        Mirrors upstream ``AppearanceGeneratorHelper.setAppearanceValue``
        (the only public method on the upstream helper). Upstream
        constructs the helper with the field, then accepts only the new
        value here; the lite port collapses both into one call.

        Per PDFBOX-3911, single-line ``PDTextField`` values collapse
        every newline-class character (``\\n``, ``\\r``, VT, FF, NEL,
        LS, PS, and the CRLF pair) to a single space before
        regeneration — matches Adobe Reader's interactive-entry
        behavior.
        """
        from .pd_text_field import PDTextField

        if isinstance(field, PDTextField) and not field.is_multiline():
            normalized = self._NEWLINE_PATTERN.sub(" ", ap_value or "")
            field.set_value(normalized)
        else:
            field.set_value(ap_value)  # type: ignore[attr-defined]
        self.generate(field)

    def generate(self, field: PDField) -> None:
        """Regenerate the ``/AP /N`` normal appearance of every widget on
        ``field``. Dispatches on field type:

        - ``/Tx`` text → flat text appearance (single-line, multi-line,
          comb, or quadded based on ``Ff`` / ``/Q``).
        - ``/Btn`` check / radio → two-state on/off appearance subdict.
        - ``/Btn`` push button → centred ``/MK /CA`` caption with
          optional border / background.
        - ``/Ch`` combo / list → flat text rendering of selected value(s).
        - ``/Sig`` signature → flat name + date box (when ``/V`` set).
        - anything else → debug-logged and skipped.
        """
        from .pd_button import PDButton
        from .pd_check_box import PDCheckBox
        from .pd_choice import PDChoice
        from .pd_push_button import PDPushButton
        from .pd_radio_button import PDRadioButton
        from .pd_signature_field import PDSignatureField
        from .pd_text_field import PDTextField

        if isinstance(field, PDTextField):
            self._generate_text_field(field)
            return
        if isinstance(field, PDPushButton):
            self._generate_push_button(field)
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
        if isinstance(field, PDSignatureField):
            self._generate_signature(field)
            return
        _LOG.debug(
            "PDAppearanceGenerator.generate: skipping %s — not a "
            "supported field type",
            type(field).__name__,
        )

    # ------------------------------------------------------------------
    # text field
    # ------------------------------------------------------------------

    def _generate_text_field(self, field: PDField) -> None:
        from .pd_text_field import PDTextField

        value = field.get_value() or ""  # type: ignore[attr-defined]
        da = self._resolve_default_appearance(field)
        font_name, font_size, color = _parse_default_appearance(da)

        is_multiline = False
        is_comb = False
        is_password = False
        max_len = -1
        quadding = 0
        if isinstance(field, PDTextField):
            is_multiline = field.is_multiline()
            is_comb = field.is_comb()
            is_password = field.is_password()
            max_len = field.get_max_len()
            quadding = field.get_q()

        # PDFBOX-3911: single-line text fields collapse newline-class
        # characters to a single space before rendering. Multi-line and
        # comb fields keep newlines so the wrap / cell logic can split on
        # them.
        if not is_multiline and not is_comb and value:
            value = self._NEWLINE_PATTERN.sub(" ", value)

        # Password fields render every char as an asterisk per PDF 32000-1
        # §12.7.4.3 — the underlying ``/V`` value is unchanged. We mask once
        # here so the multi-line / comb / quadding layout below all observe
        # the masked string consistently. ``len(value)`` measures Python
        # codepoints, which matches upstream's character-by-character mask.
        if is_password and value:
            value = "*" * len(value)

        for widget in field.get_widgets():  # type: ignore[attr-defined]
            self._regenerate_text_widget(
                widget,
                value,
                font_name,
                font_size,
                color,
                is_multiline=is_multiline,
                is_comb=is_comb,
                max_len=max_len,
                quadding=quadding,
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

        For combo boxes (single-select) the selected value is rendered
        as a single line of flat text. For list boxes the entire option
        list is laid out one-per-row starting from the field's ``/TI``
        scroll-offset (top index), and rows whose option matches the
        selected ``/V`` (or whose index appears in ``/I``) get a
        highlight rectangle drawn behind the row text — mirrors
        upstream's ``insertGeneratedListboxAppearance``.
        """
        from .pd_choice import PDChoice
        from .pd_list_box import PDListBox

        values = field.get_value()  # type: ignore[attr-defined]
        if isinstance(values, str):
            selected_values = [values] if values else []
        elif isinstance(values, list):
            selected_values = [v for v in values if v]
        else:
            selected_values = []

        da = self._resolve_default_appearance(field)
        font_name, font_size, color = _parse_default_appearance(da)

        is_listbox = isinstance(field, PDListBox)
        options: list[str] = []
        top_index = 0
        selected_indices: list[int] = []
        if isinstance(field, PDChoice):
            try:
                options = field.get_options_display_values() or field.get_options()
            except Exception:  # noqa: BLE001 — defensive on lite-port surface
                options = []
            top_index = max(0, field.get_top_index())
            selected_indices = field.get_selected_options_indices()

        for widget in field.get_widgets():  # type: ignore[attr-defined]
            if is_listbox:
                # When the field has no /Opt entries (uncommon but legal),
                # fall back to the selected values themselves so the widget
                # surface still shows something. Selection highlight then
                # covers the entire visible row range.
                rows = options if options else selected_values
                self._regenerate_listbox_widget(
                    widget,
                    rows,
                    selected_values,
                    selected_indices,
                    top_index,
                    font_name,
                    font_size,
                    color,
                )
            else:
                self._regenerate_choice_widget(
                    widget, selected_values, font_name, font_size, color
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

    def _regenerate_listbox_widget(
        self,
        widget: object,
        options: list[str],
        selected_values: list[str],
        selected_indices: list[int],
        top_index: int,
        font_name: str | None,
        font_size: float,
        color: tuple[float, ...] | None,
    ) -> None:
        """Render a list-box appearance with selection highlight + scroll offset.

        Mirrors upstream ``insertGeneratedListboxAppearance``:

        - All option rows are drawn (not just the selected ones), starting
          from row index ``top_index`` (``/TI``) so callers controlling the
          scroll position get the same visible window as Acrobat.
        - Rows whose index appears in ``/I`` (or whose value appears in
          ``/V``) get a flat blue highlight rectangle drawn behind the
          row text — RGB ``(0.6, 0.75, 0.85)`` matches Acrobat's default
          listbox selection color.
        - Rows scroll downward from the top of the rect at one
          ``line_height`` per option; rows whose baseline falls below the
          rect are clipped by the standard ``/Tx BMC`` clip path.
        """
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
        line_height = resolved_size * 1.15

        # Resolve the highlighted-row index set: union of /I and any
        # option index whose value appears in /V.
        highlighted: set[int] = set(i for i in selected_indices if i >= 0)
        for sel in selected_values:
            for idx, opt in enumerate(options):
                if opt == sel:
                    highlighted.add(idx)

        with PDAppearanceContentStream(appearance_stream) as cs:
            cs._buffer.extend(b"/Tx BMC\n")  # type: ignore[attr-defined]
            cs.save_graphics_state()
            interior_w = max(0.0, width - 2.0)
            interior_h = max(0.0, height - 2.0)
            if interior_w > 0.0 and interior_h > 0.0:
                cs.add_rect(1.0, 1.0, interior_w, interior_h)
                cs._write_operator(b"W")  # type: ignore[attr-defined]
                cs._write_operator(b"n")  # type: ignore[attr-defined]

            # Selection highlight rectangles — drawn before the text so
            # the glyphs paint on top.
            top_y = max(2.0, height - resolved_size * 1.15)
            visible_options = options[top_index:] if top_index < len(options) else []
            for visible_idx, _ in enumerate(visible_options):
                option_idx = top_index + visible_idx
                if option_idx not in highlighted:
                    continue
                row_y = top_y - visible_idx * line_height
                # Highlight rect spans the full interior width and one line.
                cs.set_non_stroking_color(self.HIGHLIGHT_COLOR)
                cs.add_rect(
                    1.0,
                    max(0.0, row_y - resolved_size * 0.15),
                    interior_w,
                    line_height,
                )
                cs.fill()

            # Row text.
            cs.begin_text()
            if color is not None:
                cs.set_non_stroking_color(color)
            else:
                cs.set_non_stroking_color((0.0,))
            cs.set_font(font, resolved_size)
            x = 2.0
            cs.new_line_at_offset(x, top_y)
            first = True
            for option in visible_options:
                if not first:
                    cs.new_line_at_offset(0.0, -line_height)
                first = False
                cs.show_text(option)
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
        is_multiline: bool = False,
        is_comb: bool = False,
        max_len: int = -1,
        quadding: int = 0,
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

        interior_w = max(0.0, width - 2.0)
        interior_h = max(0.0, height - 2.0)
        line_height = resolved_size * 1.15

        with PDAppearanceContentStream(appearance_stream) as cs:
            # /Tx BMC marked-content tag — Acrobat looks for this on form
            # field appearance streams.
            cs._buffer.extend(b"/Tx BMC\n")  # type: ignore[attr-defined]
            cs.save_graphics_state()
            # Light interior clip (1pt margin all around) so the value
            # never bleeds over the widget border.
            if interior_w > 0.0 and interior_h > 0.0:
                cs.add_rect(1.0, 1.0, interior_w, interior_h)
                cs._write_operator(b"W")  # type: ignore[attr-defined]
                cs._write_operator(b"n")  # type: ignore[attr-defined]

            if is_comb and max_len > 0:
                self._emit_comb_text(
                    cs, value, font, resolved_size, color,
                    width, height, max_len,
                )
            elif is_multiline:
                self._emit_multiline_text(
                    cs, value, font, resolved_size, color,
                    interior_w, height, line_height, quadding,
                )
            else:
                self._emit_single_line_text(
                    cs, value, font, resolved_size, color,
                    interior_w, height, quadding,
                )

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

    def _emit_single_line_text(
        self,
        cs: PDAppearanceContentStream,
        value: str,
        font: PDFont,
        size: float,
        color: tuple[float, ...] | None,
        interior_w: float,
        height: float,
        quadding: int,
    ) -> None:
        cs.begin_text()
        if color is not None:
            cs.set_non_stroking_color(color)
        cs.set_font(font, size)
        x = self._x_for_quadding(font, size, value, interior_w, quadding)
        y = max(2.0, (height - size) / 2.0)
        cs.new_line_at_offset(x, y)
        if value:
            cs.show_text(value)
        cs.end_text()

    def _emit_multiline_text(
        self,
        cs: PDAppearanceContentStream,
        value: str,
        font: PDFont,
        size: float,
        color: tuple[float, ...] | None,
        interior_w: float,
        height: float,
        line_height: float,
        quadding: int,
    ) -> None:
        lines = self._wrap_lines(value, font, size, max(interior_w, 1.0))
        cs.begin_text()
        if color is not None:
            cs.set_non_stroking_color(color)
        cs.set_font(font, size)
        # First baseline near the top of the rect; subsequent lines
        # advance downward by ``line_height``.
        top_y = max(2.0, height - size * 1.15)
        first_x = self._x_for_quadding(
            font, size, lines[0] if lines else "", interior_w, quadding
        )
        cs.new_line_at_offset(first_x, top_y)
        first = True
        prev_x = first_x
        for line in lines:
            line_x = self._x_for_quadding(
                font, size, line, interior_w, quadding
            )
            if not first:
                # Td is relative to start-of-line — undo the previous
                # quadding offset so the new x lands at ``line_x``.
                cs.new_line_at_offset(line_x - prev_x, -line_height)
            first = False
            prev_x = line_x
            if line:
                cs.show_text(line)
        cs.end_text()

    def _emit_comb_text(
        self,
        cs: PDAppearanceContentStream,
        value: str,
        font: PDFont,
        size: float,
        color: tuple[float, ...] | None,
        width: float,
        height: float,
        max_len: int,
    ) -> None:
        # Comb mode: PDF 32000-1 §12.7.3.3 — the field's value is split
        # into one-character-per-cell entries, each centered horizontally
        # within a 1/MaxLen wide cell.
        cell_w = width / float(max_len)
        y = max(2.0, (height - size) / 2.0)
        cs.begin_text()
        if color is not None:
            cs.set_non_stroking_color(color)
        cs.set_font(font, size)
        # Anchor at the absolute origin so each char's Td below is in
        # the same coord system.
        cs.new_line_at_offset(0.0, y)
        prev_x = 0.0
        chars = list(value or "")
        for idx, ch in enumerate(chars[:max_len]):
            ch_w = self._estimate_text_width(font, size, ch)
            cell_center = cell_w * (idx + 0.5)
            x = cell_center - ch_w / 2.0
            cs.new_line_at_offset(x - prev_x, 0.0)
            prev_x = x
            cs.show_text(ch)
        cs.end_text()

    def _x_for_quadding(
        self,
        font: PDFont,
        size: float,
        line: str,
        interior_w: float,
        quadding: int,
    ) -> float:
        """Pick the leftmost x-offset for ``line`` per ``/Q`` quadding.

        Quadding values per PDF 32000-1 §12.7.3.3:
        ``0`` = left, ``1`` = centered, ``2`` = right. Anything else
        falls back to left.
        """
        if quadding == 1 or quadding == 2:
            text_w = self._estimate_text_width(font, size, line)
            available = max(0.0, interior_w - text_w)
            if quadding == 1:
                return 2.0 + available / 2.0
            return 2.0 + available
        return 2.0

    def _wrap_lines(
        self,
        value: str,
        font: PDFont,
        size: float,
        interior_w: float,
    ) -> list[str]:
        """Word-wrap ``value`` onto lines that fit ``interior_w``.

        Splits on existing ``\\n`` first to preserve explicit line
        breaks, then word-wraps each resulting paragraph. Words wider
        than the rect are emitted on their own line (no mid-word break).
        """
        if not value:
            return [""]
        out: list[str] = []
        for paragraph in value.split("\n"):
            if not paragraph:
                out.append("")
                continue
            words = paragraph.split(" ")
            current = ""
            for word in words:
                candidate = word if not current else current + " " + word
                if self._estimate_text_width(font, size, candidate) <= interior_w:
                    current = candidate
                else:
                    if current:
                        out.append(current)
                    current = word
            if current:
                out.append(current)
        return out

    @staticmethod
    def _estimate_text_width(font: PDFont, size: float, text: str) -> float:
        """Estimate ``text`` width in user units at the given ``size``.

        Lite-port estimate: average-font-width per glyph (in 1/1000 em
        units) times the character count, scaled by ``size / 1000``.
        Falls back to ``size * 0.5`` when the font carries no widths
        (Standard 14 fonts without an explicit ``/Widths``).
        """
        if not text:
            return 0.0
        avg = font.get_average_font_width()
        if avg <= 0.0:
            avg = 500.0  # 0.5 em — plausible for Helvetica-style fonts
        return len(text) * avg * size / 1000.0

    # ------------------------------------------------------------------
    # push button (caption from /MK /CA)
    # ------------------------------------------------------------------

    def _generate_push_button(self, field: PDField) -> None:
        """Render the widget's ``/MK /CA`` caption flat-centered.

        For each widget:

        - If ``/MK /BG`` is set, fill the rect with the background color.
        - If ``/MK /BC`` is set, stroke a 1pt rectangular border.
        - Render ``/MK /CA`` (if present) as Helvetica text, font size
          auto-sized to the rect height, centered horizontally and
          vertically.

        Rollover (``/MK /RC``) and alternate / down (``/MK /AC``)
        captions stay deferred — viewers fall back to ``/CA`` when those
        entries are absent.
        """
        for widget in field.get_widgets():  # type: ignore[attr-defined]
            self._regenerate_push_button_widget(widget)

    def _regenerate_push_button_widget(self, widget: object) -> None:
        widget_cos = widget.get_cos_object()  # type: ignore[attr-defined]
        rect = _rect_from_cos(widget_cos.get_dictionary_object(_RECT))
        if rect is None:
            return
        llx, lly, urx, ury = rect
        width = urx - llx
        height = ury - lly
        if width <= 0.0 or height <= 0.0:
            return

        caption = ""
        bg: tuple[float, ...] | None = None
        bc: tuple[float, ...] | None = None
        ac = widget_cos.get_dictionary_object(_MK)
        if isinstance(ac, COSDictionary):
            ca = ac.get_string(COSName.get_pdf_name("CA"))
            if isinstance(ca, str):
                caption = ca
            bg = self._color_array_to_tuple(
                ac.get_dictionary_object(COSName.get_pdf_name("BG"))
            )
            bc = self._color_array_to_tuple(
                ac.get_dictionary_object(COSName.get_pdf_name("BC"))
            )

        appearance_cos = self._fresh_form_xobject(width, height)
        appearance_stream = PDAppearanceStream(appearance_cos)
        font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        size = self._auto_size(height)

        with PDAppearanceContentStream(appearance_stream) as cs:
            cs.save_graphics_state()
            # Background fill.
            if bg is not None:
                cs.set_non_stroking_color(bg)
                cs.add_rect(0.0, 0.0, width, height)
                cs.fill()
            # Border stroke (1pt inset by 0.5 so the stroke sits inside).
            if bc is not None:
                cs.set_stroking_color(bc)
                cs.set_line_width(1.0)
                cs.add_rect(0.5, 0.5, max(0.0, width - 1.0), max(0.0, height - 1.0))
                cs.stroke()
            # Caption.
            if caption:
                cs.begin_text()
                cs.set_non_stroking_color((0.0,))
                cs.set_font(font, size)
                text_w = self._estimate_text_width(font, size, caption)
                x = max(2.0, (width - text_w) / 2.0)
                y = max(2.0, (height - size) / 2.0)
                cs.new_line_at_offset(x, y)
                cs.show_text(caption)
                cs.end_text()
            cs.restore_graphics_state()

        ap_value = widget_cos.get_dictionary_object(_AP)
        if isinstance(ap_value, COSDictionary):
            ap_dict = PDAppearanceDictionary(ap_value)
        else:
            ap_dict = PDAppearanceDictionary()
            widget_cos.set_item(_AP, ap_dict.get_cos_object())
        ap_dict.set_normal_appearance(appearance_stream)

    @staticmethod
    def _color_array_to_tuple(value: COSBase | None) -> tuple[float, ...] | None:
        """Pull a ``/MK`` color array (1, 3, or 4 numeric entries) into
        a non-stroking-color components tuple. Returns ``None`` for
        empty / non-numeric arrays."""
        if not isinstance(value, COSArray):
            return None
        comps: list[float] = []
        for i in range(value.size()):
            entry = value.get_object(i)
            if isinstance(entry, (COSFloat, COSInteger)):
                comps.append(float(entry.value))
            else:
                return None
        if len(comps) in (1, 3, 4):
            return tuple(comps)
        return None

    # ------------------------------------------------------------------
    # signature field
    # ------------------------------------------------------------------

    def _generate_signature(self, field: PDField) -> None:
        """Render a flat name + date appearance for a signature field.

        Pulls ``/Name`` and ``/M`` (sign date) off the field's
        ``PDSignature`` ``/V`` value and writes them on two
        Helvetica-10 lines inside the widget rect. A 1pt border is
        stroked around the rect so unsigned-but-rendered widgets are
        still visible. Sigfields without a signature value get an
        empty stream (matches PDFBox's behavior of leaving an empty
        appearance until the field is signed).
        """
        from .pd_signature_field import PDSignatureField

        if not isinstance(field, PDSignatureField):
            return
        signature = field.get_signature()
        signer_name = signature.get_name() if signature is not None else None
        sign_date = signature.get_sign_date() if signature is not None else None

        for widget in field.get_widgets():
            self._regenerate_signature_widget(widget, signer_name, sign_date)

    # Default placeholder caption rendered for unsigned signature
    # widgets — matches Acrobat's "Sign here" hint.
    UNSIGNED_PLACEHOLDER: str = "Sign here"

    def _regenerate_signature_widget(
        self,
        widget: object,
        signer_name: str | None,
        sign_date: str | None,
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
        font = PDFontFactory.create_default_font(Standard14Fonts.HELVETICA)
        size = 10.0
        is_signed = bool(signer_name or sign_date)

        with PDAppearanceContentStream(appearance_stream) as cs:
            cs.save_graphics_state()
            # Frame the signature box with a thin border. Unsigned widgets
            # use a dashed outline so reviewers visually distinguish them
            # from signed-and-rendered widgets.
            cs.set_stroking_color((0.0,))
            cs._buffer.extend(b"1 w\n")  # type: ignore[attr-defined]
            if not is_signed:
                # 3-on / 3-off dashed line — Acrobat default for empty sigs.
                cs._buffer.extend(b"[3 3] 0 d\n")  # type: ignore[attr-defined]
            cs.add_rect(0.5, 0.5, max(0.0, width - 1.0), max(0.0, height - 1.0))
            cs.stroke()
            if not is_signed:
                # Reset the dash pattern so subsequent drawing inside the
                # appearance isn't unintentionally dashed.
                cs._buffer.extend(b"[] 0 d\n")  # type: ignore[attr-defined]

            if is_signed:
                cs.begin_text()
                cs.set_non_stroking_color((0.0,))
                cs.set_font(font, size)
                # Two-line layout: top line = signer name, bottom line = date.
                line_height = size * 1.4
                top_y = max(2.0, height - size * 1.4)
                cs.new_line_at_offset(4.0, top_y)
                cs.show_text(signer_name or "")
                cs.new_line_at_offset(0.0, -line_height)
                cs.show_text(sign_date or "")
                cs.end_text()
            else:
                # Unsigned placeholder — 50% gray "Sign here" centered in
                # the box. Helps Acrobat / Reader users locate empty
                # signature fields.
                placeholder_size = max(
                    self.AUTO_FONT_SIZE_MIN,
                    min(self.AUTO_FONT_SIZE_MAX, height * 0.5),
                )
                placeholder = self.UNSIGNED_PLACEHOLDER
                text_w = self._estimate_text_width(
                    font, placeholder_size, placeholder
                )
                x = max(2.0, (width - text_w) / 2.0)
                y = max(2.0, (height - placeholder_size) / 2.0)
                cs.begin_text()
                cs.set_non_stroking_color((0.5,))
                cs.set_font(font, placeholder_size)
                cs.new_line_at_offset(x, y)
                cs.show_text(placeholder)
                cs.end_text()

            cs.restore_graphics_state()

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
