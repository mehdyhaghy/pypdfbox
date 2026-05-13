"""Python port of ``org.apache.pdfbox.debugger.hexviewer``.

The Swing widgets have been re-implemented on top of Tkinter/Ttk; data and
event classes (``HexModel``, ``HexChangedEvent`` and friends) are pure-Python
and don't pull a display in. See the upstream Java sources for the original
intent and the project ``PROVENANCE.md`` for porting details.
"""

from pypdfbox.debugger.hexviewer.address_pane import AddressPane
from pypdfbox.debugger.hexviewer.ascii_pane import ASCIIPane
from pypdfbox.debugger.hexviewer.hex_change_listener import HexChangeListener
from pypdfbox.debugger.hexviewer.hex_changed_event import HexChangedEvent
from pypdfbox.debugger.hexviewer.hex_editor import HexEditor
from pypdfbox.debugger.hexviewer.hex_model import HexModel
from pypdfbox.debugger.hexviewer.hex_model_change_listener import (
    HexModelChangeListener,
)
from pypdfbox.debugger.hexviewer.hex_model_changed_event import (
    HexModelChangedEvent,
)
from pypdfbox.debugger.hexviewer.hex_pane import HexPane
from pypdfbox.debugger.hexviewer.hex_view import HexView
from pypdfbox.debugger.hexviewer.select_event import SelectEvent
from pypdfbox.debugger.hexviewer.selection_change_listener import (
    SelectionChangeListener,
)
from pypdfbox.debugger.hexviewer.status_pane import StatusPane
from pypdfbox.debugger.hexviewer.upper_pane import UpperPane

__all__ = [
    "AddressPane",
    "ASCIIPane",
    "HexChangeListener",
    "HexChangedEvent",
    "HexEditor",
    "HexModel",
    "HexModelChangeListener",
    "HexModelChangedEvent",
    "HexPane",
    "HexView",
    "SelectEvent",
    "SelectionChangeListener",
    "StatusPane",
    "UpperPane",
]
