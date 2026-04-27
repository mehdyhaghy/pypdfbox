from __future__ import annotations

from typing import Callable, ClassVar

from pypdfbox.cos import COSArray, COSBase, COSName

_NORMAL = "Normal"
_COMPATIBLE = "Compatible"


def _b_normal(s: float, _b: float) -> float:
    return s


def _b_multiply(s: float, b: float) -> float:
    return b * s


def _b_screen(s: float, b: float) -> float:
    return b + s - b * s


def _b_darken(s: float, b: float) -> float:
    return min(b, s)


def _b_lighten(s: float, b: float) -> float:
    return max(b, s)


def _b_difference(s: float, b: float) -> float:
    return abs(b - s)


def _b_exclusion(s: float, b: float) -> float:
    return b + s - 2.0 * b * s


def _b_hard_light(s: float, b: float) -> float:
    if s <= 0.5:
        return 2.0 * b * s
    return 1.0 - 2.0 * (1.0 - b) * (1.0 - s)


def _b_overlay(s: float, b: float) -> float:
    # Overlay(b, s) = HardLight(s, b) per PDF 32000-1 §11.3.5.1 Table 136.
    return _b_hard_light(b, s)


def _b_color_dodge(s: float, b: float) -> float:
    if s >= 1.0:
        return 1.0
    return min(1.0, b / (1.0 - s))


def _b_color_burn(s: float, b: float) -> float:
    if s <= 0.0:
        return 0.0
    return 1.0 - min(1.0, (1.0 - b) / s)


def _b_soft_light(s: float, b: float) -> float:
    # PDF spec form (matches Adobe's): two-piece quadratic.
    if s <= 0.5:
        return b - (1.0 - 2.0 * s) * b * (1.0 - b)
    if b <= 0.25:
        d = ((16.0 * b - 12.0) * b + 4.0) * b
    else:
        d = b ** 0.5
    return b + (2.0 * s - 1.0) * (d - b)


# PDF 32000-1 §11.3.5.3 non-separable HSL helpers, in [0, 1] space. The
# blend formulas operate on full RGB triples — they cannot be evaluated
# per-channel — so :class:`BlendMode` exposes them via ``blend_separable_rgb``
# rather than the scalar ``blend`` callable.

def _hsl_lum(r: float, g: float, b: float) -> float:
    return 0.30 * r + 0.59 * g + 0.11 * b


def _hsl_sat(r: float, g: float, b: float) -> float:
    return max(r, g, b) - min(r, g, b)


def _hsl_clip_color(
    r: float, g: float, b: float
) -> tuple[float, float, float]:
    lum = _hsl_lum(r, g, b)
    cmin = min(r, g, b)
    cmax = max(r, g, b)
    if cmin < 0.0:
        denom = lum - cmin
        if denom != 0.0:
            r = lum + (r - lum) * lum / denom
            g = lum + (g - lum) * lum / denom
            b = lum + (b - lum) * lum / denom
        else:
            r = g = b = lum
    if cmax > 1.0:
        denom = cmax - lum
        if denom != 0.0:
            r = lum + (r - lum) * (1.0 - lum) / denom
            g = lum + (g - lum) * (1.0 - lum) / denom
            b = lum + (b - lum) * (1.0 - lum) / denom
        else:
            r = g = b = lum
    return r, g, b


def _hsl_set_lum(
    r: float, g: float, b: float, lum: float
) -> tuple[float, float, float]:
    d = lum - _hsl_lum(r, g, b)
    return _hsl_clip_color(r + d, g + d, b + d)


def _hsl_set_sat(
    r: float, g: float, b: float, sat: float
) -> tuple[float, float, float]:
    components = [r, g, b]
    cmax = max(components)
    cmin = min(components)
    if cmax == cmin:
        return 0.0, 0.0, 0.0
    max_idx = components.index(cmax)
    min_idx = next(
        (i for i in range(3) if i != max_idx and components[i] == cmin),
        None,
    )
    if min_idx is None:
        return 0.0, 0.0, 0.0
    mid_idx = 3 - max_idx - min_idx
    out = [0.0, 0.0, 0.0]
    out[mid_idx] = (components[mid_idx] - cmin) * sat / (cmax - cmin)
    out[max_idx] = sat
    out[min_idx] = 0.0
    return out[0], out[1], out[2]


def _rgb_hue(
    sr: float, sg: float, sb: float, br: float, bg: float, bb: float
) -> tuple[float, float, float]:
    return _hsl_set_lum(*_hsl_set_sat(sr, sg, sb, _hsl_sat(br, bg, bb)),
                        lum=_hsl_lum(br, bg, bb))


def _rgb_saturation(
    sr: float, sg: float, sb: float, br: float, bg: float, bb: float
) -> tuple[float, float, float]:
    return _hsl_set_lum(*_hsl_set_sat(br, bg, bb, _hsl_sat(sr, sg, sb)),
                        lum=_hsl_lum(br, bg, bb))


def _rgb_color(
    sr: float, sg: float, sb: float, br: float, bg: float, bb: float
) -> tuple[float, float, float]:
    return _hsl_set_lum(sr, sg, sb, _hsl_lum(br, bg, bb))


def _rgb_luminosity(
    sr: float, sg: float, sb: float, br: float, bg: float, bb: float
) -> tuple[float, float, float]:
    return _hsl_set_lum(br, bg, bb, _hsl_lum(sr, sg, sb))


_SeparableFn = Callable[[float, float], float]
_RgbFn = Callable[
    [float, float, float, float, float, float],
    "tuple[float, float, float]",
]


_SEPARABLE_BLENDERS: dict[str, _SeparableFn] = {
    "Normal": _b_normal,
    "Multiply": _b_multiply,
    "Screen": _b_screen,
    "Overlay": _b_overlay,
    "Darken": _b_darken,
    "Lighten": _b_lighten,
    "ColorDodge": _b_color_dodge,
    "ColorBurn": _b_color_burn,
    "HardLight": _b_hard_light,
    "SoftLight": _b_soft_light,
    "Difference": _b_difference,
    "Exclusion": _b_exclusion,
}

_NON_SEPARABLE_BLENDERS: dict[str, _RgbFn] = {
    "Hue": _rgb_hue,
    "Saturation": _rgb_saturation,
    "Color": _rgb_color,
    "Luminosity": _rgb_luminosity,
}


class BlendMode:
    """Typed blend-mode wrapper. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.blend.BlendMode``.

    Values are interned by name so ``BlendMode.MULTIPLY is BlendMode.get("Multiply")``
    holds. ``Compatible`` is a synonym for ``Normal`` recognised by Adobe products
    (PDF 32000-1 §11.6.5.2 footnote); it interns to the same instance as ``Normal``.

    Separable blend modes (PDF 32000-1 §11.3.5.1) are
    ``Normal``/``Multiply``/``Screen``/``Overlay``/``Darken``/``Lighten``/``ColorDodge``/
    ``ColorBurn``/``HardLight``/``SoftLight``/``Difference``/``Exclusion``.
    Non-separable blend modes (§11.3.5.2) are
    ``Hue``/``Saturation``/``Color``/``Luminosity``.

    Each separable mode exposes :meth:`blend` — a per-channel function on
    floats in ``[0, 1]``. Non-separable HSL modes raise ``ValueError`` from
    :meth:`blend`; callers must use :meth:`blend_separable_rgb` (which works
    for any standard mode by either applying the per-channel formula three
    times or dispatching to the dedicated RGB-triple compose routine).
    """

    _BY_NAME: ClassVar[dict[str, BlendMode]] = {}

    # Predeclared singletons for the standard modes; populated below.
    NORMAL: ClassVar[BlendMode]
    MULTIPLY: ClassVar[BlendMode]
    SCREEN: ClassVar[BlendMode]
    OVERLAY: ClassVar[BlendMode]
    DARKEN: ClassVar[BlendMode]
    LIGHTEN: ClassVar[BlendMode]
    COLOR_DODGE: ClassVar[BlendMode]
    COLOR_BURN: ClassVar[BlendMode]
    HARD_LIGHT: ClassVar[BlendMode]
    SOFT_LIGHT: ClassVar[BlendMode]
    DIFFERENCE: ClassVar[BlendMode]
    EXCLUSION: ClassVar[BlendMode]
    HUE: ClassVar[BlendMode]
    SATURATION: ClassVar[BlendMode]
    COLOR: ClassVar[BlendMode]
    LUMINOSITY: ClassVar[BlendMode]
    COMPATIBLE: ClassVar[BlendMode]

    SEPARABLE_NAMES: ClassVar[frozenset[str]] = frozenset(
        {
            "Normal",
            "Multiply",
            "Screen",
            "Overlay",
            "Darken",
            "Lighten",
            "ColorDodge",
            "ColorBurn",
            "HardLight",
            "SoftLight",
            "Difference",
            "Exclusion",
        }
    )
    NON_SEPARABLE_NAMES: ClassVar[frozenset[str]] = frozenset(
        {"Hue", "Saturation", "Color", "Luminosity"}
    )

    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    @property
    def name(self) -> str:
        return self._name

    def get_cos_name(self) -> COSName:
        return COSName.get_pdf_name(self._name)

    def is_separable(self) -> bool:
        return self._name in BlendMode.SEPARABLE_NAMES

    def is_non_separable(self) -> bool:
        return self._name in BlendMode.NON_SEPARABLE_NAMES

    def blend(self, source_channel: float, backdrop_channel: float) -> float:
        """Per-channel blend for separable modes.

        ``source_channel`` and ``backdrop_channel`` are floats in ``[0, 1]``.
        Returns the blended channel value in ``[0, 1]`` (callers should
        clamp themselves if they want strict bounds — the spec formulas
        stay in range when both inputs are in range).

        Non-separable HSL modes (``Hue``/``Saturation``/``Color``/
        ``Luminosity``) raise :class:`ValueError` because their blend
        formulas operate on full RGB triples. Use
        :meth:`blend_separable_rgb` instead, which handles both families
        uniformly.

        Unknown / non-standard mode names fall back to ``Normal``
        (mirrors upstream's permissive ``BlendComposite`` dispatch when
        a viewer-supplied ``/BM`` value isn't recognised).
        """
        fn = _SEPARABLE_BLENDERS.get(self._name)
        if fn is not None:
            return fn(source_channel, backdrop_channel)
        if self._name in BlendMode.NON_SEPARABLE_NAMES:
            raise ValueError(
                f"Blend mode {self._name!r} is non-separable (PDF 32000-1 "
                "§11.3.5.3). Use blend_separable_rgb() instead — its blend "
                "formula operates on full RGB triples, not single channels."
            )
        return _b_normal(source_channel, backdrop_channel)

    def blend_separable_rgb(
        self,
        source: tuple[float, float, float],
        backdrop: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        """Blend two RGB triples in ``[0, 1]`` space.

        For separable modes this applies :meth:`blend` to each channel.
        For non-separable HSL modes it dispatches to the spec's
        ``Hue`` / ``Saturation`` / ``Color`` / ``Luminosity`` compose
        routines (PDF 32000-1 §11.3.5.3).
        """
        sr, sg, sb = source
        br, bg, bb = backdrop
        fn_rgb = _NON_SEPARABLE_BLENDERS.get(self._name)
        if fn_rgb is not None:
            return fn_rgb(sr, sg, sb, br, bg, bb)
        fn = _SEPARABLE_BLENDERS.get(self._name, _b_normal)
        return fn(sr, br), fn(sg, bg), fn(sb, bb)

    def __repr__(self) -> str:
        return f"BlendMode({self._name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BlendMode):
            return self._name == other._name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)

    @classmethod
    def get(cls, name: str) -> BlendMode:
        """Return the interned :class:`BlendMode` for ``name``.

        Unknown names are accepted and interned (mirrors upstream's
        permissive ``BlendMode.getInstance``); the spec treats unrecognised
        ``/BM`` names as ``Normal`` for rendering, but the wrapper still
        round-trips the original name on write.
        """
        if name == _COMPATIBLE:
            return cls._BY_NAME[_NORMAL]
        existing = cls._BY_NAME.get(name)
        if existing is not None:
            return existing
        instance = cls(name)
        cls._BY_NAME[name] = instance
        return instance

    @classmethod
    def get_instance(cls, value: COSBase | str | None) -> BlendMode:
        """Resolve a ``/BM`` value to a :class:`BlendMode`.

        Mirrors PDFBox's ``BlendMode.getInstance(COSBase)``:

        * ``COSName`` → the interned mode for that name (unknowns fall
          back to ``Normal``).
        * ``COSArray`` → the first recognised mode in the array (PDF
          32000-1 §11.3.5: viewers may supply a fallback chain). If
          none match, falls back to ``Normal``.
        * ``str`` → equivalent to ``COSName`` resolution.
        * ``None`` → ``Normal``.

        Unlike :meth:`from_cos` (which round-trips unknown names so they
        survive a write cycle), ``get_instance`` always returns a
        recognised mode — ``Normal`` is the spec-mandated fallback.
        """
        if value is None:
            return cls.NORMAL
        if isinstance(value, str):
            if value in cls.SEPARABLE_NAMES or value in cls.NON_SEPARABLE_NAMES:
                return cls.get(value)
            if value == _COMPATIBLE:
                return cls.NORMAL
            return cls.NORMAL
        if isinstance(value, COSName):
            n = value.get_name()
            if n in cls.SEPARABLE_NAMES or n in cls.NON_SEPARABLE_NAMES:
                return cls.get(n)
            if n == _COMPATIBLE:
                return cls.NORMAL
            return cls.NORMAL
        if isinstance(value, COSArray):
            for i in range(value.size()):
                item = value.get_object(i)
                if isinstance(item, COSName):
                    n = item.get_name()
                    if (
                        n in cls.SEPARABLE_NAMES
                        or n in cls.NON_SEPARABLE_NAMES
                    ):
                        return cls.get(n)
                    if n == _COMPATIBLE:
                        return cls.NORMAL
            return cls.NORMAL
        return cls.NORMAL

    @classmethod
    def from_cos(cls, base: COSBase | None) -> BlendMode | None:
        """Promote a ``/BM`` value to a :class:`BlendMode`.

        ``COSName`` resolves to the named instance; a ``COSArray`` of names
        (PDF 32000-1 §11.3.5: viewers may supply a fallback chain) returns
        the first recognised entry, falling back to the array's first name
        when none match. Returns ``None`` for ``None`` or unsupported types.
        """
        if base is None:
            return None
        if isinstance(base, COSName):
            return cls.get(base.get_name())
        if isinstance(base, COSArray):
            first: str | None = None
            for i in range(base.size()):
                item = base.get_object(i)
                if isinstance(item, COSName):
                    if first is None:
                        first = item.get_name()
                    if (
                        item.get_name() in cls.SEPARABLE_NAMES
                        or item.get_name() in cls.NON_SEPARABLE_NAMES
                    ):
                        return cls.get(item.get_name())
            if first is not None:
                return cls.get(first)
        return None


def _register(name: str) -> BlendMode:
    instance = BlendMode(name)
    BlendMode._BY_NAME[name] = instance  # noqa: SLF001 - module-private setup
    return instance


BlendMode.NORMAL = _register("Normal")
BlendMode.MULTIPLY = _register("Multiply")
BlendMode.SCREEN = _register("Screen")
BlendMode.OVERLAY = _register("Overlay")
BlendMode.DARKEN = _register("Darken")
BlendMode.LIGHTEN = _register("Lighten")
BlendMode.COLOR_DODGE = _register("ColorDodge")
BlendMode.COLOR_BURN = _register("ColorBurn")
BlendMode.HARD_LIGHT = _register("HardLight")
BlendMode.SOFT_LIGHT = _register("SoftLight")
BlendMode.DIFFERENCE = _register("Difference")
BlendMode.EXCLUSION = _register("Exclusion")
BlendMode.HUE = _register("Hue")
BlendMode.SATURATION = _register("Saturation")
BlendMode.COLOR = _register("Color")
BlendMode.LUMINOSITY = _register("Luminosity")
# Compatible is an Adobe-recognised synonym for Normal — interns to the same instance.
BlendMode.COMPATIBLE = BlendMode.NORMAL


__all__ = ["BlendMode"]
