"""Abstract base for flag-bit decoders.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.Flag``.

Subclasses describe one well-known integer flag entry (annotation ``/F``,
field ``/Ff``, encryption ``/P``, signature ``/SigFlags``, font-descriptor
``/Flags``, font ``/Panose``) by producing:

* a human-readable header string (:meth:`get_flag_type`);
* the raw integer/byte value (:meth:`get_flag_value`);
* a 2-d row table (:meth:`get_flag_bits`) where each row is
  ``[bit-position, name, set?]`` — or, for :class:`PanoseFlag`,
  ``[byte-position, name, byte-value, description]``.

The view (``FlagBitsPaneView``) reads :meth:`get_column_names` so subclasses
that produce a different column layout can override the header row.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Flag(ABC):
    """Abstract description of one PDF flag entry, decoded into rows."""

    # ---- abstract surface ---------------------------------------------------

    @abstractmethod
    def get_flag_type(self) -> str:
        """Human-readable header for this flag table (e.g. ``"Annot flag"``)."""

    @abstractmethod
    def get_flag_value(self) -> str:
        """Raw flag-value string shown above the table."""

    @abstractmethod
    def get_flag_bits(self) -> list[list[Any]]:
        """Row data — one list per bit/byte position, in display order."""

    # ---- default column headings -------------------------------------------

    def get_column_names(self) -> list[str]:
        """Default 3-column layout (bit position / name / set?)."""
        return ["Bit Position", "Name", "Set"]

    # ---- shared helper ------------------------------------------------------

    @staticmethod
    def _is_flag_bit_set(flag_value: int, bit_position: int) -> bool:
        """Return ``True`` iff the 1-indexed *bit_position* is set in *flag_value*.

        Mirrors the private ``Flag#isFlagBitSet`` helper used by upstream
        subclasses. Hoisted to the base so every subclass can share it.
        """
        mask = 1 << (bit_position - 1)
        return (flag_value & mask) == mask
