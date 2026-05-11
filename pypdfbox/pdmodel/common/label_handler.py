from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LabelHandler(Protocol):
    """Page-label callback protocol.

    Mirrors the package-private ``PDPageLabels.LabelHandler`` inner
    interface (PDPageLabels.java lines 252-255) — invoked by
    :meth:`pypdfbox.pdmodel.PDPageLabels.compute_labels` once per page
    with the 0-based page index and the rendered label string.

    Implement as any callable accepting ``(page_index: int, label: str)``;
    Python's structural typing means a bound method or lambda satisfies the
    protocol without explicit inheritance.
    """

    def new_label(self, page_index: int, label: str) -> None:
        """Receive one ``(page_index, label)`` pair from the walker."""
        ...


__all__ = ["LabelHandler"]
