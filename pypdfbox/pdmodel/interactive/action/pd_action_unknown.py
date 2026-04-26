from __future__ import annotations

from pypdfbox.cos import COSDictionary

from .pd_action import PDAction


class PDActionUnknown(PDAction):
    """Fallback action wrapper preserving unknown action dictionaries."""

    def __init__(self, action: COSDictionary | None = None) -> None:
        super().__init__(action)


__all__ = ["PDActionUnknown"]
