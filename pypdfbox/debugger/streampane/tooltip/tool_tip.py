"""Abstract base for content-stream tooltips.

Ported from ``org.apache.pdfbox.debugger.streampane.tooltip.ToolTip``.

Upstream defines a Java *interface* with a single ``getToolTipText()``
method that returns an HTML string consumed by Swing's
``JTextComponent.setToolTipText``. Because the pypdfbox debugger uses
Tkinter/Ttk (no HTMLDocument), we replace the HTML payload with a
small structured ``ToolTipText`` dataclass: a plain-text caption plus
zero or more ``ToolTipSegment`` entries describing color swatches.
A consumer can render the result directly into a ``tk.Text`` widget
with ``tag_configure`` + ``insert(..., tags=...)``.

See ``CHANGES.md`` for the HTML-to-structured-segment migration note.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolTipSegment:
    """One renderable region of a tooltip.

    Attributes
    ----------
    text:
        Plain caption text to render. May be empty when the segment is
        purely a color swatch.
    color_hex:
        Either ``None`` (no swatch — render ``text`` only) or a six-digit
        lowercase hex string (without the ``#`` prefix) describing the
        swatch fill color, suitable for ``tk.Text.tag_configure(... ,
        background='#' + color_hex)``.
    """

    text: str = ""
    color_hex: str | None = None


@dataclass(frozen=True)
class ToolTipText:
    """Structured replacement for the upstream HTML tooltip payload.

    ``plain`` is a fall-back caption a non-graphical consumer (logger,
    test, accessibility reader) can use directly. ``segments`` is the
    ordered list of regions a Tkinter consumer should render.
    """

    plain: str = ""
    segments: tuple[ToolTipSegment, ...] = field(default_factory=tuple)


class ToolTip(ABC):
    """A class that provides the tooltip for an operator.

    Mirrors the upstream package-private ``ToolTip`` interface — the
    concrete ports below (``RGToolTip``, ``KToolTip``, ``GToolTip``,
    ``SCNToolTip``, ``FontToolTip``) all expose
    :meth:`get_tool_tip_text` returning a :class:`ToolTipText` or
    ``None`` when extraction failed.
    """

    @abstractmethod
    def get_tool_tip_text(self) -> ToolTipText | None:
        """Return the tooltip payload, or ``None`` when unavailable."""
