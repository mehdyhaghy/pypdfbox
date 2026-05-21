"""Bundled Liberation TTF resolver — default last-resort font fallback.

This module has **no upstream counterpart**. It adapts the architectural
pattern established by :mod:`pypdfbox.fontbox.cjk_loader` (wave 1362) to
a *bundled* font set rather than a network-fetched one.

Upstream Apache PDFBox eagerly loads ``LiberationSans-Regular.ttf`` from
``pdfbox/src/main/resources/org/apache/pdfbox/resources/ttf/`` in the
``FontMapperImpl`` constructor and uses it whenever a referenced font is
neither embedded nor present on the system (Java line 117-133). pypdfbox
mirrors that pattern but extends it: the 12 Liberation TTFs
(Sans / Serif / Mono × Regular / Bold / Italic / BoldItalic) are bundled
inside the wheel at ``pypdfbox/resources/ttf/``, so the descriptor flags
(:meth:`PDFontDescriptor.is_fixed_pitch`, :meth:`is_serif`,
:meth:`is_italic`, plus name-based bold detection and ``/FontWeight``)
pick the *closest* family + weight match rather than always falling back
to Sans-Regular.

License: Liberation Fonts (Red Hat / Liberation Sans Reserved Font Name)
ship under the **SIL Open Font License 1.1** — permissive, already on
the project allow-list. ``DejaVuSans.ttf`` ships under Bitstream Vera /
DejaVu (BSD-style) terms. Both license texts live alongside the TTFs at
``pypdfbox/resources/ttf/LICENSE.txt`` and
``pypdfbox/resources/ttf/LICENSE-DejaVu.txt``; the project ``NOTICE``
file carries the upstream attribution chain.

Unlike :mod:`pypdfbox.fontbox.cjk_loader`, this resolver is **on by
default** — no env-var gate, no opt-in extra. The fonts are part of the
wheel and the substitution is the default behaviour, matching upstream
PDFBox's eager constructor load.

Coverage: Latin (incl. extended), Cyrillic, Greek, Hebrew, Arabic, and
~120 other languages render with real glyphs instead of ``.notdef``
placeholders. CJK is *not* covered here — that path remains
:mod:`pypdfbox.fontbox.cjk_loader` and still requires
``pip install pypdfbox[cjk]`` plus the ``PYPDFBOX_CJK_AUTODOWNLOAD``
env var. Devanagari / Bengali / Tamil / Thai and other Indic scripts
fall back to :data:`DEJAVU_PATH` (DejaVu Sans), which carries broader
Unicode coverage than Liberation.
"""

from __future__ import annotations

import functools
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


# Family + weight key -> filename inside ``pypdfbox/resources/ttf/``.
_ASSET_MAP: dict[str, str] = {
    "Sans-Regular": "LiberationSans-Regular.ttf",
    "Sans-Bold": "LiberationSans-Bold.ttf",
    "Sans-Italic": "LiberationSans-Italic.ttf",
    "Sans-BoldItalic": "LiberationSans-BoldItalic.ttf",
    "Serif-Regular": "LiberationSerif-Regular.ttf",
    "Serif-Bold": "LiberationSerif-Bold.ttf",
    "Serif-Italic": "LiberationSerif-Italic.ttf",
    "Serif-BoldItalic": "LiberationSerif-BoldItalic.ttf",
    "Mono-Regular": "LiberationMono-Regular.ttf",
    "Mono-Bold": "LiberationMono-Bold.ttf",
    "Mono-Italic": "LiberationMono-Italic.ttf",
    "Mono-BoldItalic": "LiberationMono-BoldItalic.ttf",
}

_DEJAVU_FILENAME = "DejaVuSans.ttf"


@functools.lru_cache(maxsize=1)
def bundled_dir() -> Path:
    """Return the on-disk path of the bundled ``resources/ttf/`` directory.

    Uses :func:`importlib.resources.files` so the lookup works identically
    inside installed wheels and source-tree editable installs across all
    supported platforms (Windows / macOS / Linux). Cached because the
    resolution is deterministic for the lifetime of the process.
    """
    # ``files(...)`` returns a Traversable; for an on-disk package this
    # is a concrete ``pathlib.Path`` subclass. We coerce via ``str()``
    # rather than relying on private attributes so the path is portable
    # under namespace-package / zipimport edge cases that may surface on
    # exotic install layouts.
    return Path(str(resources.files("pypdfbox.resources.ttf")))


@functools.lru_cache(maxsize=1)
def dejavu_path() -> Path:
    """Return the on-disk path of the bundled ``DejaVuSans.ttf``.

    Used as a secondary fallback for content (Devanagari, Bengali, math
    symbols) whose glyphs aren't carried by the Liberation set. Callers
    should treat this purely as a path lookup — glyph-level coverage
    testing is the renderer's responsibility.
    """
    return bundled_dir() / _DEJAVU_FILENAME


def _is_bold_via_name(font_name: str | None) -> bool:
    """Return ``True`` when *font_name* looks like a bold variant.

    Mirrors the heuristic in
    :meth:`FontMapperImpl._get_fallback_font_name` (Java line 231-307):
    case-insensitive ``"bold"`` / ``"black"`` / ``"heavy"`` substring
    match. Used as a fallback when ``/FontWeight`` is absent or zero.
    """
    if not font_name:
        return False
    lower = font_name.lower()
    return "bold" in lower or "black" in lower or "heavy" in lower


def _descriptor_to_key(font_descriptor: PDFontDescriptor | None) -> str:
    """Derive a Liberation family+weight key from *font_descriptor*.

    Family selection (most-specific first):

    * :meth:`is_fixed_pitch` -> ``Mono``
    * :meth:`is_serif`       -> ``Serif``
    * otherwise              -> ``Sans``

    Bold detection: ``/FontWeight >= 600`` OR the ``/FontName`` contains
    ``"bold"`` / ``"black"`` / ``"heavy"`` (case-insensitive). Italic
    detection: :meth:`is_italic` alone.

    ``font_descriptor=None`` maps to ``"Sans-Regular"`` — mirrors
    upstream PDFBox's default constructor fallback.
    """
    if font_descriptor is None:
        return "Sans-Regular"

    # Family ------------------------------------------------------------
    family: str
    try:
        is_fixed = bool(font_descriptor.is_fixed_pitch())
    except AttributeError:
        is_fixed = False
    if is_fixed:
        family = "Mono"
    else:
        try:
            is_serif = bool(font_descriptor.is_serif())
        except AttributeError:
            is_serif = False
        family = "Serif" if is_serif else "Sans"

    # Bold --------------------------------------------------------------
    is_bold = False
    try:
        weight = float(font_descriptor.get_font_weight() or 0)
    except (AttributeError, TypeError, ValueError):
        weight = 0.0
    if weight >= 600:
        is_bold = True
    if not is_bold:
        try:
            name = font_descriptor.get_font_name()
        except AttributeError:
            name = None
        is_bold = _is_bold_via_name(name)

    # Italic ------------------------------------------------------------
    try:
        is_italic = bool(font_descriptor.is_italic())
    except AttributeError:
        is_italic = False

    if is_bold and is_italic:
        weight_key = "BoldItalic"
    elif is_bold:
        weight_key = "Bold"
    elif is_italic:
        weight_key = "Italic"
    else:
        weight_key = "Regular"

    return f"{family}-{weight_key}"


def descriptor_to_key(font_descriptor: PDFontDescriptor | None) -> str:
    """Public spelling of :func:`_descriptor_to_key` for tests + callers."""
    return _descriptor_to_key(font_descriptor)


def ensure_font(font_descriptor: PDFontDescriptor | None) -> Path | None:
    """Return the path of the bundled Liberation TTF best matching *font_descriptor*.

    Returns ``None`` only when the bundle is somehow incomplete (e.g.
    custom wheel built without the resources package); callers should
    treat that as an inert fall-through identical to the upstream
    "font not available" branch.
    """
    key = _descriptor_to_key(font_descriptor)
    return _resolve_key(key)


@functools.lru_cache(maxsize=len(_ASSET_MAP))
def _resolve_key(key: str) -> Path | None:
    """Look up *key* in :data:`_ASSET_MAP` and return the bundled path.

    Cached because the lookup is purely a string -> Path map; callers
    invoke us once per descriptor-style and we want the second call to
    be free.
    """
    filename = _ASSET_MAP.get(key)
    if filename is None:
        return None
    path = bundled_dir() / filename
    if not path.is_file():
        return None
    return path


__all__ = [
    "bundled_dir",
    "dejavu_path",
    "descriptor_to_key",
    "ensure_font",
]
