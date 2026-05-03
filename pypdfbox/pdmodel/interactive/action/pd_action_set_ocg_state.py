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

    # Preamble names for /State entries per PDF 32000-1 §12.6.4.12 Table 207.
    STATE_ON = "ON"
    STATE_OFF = "OFF"
    STATE_TOGGLE = "Toggle"

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

    def get_preserve_rb(self) -> bool:
        """Bean-style alias of :meth:`is_preserve_rb`. Returns the
        /PreserveRB flag (default ``True`` when absent)."""
        return self.is_preserve_rb()

    def set_preserve_rb(self, preserve: bool) -> None:
        self._action.set_boolean(_PRESERVE_RB, preserve)

    # ---- predicates / clear / typed views ---------------------------------

    def has_state(self) -> bool:
        """``True`` when ``/State`` is present on the underlying dictionary
        as a :class:`COSArray`. Spec-invalid non-array ``/State`` values
        report as absent — matches the shape :meth:`get_cos_state` filters
        on. Lets callers branch on state-presence without realising the
        full :meth:`get_state` list."""
        return self.get_cos_state() is not None

    def has_preserve_rb(self) -> bool:
        """``True`` when ``/PreserveRB`` is explicitly present (independent
        of its boolean value). Distinct from :meth:`is_preserve_rb` which
        always returns the effective value (defaulting to ``True`` when
        absent) — useful for round-tripping callers that want to preserve
        the canonical "default omitted" wire shape."""
        return self._action.get_dictionary_object(_PRESERVE_RB) is not None

    def clear_state(self) -> None:
        """Remove the ``/State`` entry. Equivalent to
        ``set_state(None)``; provided as a verb-named convenience matching
        the ``clear_*`` helpers on other action wrappers."""
        self._action.remove_item(_STATE)

    def clear_preserve_rb(self) -> None:
        """Remove the ``/PreserveRB`` entry so :meth:`is_preserve_rb` falls
        back to its Table 207 default of ``True``."""
        self._action.remove_item(_PRESERVE_RB)

    def is_empty(self) -> bool:
        """``True`` when ``/State`` is absent or carries no entries.
        A freshly constructed :class:`PDActionSetOCGState` is "empty" in
        this sense. Note that ``/PreserveRB`` is *not* considered for
        emptiness — it is purely a tuning flag and an action with no
        ``/State`` array but a non-default ``/PreserveRB`` is still a
        no-op at viewer level."""
        arr = self.get_cos_state()
        return arr is None or arr.size() == 0

    def is_valid(self) -> bool:
        """``True`` when ``/S`` equals :attr:`SUB_TYPE` (``"SetOCGState"``).
        Sanity check after round-tripping through :meth:`PDAction.create`
        or when wrapping a hand-built :class:`COSDictionary`. Mirrors the
        ``is_valid`` predicate exposed on other action wrappers."""
        return self.get_sub_type() == self.SUB_TYPE

    def get_groups(self) -> list[PDOptionalContentGroup]:
        """Return the OCG entries from ``/State`` as typed
        :class:`PDOptionalContentGroup` wrappers, dropping the preamble
        names. Returns an empty list when ``/State`` is missing.

        Note: each OCG appears once in the result for every dict entry in
        ``/State`` — if the same OCG is referenced twice (e.g. once after
        ``/ON`` and once after ``/OFF``) it appears twice. Callers that
        care about uniqueness should de-duplicate by COS identity."""
        groups: list[PDOptionalContentGroup] = []
        arr = self.get_cos_state()
        if arr is None:
            return groups
        for i in range(arr.size()):
            entry = arr.get_object(i)
            if isinstance(entry, COSDictionary):
                groups.append(PDOptionalContentGroup(entry))
        return groups


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
