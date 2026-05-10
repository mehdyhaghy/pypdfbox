"""``GsubWorkerFactory`` — pick the right :class:`GsubWorker` for a language.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerFactory`` from upstream
Apache PDFBox 3.0.x. Upstream's ``Language`` is a Java enum
(``BENGALI``, ``DEVANAGARI``, ``GUJARATI``, ``LATIN``, ``DFLT``,
``UNSPECIFIED``); pypdfbox stores the active language as the enum's
``getName()`` string on :class:`GsubData`. We branch on that string.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .default_gsub_worker import DefaultGsubWorker
from .gsub_worker import GsubWorker
from .gsub_worker_for_bengali import GsubWorkerForBengali
from .gsub_worker_for_devanagari import GsubWorkerForDevanagari
from .gsub_worker_for_dflt import GsubWorkerForDflt
from .gsub_worker_for_gujarati import GsubWorkerForGujarati
from .gsub_worker_for_latin import GsubWorkerForLatin

if TYPE_CHECKING:
    from ..cmap_lookup import CmapLookup
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)


def _normalize_language(language: object) -> str:
    """Coerce ``language`` (string or ``Language`` enum) to an upper-case tag.

    Upstream uses the ``Language`` enum so the dispatch is exact-match;
    on our side :class:`GsubData` historically stored the language as a
    bare string, but the port now ships a real :class:`Language` enum.
    Accept both for parity.
    """
    if language is None:
        return ""
    # Late import to avoid pulling the ``model`` package at module load
    # time (and to keep the worker layer dependency-light).
    try:
        from ..model.language import Language  # noqa: PLC0415
    except ImportError:
        Language = None  # type: ignore[assignment]
    if Language is not None and isinstance(language, Language):
        return language.name.upper()
    return str(language).strip().upper()


class GsubWorkerFactory:
    """Factory producing a per-language :class:`GsubWorker`.

    Mirrors ``GsubWorkerFactory.getGsubWorker`` from upstream
    (GsubWorkerFactory.java:36).
    """

    def get_gsub_worker(
        self,
        cmap_lookup: CmapLookup,
        gsub_data: GsubData,
    ) -> GsubWorker:
        # TODO: upstream notes this needs to be redesigned because a
        # multi-language font ends up routed by whatever language the
        # parser pinned first.
        language = _normalize_language(gsub_data.get_language())
        _LOG.debug("Language: %s", language)

        if language == "BENGALI":
            return GsubWorkerForBengali(cmap_lookup, gsub_data)
        if language == "DEVANAGARI":
            return GsubWorkerForDevanagari(cmap_lookup, gsub_data)
        if language == "GUJARATI":
            return GsubWorkerForGujarati(cmap_lookup, gsub_data)
        if language == "LATIN":
            return GsubWorkerForLatin(gsub_data)
        if language == "DFLT":
            return GsubWorkerForDflt(gsub_data)
        return DefaultGsubWorker()


__all__ = ["GsubWorkerFactory"]
