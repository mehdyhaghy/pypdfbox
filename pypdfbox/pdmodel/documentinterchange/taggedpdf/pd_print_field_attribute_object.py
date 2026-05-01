from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_standard_attribute_object import PDStandardAttributeObject


class PDPrintFieldAttributeObject(PDStandardAttributeObject):
    """
    A PrintField attribute object (``/O /PrintField``). Mirrors PDFBox
    ``PDPrintFieldAttributeObject``.
    """

    # Upstream-parity owner constant.
    OWNER_PRINT_FIELD: str = "PrintField"
    # Pypdfbox-style alias kept for prior callers.
    OWNER: str = "PrintField"

    # Dictionary keys (upstream private static finals).
    ROLE: str = "Role"
    CHECKED: str = "checked"
    DESC: str = "Desc"

    # Role values (upstream PDFBox constants).
    ROLE_RB: str = "rb"
    ROLE_CB: str = "cb"
    ROLE_PB: str = "pb"
    ROLE_TV: str = "tv"

    # PDFBox-aligned aliases.
    ROLE_RADIO_BUTTON: str = "rb"
    ROLE_CHECK_BOX: str = "cb"
    ROLE_PUSH_BUTTON: str = "pb"
    ROLE_TEXT_VALUE: str = "tv"

    # Checked state values (upstream PDFBox constants).
    CHECKED_STATE_ON: str = "on"
    CHECKED_STATE_OFF: str = "off"
    CHECKED_STATE_NEUTRAL: str = "neutral"

    # PDFBox-aligned aliases.
    CHECKED_ON: str = "on"
    CHECKED_OFF: str = "off"
    CHECKED_NEUTRAL: str = "neutral"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        super().__init__(dictionary)
        if dictionary is None:
            self.set_owner(self.OWNER_PRINT_FIELD)

    # ---------- /Role ----------

    def get_role(self) -> str | None:
        return self._get_name(self.ROLE)

    def set_role(self, role: str | None) -> None:
        self._set_name(self.ROLE, role)

    # ---------- /checked ----------

    def get_checked_state(self) -> str:
        """Upstream-parity name. Returns the checked state, default
        :attr:`CHECKED_STATE_OFF` when absent."""
        return self._get_name(self.CHECKED, self.CHECKED_STATE_OFF)

    def set_checked_state(self, checked_state: str) -> None:
        """Upstream-parity name."""
        self._set_name(self.CHECKED, checked_state)

    # Pypdfbox-style aliases retained for prior callers.
    def get_checked(self) -> str:
        return self.get_checked_state()

    def set_checked(self, checked: str) -> None:
        self.set_checked_state(checked)

    # ---------- /Desc (alternate name) ----------

    def get_alternate_name(self) -> str | None:
        """Upstream-parity name for the ``/Desc`` entry."""
        return self._get_string(self.DESC)

    def set_alternate_name(self, alternate_name: str | None) -> None:
        """Upstream-parity setter for the ``/Desc`` entry."""
        if alternate_name is None or alternate_name == "":
            self._dictionary.remove_item(self.DESC)
        else:
            self._set_string(self.DESC, alternate_name)

    # Pypdfbox-style aliases retained for prior callers.
    def get_desc(self) -> str | None:
        return self.get_alternate_name()

    def set_desc(self, desc: str | None) -> None:
        self.set_alternate_name(desc)

    def get_description(self) -> str | None:
        return self.get_alternate_name()

    def set_description(self, description: str | None) -> None:
        self.set_alternate_name(description)

    def __str__(self) -> str:
        """Mirror upstream ``PDPrintFieldAttributeObject.toString()`` which
        appends ``", Role=<role>"`` / ``", Checked=<state>"`` /
        ``", Desc=<desc>"`` for each entry that is specified."""
        sb = super().__str__()
        if self.is_specified(self.ROLE):
            sb = f"{sb}, Role={self.get_role()}"
        if self.is_specified(self.CHECKED):
            sb = f"{sb}, Checked={self.get_checked_state()}"
        if self.is_specified(self.DESC):
            sb = f"{sb}, Desc={self.get_alternate_name()}"
        return sb

    def __repr__(self) -> str:
        return (
            f"PDPrintFieldAttributeObject(O={self.get_owner()}, "
            f"Role={self.get_role()}, checked={self.get_checked_state()})"
        )


__all__ = ["PDPrintFieldAttributeObject"]
