from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern
    from pypdfbox.pdmodel.pd_resources import PDResources


class PDPattern(PDColorSpace):
    """A Pattern color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDPattern``.

    Two forms per PDF 32000-1 §8.6.6.2 / §8.7:

    - ``/Pattern`` (name form) — *colored* patterns; the pattern's own
      content stream supplies all paint color. ``get_underlying_color_space``
      returns ``None``.
    - ``[/Pattern <underlying CS>]`` (array form) — *uncolored* tiling;
      the pattern's content stream is parameterised by tint components
      drawn against the underlying ("alternate") color space.

    Pattern resolution against ``/Resources/Pattern`` is exposed via
    :meth:`get_pattern`; upstream's ``PDPattern(PDResources, ...)``
    constructors are mirrored through the optional ``resources`` kwarg
    (or :meth:`set_resources`).
    """

    NAME: str = "Pattern"

    def __init__(
        self,
        underlying_color_space: PDColorSpace | None = None,
        *,
        resources: PDResources | None = None,
    ) -> None:
        # Pattern can be either:
        #   /Pattern                         (colored, name form)
        #   [/Pattern <underlying CS>]       (uncolored tiling)
        if underlying_color_space is None:
            super().__init__(None)
        else:
            arr = COSArray()
            arr.add(COSName.get_pdf_name(self.NAME))
            ucs = underlying_color_space.get_cos_object()
            if ucs is not None:
                arr.add(ucs)
            super().__init__(arr)
        self._underlying = underlying_color_space
        self._resources = resources
        # Upstream returns ``EMPTY_PATTERN`` — a PDColor with empty
        # components and a ``null`` color space — as the initial color of
        # the Pattern color space (a pattern that leaves no marks). We
        # mirror that with ``color_space=self`` (Python doesn't accept
        # ``None`` here) so that round-trips through ``get_color_space``
        # still see a Pattern; ``get_components()`` is empty either way.
        self._initial_color = PDColor([], self)

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSBase:
        if self._array is not None:
            return self._array
        return COSName.get_pdf_name(self.NAME)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        # Upstream throws UnsupportedOperationException — components are
        # only meaningful for the underlying CS in the uncolored tiling
        # case. We return 0 so callers that just want a size get a sane
        # answer; explicit lookups should ask the underlying CS instead.
        return 0

    def get_initial_color(self) -> PDColor:
        """Return the *empty pattern* — a ``PDColor`` with no components
        that paints nothing. Mirrors upstream
        ``PDPattern.getInitialColor()`` returning ``EMPTY_PATTERN``."""
        return self._initial_color

    # ---------- pattern-specific ----------

    def get_underlying_color_space(self) -> PDColorSpace | None:
        return self._underlying

    def get_resources(self) -> PDResources | None:
        """Return the ``PDResources`` against which patterns are resolved
        by :meth:`get_pattern`, or ``None`` if not set. Upstream's
        constructor takes resources eagerly; we accept lazy attachment so
        a Pattern color space round-tripped through ``PDColorSpace.create``
        can still later locate its pattern dictionary."""
        return self._resources

    def set_resources(self, resources: PDResources | None) -> None:
        """Attach (or clear) the ``PDResources`` used for
        :meth:`get_pattern` lookups. pypdfbox enrichment — upstream sets
        resources only at construction time."""
        self._resources = resources

    def get_pattern(self, color: PDColor) -> PDAbstractPattern:
        """Resolve the pattern named by ``color``'s pattern-name component
        against the attached ``PDResources``. Mirrors upstream
        ``PDPattern.getPattern(PDColor)``.

        :raises OSError: when no resources are attached, when ``color``
            has no pattern name, or when the named pattern is not present
            in ``/Resources/Pattern`` — upstream throws ``IOException`` in
            the missing-name case (we map that to ``OSError`` per the
            project's Java→Python exception convention; the no-resources
            case is a pypdfbox-specific addition).
        """
        if self._resources is None:
            raise OSError(
                "PDPattern.get_pattern requires PDResources; pass via "
                "PDPattern(resources=...) or set_resources(...)"
            )
        pattern_name = color.get_pattern_name()
        if pattern_name is None:
            raise OSError("color has no pattern name")
        pattern = self._resources.get_pattern(pattern_name)
        if pattern is None:
            raise OSError(f"pattern {pattern_name} was not found")
        return pattern

    # ---------- conversion ----------

    def to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Resolve a Pattern color to sRGB.

        - **Uncolored** tiling pattern (``PaintType=2``, indicated here by
          a non-``None`` underlying color space): the supplied
          ``components`` carry the tint color in the underlying
          ("alternate") color space — recurse into it via
          :meth:`PDColor.to_rgb`. This is the standard interpretation per
          PDF 32000-1 §8.7.3.3.
        - **Colored** tiling pattern (``PaintType=1``) and shading
          patterns (no underlying color space): the per-cell color comes
          from the pattern's content stream / shading function, which
          requires full rendering. Return ``None`` so callers can either
          fall back (e.g. paint a representative color from elsewhere) or
          escalate to the renderer. Upstream throws
          ``UnsupportedOperationException``; we prefer ``None`` so a
          best-effort color resolver can short-circuit without catching
          exceptions in hot paths.
        """
        from .pd_color import PDColor

        if self._underlying is None:
            return None
        return PDColor(components, self._underlying).to_rgb()

    def __str__(self) -> str:
        return self.NAME


__all__ = ["PDPattern"]
