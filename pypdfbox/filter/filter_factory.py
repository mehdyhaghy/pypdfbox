from __future__ import annotations

from typing import ClassVar

from pypdfbox.cos import COSName

from .filter import Filter


class FilterFactory:
    """
    Registry mapping ``COSName`` filter names to ``Filter`` instances.

    Filters register themselves at import time via
    ``FilterFactory.register(name, instance)``. The PDF specification
    allows both long names (``/FlateDecode``) and short abbreviations
    (``/Fl``) per ISO 32000-1 §7.4.2 Table 6 — both forms are accepted
    by ``get`` so callers don't need to disambiguate.

    Mirrors `org.apache.pdfbox.filter.FilterFactory`. Upstream exposes
    a singleton via ``FilterFactory.INSTANCE``; the singleton is
    populated lazily on first access (see ``__class_getattr__`` below).
    """

    INSTANCE: ClassVar[FilterFactory]
    _registry: dict[str, Filter] = {}

    # Standard short-name → long-name mapping per ISO 32000-1 §7.4.2 Table 6.
    _ABBREVIATIONS: dict[str, str] = {
        "AHx": "ASCIIHexDecode",
        "A85": "ASCII85Decode",
        "LZW": "LZWDecode",
        "Fl": "FlateDecode",
        "RL": "RunLengthDecode",
        "CCF": "CCITTFaxDecode",
        "DCT": "DCTDecode",
        "JPX": "JPXDecode",
    }

    @classmethod
    def register(cls, name: str | COSName, instance: Filter) -> None:
        key = name.name if isinstance(name, COSName) else name
        cls._registry[key] = instance

    @classmethod
    def get(cls, name: str | COSName) -> Filter:
        """Return the filter for ``name``. Raises ``KeyError`` when no
        filter is registered for that name. Resolves short-name
        abbreviations (e.g. ``/Fl`` → ``/FlateDecode``)."""
        key = name.name if isinstance(name, COSName) else name
        canonical = cls._ABBREVIATIONS.get(key, key)
        if canonical not in cls._registry:
            raise KeyError(f"no filter registered for {key!r} (resolved to {canonical!r})")
        return cls._registry[canonical]

    # ------------------------------------------------------------------
    # Upstream-named accessors (mirror ``org.apache.pdfbox.filter.FilterFactory``).
    # ------------------------------------------------------------------

    @classmethod
    def get_filter(cls, filter_name: str | COSName) -> Filter:
        """Look up a filter by its long PDF name (or COSName).

        Mirrors ``FilterFactory#getFilter(COSName)``. Short-name
        abbreviations are also resolved here for caller convenience.
        """
        return cls.get(filter_name)

    @classmethod
    def get_filter_by_short_name(cls, short_name: str | COSName) -> Filter:
        """Look up a filter by its PDF abbreviation per ISO 32000-1
        §7.4.2 Table 6 (e.g. ``"Fl"`` → ``FlateDecode``).

        Mirrors ``FilterFactory#getFilterByShortName(COSName)``. Raises
        ``KeyError`` when ``short_name`` is not a recognised abbreviation
        or when the resolved long name is not registered.
        """
        key = short_name.name if isinstance(short_name, COSName) else short_name
        if key not in cls._ABBREVIATIONS:
            raise KeyError(f"unknown filter short name {key!r}")
        canonical = cls._ABBREVIATIONS[key]
        if canonical not in cls._registry:
            raise KeyError(
                f"no filter registered for short name {key!r} (resolved to {canonical!r})"
            )
        return cls._registry[canonical]

    @classmethod
    def is_registered(cls, name: str | COSName) -> bool:
        key = name.name if isinstance(name, COSName) else name
        canonical = cls._ABBREVIATIONS.get(key, key)
        return canonical in cls._registry

    @classmethod
    def registered_names(cls) -> list[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def get_all_filters(cls) -> list[Filter]:
        """Return every registered ``Filter`` instance, deduplicated.

        Mirrors ``FilterFactory#getAllFilters`` (package-private in
        upstream, used in tests). The Java map keys both long and short
        ``COSName`` entries to the same singleton; we keep just one copy
        per filter instance here so consumers iterating over the result
        don't double-process a stream.
        """
        seen: list[Filter] = []
        for instance in cls._registry.values():
            if instance not in seen:
                seen.append(instance)
        return seen


# Upstream exposes ``FilterFactory.INSTANCE`` as a class-level singleton.
# Bind it after the class body so the attribute is concrete (no metaclass
# tricks needed). All state lives on the class itself, so the singleton
# acts as a thin handle that delegates through the shared registry.
FilterFactory.INSTANCE = FilterFactory()
