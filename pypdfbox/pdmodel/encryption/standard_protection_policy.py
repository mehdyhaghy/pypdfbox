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

    # ---------- predicate helpers (no upstream equivalent) ----------
    #
    # Upstream PDFBox stores both passwords as Java ``String`` and defaults
    # them to ``""`` so every accessor returns a non-null value. Our port
    # uses ``None`` as the unset sentinel to keep the typing honest, which
    # leaves callers writing ``policy.get_owner_password() is not None``
    # everywhere. The predicates below collapse that into a single call so
    # call sites read more naturally and don't have to know about the
    # ``None`` sentinel.

    def is_owner_password_set(self) -> bool:
        """Return ``True`` when an owner password has been provided.

        Both ``None`` (the unset sentinel used throughout this port) and the
        empty string (matching upstream's default) count as *not set* — an
        empty-string password produces no encryption protection so callers
        treating it as ``set`` would be misleading.
        """
        return bool(self._owner_password)

    def is_user_password_set(self) -> bool:
        """Return ``True`` when a user password has been provided.

        See :py:meth:`is_owner_password_set` for the empty-string note.
        """
        return bool(self._user_password)

    def is_password_protected(self) -> bool:
        """Return ``True`` when either an owner or user password is set.

        The PDF spec allows protecting a document with only an owner
        password (the user opens with no password and inherits the policy)
        or only a user password (rare, but legal). This predicate is the
        OR of the two more granular helpers and answers "would the
        standard handler actually encrypt anything if asked?".
        """
        return self.is_owner_password_set() or self.is_user_password_set()

    def clear_passwords(self) -> None:
        """Reset both passwords to ``None``.

        Useful after a document has been written and the policy object
        outlives the encryption operation — wiping the password fields
        keeps the credential out of the handler's lifecycle longer than
        strictly necessary. No upstream equivalent (Java callers rely on
        garbage collection) but trivially supportable here.
        """
        self._owner_password = None
        self._user_password = None


__all__ = ["StandardProtectionPolicy"]
