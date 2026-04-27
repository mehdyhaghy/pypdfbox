from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import COSArray, COSBase, COSName

_NORMAL = "Normal"
_COMPATIBLE = "Compatible"


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
