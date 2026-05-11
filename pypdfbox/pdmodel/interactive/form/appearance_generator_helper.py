from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from .pd_appearance_generator import PDAppearanceGenerator

if TYPE_CHECKING:
    from .pd_default_appearance_string import PDDefaultAppearanceString
    from .pd_variable_text import PDVariableText


# Newline characters upstream's PATTERN regex matches (PDFBOX-3911):
# CRLF, LF, VT, FF, CR, NEL (U+0085), LS (U+2028), PS (U+2029).
# Single-line text fields collapse any of these to a single space.
_NEWLINE_PATTERN: re.Pattern[str] = re.compile(
    "\r\n|[\n\r  ]"
)


class AppearanceGeneratorHelper:
    """Create the AcroForm field appearance helper. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.form.AppearanceGeneratorHelper``
    (upstream lines 63–1051).

    The upstream helper is a per-field worker that composes a
    normal-appearance content stream from the field's ``/DA`` and
    value. In pypdfbox the same algorithm already ships as
    :class:`PDAppearanceGenerator` (the lite-port worker that is wired
    through :meth:`PDAcroForm.refresh_appearances`). This class is a
    thin façade exposing the upstream identifier and method shape on
    top of the existing worker so code ported from PDFBox can keep its
    original imports (``new AppearanceGeneratorHelper(field).setAppearanceValue(value)``).
    """

    # Upstream parity constants
    FONTSCALE: int = 1000
    DEFAULT_FONT_SIZE: float = 12.0
    MINIMUM_FONT_SIZE: float = 4.0
    DEFAULT_PADDING: float = 0.5
    HIGHLIGHT_COLOR: tuple[float, float, float] = (
        153.0 / 255.0,
        193.0 / 255.0,
        215.0 / 255.0,
    )

    def __init__(self, field: PDVariableText) -> None:
        """Bind the helper to ``field``. Mirrors upstream constructor
        (lines 112–127): captures the field and resolves the default
        appearance string."""
        self._field = field
        self._default_appearance: PDDefaultAppearanceString | None = None
        self._value: str = ""

        try:
            self._default_appearance = field.get_default_appearance_string()
        except OSError:
            # Match upstream: re-raise wrapped in OSError with context;
            # the lite port forwards the underlying error unchanged
            # because PDDefaultAppearanceString already tags its errors.
            raise
        except Exception:
            # Defensive: PDVariableText.get_default_appearance_string
            # may not be present on every field type in the lite port.
            self._default_appearance = None

    def get_field(self) -> PDVariableText:
        """Return the field this helper is bound to."""
        return self._field

    def get_default_appearance(self) -> PDDefaultAppearanceString | None:
        """Return the parsed default appearance string."""
        return self._default_appearance

    def get_value(self) -> str:
        """Return the most recently formatted appearance value."""
        return self._value

    def set_appearance_value(self, ap_value: str | None) -> None:
        """Compose the field's normal appearance stream for
        ``ap_value`` and install it on each widget. Mirrors upstream
        ``setAppearanceValue`` (lines 186–...).

        Single-line text fields collapse any newline-class character
        in the value to a single space (PDFBOX-3911). The actual
        content-stream emission is delegated to
        :class:`PDAppearanceGenerator`.
        """
        value = "" if ap_value is None else ap_value
        self._value = value

        generator = PDAppearanceGenerator()
        generator.set_appearance_value(self._field, value)

    @staticmethod
    def get_formatted_value(value: str) -> str:
        """Apply the upstream newline-collapse pattern to ``value``.
        Mirrors the regex applied by upstream's
        ``setAppearanceValue`` for single-line ``/Tx`` fields."""
        return _NEWLINE_PATTERN.sub(" ", value)

    # ------------------------------------------------------------------
    # Upstream parity surface. The real work is delegated to
    # ``PDAppearanceGenerator``; the stubs below match upstream's
    # private method shape so code ported from PDFBox can keep its
    # original call sites without losing semantic information.
    # ------------------------------------------------------------------

    def validate_and_ensure_acro_form_resources(self) -> None:
        """Hoist widget-level fonts onto the AcroForm-level resource
        dictionary. Mirrors upstream lines 133–178."""
        field = self._field
        try:
            acro_form = field.get_acro_form()
        except AttributeError:
            return
        if acro_form is None:
            return
        acro_form_resources = acro_form.get_default_resources()
        if acro_form_resources is None:
            return
        for widget in field.get_widgets():
            try:
                stream = widget.get_normal_appearance_stream()
            except AttributeError:
                continue
            if stream is None:
                continue
            widget_resources = stream.get_resources()
            if widget_resources is None:
                continue
            for font_name in widget_resources.get_font_names():
                if acro_form_resources.get_font(font_name) is None:
                    acro_form_resources.put(
                        font_name, widget_resources.get_font(font_name)
                    )

    @staticmethod
    def is_valid_appearance_stream(appearance: Any) -> bool:
        """Return ``True`` when ``appearance`` is a stream with a
        non-degenerate bounding box. Mirrors upstream lines 292–308."""
        if appearance is None:
            return False
        try:
            if not appearance.is_stream():
                return False
            bbox = appearance.get_appearance_stream().get_b_box()
        except AttributeError:
            return False
        if bbox is None:
            return False
        return abs(bbox.get_width()) > 0 and abs(bbox.get_height()) > 0

    def prepare_normal_appearance_stream(self, widget: Any) -> Any:
        """Build a fresh ``PDAppearanceStream`` sized to the widget's
        rectangle. Mirrors upstream lines 310–332."""
        return PDAppearanceGenerator()._fresh_form_xobject(
            float(widget.get_rectangle().get_width()),
            float(widget.get_rectangle().get_height()),
        )

    def get_widget_default_appearance_string(self, widget: Any) -> Any:
        """Return a per-widget default appearance string. Mirrors
        upstream lines 334–339."""
        from pypdfbox.cos import COSName

        from .pd_default_appearance_string import PDDefaultAppearanceString

        da = widget.get_cos_object().get_dictionary_object(COSName.DA)
        dr = self._field.get_acro_form().get_default_resources()
        return PDDefaultAppearanceString(da, dr)

    @staticmethod
    def resolve_rotation(widget: Any) -> int:
        """Return the widget's appearance rotation. Mirrors upstream
        lines 341–350."""
        characteristics = widget.get_appearance_characteristics()
        if characteristics is not None:
            return characteristics.get_rotation()
        return 0

    def initialize_appearance_content(
        self,
        widget: Any,
        appearance_characteristics: Any,
        appearance_stream: Any,
    ) -> None:
        """Stub for upstream's appearance-shell initialiser (lines
        364–429). The pypdfbox port delegates to
        :class:`PDAppearanceGenerator`."""
        generator = PDAppearanceGenerator()
        generator.set_appearance_value(self._field, self._value)

    def set_appearance_content(
        self,
        widget: Any,
        appearance_stream: Any,
    ) -> None:
        """Stub for upstream's BMC/EMC splicing routine (lines 434–477).
        The pypdfbox port regenerates the whole appearance via
        :class:`PDAppearanceGenerator`."""
        generator = PDAppearanceGenerator()
        generator.set_appearance_value(self._field, self._value)

    def insert_generated_appearance(
        self,
        widget: Any,
        appearance_stream: Any,
        output: Any,
    ) -> None:
        """Stub for upstream's text emission routine (lines 482–638)."""
        generator = PDAppearanceGenerator()
        generator.set_appearance_value(self._field, self._value)

    def get_text_align(self, widget: Any) -> int:
        """Return the per-widget quadding value, falling back to the
        field. Mirrors upstream lines 646–650."""
        from pypdfbox.cos import COSName

        cos = widget.get_cos_object()
        try:
            field_q = self._field.get_q()
        except AttributeError:
            field_q = 0
        return cos.get_int(COSName.Q, field_q)

    def calculate_matrix(self, bbox: Any, rotation: int) -> tuple[
        float, float, float, float, float, float
    ]:
        """Return a 6-tuple matrix for ``rotation``. Mirrors upstream
        lines 653–677."""
        import math

        if rotation == 0:
            return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        tx = 0.0
        ty = 0.0
        if rotation == 90:
            tx = bbox.get_upper_right_y()
        elif rotation == 180:
            tx = bbox.get_upper_right_y()
            ty = bbox.get_upper_right_x()
        elif rotation == 270:
            ty = bbox.get_upper_right_x()
        rad = math.radians(rotation)
        cos_r = math.cos(rad)
        sin_r = math.sin(rad)
        return (cos_r, sin_r, -sin_r, cos_r, tx, ty)

    def is_multi_line(self) -> bool:
        """``True`` if the field is a multiline text field. Mirrors
        upstream lines 679–682."""
        from .pd_text_field import PDTextField

        return (
            isinstance(self._field, PDTextField)
            and self._field.is_multiline()
        )

    def shall_comb(self) -> bool:
        """``True`` if the field is a comb text field. Mirrors upstream
        lines 696–704."""
        from .pd_text_field import PDTextField

        field = self._field
        if not isinstance(field, PDTextField):
            return False
        return (
            field.is_comb()
            and field.get_max_len() != -1
            and not field.is_multiline()
            and not field.is_password()
            and not field.is_file_select()
        )

    def insert_generated_comb_appearance(
        self,
        contents: Any,
        appearance_stream: Any,
        font: Any,
        font_size: float,
    ) -> None:
        """Stub for upstream's comb-text emitter (lines 715–768)."""
        generator = PDAppearanceGenerator()
        generator.set_appearance_value(self._field, self._value)

    def insert_generated_listbox_selection_highlight(
        self,
        contents: Any,
        appearance_stream: Any,
        font: Any,
        font_size: float,
    ) -> None:
        """Stub for upstream's listbox-highlight emitter (lines 770–809)."""
        return None

    def insert_generated_listbox_appearance(
        self,
        contents: Any,
        appearance_stream: Any,
        content_rect: Any,
        font: Any,
        font_size: float,
    ) -> None:
        """Stub for upstream's listbox-option emitter (lines 812–866)."""
        generator = PDAppearanceGenerator()
        generator.set_appearance_value(self._field, self._value)

    @staticmethod
    def write_to_stream(data: bytes, appearance_stream: Any) -> None:
        """Replace ``appearance_stream``'s payload with ``data``. Mirrors
        upstream lines 873–879."""
        cos = appearance_stream.get_cos_object()
        with cos.create_output_stream() as out:
            out.write(data)

    def calculate_font_size(self, font: Any, content_rect: Any) -> float:
        """Resolve a non-zero font size for ``content_rect``. Mirrors
        upstream lines 888–957 — pypdfbox uses
        :meth:`PDAppearanceGenerator._auto_size` for the same purpose."""
        if self._default_appearance is None:
            return self.DEFAULT_FONT_SIZE
        size = self._default_appearance.get_font_size()
        if size != 0:
            return float(size)
        try:
            height = float(content_rect.get_height())
        except AttributeError:
            return self.DEFAULT_FONT_SIZE
        return PDAppearanceGenerator._auto_size(height)

    @staticmethod
    def resolve_cap_height(font: Any) -> float:
        """Estimate cap-height via the "H" glyph. Mirrors upstream
        lines 964–966."""
        return AppearanceGeneratorHelper.resolve_glyph_height(
            font, ord("H")
        )

    @staticmethod
    def resolve_descent(font: Any) -> float:
        """Estimate descent via the difference between "y" and "a".
        Mirrors upstream lines 973–975."""
        return AppearanceGeneratorHelper.resolve_glyph_height(
            font, ord("y")
        ) - AppearanceGeneratorHelper.resolve_glyph_height(font, ord("a"))

    @staticmethod
    def resolve_glyph_height(font: Any, code: int) -> float:
        """Glyph height for ``code``. Mirrors upstream lines 978–1018.
        Returns -1.0 when no path is available (matches upstream)."""
        try:
            path = font.get_path(code)
        except (AttributeError, OSError):
            path = None
        if path is None:
            return -1.0
        try:
            return float(path.get_bounds_2d().get_height())
        except AttributeError:
            try:
                return float(path.height)
            except AttributeError:
                return -1.0

    @staticmethod
    def resolve_bounding_box(
        field_widget: Any, appearance_stream: Any
    ) -> Any:
        """Return ``appearance_stream``'s bounding box, falling back to
        the widget's translated rectangle. Mirrors upstream lines
        1027–1036."""
        bbox = appearance_stream.get_b_box()
        if bbox is None:
            bbox = field_widget.get_rectangle().create_retranslated_rectangle()
        return bbox

    @staticmethod
    def apply_padding(box: Any, padding: float) -> Any:
        """Return a new rectangle with ``padding`` units of inset on
        each side. Mirrors upstream lines 1044–1050."""
        from pypdfbox.pdmodel.common import PDRectangle

        return PDRectangle(
            box.get_lower_left_x() + padding,
            box.get_lower_left_y() + padding,
            box.get_width() - 2 * padding,
            box.get_height() - 2 * padding,
        )


__all__ = ["AppearanceGeneratorHelper"]
