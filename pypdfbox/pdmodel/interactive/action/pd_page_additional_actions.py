from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_O: COSName = COSName.get_pdf_name("O")
_C: COSName = COSName.C  # type: ignore[attr-defined]


class PDPageAdditionalActions:
    """
    Page additional-actions dictionary. Mirrors PDFBox
    ``PDPageAdditionalActions`` for the page-open (``/O``) and page-close
    (``/C``) triggers.
    """

    # ------------------------------------------------------------------
    # Trigger name constants. PDF 32000-1:2008 §12.6.3 Table 194 names
    # these single-letter keys; expose them so producers can write
    # ``aa.get_cos_object().contains_key(PDPageAdditionalActions.TRIGGER_O)``
    # without hard-coding string literals.
    # ------------------------------------------------------------------
    TRIGGER_O: COSName = _O
    TRIGGER_C: COSName = _C

    _ALL_TRIGGERS: tuple[tuple[str, COSName], ...] = (
        ("O", _O),
        ("C", _C),
    )

    def __init__(self, actions: COSDictionary | None = None) -> None:
        self._actions = actions if actions is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._actions

    def get_o(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_O)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_o(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_O)
            return
        self._actions.set_item(_O, action.get_cos_object())

    def get_c(self) -> PDAction | None:
        value = self._actions.get_dictionary_object(_C)
        return PDAction.create(value) if isinstance(value, COSDictionary) else None

    def set_c(self, action: PDAction | None) -> None:
        if action is None:
            self._actions.remove_item(_C)
            return
        self._actions.set_item(_C, action.get_cos_object())

    # ------------------------------------------------------------------
    # Upstream-named aliases. PDFBox exposes longer descriptive accessors
    # alongside the single-letter ones; mirror those for source-level
    # familiarity.
    # ------------------------------------------------------------------

    def get_open_action(self) -> PDAction | None:
        return self.get_o()

    def set_open_action(self, action: PDAction | None) -> None:
        self.set_o(action)

    def get_close_action(self) -> PDAction | None:
        return self.get_c()

    def set_close_action(self, action: PDAction | None) -> None:
        self.set_c(action)

    # ------------------------------------------------------------------
    # Predicate helpers. ``has_*`` checks key presence (cheap) without
    # resolving the indirect reference or constructing a typed wrapper,
    # so callers iterating over many pages can short-circuit.
    # ------------------------------------------------------------------

    def has_o(self) -> bool:
        return self._actions.contains_key(_O)

    def has_c(self) -> bool:
        return self._actions.contains_key(_C)

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return ``True`` when neither ``/O`` nor ``/C`` is set. Matches
        upstream's notion of an "empty" additional-actions entry — a
        producer that finds no triggers attached can elide the dictionary
        entirely."""
        return not self._actions.contains_key(_O) and not self._actions.contains_key(_C)

    def __repr__(self) -> str:
        flags: list[str] = []
        if self._actions.contains_key(_O):
            flags.append("O")
        if self._actions.contains_key(_C):
            flags.append("C")
        return f"PDPageAdditionalActions({','.join(flags) or 'empty'})"


__all__ = ["PDPageAdditionalActions"]
