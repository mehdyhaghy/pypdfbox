"""Opt-in Noto Sans CJK auto-downloader for last-resort CJK fallback.

This module has **no upstream counterpart**. Apache PDFBox does not bundle
or fetch CJK fonts — when a PDF references a CJK font that is neither
embedded nor available on the system, upstream produces ``.notdef``
glyphs. pypdfbox preserves that behaviour by default; this loader is an
opt-in extension activated by two independent conditions:

1. The user installs pypdfbox with the ``cjk`` extra
   (``pip install pypdfbox[cjk]``). The extra carries no Python deps —
   it is purely a marker that the user has consented to potential
   network fetches.

2. The environment variable ``PYPDFBOX_CJK_AUTODOWNLOAD`` is set to
   ``"1"`` / ``"true"`` / ``"yes"`` (case-insensitive). Without this
   second toggle the loader stays inert even when the extra is
   installed — so a user who installs ``pypdfbox[cjk]`` for some other
   reason never accidentally triggers a download.

When both gates are open, :func:`ensure_language` resolves the requested
CIDSystemInfo ordering to one of the five single-language Noto Sans CJK
release zips (JP / KR / SC / TC / HK), downloads it from
``github.com/notofonts/noto-cjk`` releases, verifies the SHA-256 against
a pinned manifest, and extracts ``Noto Sans{lang}-Regular.otf`` into the
per-user cache directory. Subsequent calls reuse the cached file.

License: Noto Sans CJK is SIL Open Font License 1.1 — permissive,
already on the project allow-list. Pypdfbox itself does not redistribute
the font binaries; it only fetches them from the upstream release on
the user's behalf.

Upstream release pinned: ``Sans2.004`` (2022-01-27,
https://github.com/notofonts/noto-cjk/releases/tag/Sans2.004).
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import sys
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

_LOG = logging.getLogger(__name__)

_RELEASE_TAG = "Sans2.004"
_BASE_URL = (
    "https://github.com/notofonts/noto-cjk/releases/download/" + _RELEASE_TAG
)

_ENV_FLAG = "PYPDFBOX_CJK_AUTODOWNLOAD"
_ENV_CACHE_OVERRIDE = "PYPDFBOX_CJK_CACHE_DIR"
_TRUTHY = frozenset({"1", "true", "yes", "on"})

# Map Adobe CIDSystemInfo ordering -> Noto language code.
_ORDERING_TO_LANG: dict[str, str] = {
    "Japan1": "JP",
    "Korea1": "KR",
    "GB1": "SC",
    "CNS1": "TC",
}


@dataclass(frozen=True)
class _Asset:
    """One pinned single-language Noto Sans CJK release zip."""

    asset_name: str
    sha256: str
    font_filename: str  # the Regular weight inside the zip


_MANIFEST: dict[str, _Asset] = {
    "JP": _Asset(
        asset_name="16_NotoSansJP.zip",
        sha256="2bbdd2c20f30670b39ca735c96d75f1fdabdb348103e43b820cf17701fd22b18",
        font_filename="NotoSansJP-Regular.otf",
    ),
    "KR": _Asset(
        asset_name="17_NotoSansKR.zip",
        sha256="ac7eeb4e2b0d41de8ff31b2d6e1e2a41caf253fd5cefb380bfa1f40f1747b612",
        font_filename="NotoSansKR-Regular.otf",
    ),
    "SC": _Asset(
        asset_name="18_NotoSansSC.zip",
        sha256="4d107c09ada479d3e48b6e78c83835773cbd9214bf6e12cdb7b60f8e068292ec",
        font_filename="NotoSansSC-Regular.otf",
    ),
    "TC": _Asset(
        asset_name="19_NotoSansTC.zip",
        sha256="fbbcb216be8056a436c7ec142847f302bb1932d07bdad8b322f4953a389d7cbc",
        font_filename="NotoSansTC-Regular.otf",
    ),
    "HK": _Asset(
        asset_name="20_NotoSansHK.zip",
        sha256="c2d8a17fc668116920b75a3bc6f63606faefe43722efec7bb03c66164b3ec52f",
        font_filename="NotoSansHK-Regular.otf",
    ),
}


def is_autodownload_enabled() -> bool:
    """Return ``True`` when the env-var gate is set to a truthy value."""
    return os.environ.get(_ENV_FLAG, "").lower() in _TRUTHY


def cache_dir() -> Path:
    """Return the per-user cache directory for fetched Noto CJK fonts.

    Honours ``PYPDFBOX_CJK_CACHE_DIR`` first (mainly for tests + ops
    overrides), then falls back to platform-default user cache roots
    via stdlib only — mirrors the pattern in
    :mod:`pypdfbox.debugger.ui.window_prefs`.
    """
    override = os.environ.get(_ENV_CACHE_OVERRIDE)
    if override:
        return Path(override)
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        base = (
            Path(local)
            if local
            else Path.home() / "AppData" / "Local"
        )
        return base / "pypdfbox" / "fonts" / "noto-cjk"
    # macOS + Linux honour XDG_CACHE_HOME, falling back to ~/.cache.
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "pypdfbox" / "fonts" / "noto-cjk"


def language_for_ordering(ordering: str) -> str | None:
    """Map an Adobe CIDSystemInfo ordering to a Noto language code.

    Returns ``None`` for orderings without a Noto Sans CJK equivalent.
    Adobe-KR / Adobe-Identity etc. fall through to ``None`` — callers
    treat that as "no auto-download available".
    """
    return _ORDERING_TO_LANG.get(ordering)


def ensure_language(
    ordering: str,
    *,
    opener=urlopen,  # injected in tests
) -> Path | None:
    """Return path to a cached Noto Sans CJK Regular font for *ordering*.

    Behaviour:

    * If the loader is not opted-in via :func:`is_autodownload_enabled`,
      returns ``None`` without touching disk or network.
    * If *ordering* is not a recognised CJK ordering, returns ``None``.
    * If the font is already present in :func:`cache_dir`, returns it.
    * Otherwise fetches the upstream release zip via *opener* (defaults
      to :func:`urllib.request.urlopen`), verifies SHA-256, extracts
      only the Regular weight, and returns the resulting path. On any
      failure (network error, SHA mismatch, missing entry in zip) logs
      a warning and returns ``None`` so callers can fall through to
      ``.notdef`` rendering rather than raising.
    """
    if not is_autodownload_enabled():
        return None
    lang = language_for_ordering(ordering)
    if lang is None:
        return None
    asset = _MANIFEST[lang]
    target = cache_dir() / asset.font_filename
    if target.is_file():
        return target
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as ex:
        _LOG.warning(
            "pypdfbox CJK loader: could not create cache dir %s: %s",
            target.parent,
            ex,
        )
        return None
    url = _BASE_URL + "/" + asset.asset_name
    _LOG.info(
        "pypdfbox CJK loader: fetching %s (~%s) for ordering %s",
        url,
        _approximate_size(lang),
        ordering,
    )
    try:
        payload = _fetch(url, opener=opener)
    except (URLError, OSError, TimeoutError) as ex:
        _LOG.warning(
            "pypdfbox CJK loader: download failed for %s: %s", url, ex
        )
        return None
    digest = hashlib.sha256(payload).hexdigest()
    if digest != asset.sha256:
        _LOG.warning(
            "pypdfbox CJK loader: SHA-256 mismatch for %s "
            "(expected %s, got %s) — refusing to extract; "
            "delete %s and retry, or unset %s to disable",
            asset.asset_name,
            asset.sha256,
            digest,
            target.parent,
            _ENV_FLAG,
        )
        return None
    try:
        _extract_regular(payload, asset.font_filename, target)
    except (zipfile.BadZipFile, KeyError, OSError) as ex:
        _LOG.warning(
            "pypdfbox CJK loader: extraction failed for %s: %s",
            asset.asset_name,
            ex,
        )
        return None
    return target


def _fetch(url: str, *, opener) -> bytes:
    """Download *url* and return its body. Honours redirects via urllib."""
    req = Request(url, headers={"User-Agent": "pypdfbox-cjk-loader"})
    with opener(req, timeout=60) as resp:  # noqa: S310 - URL is the pinned manifest
        return resp.read()


def _extract_regular(payload: bytes, font_filename: str, target: Path) -> None:
    """Extract only the Regular weight into *target*, atomically."""
    with zipfile.ZipFile(BytesIO(payload)) as zf, zf.open(font_filename) as src:
        data = src.read()
    tmp = target.with_suffix(target.suffix + ".partial")
    try:
        tmp.write_bytes(data)
        tmp.replace(target)
    finally:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()


def _approximate_size(lang: str) -> str:
    """Return a human-readable size hint for log lines."""
    return {
        "JP": "27 MB",
        "KR": "26 MB",
        "SC": "50 MB",
        "TC": "34 MB",
        "HK": "34 MB",
    }.get(lang, "~30 MB")


__all__ = [
    "cache_dir",
    "ensure_language",
    "is_autodownload_enabled",
    "language_for_ordering",
]
