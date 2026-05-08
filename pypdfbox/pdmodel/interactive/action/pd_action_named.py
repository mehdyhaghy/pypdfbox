from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_action import PDAction

_N: COSName = COSName.get_pdf_name("N")


class PDActionNamed(PDAction):
    """Named action. Mirrors PDFBox ``PDActionNamed``."""

    SUB_TYPE = "Named"

    # Standard named actions (PDF 32000-1 §12.6.4.11). PDF 1.5+ allows
    # extension names beyond these four; callers may pass arbitrary
    # strings to :meth:`set_n`.
    NAMED_ACTION_NEXT_PAGE = "NextPage"
    NAMED_ACTION_PREV_PAGE = "PrevPage"
    NAMED_ACTION_FIRST_PAGE = "FirstPage"
    NAMED_ACTION_LAST_PAGE = "LastPage"

    #: The four named actions every conforming reader must support
    #: (PDF 32000-1 §12.6.4.11 Table 211). Anything else in ``/N`` is an
    #: extension name and may be unsupported by the viewer.
    STANDARD_NAMED_ACTIONS: frozenset[str] = frozenset(
        {
            NAMED_ACTION_NEXT_PAGE,
            NAMED_ACTION_PREV_PAGE,
            NAMED_ACTION_FIRST_PAGE,
            NAMED_ACTION_LAST_PAGE,
        }
    )

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_n(self) -> str | None:
        return self._action.get_name_as_string(_N)

    def set_n(self, name: str | None) -> None:
        if name is None:
            self._action.remove_item(_N)
            return
        self._action.set_name(_N, name)

    def has_n(self) -> bool:
        """``True`` when ``/N`` is present as a PDF name or string.

        Mirrors upstream's ``getNameAsString`` tolerance: conforming named
        actions store ``/N`` as a name, but string-form entries from
        malformed producers are still readable.
        """
        return self.get_n() is not None

    def clear_n(self) -> None:
        """Remove ``/N`` from the underlying dictionary."""
        self._action.remove_item(_N)

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals ``"Named"``."""
        return self.get_sub_type() == self.SUB_TYPE

    # ---------- predicate helpers (Table 211) ----------

    def is_next_page(self) -> bool:
        """Return ``True`` when ``/N`` is exactly ``"NextPage"`` (Table 211).

        Returns ``False`` for any other value, including ``None`` and
        case-shifted variants — PDF name comparison is case-sensitive."""
        return self.get_n() == self.NAMED_ACTION_NEXT_PAGE

    def is_prev_page(self) -> bool:
        """Return ``True`` when ``/N`` is exactly ``"PrevPage"`` (Table 211)."""
        return self.get_n() == self.NAMED_ACTION_PREV_PAGE

    def is_first_page(self) -> bool:
        """Return ``True`` when ``/N`` is exactly ``"FirstPage"`` (Table 211)."""
        return self.get_n() == self.NAMED_ACTION_FIRST_PAGE

    def is_last_page(self) -> bool:
        """Return ``True`` when ``/N`` is exactly ``"LastPage"`` (Table 211)."""
        return self.get_n() == self.NAMED_ACTION_LAST_PAGE

    def is_standard_named_action(self) -> bool:
        """Return ``True`` when ``/N`` is one of the four standard named
        actions defined in PDF 32000-1 §12.6.4.11 Table 211. Returns
        ``False`` for extension names (PDF 1.5+) and for missing ``/N``."""
        n = self.get_n()
        return n is not None and n in self.STANDARD_NAMED_ACTIONS


__all__ = ["PDActionNamed"]
