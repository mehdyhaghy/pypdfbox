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
        return self._dictionary.get_name_as_string(self.ROLE)

    def set_role(self, role: str | None) -> None:
        self._set_name(self.ROLE, role)

    # ---------- /checked ----------

    def get_checked_state(self) -> str:
        """Upstream-parity name. Returns the checked state, default
        :attr:`CHECKED_STATE_OFF` when absent."""
        value = self._dictionary.get_name_as_string(
            self.CHECKED, self.CHECKED_STATE_OFF
        )
        return value if value is not None else self.CHECKED_STATE_OFF

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

    # ---------- per-key presence / clear helpers ----------

    def is_role_specified(self) -> bool:
        """``True`` iff ``/Role`` is explicitly written."""
        return self.is_specified(self.ROLE)

    def has_role(self) -> bool:
        """Alias for :meth:`is_role_specified`."""
        return self.is_role_specified()

    def clear_role(self) -> None:
        """Remove the ``/Role`` entry if present."""
        self.clear_attribute(self.ROLE)

    def is_checked_state_specified(self) -> bool:
        """``True`` iff ``/checked`` is explicitly written."""
        return self.is_specified(self.CHECKED)

    def has_checked_state(self) -> bool:
        """Alias for :meth:`is_checked_state_specified`."""
        return self.is_checked_state_specified()

    def clear_checked_state(self) -> None:
        """Remove the ``/checked`` entry if present."""
        self.clear_attribute(self.CHECKED)

    def clear_checked(self) -> None:
        """Pypdfbox-style alias for :meth:`clear_checked_state`."""
        self.clear_checked_state()

    def is_alternate_name_specified(self) -> bool:
        """``True`` iff ``/Desc`` is explicitly written."""
        return self.is_specified(self.DESC)

    def has_alternate_name(self) -> bool:
        """Alias for :meth:`is_alternate_name_specified`."""
        return self.is_alternate_name_specified()

    def clear_alternate_name(self) -> None:
        """Remove the ``/Desc`` entry if present."""
        self.clear_attribute(self.DESC)

    def clear_desc(self) -> None:
        """Pypdfbox-style alias for :meth:`clear_alternate_name`."""
        self.clear_alternate_name()

    def clear_description(self) -> None:
        """Pypdfbox-style alias for :meth:`clear_alternate_name`."""
        self.clear_alternate_name()

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
