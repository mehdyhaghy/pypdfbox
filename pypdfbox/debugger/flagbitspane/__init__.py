"""Flag-bit decoding views for the pypdfbox debugger.

Tkinter port of ``org.apache.pdfbox.debugger.flagbitspane``. Each ``Flag``
subclass decodes one well-known integer flag entry (annotation ``/F``, field
``/Ff``, encryption ``/P``, signature ``/SigFlags``, font-descriptor
``/Flags``, font ``/Panose``) into a row table that mirrors the JTable
shown by the upstream Swing debugger.
"""

from pypdfbox.debugger.flagbitspane.annot_flag import AnnotFlag
from pypdfbox.debugger.flagbitspane.encrypt_flag import EncryptFlag
from pypdfbox.debugger.flagbitspane.field_flag import FieldFlag
from pypdfbox.debugger.flagbitspane.flag import Flag
from pypdfbox.debugger.flagbitspane.flag_bits_pane import FlagBitsPane
from pypdfbox.debugger.flagbitspane.flag_bits_pane_view import FlagBitsPaneView
from pypdfbox.debugger.flagbitspane.font_flag import FontFlag
from pypdfbox.debugger.flagbitspane.panose_flag import PanoseFlag
from pypdfbox.debugger.flagbitspane.sig_flag import SigFlag

__all__ = [
    "AnnotFlag",
    "EncryptFlag",
    "FieldFlag",
    "Flag",
    "FlagBitsPane",
    "FlagBitsPaneView",
    "FontFlag",
    "PanoseFlag",
    "SigFlag",
]
