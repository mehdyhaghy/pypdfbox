from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace
from .pd_special_color_space import PDSpecialColorSpace

if TYPE_CHECKING:
    from pypdfbox.pdmodel.graphics.pattern import PDAbstractPattern
    from pypdfbox.pdmodel.pd_resources import PDResources


class PDPattern(PDSpecialColorSpace):
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
            if ucs is not None:  # pragma: no branch
                # Defensive: every PDColorSpace surfaces a COS object;
                # the False arm has no live caller.
                arr.add(ucs)
            super().__init__(arr)
        self._underlying = underlying_color_space
        self._resources = resources
        # Upstream returns ``EMPTY_PATTERN`` — a PDColor with empty
        # components and a ``null`` color space — as the initial color of
        # the Pattern color space (a pattern that leaves no marks):
        # ``private static final PDColor EMPTY_PATTERN =
        # new PDColor(new float[] { }, null);``. Mirror that exactly with
        # ``color_space=None`` (``PDColor`` accepts a null colour space —
        # the same invalid-colour form SetColor.process produces for
        # PDFBOX-5851); ``get_components()`` is empty either way.
        self._initial_color = PDColor([], None)

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

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Pattern color spaces have no per-component decode array —
        components only make sense for the *underlying* color space in
        the uncolored tiling form. Mirrors upstream
        ``PDPattern.getDefaultDecode(int)`` which throws
        ``UnsupportedOperationException``; we surface the same intent as
        :class:`NotImplementedError` (the base ``PDColorSpace`` would
        otherwise return an empty list because
        :meth:`get_number_of_components` is 0, which is misleading).
        """
        _ = bits_per_component
        raise NotImplementedError(
            "PDPattern has no default decode array — query the underlying "
            "color space (uncolored tiling) or render the pattern's "
            "content stream (colored / shading)."
        )

    def get_initial_color(self) -> PDColor:
        """Return the *empty pattern* — a ``PDColor`` with no components
        that paints nothing. Mirrors upstream
        ``PDPattern.getInitialColor()`` returning ``EMPTY_PATTERN``."""
        return self._initial_color

    # ---------- pattern-specific ----------

    def get_underlying_color_space(self) -> PDColorSpace | None:
        return self._underlying

    def has_underlying_color_space(self) -> bool:
        """Return ``True`` when this Pattern color space carries an
        *underlying* (alternate) color space — i.e. it was constructed
        in the array form ``[/Pattern <CS>]`` for an uncolored tiling
        pattern. ``False`` for the bare-name ``/Pattern`` form used by
        colored tiling and shading patterns. pypdfbox enrichment — a
        terse way to ask the question without comparing to ``None``.
        """
        return self._underlying is not None

    def is_uncolored(self) -> bool:
        """Return ``True`` for the *uncolored* form ``[/Pattern <CS>]``
        — the form that supplies tint components against an underlying
        color space (PaintType=2 tiling per PDF 32000-1 §8.7.3.3).
        Mirrors the predicate naming on :class:`PDTilingPattern` but
        operates on the *color space* side of the relationship: a
        :class:`PDPattern` doesn't know its tiling pattern's PaintType
        without resource resolution, so we use the structural
        ``has-underlying-CS?`` test as the proxy (which is exactly how
        upstream's ``PDColorSpace.create`` distinguishes the two forms).
        """
        return self._underlying is not None

    def is_colored(self) -> bool:
        """Return ``True`` for the *colored* / *name* form ``/Pattern``
        — the form whose pattern content stream supplies its own paint
        color (PaintType=1 tiling) and for shading patterns. Inverse
        of :meth:`is_uncolored`. See :meth:`is_uncolored` for the
        rationale of the structural test.
        """
        return self._underlying is None

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

    def has_resources(self) -> bool:
        """Return ``True`` when pattern-name resolution has resources attached."""
        return self._resources is not None

    def clear_resources(self) -> None:
        """Detach the resources used for pattern-name resolution."""
        self.set_resources(None)

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

    def get_pattern_or_none(
        self, color: PDColor
    ) -> PDAbstractPattern | None:
        """Soft variant of :meth:`get_pattern` — returns ``None`` instead
        of raising when the pattern can't be resolved (no resources
        attached, no pattern name on the color, or the named pattern
        isn't in ``/Resources/Pattern``). pypdfbox enrichment for
        best-effort callers (e.g. text-extraction stripping a colored
        pattern back to a representative color) that prefer to fall
        through to a default rather than catch ``OSError`` in a hot
        path. Upstream offers only the throwing variant.
        """
        if self._resources is None:
            return None
        pattern_name = color.get_pattern_name()
        if pattern_name is None:
            return None
        return self._resources.get_pattern(pattern_name)

    # ---------- conversion ----------

    def to_rgb_image(
        self, raster: bytes, width: int = 0, height: int = 0
    ) -> Any:
        """Pattern color spaces cannot be rasterised directly — paint
        comes from the pattern's content stream / shading function or
        (for uncolored tiling) from the *underlying* color space, neither
        of which the bare ``raster`` exposes. Mirrors upstream
        ``PDPattern.toRGBImage(WritableRaster)`` (PDPattern.java line 99)
        which throws ``UnsupportedOperationException``; we surface the
        same intent as :class:`NotImplementedError` per the project's
        Java→Python exception convention.
        """
        _ = (raster, width, height)
        raise NotImplementedError(
            "PDPattern.to_rgb_image is unsupported — render the pattern's "
            "content stream / shading instead, or recurse into the "
            "underlying color space for uncolored tiling."
        )

    def to_raw_image(
        self, raster: bytes, width: int = 0, height: int = 0
    ) -> Any:
        """Pattern color spaces have no native raster form. Mirrors
        upstream ``PDPattern.toRawImage(WritableRaster)`` (PDPattern.java
        line 105) which throws ``UnsupportedOperationException``; we
        surface the same intent as :class:`NotImplementedError`.
        """
        _ = (raster, width, height)
        raise NotImplementedError(
            "PDPattern.to_raw_image is unsupported — Pattern color spaces "
            "have no native raster form."
        )

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
        """Return the literal ``"Pattern"``. Mirrors upstream
        ``PDPattern.toString()`` (PDPattern.java line 141) which returns
        the constant string ``"Pattern"`` rather than delegating to
        :meth:`get_name`. The two happen to coincide for this color
        space, but we keep the override explicit for parity-scanner
        matching against ``toString``.
        """
        return "Pattern"

    def to_string(self) -> str:
        """Snake-case alias of :meth:`__str__`. Mirrors upstream
        ``PDPattern.toString()`` (PDPattern.java line 141). Surfaced
        explicitly so callers porting from PDFBox can keep the literal
        ``.toString()`` invocation spelled snake_case (matches the
        convention used by :class:`PDSeparation`, :class:`PDDeviceN`,
        :class:`PDIndexed`, :class:`PDICCBased`, :class:`PDColor`).
        """
        return self.__str__()


__all__ = ["PDPattern"]
