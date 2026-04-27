"""CMap resource loader and cache.

Mirrors the upstream ``org.apache.pdfbox.pdmodel.font.CMapManager`` helper
(which lives in the ``pdmodel.font`` package upstream because the bundled
predefined CMap resources ship with the ``fontbox`` jar). pypdfbox keeps
the loader co-located with the resources directory under
``pypdfbox.fontbox.cmap`` so the cache and the on-disk fixtures sit
together.

Only a small subset of the Adobe predefined CMaps is bundled (the CJK
Unicode-mapping ones plus ``Identity-H`` / ``Identity-V``). The full set
is ~50 files / tens of megabytes — too heavy to ship with the wheel by
default. PDFs referencing other predefined CMaps fall through to a
``None`` return from :meth:`CMapManager.get_predefined_cmap`, which the
caller can degrade gracefully on (matching upstream's
``IOException``-as-control-flow behaviour without forcing the exception).
"""

from __future__ import annotations

from threading import Lock

from .cmap import CMap
from .cmap_parser import CMapParser


class CMapManager:
    """CMap resource loader and cache (parity with upstream).

    All methods are static — the upstream class has a private
    constructor and exposes only ``getPredefinedCMap`` /
    ``parseCMap``. The cache is shared process-wide and is keyed by the
    upstream name (``Identity-H``, ``Adobe-Japan1-UCS2``, etc).
    """

    _CMAP_CACHE: dict[str, CMap] = {}
    _CACHE_LOCK = Lock()

    def __init__(self) -> None:  # pragma: no cover - parity with upstream
        raise TypeError(
            "CMapManager has no instance API; use the static methods."
        )

    @classmethod
    def get_predefined_cmap(cls, cmap_name: str) -> CMap | None:
        """Fetch the predefined CMap from disk (or cache).

        Returns ``None`` when the requested CMap is not bundled with this
        build of pypdfbox. Upstream throws ``IOException`` here; we
        prefer ``None`` so callers can fall back to font-level encoding
        without having to catch an exception around every call site
        (the upstream ``PDType0Font`` already swallows the exception).

        :param cmap_name: predefined CMap name, e.g. ``Identity-H``,
            ``Adobe-Japan1-UCS2``.
        """
        cached = cls._CMAP_CACHE.get(cmap_name)
        if cached is not None:
            return cached
        try:
            target = CMapParser.parse_predefined(cmap_name)
        except OSError:
            return None
        with cls._CACHE_LOCK:
            # Re-check inside the lock so concurrent first-loads share an
            # instance. The cache is keyed by the *parsed* CMap name (which
            # may differ from the request — upstream stores it under
            # ``targetCmap.getName()``).
            stored_name = target.get_name() or cmap_name
            cached = cls._CMAP_CACHE.get(stored_name)
            if cached is not None:
                return cached
            cls._CMAP_CACHE[stored_name] = target
        return target

    @classmethod
    def parse_cmap(cls, source: object) -> CMap | None:
        """Parse a CMap from an arbitrary input source (parity hook).

        Mirrors upstream ``parseCMap(RandomAccessRead)``: returns the
        parsed CMap or ``None`` when ``source`` is ``None``. ``source``
        may be any input ``CMapParser.parse`` accepts —
        ``RandomAccessRead``, a binary file-like, or a bytes-like buffer.
        """
        if source is None:
            return None
        return CMapParser().parse(source)

    @classmethod
    def clear_cache(cls) -> None:
        """Drop all cached predefined CMaps.

        Not present upstream — pypdfbox enrichment to make tests
        deterministic. The upstream cache is process-lifetime; ours can
        be reset between test cases.
        """
        with cls._CACHE_LOCK:
            cls._CMAP_CACHE.clear()
