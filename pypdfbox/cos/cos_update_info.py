from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cos_increment import COSIncrement
    from .cos_update_state import COSUpdateState


class COSUpdateInfo(ABC):
    """Marker interface implemented by COS objects that participate in
    incremental save. Mirrors ``org.apache.pdfbox.cos.COSUpdateInfo``
    (an interface in Java that extends ``COSObjectable``).

    All concrete COS types (``COSDictionary``, ``COSArray``, ``COSStream``,
    ``COSObject``) provide a ``get_update_state()`` method that returns a
    ``COSUpdateState``; the default helpers here mirror upstream's default
    methods on the interface.
    """

    @abstractmethod
    def get_update_state(self) -> COSUpdateState:
        """Return the ``COSUpdateState`` for this update-info object.

        Mirrors upstream ``COSUpdateInfo.getUpdateState`` (Java line 63).
        """

    def is_need_to_be_updated(self) -> bool:
        """``True`` if this object must be written on incremental save.

        Mirrors upstream ``COSUpdateInfo.isNeedToBeUpdated`` (Java line 30).
        """
        return self.get_update_state().is_updated()

    def set_need_to_be_updated(self, flag: bool) -> None:
        """Set the update flag (``True`` to mark the object as dirty).

        Mirrors upstream ``COSUpdateInfo.setNeedToBeUpdated`` (Java line 41).
        """
        self.get_update_state().update(flag)

    def to_increment(self) -> COSIncrement:
        """Create a fresh ``COSIncrement`` seeded with this update-info.

        Mirrors upstream ``COSUpdateInfo.toIncrement`` (Java line 52).
        """
        return self.get_update_state().to_increment()
