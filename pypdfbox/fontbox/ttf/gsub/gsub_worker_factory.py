"""``GsubWorkerFactory`` — pick the right :class:`GsubWorker` for a language.

Mirrors ``org.apache.fontbox.ttf.gsub.GsubWorkerFactory`` from upstream
Apache PDFBox 3.0.x. Upstream's ``Language`` is a Java enum
(``BENGALI``, ``DEVANAGARI``, ``GUJARATI``, ``LATIN``, ``DFLT``,
``UNSPECIFIED``); pypdfbox stores the active language as the enum's
``getName()`` string on :class:`GsubData`. We branch on that string.

Wave 1286 redesign (upstream ``GsubWorkerFactory.java:38`` TODO): when
the explicit ``language`` hint is unknown / ``UNSPECIFIED`` we walk the
font's ``script_list`` and pick the *first* language enum whose ordered
script tags are present in the font. Upstream's bare switch routes every
multi-script font through whatever language the parser pinned first — by
inspecting the actual script tags here we now route on the script tags
the font *carries*, falling back to the explicit hint when both match.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .default_gsub_worker import DefaultGsubWorker
from .gsub_worker import GsubWorker
from .gsub_worker_for_aalt import GsubWorkerForAALT
from .gsub_worker_for_bengali import GsubWorkerForBengali
from .gsub_worker_for_devanagari import GsubWorkerForDevanagari
from .gsub_worker_for_dflt import GsubWorkerForDflt
from .gsub_worker_for_gujarati import GsubWorkerForGujarati
from .gsub_worker_for_latin import GsubWorkerForLatin
from .gsub_worker_for_smcp import GsubWorkerForSMCP
from .gsub_worker_for_tamil import GsubWorkerForTamil

if TYPE_CHECKING:
    from ..cmap_lookup import CmapLookup
    from .gsub_data import GsubData

_LOG = logging.getLogger(__name__)

# Ordered list of (language tag, script tags) pairs. Each entry's script
# tags are checked against the font's ScriptList in order — the first
# language whose preferred script (tags[0]) is present wins; otherwise
# any of the language's secondary script tags counts as a fallback
# match. Order here matches the ``Language`` enum declaration order to
# preserve upstream's tie-breaking when several languages share a font.
_LANGUAGE_SCRIPT_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("BENGALI", ("bng2", "beng")),
    ("DEVANAGARI", ("dev2", "deva")),
    ("GUJARATI", ("gjr2", "gujr")),
    ("TAMIL", ("tml2", "taml")),
    ("LATIN", ("latn",)),
    ("DFLT", ("DFLT",)),
)


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


def _get_script_tags(gsub_data: GsubData) -> set[str]:
    """Return the font's ScriptList tags, or an empty set when unavailable.

    Not every ``GsubData`` implementation carries a ScriptList. Upstream's
    ``MapBackedGsubData`` has no ``getScriptList`` method at all (its factory
    dispatches purely on ``getLanguage()``); the pypdfbox dict-shaped
    :class:`GsubData` does. Returning ``set()`` for the former lets the
    script-tag-confirmation logic degrade gracefully to the bare language
    hint instead of crashing with ``AttributeError``.
    """
    get_script_list = getattr(gsub_data, "get_script_list", None)
    if get_script_list is None:
        return set()
    try:
        return set(get_script_list().keys())
    except (AttributeError, TypeError):
        return set()


def _resolve_language_from_scripts(gsub_data: GsubData) -> str:
    """Walk the font's ScriptList and return the best language tag.

    Returns ``""`` when no language's script tags are present in the
    font — the caller then falls back to the explicit hint or to
    :class:`DefaultGsubWorker`. Preference order:

    1. Preferred (index 0) script tag of each language, in
       :data:`_LANGUAGE_SCRIPT_TAGS` order — e.g. ``"bng2"`` beats
       ``"beng"``.
    2. Secondary tags (index 1+) of each language, same order.

    This implements the upstream TODO redesign: a font carrying both
    ``"latn"`` and ``"deva"`` is now routed to Devanagari when the
    explicit hint asks for it (``"DEVANAGARI"``), and falls back to
    Latin only when nothing more specific is present.
    """
    script_tags = _get_script_tags(gsub_data)
    if not script_tags:
        return ""
    # Pass 1: preferred script tag (index 0) per language.
    for name, tags in _LANGUAGE_SCRIPT_TAGS:
        if tags and tags[0] in script_tags:
            return name
    # Pass 2: any secondary tag.
    for name, tags in _LANGUAGE_SCRIPT_TAGS:
        for tag in tags[1:]:
            if tag in script_tags:
                return name
    return ""


class GsubWorkerFactory:
    """Factory producing a per-language :class:`GsubWorker`.

    Mirrors ``GsubWorkerFactory.getGsubWorker`` from upstream
    (GsubWorkerFactory.java:36). Wave 1286 closes the upstream TODO at
    line 38 — see module docstring for the redesigned dispatch.
    """

    def get_gsub_worker(
        self,
        cmap_lookup: CmapLookup,
        gsub_data: GsubData,
    ) -> GsubWorker:
        # Wave 1286: resolve the language by walking ``script_list`` so a
        # multi-script font is routed by what it actually carries rather
        # than by whichever ``language`` happened to be pinned first.
        hint = _normalize_language(gsub_data.get_language())
        resolved = _resolve_language_from_scripts(gsub_data)
        _LOG.debug("Language hint=%s resolved=%s", hint, resolved)

        # Resolve the font's script tags through the same defensive guard
        # :func:`_resolve_language_from_scripts` uses. Not every ``GsubData``
        # implementation carries a ScriptList: upstream's
        # ``MapBackedGsubData`` (a first-class ``GsubData``) has no
        # ``getScriptList`` at all, and its factory dispatches purely on
        # ``getLanguage()``. Calling ``get_script_list()`` unconditionally
        # here raised ``AttributeError`` on those objects, so guard it and
        # treat "no ScriptList" as "no script-tag confirmation".
        script_tags = _get_script_tags(gsub_data)

        # If the explicit hint matches a language whose script tags are
        # also present in the font, prefer it (matches upstream's
        # exact-match contract). Otherwise prefer the script-derived
        # resolution; only fall through to the bare hint when neither
        # rule fired.
        candidates: list[str] = []
        for name, tags in _LANGUAGE_SCRIPT_TAGS:
            if hint == name and any(t in script_tags for t in tags):
                candidates.append(name)
                break
        if resolved:
            candidates.append(resolved)
        if hint:
            candidates.append(hint)

        for language in candidates:
            if language == "BENGALI":
                return GsubWorkerForBengali(cmap_lookup, gsub_data)
            if language == "DEVANAGARI":
                return GsubWorkerForDevanagari(cmap_lookup, gsub_data)
            if language == "GUJARATI":
                return GsubWorkerForGujarati(cmap_lookup, gsub_data)
            if language == "TAMIL":
                return GsubWorkerForTamil(cmap_lookup, gsub_data)
            if language == "LATIN":
                return GsubWorkerForLatin(gsub_data)
            if language == "DFLT":
                return GsubWorkerForDflt(gsub_data)
            # AALT / SMCP are feature-tag workers rather than per-script
            # workers — wired so callers that pass an explicit hint can
            # opt into the dedicated shaper. They have no preferred
            # ``ScriptList`` tag in :data:`_LANGUAGE_SCRIPT_TAGS`, so
            # they only fire when the caller passes the language
            # explicitly via ``GsubData.language``.
            if language == "AALT":
                return GsubWorkerForAALT(gsub_data)
            if language == "SMCP":
                return GsubWorkerForSMCP(cmap_lookup, gsub_data)
        return DefaultGsubWorker()


__all__ = ["GsubWorkerFactory"]
