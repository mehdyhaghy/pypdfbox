from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSName,
    COSNumber,
)

from pypdfbox.pdmodel.graphics.blend_mode import BlendMode

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
    from pypdfbox.pdmodel.graphics.state.pd_font_setting import PDFontSetting

# Single-letter / short name keys defined by PDF spec for the ExtGState
# dictionary. Local aliases keep the wrappers terse without polluting
# COSName's predefined set with names only this module needs.
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_EXT_G_STATE: COSName = COSName.get_pdf_name("ExtGState")
_LW: COSName = COSName.get_pdf_name("LW")
_LC: COSName = COSName.get_pdf_name("LC")
_LJ: COSName = COSName.get_pdf_name("LJ")
_ML: COSName = COSName.get_pdf_name("ML")
_D: COSName = COSName.D  # type: ignore[attr-defined]
_RI: COSName = COSName.get_pdf_name("RI")
_OP: COSName = COSName.get_pdf_name("OP")
_OP_NS: COSName = COSName.get_pdf_name("op")
_OPM: COSName = COSName.get_pdf_name("OPM")
_FONT: COSName = COSName.get_pdf_name("Font")
_FL: COSName = COSName.get_pdf_name("FL")
_SM: COSName = COSName.get_pdf_name("SM")
_SA: COSName = COSName.get_pdf_name("SA")
_CA: COSName = COSName.get_pdf_name("CA")
_CA_NS: COSName = COSName.get_pdf_name("ca")
_AIS: COSName = COSName.get_pdf_name("AIS")
_TK: COSName = COSName.get_pdf_name("TK")
_BM: COSName = COSName.get_pdf_name("BM")


class PDExtendedGraphicsState:
    """An extended graphics state dictionary. Mirrors PDFBox
    ``PDExtendedGraphicsState``.

    This is a "lite" port: line dash pattern is exposed as the raw
    ``COSArray`` (full ``PDLineDashPattern`` typed wrapper deferred), the
    ``/Font`` entry exposes raw font + size helpers (full
    ``PDFontSetting`` deferred). There is not yet a public
    ``PDGraphicsState`` port, so ``copy_into_graphics_state`` accepts
    objects with matching snake_case setters/attributes or a mutable
    mapping. Soft mask / transfer function support is deferred.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _EXT_G_STATE)

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- copyIntoGraphicsState ----------

    def copy_into_graphics_state(self, graphics_state: Any) -> None:
        """Apply entries from this ExtGState to ``graphics_state``.

        Upstream PDFBox targets ``PDGraphicsState`` directly. Until that
        class exists here, this method copies only keys represented by this
        lite wrapper and only when the target exposes a matching setter,
        existing attribute, text-state setter/attribute, or mutable mapping
        slot.
        """

        for key in self._dict.key_set():
            if key == _LW:
                self._copy_value(
                    graphics_state, "set_line_width", "line_width", self.get_line_width()
                )
            elif key == _LC:
                self._copy_value(
                    graphics_state, "set_line_cap", "line_cap", self.get_line_cap_style()
                )
            elif key == _LJ:
                self._copy_value(
                    graphics_state, "set_line_join", "line_join", self.get_line_join_style()
                )
            elif key == _ML:
                self._copy_value(
                    graphics_state, "set_miter_limit", "miter_limit", self.get_miter_limit()
                )
            elif key == _D:
                self._copy_value(
                    graphics_state,
                    "set_line_dash_pattern",
                    "line_dash_pattern",
                    self.get_line_dash_pattern(),
                )
            elif key == _RI:
                self._copy_value(
                    graphics_state,
                    "set_rendering_intent",
                    "rendering_intent",
                    self.get_rendering_intent(),
                )
            elif key == _OP:
                self._copy_value(
                    graphics_state,
                    "set_stroking_overprint_control",
                    "stroking_overprint_control",
                    self.get_strokeOverprint(),
                )
            elif key == _OP_NS:
                self._copy_value(
                    graphics_state,
                    "set_non_stroking_overprint_control",
                    "non_stroking_overprint_control",
                    self.get_non_stroking_overprint(),
                )
            elif key == _OPM:
                self._copy_value(
                    graphics_state,
                    "set_overprint_mode",
                    "overprint_mode",
                    self.get_overprint_mode(),
                )
            elif key == _FONT:
                self._copy_font_setting(graphics_state)
            elif key == _FL:
                self._copy_value(
                    graphics_state, "set_flatness", "flatness", self.get_flatness()
                )
            elif key == _SM:
                self._copy_value(
                    graphics_state, "set_smoothness", "smoothness", self.get_smoothness()
                )
            elif key == _SA:
                self._copy_value(
                    graphics_state,
                    "set_stroke_adjustment",
                    "stroke_adjustment",
                    self.get_stroke_adjustment(),
                )
            elif key == _CA:
                copied = self._copy_value(
                    graphics_state,
                    "set_alpha_constants",
                    "alpha_constants",
                    self.get_stroking_alpha_constant(),
                )
                if not copied:
                    self._copy_value(
                        graphics_state,
                        "set_stroking_alpha_constant",
                        "stroking_alpha_constant",
                        self.get_stroking_alpha_constant(),
                    )
            elif key == _CA_NS:
                copied = self._copy_value(
                    graphics_state,
                    "set_non_stroke_alpha_constants",
                    "non_stroke_alpha_constants",
                    self.get_non_stroking_alpha_constant(),
                )
                if not copied:
                    self._copy_value(
                        graphics_state,
                        "set_non_stroking_alpha_constant",
                        "non_stroking_alpha_constant",
                        self.get_non_stroking_alpha_constant(),
                    )
            elif key == _AIS:
                copied = self._copy_value(
                    graphics_state,
                    "set_alpha_source",
                    "alpha_source",
                    self.get_alpha_source_flag(),
                )
                if not copied:
                    self._copy_value(
                        graphics_state,
                        "set_alpha_source_flag",
                        "alpha_source_flag",
                        self.get_alpha_source_flag(),
                    )
            elif key == _TK:
                copied = self._copy_text_value(
                    graphics_state,
                    "set_knockout_flag",
                    "knockout_flag",
                    self.get_text_knockout_flag(),
                )
                if not copied:
                    self._copy_value(
                        graphics_state,
                        "set_text_knockout_flag",
                        "text_knockout_flag",
                        self.get_text_knockout_flag(),
                    )
            elif key == _BM:
                self._copy_value(
                    graphics_state, "set_blend_mode", "blend_mode", self.get_blend_mode()
                )

    @staticmethod
    def _copy_value(
        target: Any, setter_name: str, attribute_name: str, value: Any
    ) -> bool:
        if value is None:
            return False
        if isinstance(target, MutableMapping):
            target[attribute_name] = value
            return True
        setter = getattr(target, setter_name, None)
        if callable(setter):
            setter(value)
            return True
        if hasattr(target, attribute_name):
            setattr(target, attribute_name, value)
            return True
        return False

    @staticmethod
    def _get_text_state(target: Any) -> Any | None:
        if isinstance(target, MutableMapping):
            return target.get("text_state")
        getter = getattr(target, "get_text_state", None)
        if callable(getter):
            return getter()
        return getattr(target, "text_state", None)

    def _copy_text_value(
        self, target: Any, setter_name: str, attribute_name: str, value: Any
    ) -> bool:
        text_state = self._get_text_state(target)
        if text_state is not None and self._copy_value(
            text_state, setter_name, attribute_name, value
        ):
            return True
        return self._copy_value(target, setter_name, attribute_name, value)

    def _copy_font_setting(self, target: Any) -> None:
        font = self.get_font()
        size = self.get_font_size()
        if not self._copy_text_value(target, "set_font", "font", font):
            self._copy_value(target, "set_text_font", "text_font", font)
        if not self._copy_text_value(target, "set_font_size", "font_size", size):
            self._copy_value(target, "set_text_font_size", "text_font_size", size)

    # ---------- private float helpers (mirrors upstream getFloatItem/setFloatItem) ----------

    def _get_float_item(self, key: COSName) -> float | None:
        base = self._dict.get_dictionary_object(key)
        if isinstance(base, COSNumber):
            return float(base.value)
        return None

    def _set_float_item(self, key: COSName, value: float | None) -> None:
        if value is None:
            self._dict.remove_item(key)
        else:
            self._dict.set_item(key, COSFloat(float(value)))

    # ---------- LW ----------

    def get_line_width(self) -> float | None:
        return self._get_float_item(_LW)

    def set_line_width(self, width: float | None) -> None:
        self._set_float_item(_LW, width)

    # ---------- LC ----------

    def get_line_cap_style(self) -> int | None:
        base = self._dict.get_dictionary_object(_LC)
        if isinstance(base, COSNumber):
            return int(base.value)
        return None

    def set_line_cap_style(self, style: int) -> None:
        self._dict.set_int(_LC, int(style))

    # ---------- LJ ----------

    def get_line_join_style(self) -> int | None:
        base = self._dict.get_dictionary_object(_LJ)
        if isinstance(base, COSNumber):
            return int(base.value)
        return None

    def set_line_join_style(self, style: int) -> None:
        self._dict.set_int(_LJ, int(style))

    # ---------- ML ----------

    def get_miter_limit(self) -> float | None:
        return self._get_float_item(_ML)

    def set_miter_limit(self, miter_limit: float | None) -> None:
        self._set_float_item(_ML, miter_limit)

    # ---------- D (line dash pattern) ----------

    def get_line_dash_pattern(self) -> PDLineDashPattern | None:
        from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

        base = self._dict.get_dictionary_object(_D)
        if isinstance(base, COSArray):
            return PDLineDashPattern.from_cos_array(base)
        return None

    def set_line_dash_pattern(
        self, dash_pattern: PDLineDashPattern | COSArray | None
    ) -> None:
        if dash_pattern is None:
            self._dict.remove_item(_D)
            return
        if isinstance(dash_pattern, COSArray):
            self._dict.set_item(_D, dash_pattern)
            return
        self._dict.set_item(_D, dash_pattern.get_cos_array())

    # ---------- RI ----------

    def get_rendering_intent(self) -> str | None:
        return self._dict.get_name(_RI)

    def set_rendering_intent(self, ri: str | None) -> None:
        if ri is None:
            self._dict.remove_item(_RI)
        else:
            self._dict.set_name(_RI, ri)

    # ---------- CA (stroking alpha) ----------

    def get_stroking_alpha_constant(self) -> float | None:
        return self._get_float_item(_CA)

    def set_stroking_alpha_constant(self, alpha: float | None) -> None:
        self._set_float_item(_CA, alpha)

    # ---------- ca (non-stroking alpha) ----------

    def get_non_stroking_alpha_constant(self) -> float | None:
        return self._get_float_item(_CA_NS)

    def set_non_stroking_alpha_constant(self, alpha: float | None) -> None:
        self._set_float_item(_CA_NS, alpha)

    # ---------- BM (blend mode) ----------

    def get_blend_mode(self) -> BlendMode | None:
        return BlendMode.from_cos(self._dict.get_dictionary_object(_BM))

    def set_blend_mode(self, bm: BlendMode | COSName | str | None) -> None:
        if bm is None:
            self._dict.remove_item(_BM)
            return
        if isinstance(bm, BlendMode):
            self._dict.set_item(_BM, bm.get_cos_name())
            return
        if isinstance(bm, COSName):
            self._dict.set_item(_BM, bm)
            return
        self._dict.set_name(_BM, bm)

    # ---------- AIS (alpha source flag) ----------

    def get_alpha_source_flag(self) -> bool:
        return self._dict.get_boolean(_AIS, False)

    def set_alpha_source_flag(self, alpha: bool) -> None:
        self._dict.set_boolean(_AIS, bool(alpha))

    # ---------- TK (text knockout flag) — upstream defaults to True ----------

    def get_text_knockout_flag(self) -> bool:
        return self._dict.get_boolean(_TK, True)

    def set_text_knockout_flag(self, tk: bool) -> None:
        self._dict.set_boolean(_TK, bool(tk))

    # ---------- SA (automatic stroke adjustment) ----------

    def get_stroke_adjustment(self) -> bool:
        return self._dict.get_boolean(_SA, False)

    def set_stroke_adjustment(self, sa: bool) -> None:
        self._dict.set_boolean(_SA, bool(sa))

    # ---------- OPM (overprint mode) ----------

    def get_overprint_mode(self) -> int:
        base = self._dict.get_dictionary_object(_OPM)
        if isinstance(base, COSNumber):
            return int(base.value)
        return 0

    def set_overprint_mode(self, om: int | None) -> None:
        if om is None:
            self._dict.remove_item(_OPM)
        else:
            self._dict.set_int(_OPM, int(om))

    # ---------- OP (stroking overprint) ----------

    def get_strokeOverprint(self) -> bool:  # noqa: N802 - upstream-style accessor name preserved
        return self._dict.get_boolean(_OP, False)

    def set_stroke_overprint(self, op: bool) -> None:
        self._dict.set_boolean(_OP, bool(op))

    # ---------- op (non-stroking overprint) ----------

    def get_non_stroking_overprint(self) -> bool:
        # Upstream falls back to the stroking overprint when /op is absent.
        return self._dict.get_boolean(_OP_NS, self.get_strokeOverprint())

    def set_non_stroking_overprint(self, op: bool) -> None:
        self._dict.set_boolean(_OP_NS, bool(op))

    # ---------- SM (smoothness tolerance) ----------

    def get_smoothness(self) -> float:
        v = self._get_float_item(_SM)
        return v if v is not None else 0.0

    def set_smoothness(self, s: float | None) -> None:
        self._set_float_item(_SM, s)

    # ---------- FL (flatness tolerance) ----------

    def get_flatness(self) -> float:
        v = self._get_float_item(_FL)
        return v if v is not None else 1.0

    def set_flatness(self, f: float | None) -> None:
        self._set_float_item(_FL, f)

    # ---------- /Font helper (size only — full PDFontSetting deferred) ----------

    def get_font(self) -> COSBase | None:
        base = self._dict.get_dictionary_object(_FONT)
        if isinstance(base, COSArray) and base.size() >= 1:
            return base.get_object(0)
        return None

    def set_font(self, font: COSBase | None) -> None:
        if font is None:
            self._dict.remove_item(_FONT)
            return
        base = self._dict.get_dictionary_object(_FONT)
        if not isinstance(base, COSArray):
            base = COSArray()
            self._dict.set_item(_FONT, base)
        base.grow_to_size(2)
        base.set(0, font)

    def get_font_size(self) -> float | None:
        base = self._dict.get_dictionary_object(_FONT)
        if isinstance(base, COSArray) and base.size() >= 2:
            entry = base.get_object(1)
            if isinstance(entry, COSNumber):
                return float(entry.value)
        return None

    def set_font_size(self, size: float) -> None:
        base = self._dict.get_dictionary_object(_FONT)
        if not isinstance(base, COSArray):
            base = COSArray()
            base.grow_to_size(2)
            self._dict.set_item(_FONT, base)
        else:
            base.grow_to_size(2)
        base.set(1, COSFloat(float(size)))

    # ---------- /Font (typed PDFontSetting wrapper) ----------

    def get_font_setting(self) -> PDFontSetting | None:
        from pypdfbox.pdmodel.graphics.state.pd_font_setting import PDFontSetting

        base = self._dict.get_dictionary_object(_FONT)
        if isinstance(base, COSArray):
            return PDFontSetting(base)
        return None

    def set_font_setting(self, setting: PDFontSetting | None) -> None:
        if setting is None:
            self._dict.remove_item(_FONT)
            return
        self._dict.set_item(_FONT, setting.get_cos_object())


__all__ = ["PDExtendedGraphicsState"]
