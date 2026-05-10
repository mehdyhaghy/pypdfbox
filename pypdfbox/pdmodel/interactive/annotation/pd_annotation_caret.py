from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName

from .pd_annotation_markup import PDAnnotationMarkup

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .handlers.pd_appearance_handler import PDAppearanceHandler

_RD: COSName = COSName.get_pdf_name("RD")
_SY: COSName = COSName.get_pdf_name("Sy")


class PDAnnotationCaret(PDAnnotationMarkup):
    """``/Subtype /Caret`` annotation. Mirrors
    ``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCaret``.

    A caret annotation is a visual symbol that indicates the presence of
    text edits (PDF 32000-1:2008 §12.5.6.11, Table 180). Extends
    :class:`PDAnnotationMarkup` so review-workflow metadata (``/CreationDate``,
    ``/Subj``, ``/IRT``, ``/CA``, …) come for free.

    Subtype-specific entries beyond markup base:

    * ``/RD`` — rectangle differences (``[lx ly rx ry]`` — distances from
      ``/Rect`` edges to the actual caret) (Table 180).
    * ``/Sy`` — symbol drawn inside the rectangle. ``"P"`` (paragraph) or
      ``"None"`` (default).
    """

    SUB_TYPE: str = "Caret"

    # /Sy values per spec Table 180.
    SY_PARAGRAPH: str = "P"
    SY_NONE: str = "None"  # spec default

    def __init__(self, annotation_dict: COSDictionary | None = None) -> None:
        super().__init__(annotation_dict)
        self._custom_appearance_handler: PDAppearanceHandler | None = None
        if annotation_dict is None:
            self._set_subtype(self.SUB_TYPE)

    # ---------- /RD (rectangle differences) ----------

    def get_rectangle_differences(self) -> list[float] | None:
        """Return the four-float ``/RD`` rectangle-difference array
        (``[lx ly rx ry]``) or ``None`` when absent."""
        value = self._dict.get_dictionary_object(_RD)
        if isinstance(value, COSArray):
            return value.to_float_array()
        return None

    def set_rectangle_differences(
        self, rd: list[float] | tuple[float, ...] | None
    ) -> None:
        if rd is None:
            self._dict.remove_item(_RD)
            return
        if len(rd) != 4:
            raise ValueError(
                f"/RD must be a 4-element [lx ly rx ry] array; got {len(rd)} elements"
            )
        self._dict.set_item(_RD, COSArray([COSFloat(float(v)) for v in rd]))

    def get_rect_differences(self) -> list[float] | None:
        """Upstream-spelled alias for ``get_rectangle_differences``."""
        return self.get_rectangle_differences()

    def set_rect_differences(
        self, rd: list[float] | tuple[float, ...] | None
    ) -> None:
        """Upstream-spelled alias for ``set_rectangle_differences``."""
        self.set_rectangle_differences(rd)

    def set_rect_differences_uniform(self, difference: float) -> None:
        """Set the same ``/RD`` margin on all four sides.

        Mirrors upstream ``setRectDifferences(float)`` overload — the
        single-argument form that applies an equal difference for left,
        top, right and bottom.
        """
        self.set_rectangle_differences(
            [float(difference), float(difference), float(difference), float(difference)]
        )

    def set_rect_differences_lrtb(
        self,
        difference_left: float,
        difference_top: float,
        difference_right: float,
        difference_bottom: float,
    ) -> None:
        """Set ``/RD`` from individual side margins.

        Mirrors upstream ``setRectDifferences(float, float, float, float)``
        overload (left, top, right, bottom — the spec ordering for ``/RD``).
        """
        self.set_rectangle_differences(
            [
                float(difference_left),
                float(difference_top),
                float(difference_right),
                float(difference_bottom),
            ]
        )

    def has_rectangle_differences(self) -> bool:
        """``True`` when ``/RD`` is present (regardless of contents).

        Predicate companion to :meth:`get_rectangle_differences`; useful for
        callers that need to distinguish "no margins set" from "explicit
        zero margins".
        """
        return self._dict.get_dictionary_object(_RD) is not None

    def clear_rectangle_differences(self) -> None:
        """Remove ``/RD`` entirely.

        Equivalent to ``set_rectangle_differences(None)`` but reads more
        clearly at call sites that explicitly intend to clear the entry.
        """
        self._dict.remove_item(_RD)

    def get_left_difference(self) -> float | None:
        """Return the left ``/RD`` margin, or ``None`` when ``/RD`` is unset.

        Convenience accessor for the first ``[lx _ _ _]`` slot — Table 180
        ordering is ``[left top right bottom]``.
        """
        rd = self.get_rectangle_differences()
        return rd[0] if rd is not None and len(rd) >= 4 else None

    def get_top_difference(self) -> float | None:
        """Return the top ``/RD`` margin (second slot) or ``None``."""
        rd = self.get_rectangle_differences()
        return rd[1] if rd is not None and len(rd) >= 4 else None

    def get_right_difference(self) -> float | None:
        """Return the right ``/RD`` margin (third slot) or ``None``."""
        rd = self.get_rectangle_differences()
        return rd[2] if rd is not None and len(rd) >= 4 else None

    def get_bottom_difference(self) -> float | None:
        """Return the bottom ``/RD`` margin (fourth slot) or ``None``."""
        rd = self.get_rectangle_differences()
        return rd[3] if rd is not None and len(rd) >= 4 else None

    # ---------- /Sy (caret symbol) ----------

    def get_symbol(self) -> str:
        """Return the caret ``/Sy`` symbol name. Defaults to ``"None"`` per spec."""
        value = self._dict.get_name(_SY)
        return value if value is not None else self.SY_NONE

    def set_symbol(self, symbol: str | None) -> None:
        if symbol is None:
            self._dict.remove_item(_SY)
            return
        self._dict.set_name(_SY, symbol)

    def has_symbol(self) -> bool:
        """``True`` when ``/Sy`` is explicitly set (vs. relying on the
        ``"None"`` spec default).
        """
        return self._dict.get_name(_SY) is not None

    def is_paragraph_symbol(self) -> bool:
        """``True`` when ``/Sy`` is ``"P"`` (paragraph symbol drawn inside
        the caret rectangle, per Table 180).
        """
        return self.get_symbol() == self.SY_PARAGRAPH

    def is_no_symbol(self) -> bool:
        """``True`` when no symbol is associated with the caret — either
        ``/Sy`` is ``"None"`` or the entry is absent (the spec default).
        """
        return self.get_symbol() == self.SY_NONE

    def clear_symbol(self) -> None:
        """Remove the explicit ``/Sy`` entry, reverting to the spec default
        (``"None"``).

        Equivalent to ``set_symbol(None)`` but makes intent explicit at the
        call site.
        """
        self._dict.remove_item(_SY)

    # ---------- aggregate predicates ----------

    def is_caret_default(self) -> bool:
        """``True`` when neither ``/RD`` nor ``/Sy`` is explicitly set, so
        the annotation relies entirely on PDF spec defaults for the
        caret-specific entries (margins of zero and ``/Sy = None``).

        Markup metadata (``/Subj``, ``/IRT``, …) is not considered — see
        :class:`PDAnnotationMarkup` for those entries.
        """
        return not self.has_rectangle_differences() and not self.has_symbol()

    # ---------- appearance construction ----------

    def set_custom_appearance_handler(
        self, appearance_handler: PDAppearanceHandler | None
    ) -> None:
        """Set the custom appearance handler used by
        :meth:`construct_appearances`.

        Mirrors upstream ``setCustomAppearanceHandler``
        (``PDAnnotationCaret.java`` line 103). Pass ``None`` to clear the
        custom handler and restore the default construction path.
        """
        self._custom_appearance_handler = appearance_handler

    def get_custom_appearance_handler(self) -> PDAppearanceHandler | None:
        """Return the custom appearance handler previously set via
        :meth:`set_custom_appearance_handler`, or ``None`` when the default
        construction path is in use. No upstream getter exists (the field is
        private in Java); this is the Pythonic accessor used by tests and
        downstream code that needs to inspect the wired handler.
        """
        return self._custom_appearance_handler

    def construct_appearances(self, document: PDDocument | None = None) -> None:
        """Generate caret annotation appearances.

        Mirrors upstream ``constructAppearances()`` and
        ``constructAppearances(PDDocument)`` (``PDAnnotationCaret.java``
        lines 109-125). A custom handler, when configured, is invoked
        exactly as upstream does. The built-in ``PDCaretAppearanceHandler``
        is not ported yet, so the default path remains a no-op like the
        base annotation implementation.
        """
        if self._custom_appearance_handler is not None:
            self._custom_appearance_handler.generate_appearance_streams()
            return None
        return super().construct_appearances(document)


__all__ = ["PDAnnotationCaret"]
