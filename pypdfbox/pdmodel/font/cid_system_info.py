"""Plain-data ``CIDSystemInfo`` value used by the font-mapper API.

Mirrors ``org.apache.pdfbox.pdmodel.font.CIDSystemInfo`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/CIDSystemInfo.java``
lines 25-58).

This is the *value* class — three immutable fields ``(registry, ordering,
supplement)`` plus a ``toString()`` that emits ``"R-O-S"``. Distinct from
:class:`pypdfbox.pdmodel.font.pd_cid_system_info.PDCIDSystemInfo`, which
wraps a full ``/CIDSystemInfo`` PDF dictionary. The mapper API
(:class:`FontInfo`, :class:`FileSystemFontProvider`) pivots on this
lightweight record because no COS object is required for in-memory
comparison.
"""

from __future__ import annotations


class CIDSystemInfo:
    """Immutable ``(registry, ordering, supplement)`` triple.

    Mirrors upstream Java line 25-58. The class is ``final`` upstream;
    we don't enforce that in Python but the fields are exposed via
    accessors only so subclasses won't accidentally shadow state.
    """

    __slots__ = ("_registry", "_ordering", "_supplement")

    def __init__(self, registry: str, ordering: str, supplement: int) -> None:
        # Upstream constructor (Java line 31-36): plain field assignment.
        self._registry: str = registry
        self._ordering: str = ordering
        self._supplement: int = supplement

    def get_registry(self) -> str:
        """Return the registry identifier (e.g. ``"Adobe"``).

        Mirrors upstream ``getRegistry()`` (Java line 38-41).
        """
        return self._registry

    def get_ordering(self) -> str:
        """Return the ordering identifier (e.g. ``"Japan1"``).

        Mirrors upstream ``getOrdering()`` (Java line 43-46).
        """
        return self._ordering

    def get_supplement(self) -> int:
        """Return the supplement number.

        Mirrors upstream ``getSupplement()`` (Java line 48-51).
        """
        return self._supplement

    def to_string(self) -> str:
        """Return the ``"registry-ordering-supplement"`` form.

        Mirrors upstream ``toString()`` (Java line 53-57).
        """
        return f"{self._registry}-{self._ordering}-{self._supplement}"

    def __str__(self) -> str:
        # Upstream ``toString()`` (Java line 53-57): "R-O-S".
        return self.to_string()

    def __repr__(self) -> str:
        return (
            f"CIDSystemInfo(registry={self._registry!r}, "
            f"ordering={self._ordering!r}, supplement={self._supplement})"
        )

    def __eq__(self, other: object) -> bool:
        # Java's ``final`` value class doesn't override equals, so two
        # instances with the same fields are *not* equal in Java
        # (identity-only). pypdfbox provides structural equality because
        # the in-memory cache keys on this triple and dict lookup needs
        # ``__hash__`` consistency — recorded in CHANGES.md.
        if not isinstance(other, CIDSystemInfo):
            return NotImplemented
        return (
            self._registry == other._registry
            and self._ordering == other._ordering
            and self._supplement == other._supplement
        )

    def __hash__(self) -> int:
        return hash((self._registry, self._ordering, self._supplement))


__all__ = ["CIDSystemInfo"]
