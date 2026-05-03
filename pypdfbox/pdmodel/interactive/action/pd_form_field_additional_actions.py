from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_K: COSName = COSName.get_pdf_name("K")
_F: COSName = COSName.get_pdf_name("F")
_V: COSName = COSName.get_pdf_name("V")
_C: COSName = COSName.C  # type: ignore[attr-defined]


class PDFormFieldAdditionalActions:
    """
    Form-field additional-actions dictionary. Mirrors PDFBox
    ``PDFormFieldAdditionalActions`` for the keystroke (``/K``), format
    (``/F``), validate (``/V``) and calculate (``/C``) triggers (PDF
    32000-1:2008 §12.6.3, Table 196).
    """

    # ------------------------------------------------------------------
    # Trigger name constants. PDF 32000-1:2008 §12.6.3 Table 196 names
    # these single-letter keys; expose them so producers can write
    # ``aa.get_cos_object().contains_key(PDFormFieldAdditionalActions.TRIGGER_K)``
    # without hard-coding string literals.
    # ------------------------------------------------------------------
    TRIGGER_K: COSName = _K
    TRIGGER_F: COSName = _F
    TRIGGER_V: COSName = _V
    TRIGGER_C: COSName = _C

    _ALL_TRIGGERS: tuple[tuple[str, COSName], ...] = (
        ("K", _K),
        ("F", _F),
        ("V", _V),
        ("C", _C),
    )

    def __init__(self, actions: COSDictionary | None = None) -> None:
        self._actions = actions if actions is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._actions

    def get_k(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_K)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_k(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_K)
            return
        self._actions.set_item(_K, action.get_cos_object())

    def get_f(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_F)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_f(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_F)
            return
        self._actions.set_item(_F, action.get_cos_object())

    def get_v(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_V)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_v(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_V)
            return
        self._actions.set_item(_V, action.get_cos_object())

    def get_c(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_C)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_c(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_C)
            return
        self._actions.set_item(_C, action.get_cos_object())

    # ------------------------------------------------------------------
    # Predicate helpers. ``has_*`` checks key presence (cheap) without
    # resolving the indirect reference or constructing a typed wrapper,
    # so callers iterating over many fields can short-circuit.
    # ------------------------------------------------------------------

    def has_k(self) -> bool:
        return self._actions.contains_key(_K)

    def has_f(self) -> bool:
        return self._actions.contains_key(_F)

    def has_v(self) -> bool:
        return self._actions.contains_key(_V)

    def has_c(self) -> bool:
        return self._actions.contains_key(_C)

    def is_empty(self) -> bool:
        """Return ``True`` when no field trigger is set. Producers that
        find an empty additional-actions dictionary can elide the ``/AA``
        entry from the field entirely."""
        return not any(self._actions.contains_key(key) for _, key in self._ALL_TRIGGERS)

    def __repr__(self) -> str:
        flags = [label for label, key in self._ALL_TRIGGERS if self._actions.contains_key(key)]
        return f"PDFormFieldAdditionalActions({','.join(flags) or 'empty'})"


__all__ = ["PDFormFieldAdditionalActions"]
