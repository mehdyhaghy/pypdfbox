from __future__ import annotations

from .access_permission import AccessPermission
from .protection_policy import ProtectionPolicy


class StandardProtectionPolicy(ProtectionPolicy):
    """
    Password-based protection (the PDF "Standard" security handler). Holds
    owner + user passwords and the bit-flag permission set applied when the
    document is opened with the user password.
    """

    def __init__(
        self,
        owner_password: str | None = None,
        user_password: str | None = None,
        permissions: AccessPermission | None = None,
    ) -> None:
        super().__init__()
        self._owner_password: str | None = owner_password
        self._user_password: str | None = user_password
        self._permissions: AccessPermission = (
            permissions if permissions is not None else AccessPermission()
        )

    def get_owner_password(self) -> str | None:
        return self._owner_password

    def set_owner_password(self, p: str | None) -> None:
        self._owner_password = p

    def get_user_password(self) -> str | None:
        return self._user_password

    def set_user_password(self, p: str | None) -> None:
        self._user_password = p

    def get_permissions(self) -> AccessPermission:
        return self._permissions

    def set_permissions(self, p: AccessPermission) -> None:
        self._permissions = p


__all__ = ["StandardProtectionPolicy"]
