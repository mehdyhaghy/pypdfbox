"""Top-level flag-bits pane.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.FlagBitsPane``.

Dispatches a (dictionary, flag-type) pair to the correct :class:`Flag`
subclass and wraps the resulting decoded rows in a :class:`FlagBitsPaneView`.
"""

from __future__ import annotations

import tkinter as tk

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.flagbitspane.annot_flag import AnnotFlag
from pypdfbox.debugger.flagbitspane.encrypt_flag import EncryptFlag
from pypdfbox.debugger.flagbitspane.field_flag import FieldFlag
from pypdfbox.debugger.flagbitspane.flag import Flag
from pypdfbox.debugger.flagbitspane.flag_bits_pane_view import FlagBitsPaneView
from pypdfbox.debugger.flagbitspane.font_flag import FontFlag
from pypdfbox.debugger.flagbitspane.panose_flag import PanoseFlag
from pypdfbox.debugger.flagbitspane.sig_flag import SigFlag

# The six flag-type COSNames we dispatch on. Each one matches the upstream
# ``COSName`` constant used in the Java ``FlagBitsPane.createPane`` method.
_FLAGS: COSName = COSName.get_pdf_name("Flags")
_F: COSName = COSName.get_pdf_name("F")
_FF: COSName = COSName.get_pdf_name("Ff")
_PANOSE: COSName = COSName.get_pdf_name("Panose")
_P: COSName = COSName.get_pdf_name("P")
_SIG_FLAGS: COSName = COSName.get_pdf_name("SigFlags")


class FlagBitsPane:
    """Render the appropriate flag table for a dictionary entry."""

    def __init__(
        self,
        document: object | None,
        dictionary: COSDictionary,
        flag_type: COSName,
        master: tk.Misc | None = None,
    ) -> None:
        """Build the pane.

        :param document: the host :class:`PDDocument` (needed by
            :class:`SigFlag` to construct an :class:`PDAcroForm` view). May
            be ``None`` for flag types that do not need it.
        :param dictionary: the COS dictionary whose flag we are decoding.
        :param flag_type: which entry of *dictionary* to decode — one of
            ``/Flags``, ``/F``, ``/Ff``, ``/Panose``, ``/P``, ``/SigFlags``.
        :param master: parent Tk widget for the view. ``None`` uses an
            implicit default root.
        """
        self._document = document
        self._view: FlagBitsPaneView | None = None
        self.create_pane(dictionary, flag_type, master)

    # ---- dispatch ----------------------------------------------------------

    def create_pane(
        self,
        dictionary: COSDictionary,
        flag_type: COSName,
        master: tk.Misc | None,
    ) -> None:
        """Build the flag-decoded view for ``dictionary[flag_type]``.

        Mirrors upstream private ``FlagBitsPane.createPane()``. Public on
        the Python port for parity tooling.
        """
        flag = self._select_flag(dictionary, flag_type)
        if flag is None:
            return
        self._view = FlagBitsPaneView(
            master,
            flag.get_flag_type(),
            flag.get_flag_value(),
            flag.get_flag_bits(),
            flag.get_column_names(),
        )

    # Back-compat private alias.
    _create_pane = create_pane

    def _select_flag(
        self, dictionary: COSDictionary, flag_type: COSName
    ) -> Flag | None:
        # The dispatch table mirrors upstream FlagBitsPane.createPane: every
        # branch is independent (upstream uses a sequence of `if`s, not
        # else-if), but only one ever matches.
        if flag_type == _FLAGS:
            return FontFlag(dictionary)
        if flag_type == _F:
            return AnnotFlag(dictionary)
        if flag_type == _FF:
            return FieldFlag(dictionary)
        if flag_type == _PANOSE:
            return PanoseFlag(dictionary)
        if flag_type == _P:
            return EncryptFlag(dictionary)
        if flag_type == _SIG_FLAGS:
            return SigFlag(self._document, dictionary)
        return None

    # ---- public surface ----------------------------------------------------

    def get_pane(self) -> FlagBitsPaneView | None:
        """Return the underlying view widget (``None`` if no flag matched)."""
        return self._view
