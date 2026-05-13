"""Syntax-highlight color/style table for content-stream operators.

Ported from ``org.apache.pdfbox.debugger.streampane.OperatorMarker``.

The upstream class wraps Swing ``Style`` objects in a static map keyed
by operator name. Tkinter has no ``Style`` abstraction for text tags;
callers configure ``tk.Text`` tags directly via ``tag_configure``.
We therefore expose a plain ``dict[str, dict[str, Any]]`` mapping each
operator to the keyword arguments callers should pass to
``tag_configure`` — ``{"foreground": "#hex", "font": (..., "bold")}``.

Colors mirror upstream RGB values verbatim (converted to ``#rrggbb``).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream.operator_name import OperatorName


def _rgb(red: int, green: int, blue: int) -> str:
    """Format an RGB triple as a Tk-compatible ``#rrggbb`` string."""
    return f"#{red:02x}{green:02x}{blue:02x}"


# Style payload — values map straight onto ``tk.Text.tag_configure`` kwargs.
# Upstream uses bold weight for every entry; we mirror that with a tuple
# describing the font request. Callers are expected to substitute their
# preferred family / size at widget-construction time.
_BOLD: tuple[str, str] = ("TkFixedFont", "bold")

_TEXT_OBJECT_STYLE: dict[str, Any] = {"foreground": _rgb(0, 100, 0), "weight": "bold"}
_GRAPHICS_STYLE: dict[str, Any] = {"foreground": _rgb(255, 68, 68), "weight": "bold"}
_CONCAT_STYLE: dict[str, Any] = {"foreground": _rgb(1, 169, 219), "weight": "bold"}
_INLINE_IMAGE_STYLE: dict[str, Any] = {
    "foreground": _rgb(71, 117, 163),
    "weight": "bold",
}
_IMAGE_DATA_STYLE: dict[str, Any] = {
    "foreground": _rgb(255, 165, 0),
    "weight": "bold",
}


class OperatorMarker:
    """Lookup table of operator → ``tag_configure`` keyword arguments.

    Mirrors upstream's static API: callers invoke
    :meth:`get_style` for a given operator name. ``None`` is returned
    for unknown operators (upstream returns ``null``).
    """

    _operator_style_map: dict[str, dict[str, Any]] = {
        OperatorName.BEGIN_TEXT: _TEXT_OBJECT_STYLE,
        OperatorName.END_TEXT: _TEXT_OBJECT_STYLE,
        OperatorName.SAVE: _GRAPHICS_STYLE,
        OperatorName.RESTORE: _GRAPHICS_STYLE,
        OperatorName.CONCAT: _CONCAT_STYLE,
        OperatorName.BEGIN_INLINE_IMAGE: _INLINE_IMAGE_STYLE,
        OperatorName.BEGIN_INLINE_IMAGE_DATA: _IMAGE_DATA_STYLE,
        OperatorName.END_INLINE_IMAGE: _INLINE_IMAGE_STYLE,
    }

    def __init__(self) -> None:
        # Mirrors upstream's package-private constructor — the class is
        # a pure constants holder. Tests can still construct one if they
        # really want; the staticmethods do not depend on an instance.
        raise TypeError(
            "OperatorMarker is a constants holder; do not instantiate"
        )

    @classmethod
    def get_style(cls, operator: str) -> dict[str, Any] | None:
        """Return the style dict for ``operator`` or ``None`` when absent."""
        return cls._operator_style_map.get(operator)
