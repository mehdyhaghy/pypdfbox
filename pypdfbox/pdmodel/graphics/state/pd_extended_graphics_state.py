from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSNumber,
)

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
    ``/Font`` entry exposes only the size helper (full ``PDFontSetting``
    deferred), and ``copyIntoGraphicsState`` / soft mask / transfer
    function support are not yet implemented.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        self._dict = dictionary if dictionary is not None else COSDictionary()
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, _EXT_G_STATE)

    def get_cos_object(self) -> COSDictionary:
        return self._dict

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

    def get_line_dash_pattern(self) -> "PDLineDashPattern | None":
        from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern

        base = self._dict.get_dictionary_object(_D)
        if isinstance(base, COSArray):
            return PDLineDashPattern.from_cos_array(base)
        return None

    def set_line_dash_pattern(
        self, dash_pattern: "PDLineDashPattern | COSArray | None"
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

    # ---------- BM (blend mode, raw — typed BlendMode wrapper deferred) ----------

    def get_blend_mode(self) -> COSName | str | None:
        base = self._dict.get_dictionary_object(_BM)
        if base is None:
            return None
        if isinstance(base, COSName):
            return base
        return None

    def set_blend_mode(self, bm: COSName | str | None) -> None:
        if bm is None:
            self._dict.remove_item(_BM)
        elif isinstance(bm, COSName):
            self._dict.set_item(_BM, bm)
        else:
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


__all__ = ["PDExtendedGraphicsState"]
