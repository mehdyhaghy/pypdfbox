"""Color-space inspector panes for the pypdfbox debugger.

Tkinter port of ``org.apache.pdfbox.debugger.colorpane``. Provides
panels for inspecting DeviceN, Indexed and Separation color spaces
plus a generic :class:`CSArrayBased` view for any other array-form
color space (ICCBased, CalRGB, CalGray, Lab).
"""

from pypdfbox.debugger.colorpane.color_bar_cell_renderer import (
    ColorBarCellRenderer,
)
from pypdfbox.debugger.colorpane.cs_array_based import CSArrayBased
from pypdfbox.debugger.colorpane.cs_device_n import CSDeviceN
from pypdfbox.debugger.colorpane.cs_indexed import CSIndexed
from pypdfbox.debugger.colorpane.cs_separation import CSSeparation
from pypdfbox.debugger.colorpane.device_n_colorant import DeviceNColorant
from pypdfbox.debugger.colorpane.device_n_table_model import DeviceNTableModel
from pypdfbox.debugger.colorpane.indexed_colorant import IndexedColorant
from pypdfbox.debugger.colorpane.indexed_table_model import IndexedTableModel

__all__ = [
    "CSArrayBased",
    "CSDeviceN",
    "CSIndexed",
    "CSSeparation",
    "ColorBarCellRenderer",
    "DeviceNColorant",
    "DeviceNTableModel",
    "IndexedColorant",
    "IndexedTableModel",
]
