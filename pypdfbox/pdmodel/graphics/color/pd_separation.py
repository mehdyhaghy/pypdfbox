from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.function import PDFunction


class PDSeparation(PDColorSpace):
    """A Separation color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDSeparation``.

    Array form: ``[/Separation <colorant name> <alternate CS> <tint
    transform>]``.
    """

    NAME: str = "Separation"

    # Array index constants — match upstream private fields.
    _COLORANT_NAMES = 1
    _ALTERNATE_CS = 2
    _TINT_TRANSFORM = 3

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            # Placeholders matching upstream PDSeparation() default ctor.
            array.add(COSName.get_pdf_name(""))
            array.add(COSName.get_pdf_name(""))
            array.add(COSName.get_pdf_name(""))
        super().__init__(array)
        # Initial color per upstream is a single component at 1.0 (full
        # tint).
        self._initial_color = PDColor([1.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- separation-specific ----------

    def get_colorant_name(self) -> str | None:
        assert self._array is not None
        entry = self._array.get_object(self._COLORANT_NAMES)
        if isinstance(entry, COSName):
            return entry.get_name()
        return None

    def set_colorant_name(self, name: str) -> None:
        assert self._array is not None
        self._array.set(self._COLORANT_NAMES, COSName.get_pdf_name(name))

    def get_alternate_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        entry = self._array.get_object(self._ALTERNATE_CS)
        if entry is None:
            return None
        return PDColorSpace.create(entry)

    def set_alternate_color_space(self, alternate: PDColorSpace) -> None:
        assert self._array is not None
        self._array.set(self._ALTERNATE_CS, alternate.get_cos_object())

    def get_tint_transform(self) -> PDFunction | None:
        """Return the tint transform as a :class:`PDFunction`. Mirrors
        upstream ``PDSeparation.getTintTransform()``.

        Returns ``None`` for placeholder slots that don't dispatch to a
        concrete function type — keep the default ctor's empty-name
        slot from blowing up callers that probe before populating.
        """
        from pypdfbox.pdmodel.common.function import PDFunction

        raw = self.get_tint_transform_cos()
        if raw is None:
            return None
        try:
            return PDFunction.create(raw)
        except (TypeError, ValueError):
            return None

    def get_tint_transform_cos(self) -> COSBase | None:
        """Return the raw tint transform COS object (function dictionary
        or stream). Pypdfbox enrichment — upstream exposes only the
        typed ``PDFunction`` accessor."""
        assert self._array is not None
        return self._array.get_object(self._TINT_TRANSFORM)

    def set_tint_transform(self, transform: object) -> None:
        """Store the tint transform. Accepts either a :class:`PDFunction`
        (upstream signature) or a raw COS object (pypdfbox enrichment).
        """
        assert self._array is not None
        if hasattr(transform, "get_cos_object"):
            self._array.set(self._TINT_TRANSFORM, transform.get_cos_object())
        elif isinstance(transform, COSBase):
            self._array.set(self._TINT_TRANSFORM, transform)
        else:
            raise TypeError(
                "set_tint_transform expects PDFunction or COSBase, "
                f"got {type(transform).__name__}"
            )

    # ---------- conversion ----------

    def to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Evaluate the tint transform and forward to the alternate CS.

        Per PDF 32000-1 §8.6.6.4, ``components`` is the single tint
        value in ``[0, 1]``. The tint transform (a PDF function) maps
        it to coordinates in the alternate color space, which then
        produces the RGB output.
        """
        alternate = self.get_alternate_color_space()
        if alternate is None:
            return None
        function = self.get_tint_transform()
        if function is None:
            return None
        alt_components = function.eval(list(components))
        return PDColor(alt_components, alternate).to_rgb()


__all__ = ["PDSeparation"]
