"""Tkinter port of ``org.apache.pdfbox.debugger.streampane.tooltip``.

Hover-tooltip subsystem for the StreamPane operator viewer. Public
classes mirror upstream names exactly; methods follow the project's
camelCase-to-snake_case convention.

The Swing payload was an HTML fragment fed to ``setToolTipText``; this
port replaces it with a structured :class:`ToolTipText` dataclass made
of :class:`ToolTipSegment` entries that a Tkinter consumer renders
through ``tk.Text.tag_configure`` + ``tk.Text.insert``. See
``CHANGES.md`` for the deviation note.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .color_tool_tip import ColorToolTip
    from .font_tool_tip import FontToolTip
    from .g_tool_tip import GToolTip
    from .k_tool_tip import KToolTip
    from .rg_tool_tip import RGToolTip
    from .scn_tool_tip import SCNToolTip
    from .tool_tip import (
        ToolTip,
        ToolTipSegment,
        ToolTipText,
    )
    from .tool_tip_controller import ToolTipController

__getattr__, __dir__ = _attach(
    __name__,
    {
        "ColorToolTip": ".color_tool_tip",
        "FontToolTip": ".font_tool_tip",
        "GToolTip": ".g_tool_tip",
        "KToolTip": ".k_tool_tip",
        "RGToolTip": ".rg_tool_tip",
        "SCNToolTip": ".scn_tool_tip",
        "ToolTip": ".tool_tip",
        "ToolTipSegment": ".tool_tip",
        "ToolTipText": ".tool_tip",
        "ToolTipController": ".tool_tip_controller",
    },
)

__all__ = [
    "ColorToolTip",
    "FontToolTip",
    "GToolTip",
    "KToolTip",
    "RGToolTip",
    "SCNToolTip",
    "ToolTip",
    "ToolTipController",
    "ToolTipSegment",
    "ToolTipText",
]
