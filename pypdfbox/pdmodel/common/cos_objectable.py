from __future__ import annotations

from typing import Protocol, runtime_checkable

from pypdfbox.cos import COSBase


@runtime_checkable
class COSObjectable(Protocol):
    """Protocol for objects that can be converted to a ``COSBase``.

    Mirrors ``org.apache.pdfbox.pdmodel.common.COSObjectable`` (Java
    lines 26-34). PDFBox uses this single-method interface as the lingua
    franca for "wrapper carries a backing COS object" — every PD-level
    wrapper exposes ``get_cos_object()`` returning its underlying
    ``COSDictionary`` / ``COSArray`` / ``COSStream``.

    Python uses a :class:`Protocol` with :func:`runtime_checkable`, so
    ``isinstance(wrapper, COSObjectable)`` works without requiring the
    wrapper to subclass anything. This mirrors Java's "duck typing via
    interface" without forcing structural inheritance through the entire
    PD hierarchy.
    """

    def get_cos_object(self) -> COSBase:
        """Return the underlying COS object."""
        ...


__all__ = ["COSObjectable"]
