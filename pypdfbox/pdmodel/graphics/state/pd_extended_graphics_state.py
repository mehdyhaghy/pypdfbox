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
    from pypdfbox.pdmodel.graphics.state.rendering_intent import RenderingIntent

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
_SMASK: COSName = COSName.get_pdf_name("SMask")
_TR: COSName = COSName.get_pdf_name("TR")
_TR2: COSName = COSName.get_pdf_name("TR2")
_HT: COSName = COSName.get_pdf_name("HT")
_HTO: COSName = COSName.get_pdf_name("HTO")
_UCR: COSName = COSName.get_pdf_name("UCR")
_UCR2: COSName = COSName.get_pdf_name("UCR2")
_BG: COSName = COSName.get_pdf_name("BG")
_BG2: COSName = COSName.get_pdf_name("BG2")
# Apple-specific advanced-annotations key (PDFBox PDFBOX-3017 / ISO 32000-2
# §11.6.8). Upstream stores it as the literal string ``AAPL:AA``.
_AAPL_AA: COSName = COSName.get_pdf_name("AAPL:AA")


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

    # ---------- line cap style codes (PDF 32000-1 §8.4.3.3, Table 54) ----------
    # The integer values stored in the ``/LC`` entry. Provided as named
    # constants so callers don't have to hard-code magic numbers — upstream
    # PDFBox uses raw ints throughout, but the Pythonic spelling makes
    # ``set_line_cap_style(PDExtendedGraphicsState.BUTT_CAP)`` self-documenting.
    BUTT_CAP: int = 0
    ROUND_CAP: int = 1
    PROJECTING_SQUARE_CAP: int = 2

    # ---------- line join style codes (PDF 32000-1 §8.4.3.4, Table 55) ----------
    MITER_JOIN: int = 0
    ROUND_JOIN: int = 1
    BEVEL_JOIN: int = 2

    def __init__(
        self,
        dictionary: COSDictionary | None = None,
        resource_cache: Any | None = None,
    ) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _EXT_G_STATE)
        # Optional resource cache — mirrors the upstream two-arg
        # constructor. Forwarded to :meth:`get_soft_mask_typed` so cached
        # form XObjects survive activation.
        self._resource_cache = resource_cache

    def get_resource_cache(self) -> Any | None:
        """Return the optional resource cache passed at construction
        time. Mirrors upstream's package-private ``cache`` field —
        exposed publicly for parity with renderer / soft-mask plumbing.
        """
        return self._resource_cache

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
                # Upstream applies ``defaultIfNull(getLineWidth(), 1)``
                # so a malformed /LW (key present, value not a number)
                # still pushes the spec default of 1 into the graphics
                # state. PDF 32000-1 §8.4.3.2 Table 52: default 1.0.
                self._copy_value(
                    graphics_state,
                    "set_line_width",
                    "line_width",
                    self._default_if_none(self.get_line_width(), 1.0),
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
                # PDF 32000-1 §8.4.3.5 Table 52: miter limit default 10.0.
                self._copy_value(
                    graphics_state,
                    "set_miter_limit",
                    "miter_limit",
                    self._default_if_none(self.get_miter_limit(), 10.0),
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
                # PDF 32000-1 §10.6.2 Table 52: flatness default 1.0.
                # Upstream's ``defaultIfNull`` ensures a malformed /FL still
                # forwards the default rather than skipping the setter.
                self._copy_value(
                    graphics_state,
                    "set_flatness",
                    "flatness",
                    self._default_if_none(self.get_flatness(), 1.0),
                )
            elif key == _SM:
                # PDF 32000-1 §10.7.2 Table 52: smoothness default 0.
                self._copy_value(
                    graphics_state,
                    "set_smoothness",
                    "smoothness",
                    self._default_if_none(self.get_smoothness(), 0.0),
                )
            elif key == _SA:
                self._copy_value(
                    graphics_state,
                    "set_stroke_adjustment",
                    "stroke_adjustment",
                    self.get_stroke_adjustment(),
                )
            elif key == _CA:
                # PDF 32000-1 §11.6.4.4 Table 52: stroking alpha default 1.0.
                stroking_alpha = self._default_if_none(
                    self.get_stroking_alpha_constant(), 1.0
                )
                copied = self._copy_value(
                    graphics_state,
                    "set_alpha_constants",
                    "alpha_constants",
                    stroking_alpha,
                )
                if not copied:
                    self._copy_value(
                        graphics_state,
                        "set_stroking_alpha_constant",
                        "stroking_alpha_constant",
                        stroking_alpha,
                    )
            elif key == _CA_NS:
                # PDF 32000-1 §11.6.4.4 Table 52: non-stroking alpha default 1.0.
                non_stroking_alpha = self._default_if_none(
                    self.get_non_stroking_alpha_constant(), 1.0
                )
                copied = self._copy_value(
                    graphics_state,
                    "set_non_stroke_alpha_constants",
                    "non_stroke_alpha_constants",
                    non_stroking_alpha,
                )
                if not copied:
                    self._copy_value(
                        graphics_state,
                        "set_non_stroking_alpha_constant",
                        "non_stroking_alpha_constant",
                        non_stroking_alpha,
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
            elif key == _TR:
                # Per PDF 32000-1 §11.7.5.3: "If both TR and TR2 are present
                # in the same graphics state parameter dictionary, TR2 shall
                # take precedence." Skip /TR when /TR2 is also present so the
                # /TR2 branch wins.
                if self._dict.contains_key(_TR2):
                    continue
                self._copy_value(
                    graphics_state, "set_transfer", "transfer", self.get_transfer()
                )
            elif key == _TR2:
                self._copy_value(
                    graphics_state, "set_transfer", "transfer", self.get_transfer2()
                )

    @staticmethod
    def _default_if_none(value: float | None, default: float) -> float:
        """Mirror upstream private ``defaultIfNull(Float, float)``.

        Returns ``value`` when not ``None``, otherwise ``default``.
        Used by :meth:`copy_into_graphics_state` to push spec defaults
        for /LW, /ML, /FL, /SM, /CA, /CA_NS when the dictionary entry is
        present but the value is missing or malformed (matches the
        Java unboxing-with-default pattern).
        """
        return default if value is None else value

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
        # Mirror upstream's defensive shape check: a malformed ``/D`` entry
        # (size != 2, or wrong inner types) silently returns ``None`` rather
        # than raising — PDF readers must tolerate broken ExtGState entries
        # so the rest of the dictionary stays usable. PDFBox's
        # ``getLineDashPattern`` returns ``null`` in exactly these cases.
        if not isinstance(base, COSArray) or base.size() != 2:
            return None
        inner = base.get_object(0)
        phase = base.get_object(1)
        if not isinstance(inner, COSArray):
            return None
        if not isinstance(phase, COSNumber):
            return None
        return PDLineDashPattern.from_cos_array(base)

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

    def set_rendering_intent(self, ri: RenderingIntent | str | None) -> None:
        from pypdfbox.pdmodel.graphics.state.rendering_intent import (  # noqa: PLC0415
            RenderingIntent,
        )

        if ri is None:
            self._dict.remove_item(_RI)
            return
        if isinstance(ri, RenderingIntent):
            self._dict.set_name(_RI, ri.string_value())
            return
        self._dict.set_name(_RI, ri)

    def get_rendering_intent_typed(self) -> RenderingIntent | None:
        """Return ``/RI`` resolved to the typed :class:`RenderingIntent`
        enum, or ``None`` when ``/RI`` is absent.

        Mirrors upstream ``getRenderingIntent()`` which returns the enum
        directly. Companion to :meth:`get_rendering_intent` (which keeps
        the raw string for back-compat with earlier waves). Per PDF
        32000-1 §8.6.5.8, an unrecognised name is mapped to
        :attr:`RenderingIntent.RELATIVE_COLORIMETRIC`.
        """
        from pypdfbox.pdmodel.graphics.state.rendering_intent import (  # noqa: PLC0415
            RenderingIntent,
        )

        ri = self._dict.get_name(_RI)
        if ri is None:
            return None
        return RenderingIntent.from_string(ri)

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

    def get_stroke_overprint(self) -> bool:
        """Snake_case spelling of :meth:`get_strokeOverprint` for callers
        that prefer PEP 8 style. Behaviour is identical — both read the
        ``/OP`` boolean (default ``False``).
        """
        return self.get_strokeOverprint()

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

    # ---------- Aliases mirroring upstream PDFBox 3.0.x naming ----------

    # Upstream renamed several boolean accessors to *_control / *_tolerance /
    # automatic_* variants. Keep both spellings so existing call sites continue
    # to work while new code can use the upstream-preferred name.

    def get_stroking_overprint_control(self) -> bool:
        """Mirror upstream ``getStrokingOverprintControl()`` (alias of ``get_strokeOverprint``)."""
        return self.get_strokeOverprint()

    def set_stroking_overprint_control(self, op: bool) -> None:
        """Mirror upstream ``setStrokingOverprintControl()`` (alias of ``set_stroke_overprint``)."""
        self.set_stroke_overprint(op)

    def get_non_stroking_overprint_control(self) -> bool:
        """Mirror upstream ``getNonStrokingOverprintControl()``.

        Upstream falls back to the stroking overprint when ``/op`` is absent;
        this delegates to ``get_non_stroking_overprint`` which already has
        that behaviour.
        """
        return self.get_non_stroking_overprint()

    def set_non_stroking_overprint_control(self, op: bool) -> None:
        self.set_non_stroking_overprint(op)

    def get_flatness_tolerance(self) -> float:
        """Mirror upstream ``getFlatnessTolerance()`` (alias of ``get_flatness``)."""
        return self.get_flatness()

    def set_flatness_tolerance(self, f: float | None) -> None:
        self.set_flatness(f)

    def get_smoothness_tolerance(self) -> float:
        """Mirror upstream ``getSmoothnessTolerance()`` (alias of ``get_smoothness``)."""
        return self.get_smoothness()

    def set_smoothness_tolerance(self, s: float | None) -> None:
        self.set_smoothness(s)

    def get_automatic_stroke_adjustment(self) -> bool:
        """Mirror upstream ``getAutomaticStrokeAdjustment()`` (alias of
        ``get_stroke_adjustment``)."""
        return self.get_stroke_adjustment()

    def set_automatic_stroke_adjustment(self, sa: bool) -> None:
        self.set_stroke_adjustment(sa)

    # ---------- SMask (soft mask) ----------

    def get_soft_mask(self) -> COSBase | None:
        """Returns the raw ``/SMask`` entry.

        Upstream returns a ``PDSoftMask`` typed wrapper which is not yet
        ported here; callers receive the raw COS object (a ``COSName``
        ``/None`` mask, or a ``COSDictionary`` describing a soft-mask
        dictionary). When ``/SMask`` is absent, returns ``None``.
        """
        return self._dict.get_dictionary_object(_SMASK)

    def set_soft_mask(self, mask: COSBase | None) -> None:
        if mask is None:
            self._dict.remove_item(_SMASK)
            return
        self._dict.set_item(_SMASK, mask)

    def get_soft_mask_typed(self) -> Any | None:
        """Return ``/SMask`` wrapped as :class:`PDSoftMask`, or ``None``
        for the literal ``/None`` mask name (or when ``/SMask`` is
        absent / not a soft-mask dictionary).

        Companion to :meth:`get_soft_mask` (which returns the raw COS
        object for upstream-parity tests). Mirrors upstream
        ``PDExtendedGraphicsState.getSoftMask()``'s typed return.
        """
        from pypdfbox.pdmodel.graphics.state.pd_soft_mask import (  # noqa: PLC0415
            PDSoftMask,
        )

        return PDSoftMask.create(self.get_soft_mask(), self._resource_cache)

    # ---------- TR / TR2 (transfer functions) ----------

    def get_transfer(self) -> COSBase | None:
        """Returns the raw ``/TR`` entry (transfer function).

        Per the PDF spec the value is one of: a function, an array of four
        functions, or the name ``/Identity``. Mirrors upstream:
        a ``COSArray`` whose size is not 4 is filtered out and ``None``
        is returned.
        """
        base = self._dict.get_dictionary_object(_TR)
        if isinstance(base, COSArray) and base.size() != 4:
            return None
        return base

    def set_transfer(self, transfer: COSBase | None) -> None:
        if transfer is None:
            self._dict.remove_item(_TR)
            return
        self._dict.set_item(_TR, transfer)

    def get_transfer2(self) -> COSBase | None:
        """Returns the raw ``/TR2`` entry (transfer function).

        Per the PDF spec the value is one of: a function, an array of four
        functions, the name ``/Identity``, or the name ``/Default``.
        Mirrors upstream: a ``COSArray`` whose size is not 4 is filtered
        out and ``None`` is returned.
        """
        base = self._dict.get_dictionary_object(_TR2)
        if isinstance(base, COSArray) and base.size() != 4:
            return None
        return base

    def set_transfer2(self, transfer: COSBase | None) -> None:
        if transfer is None:
            self._dict.remove_item(_TR2)
            return
        self._dict.set_item(_TR2, transfer)

    def get_transfer_typed(self) -> Any | None:
        """Return ``/TR`` resolved to a typed :class:`PDFunction` (or list
        of four ``PDFunction`` instances when the entry is a 4-array).

        - ``None`` when the entry is absent or is a ``COSArray`` whose size
          is not 4 (mirrors :meth:`get_transfer` upstream-parity filter).
        - :class:`PDFunctionTypeIdentity` for the name ``/Identity``.
        - A list of four ``PDFunction`` instances when the entry is a
          4-array (one per process colorant; see PDF 32000-1 §11.7.5.3).
        - A single :class:`PDFunction` instance otherwise.

        Companion to :meth:`get_transfer` (raw COS access). Typed version
        deferred until Wave 42 — see CHANGES.md.
        """
        return self._resolve_transfer(self.get_transfer())

    def get_transfer2_typed(self) -> Any | None:
        """Return ``/TR2`` resolved to a typed :class:`PDFunction` (or list
        of four). See :meth:`get_transfer_typed` — only difference is the
        spec-allowed ``/Default`` name, which is returned as the raw
        ``COSName`` (no typed wrapper exists for /Default; callers compare
        by name).
        """
        return self._resolve_transfer(self.get_transfer2())

    @staticmethod
    def _resolve_transfer(base: COSBase | None) -> Any | None:
        from pypdfbox.pdmodel.common.function.pd_function import PDFunction  # noqa: PLC0415

        if base is None:
            return None
        if isinstance(base, COSName):
            # /Identity → typed identity function; /Default has no typed
            # wrapper so return the raw COSName for caller inspection.
            if base.get_name() == "Identity":
                return PDFunction.create(base)
            return base
        if isinstance(base, COSArray):
            # Already filtered to size==4 by get_transfer / get_transfer2.
            return [PDFunction.create(base.get_object(i)) for i in range(4)]
        return PDFunction.create(base)

    # ---------- BG / BG2 (black-generation functions) ----------

    def get_black_generation(self) -> COSBase | None:
        """Returns the raw ``/BG`` entry — a function (dictionary or
        stream). Per PDF 32000-1 §11.7.5.3, ``/BG`` is always a single
        function (no array, no name forms).
        """
        return self._dict.get_dictionary_object(_BG)

    def set_black_generation(self, function: COSBase | None) -> None:
        if function is None:
            self._dict.remove_item(_BG)
            return
        self._dict.set_item(_BG, function)

    def get_black_generation_typed(self) -> Any | None:
        from pypdfbox.pdmodel.common.function.pd_function import PDFunction  # noqa: PLC0415

        return PDFunction.create(self.get_black_generation())

    def get_black_generation2(self) -> COSBase | None:
        """Returns the raw ``/BG2`` entry — a function or the name
        ``/Default`` (PDF 32000-1 §11.7.5.3).
        """
        return self._dict.get_dictionary_object(_BG2)

    def set_black_generation2(self, function: COSBase | None) -> None:
        if function is None:
            self._dict.remove_item(_BG2)
            return
        self._dict.set_item(_BG2, function)

    def get_black_generation2_typed(self) -> Any | None:
        from pypdfbox.pdmodel.common.function.pd_function import PDFunction  # noqa: PLC0415

        base = self.get_black_generation2()
        if base is None:
            return None
        if isinstance(base, COSName):
            # /Default — no typed wrapper; return raw for caller inspection.
            return base
        return PDFunction.create(base)

    # ---------- UCR / UCR2 (undercolor-removal functions) ----------

    def get_undercolor_removal(self) -> COSBase | None:
        """Returns the raw ``/UCR`` entry — a single function (PDF
        32000-1 §11.7.5.3).
        """
        return self._dict.get_dictionary_object(_UCR)

    def set_undercolor_removal(self, function: COSBase | None) -> None:
        if function is None:
            self._dict.remove_item(_UCR)
            return
        self._dict.set_item(_UCR, function)

    def get_undercolor_removal_typed(self) -> Any | None:
        from pypdfbox.pdmodel.common.function.pd_function import PDFunction  # noqa: PLC0415

        return PDFunction.create(self.get_undercolor_removal())

    def get_undercolor_removal2(self) -> COSBase | None:
        """Returns the raw ``/UCR2`` entry — a function or the name
        ``/Default`` (PDF 32000-1 §11.7.5.3).
        """
        return self._dict.get_dictionary_object(_UCR2)

    def set_undercolor_removal2(self, function: COSBase | None) -> None:
        if function is None:
            self._dict.remove_item(_UCR2)
            return
        self._dict.set_item(_UCR2, function)

    def get_undercolor_removal2_typed(self) -> Any | None:
        from pypdfbox.pdmodel.common.function.pd_function import PDFunction  # noqa: PLC0415

        base = self.get_undercolor_removal2()
        if base is None:
            return None
        if isinstance(base, COSName):
            return base
        return PDFunction.create(base)

    # ---------- AAPL:AA (Apple advanced annotations) ----------

    def get_advanced_annotations(self) -> COSBase | None:
        """Returns the raw ``/AAPL:AA`` entry. This is an Apple-specific
        extension (not in the PDF spec); upstream PDFBox preserves the
        entry on round-trip rather than parsing it. Returns ``None`` when
        absent.
        """
        return self._dict.get_dictionary_object(_AAPL_AA)

    def set_advanced_annotations(self, value: COSBase | None) -> None:
        if value is None:
            self._dict.remove_item(_AAPL_AA)
            return
        self._dict.set_item(_AAPL_AA, value)

    # ---------- HT / HTO (halftone) ----------

    def get_halftone(self) -> COSBase | None:
        """Returns the raw ``/HT`` entry (halftone).

        Per the PDF spec the value is one of: a halftone dictionary,
        a halftone stream, or the name ``/Default``. This lite port
        returns the raw COS object; a typed ``PDHalftone`` wrapper is
        deferred.
        """
        return self._dict.get_dictionary_object(_HT)

    def set_halftone(self, halftone: COSBase | None) -> None:
        if halftone is None:
            self._dict.remove_item(_HT)
            return
        self._dict.set_item(_HT, halftone)

    def get_halftone_origin(self) -> COSArray | None:
        """Returns the raw ``/HTO`` entry (halftone origin) — a 2-element
        ``COSArray`` of numbers, or ``None`` when absent.
        """
        base = self._dict.get_dictionary_object(_HTO)
        if isinstance(base, COSArray):
            return base
        return None

    def set_halftone_origin(self, origin: COSArray | None) -> None:
        if origin is None:
            self._dict.remove_item(_HTO)
            return
        self._dict.set_item(_HTO, origin)


__all__ = ["PDExtendedGraphicsState"]
