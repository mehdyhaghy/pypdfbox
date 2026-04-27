from __future__ import annotations

from collections.abc import Iterable

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (
    PDOptionalContentGroup,
)

from .pd_action import PDAction

_STATE: COSName = COSName.get_pdf_name("State")
_PRESERVE_RB: COSName = COSName.get_pdf_name("PreserveRB")

# PDF 32000-1 §12.6.4.12 Table 207 — state-array preamble names.
_ON: COSName = COSName.get_pdf_name("ON")
_OFF: COSName = COSName.get_pdf_name("OFF")
_TOGGLE: COSName = COSName.get_pdf_name("Toggle")
_PREAMBLES: frozenset[COSName] = frozenset({_ON, _OFF, _TOGGLE})


class PDActionSetOCGState(PDAction):
    """Set-OCG-state action. Wraps a /S = SetOCGState action dictionary.

    Implements the PDF 32000-1 §12.6.4.12 Set-OCG-State action surface.
    The /State entry is a heterogeneous array of preamble names ('ON',
    'OFF', 'Toggle') interleaved with one or more OCG dictionary
    references; the preamble applies to every following OCG until the
    next preamble. /PreserveRB controls radio-button group preservation
    semantics.

    Note: not present in upstream Apache PDFBox 3.0.x — this class fills
    a documented gap so SetOCGState dictionaries round-trip through the
    typed action surface instead of falling through to ``PDActionUnknown``.
    """

    SUB_TYPE = "SetOCGState"

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    # ---- /State -------------------------------------------------------------

    def get_cos_state(self) -> COSArray | None:
        """Return the raw /State COSArray, or ``None`` when absent."""
        value = self._action.get_dictionary_object(_STATE)
        if isinstance(value, COSArray):
            return value
        return None

    def get_state(self) -> list[COSBase]:
        """Return /State as a flat Python list of its raw entries.

        Preserves order. Each entry is either a preamble ``COSName``
        ('ON' / 'OFF' / 'Toggle') or a ``COSDictionary`` (or indirect
        reference to one) representing an OCG. Returns an empty list
        when /State is missing.
        """
        arr = self.get_cos_state()
        if arr is None:
            return []
        return arr.to_list()

    def set_state(
        self,
        state: COSArray | Iterable[COSBase | PDOptionalContentGroup] | None,
    ) -> None:
        """Set /State.

        Accepts a ``COSArray`` (stored as-is), an iterable of mixed
        ``COSName`` preambles and ``COSDictionary``/``PDOptionalContentGroup``
        OCG references, or ``None`` to remove the entry. Preamble strings
        like ``"ON"`` / ``"OFF"`` / ``"Toggle"`` are accepted as a
        convenience and converted to ``COSName``.
        """
        if state is None:
            self._action.remove_item(_STATE)
            return
        if isinstance(state, COSArray):
            self._action.set_item(_STATE, state)
            return
        arr = COSArray()
        for entry in state:
            arr.add(_coerce_state_entry(entry))
        self._action.set_item(_STATE, arr)

    # ---- /PreserveRB --------------------------------------------------------

    def is_preserve_rb(self) -> bool:
        """Return /PreserveRB; defaults to ``True`` per PDF 32000-1
        Table 207."""
        return self._action.get_boolean(_PRESERVE_RB, True)

    def set_preserve_rb(self, preserve: bool) -> None:
        self._action.set_boolean(_PRESERVE_RB, preserve)


def _coerce_state_entry(
    entry: COSBase | PDOptionalContentGroup | str,
) -> COSBase:
    """Coerce a /State list entry into a ``COSBase`` for storage.

    - ``PDOptionalContentGroup`` -> its underlying ``COSDictionary``.
    - ``str`` matching a preamble (case-insensitive) -> the canonical
      ``COSName`` (``ON`` / ``OFF`` / ``Toggle``).
    - ``COSBase`` -> passed through unchanged.
    Other types raise ``TypeError``.
    """
    if isinstance(entry, PDOptionalContentGroup):
        return entry.get_cos_object()
    if isinstance(entry, COSBase):
        return entry
    if isinstance(entry, str):
        upper = entry.upper()
        if upper == "ON":
            return _ON
        if upper == "OFF":
            return _OFF
        if upper == "TOGGLE":
            return _TOGGLE
        raise ValueError(
            "string /State entries must be 'ON', 'OFF', or 'Toggle'; "
            f"got {entry!r}"
        )
    raise TypeError(
        "/State entry must be COSBase, PDOptionalContentGroup, or preamble "
        f"string; got {type(entry).__name__}"
    )


__all__ = ["PDActionSetOCGState"]
