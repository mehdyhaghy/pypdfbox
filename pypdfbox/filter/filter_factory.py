from __future__ import annotations

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

    Mirrors `org.apache.pdfbox.filter.FilterFactory`.
    """

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

    @classmethod
    def is_registered(cls, name: str | COSName) -> bool:
        key = name.name if isinstance(name, COSName) else name
        canonical = cls._ABBREVIATIONS.get(key, key)
        return canonical in cls._registry

    @classmethod
    def registered_names(cls) -> list[str]:
        return sorted(cls._registry.keys())
