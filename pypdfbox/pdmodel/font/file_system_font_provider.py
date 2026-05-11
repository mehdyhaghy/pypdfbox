"""Filesystem-scanning :class:`FontProvider` — discovers system fonts.

Mirrors ``org.apache.pdfbox.pdmodel.font.FileSystemFontProvider`` (PDFBox
3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/
FileSystemFontProvider.java`` lines 58-895).

The provider walks the well-known OS font directories, parses each
TTF/OTF/PFB, and produces a :class:`FSFontInfo` per font found. Results
are stored in an in-process list (and optionally an on-disk cache file)
so subsequent runs avoid re-scanning the filesystem.

Library-first: fontTools handles the actual TTF/OTF parsing —
:class:`FSFontInfo` delegates there for the lazy ``get_font()`` path.
For the *scan* phase we only need the OS/2 + name tables, so we use
fontTools' ``ttLib`` with ``lazy=True`` to keep memory bounded.

OS font directories (mirrors upstream's ``FontFileFinder`` walk):

* macOS: ``/System/Library/Fonts``, ``/Library/Fonts``,
  ``~/Library/Fonts``.
* Linux: ``/usr/share/fonts``, ``/usr/local/share/fonts``, ``~/.fonts``,
  ``~/.local/share/fonts``.
* Windows: ``C:\\Windows\\Fonts``, ``%LOCALAPPDATA%\\Microsoft\\Windows\\Fonts``.

The scanner is deliberately defensive — every missing path / unreadable
file is logged and skipped, never propagated. Matches upstream's
``"AccessControlException -> log and continue"`` behaviour.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_provider import FontProvider

from .font_cache import FontCache
from .fs_font_info import FSFontInfo

_LOG = logging.getLogger(__name__)

_TTF_SUFFIXES: frozenset[str] = frozenset({".ttf"})
_OTF_SUFFIXES: frozenset[str] = frozenset({".otf"})
_TTC_SUFFIXES: frozenset[str] = frozenset({".ttc", ".otc"})
_TYPE1_SUFFIXES: frozenset[str] = frozenset({".pfb"})


def _default_font_dirs() -> list[Path]:
    """Return well-known OS font directories for the current platform.

    Mirrors upstream's ``FontFileFinder`` (lives in ``fontbox.util.autodetect``
    in Java). pypdfbox uses stdlib :class:`pathlib.Path` rather than a
    dedicated finder utility — the platform list is small enough to
    inline.
    """
    dirs: list[Path] = []
    home = Path.home()
    if sys.platform == "darwin":
        dirs.extend([
            Path("/System/Library/Fonts"),
            Path("/Library/Fonts"),
            home / "Library" / "Fonts",
        ])
    elif sys.platform.startswith("linux"):
        dirs.extend([
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
            home / ".fonts",
            home / ".local" / "share" / "fonts",
        ])
    elif sys.platform == "win32":
        windir = os.environ.get("WINDIR") or "C:\\Windows"
        dirs.append(Path(windir) / "Fonts")
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            dirs.append(
                Path(local_app) / "Microsoft" / "Windows" / "Fonts"
            )
    return dirs


class FileSystemFontProvider(FontProvider):
    """Scans the local filesystem for TTF/OTF/PFB fonts.

    Mirrors upstream Java line 58-895. The pypdfbox port trims down the
    full upstream surface to the publicly observable behaviour:

    * Construction with an optional :class:`FontCache` triggers a scan.
    * :meth:`get_font_info` returns the discovered :class:`FSFontInfo`
      list.
    * :meth:`to_debug_string` returns a multi-line listing for logging.

    The upstream on-disk cache (``.pdfbox.cache``) is *not* ported — it
    is an internal optimisation that adds significant complexity and is
    not part of the public contract. Tests that require deterministic
    behaviour should pass an explicit ``directories`` list.
    """

    def __init__(
        self,
        cache: FontCache | None = None,
        directories: Sequence[Path] | None = None,
    ) -> None:
        """Construct a provider and immediately scan.

        Mirrors upstream constructor (Java line 336-382). The
        ``directories`` parameter is a pypdfbox extension that lets
        callers (and tests) override the platform-default font paths.
        """
        self._cache: FontCache = cache if cache is not None else FontCache()
        self._font_info_list: list[FSFontInfo] = []
        scan_dirs = (
            list(directories) if directories is not None else _default_font_dirs()
        )
        files = self._collect_font_files(scan_dirs)
        if files:
            _LOG.info("Building font index (%d files)", len(files))
            self._scan_fonts(files)
            _LOG.info(
                "Finished building font index, found %d fonts",
                len(self._font_info_list),
            )

    def get_cache(self) -> FontCache:
        """Return the associated :class:`FontCache`."""
        return self._cache

    def get_font_info(self) -> Sequence[FSFontInfo]:
        """Return the list of discovered fonts.

        Mirrors upstream ``getFontInfo()`` (Java line on parent class).
        """
        return list(self._font_info_list)

    def to_debug_string(self) -> str:
        """Return a multi-line listing of every discovered font.

        Mirrors upstream ``toDebugString()`` (Java method on parent
        class).
        """
        return "\n".join(str(info) for info in self._font_info_list)

    # ---------- internal scanning ----------

    @staticmethod
    def _collect_font_files(directories: Sequence[Path]) -> list[Path]:
        """Recursively enumerate font files under *directories*.

        Mirrors upstream's ``FontFileFinder.find()`` (Java line 347-358).
        """
        files: list[Path] = []
        for directory in directories:
            try:
                if not directory.is_dir():
                    continue
            except OSError:
                continue
            try:
                for path in directory.rglob("*"):
                    suffix = path.suffix.lower()
                    if (
                        suffix in _TTF_SUFFIXES
                        or suffix in _OTF_SUFFIXES
                        or suffix in _TTC_SUFFIXES
                        or suffix in _TYPE1_SUFFIXES
                    ):
                        files.append(path)
            except OSError as ex:
                _LOG.debug("Could not walk %s: %s", directory, ex)
        return files

    def scan_fonts(self, files: Sequence[Path]) -> None:
        """Public spelling of :meth:`_scan_fonts`.

        Mirrors upstream private ``scanFonts`` (Java line 384-405).
        """
        self._scan_fonts(files)

    def add_true_type_font(self, file: Path) -> None:
        """Public spelling of :meth:`_add_true_type_font`.

        Mirrors upstream private ``addTrueTypeFont`` (Java line 696-723).
        """
        self._add_true_type_font(file)

    def add_true_type_collection(self, file: Path) -> None:
        """Public spelling of :meth:`_add_true_type_collection`.

        Mirrors upstream private ``addTrueTypeCollection`` (Java line 678-695).
        """
        self._add_true_type_collection(file)

    def add_true_type_font_impl(self, ttf: object, file: Path, font_hash: str) -> None:
        """Add a parsed TTF object with a precomputed hash.

        Mirrors upstream private ``addTrueTypeFontImpl`` (Java line 726-816).
        pypdfbox extracts metadata in :meth:`_add_ttf_metadata` so this is a
        thin adapter that records the supplied hash on the resulting
        :class:`FSFontInfo`.
        """
        before = len(self._font_info_list)
        self._add_ttf_metadata(file, ttf)
        if len(self._font_info_list) > before:
            self._font_info_list[-1]._hash = font_hash  # noqa: SLF001

    def add_type1_font(self, file: Path) -> None:
        """Public spelling of :meth:`_add_type1_font`.

        Mirrors upstream private ``addType1Font`` (Java line 818-872).
        """
        self._add_type1_font(file)

    @staticmethod
    def compute_hash(stream: object) -> str:
        """Return a SHA-1 hex digest of *stream* (binary file-like or bytes).

        Mirrors upstream private ``computeHash`` (Java line 874-894).
        Library-first: delegates to :mod:`hashlib`.
        """
        digest = hashlib.sha1()  # noqa: S324 - parity with upstream choice
        if hasattr(stream, "read"):
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
            with contextlib.suppress(Exception):
                stream.close()
        else:
            digest.update(bytes(stream))
        return digest.hexdigest()

    def create_fs_ignored(
        self, file: Path, font_format: object, post_script_name: str
    ) -> FSFontInfo:
        """Record *file* in the cache as ignored (parse failure).

        Mirrors upstream private ``createFSIgnored`` (Java line 319-331).
        """
        try:
            font_hash = self.compute_hash(file.open("rb"))
        except OSError:
            font_hash = ""
        try:
            last_modified = int(file.stat().st_mtime)
        except OSError:
            last_modified = 0
        info = FSFontInfo(
            file=file,
            font_format=font_format,  # type: ignore[arg-type]
            post_script_name=post_script_name,
            cid_system_info=None,
            us_weight_class=0,
            s_family_class=0,
            ul_code_page_range1=0,
            ul_code_page_range2=0,
            mac_style=0,
            panose=None,
            parent=self,
            font_hash=font_hash,
            last_modified=last_modified,
        )
        self._font_info_list.append(info)
        return info

    @staticmethod
    def get_disk_cache_file() -> Path:
        """Return the path of the on-disk cache file.

        Mirrors upstream private ``getDiskCacheFile`` (Java line 407-419).
        pypdfbox doesn't ship a disk cache writer, but the path is exposed
        so callers can probe / clear stale upstream artifacts.
        """
        candidate = os.environ.get("PDFBOX_FONTCACHE")
        if candidate and not FileSystemFontProvider.is_bad_path(candidate):
            return Path(candidate) / ".pdfbox.cache"
        home = str(Path.home())
        if not FileSystemFontProvider.is_bad_path(home):
            return Path(home) / ".pdfbox.cache"
        return Path(tempfile.gettempdir()) / ".pdfbox.cache"

    @staticmethod
    def is_bad_path(path: str | None) -> bool:
        """Return ``True`` if *path* is unusable as a cache directory.

        Mirrors upstream private ``isBadPath`` (Java line 421-424).
        """
        if not path:
            return True
        p = Path(path)
        return not p.is_dir() or not os.access(p, os.W_OK)

    def save_disk_cache(self) -> None:
        """Persist the in-memory font index to the disk cache file.

        Mirrors upstream private ``saveDiskCache`` (Java line 429-454).
        pypdfbox writes a minimal newline-delimited record per font so
        repeated runs may skip re-parsing; absent fontTools fields are
        recorded as blanks.
        """
        try:
            cache_file = self.get_disk_cache_file()
            with open(cache_file, "w", encoding="utf-8") as handle:
                for info in self._font_info_list:
                    self.write_font_info(handle, info)
        except OSError as ex:
            _LOG.debug("Could not write font cache: %s", ex)

    def write_font_info(self, writer: object, font_info: FSFontInfo) -> None:
        """Append a single record to the cache writer.

        Mirrors upstream private ``writeFontInfo`` (Java line 456-508).
        """
        line = "|".join([
            font_info.get_post_script_name().strip(),
            font_info.get_format().name,
            "",  # cidSystemInfo - not tracked at scan time in pypdfbox
            f"{font_info.get_weight_class():x}",
            f"{font_info.get_family_class():x}",
            f"{font_info.get_code_page_range1():x}",
            f"{font_info.get_code_page_range2():x}",
            f"{font_info.get_mac_style():x}",
            "",  # panose
            str(font_info.file),
            font_info.font_hash,
            str(font_info.last_modified),
        ])
        write = getattr(writer, "write", None)
        if callable(write):
            write(line + "\n")

    def load_disk_cache(self, files: Sequence[Path]) -> list[FSFontInfo]:
        """Reload font records from the on-disk cache.

        Mirrors upstream private ``loadDiskCache`` (Java line 513-660).
        pypdfbox currently re-scans on every construction; this stub
        preserves the API for callers that probe for cache presence.
        """
        _ = files
        return []

    def _scan_fonts(self, files: Sequence[Path]) -> None:
        """Add each font in *files* to the in-process index.

        Mirrors upstream ``scanFonts(List<File>)`` (Java line 384-405).
        fontTools raises ``TTLibError`` (a plain ``Exception``) for
        malformed inputs; catch broadly so unreadable files don't fail
        the entire scan.
        """
        for file in files:
            suffix = file.suffix.lower()
            try:
                if suffix in _TTF_SUFFIXES or suffix in _OTF_SUFFIXES:
                    self._add_true_type_font(file)
                elif suffix in _TTC_SUFFIXES:
                    self._add_true_type_collection(file)
                elif suffix in _TYPE1_SUFFIXES:
                    self._add_type1_font(file)
            except Exception as ex:  # noqa: BLE001
                _LOG.debug("Could not load font %s: %s", file, ex)

    def _add_true_type_font(self, file: Path) -> None:
        """Add a single TTF or OTF font file.

        Mirrors upstream ``addTrueTypeFont(File)`` (Java around line 410+).
        Uses fontTools to parse only the metadata we need (name, OS/2)
        without materialising the glyph table.
        """
        try:
            from fontTools.ttLib import TTFont
        except ImportError:
            return
        try:
            ttf = TTFont(str(file), lazy=True)
        except Exception as ex:  # noqa: BLE001
            _LOG.debug("Could not parse %s: %s", file, ex)
            return
        try:
            self._add_ttf_metadata(file, ttf)
        finally:
            with contextlib.suppress(OSError):
                ttf.close()

    def _add_true_type_collection(self, file: Path) -> None:
        """Add every font inside a TTC / OTC.

        Mirrors upstream ``addTrueTypeCollection(File)``. fontTools
        exposes :class:`TTCollection` whose ``.fonts`` attribute lists
        the individual :class:`TTFont`s.
        """
        try:
            from fontTools.ttLib import TTCollection
        except ImportError:
            return
        try:
            ttc = TTCollection(str(file))
        except Exception as ex:  # noqa: BLE001
            _LOG.debug("Could not parse TTC %s: %s", file, ex)
            return
        for font in ttc.fonts:
            try:
                self._add_ttf_metadata(file, font)
            except OSError as ex:
                _LOG.debug("Could not extract metadata from %s: %s", file, ex)

    def _add_ttf_metadata(self, file: Path, ttf: object) -> None:
        """Common metadata-extraction path for TTF/OTF and TTC entries."""
        try:
            name_table = ttf["name"]  # type: ignore[index]
        except KeyError:
            return
        ps_name = name_table.getDebugName(6)
        if not ps_name:
            return
        # OS/2 — optional; absence is recorded as zeros so the FontInfo
        # still ranks (matches upstream which logs a warning and uses
        # zero defaults).
        us_weight_class = 0
        s_family_class = 0
        ul_code_page_range1 = 0
        ul_code_page_range2 = 0
        panose: bytes | None = None
        try:
            os2 = ttf["OS/2"]  # type: ignore[index]
            us_weight_class = int(getattr(os2, "usWeightClass", 0))
            s_family_class = int(getattr(os2, "sFamilyClass", 0))
            ul_code_page_range1 = int(getattr(os2, "ulCodePageRange1", 0))
            ul_code_page_range2 = int(getattr(os2, "ulCodePageRange2", 0))
            panose_obj = getattr(os2, "panose", None)
            if panose_obj is not None:
                panose = bytes(
                    int(getattr(panose_obj, attr, 0))
                    for attr in (
                        "bFamilyType",
                        "bSerifStyle",
                        "bWeight",
                        "bProportion",
                        "bContrast",
                        "bStrokeVariation",
                        "bArmStyle",
                        "bLetterform",
                        "bMidline",
                        "bXHeight",
                    )
                )
        except KeyError:
            pass
        mac_style = 0
        try:
            head = ttf["head"]  # type: ignore[index]
            mac_style = int(getattr(head, "macStyle", 0))
        except KeyError:
            pass
        font_format = (
            FontFormat.OTF if file.suffix.lower() in {".otf", ".otc"} else FontFormat.TTF
        )
        try:
            last_modified = int(file.stat().st_mtime)
        except OSError:
            last_modified = 0
        info = FSFontInfo(
            file=file,
            font_format=font_format,
            post_script_name=ps_name,
            cid_system_info=None,
            us_weight_class=us_weight_class,
            s_family_class=s_family_class,
            ul_code_page_range1=ul_code_page_range1,
            ul_code_page_range2=ul_code_page_range2,
            mac_style=mac_style,
            panose=panose,
            parent=self,
            font_hash="",
            last_modified=last_modified,
        )
        self._font_info_list.append(info)

    def _add_type1_font(self, file: Path) -> None:
        """Add a Type 1 PFB font.

        Mirrors upstream ``addType1Font(File)``. Uses fontTools'
        :class:`T1Font` to extract the PostScript name. Type 1 fonts
        carry no OS/2 / Panose data, so most metadata fields are zero.
        """
        try:
            from fontTools.t1Lib import T1Font
        except ImportError:
            return
        try:
            t1 = T1Font(str(file))
        except Exception as ex:  # noqa: BLE001
            _LOG.debug("Could not parse Type 1 font %s: %s", file, ex)
            return
        ps_name = t1.font.get("FontName") if isinstance(t1.font, dict) else None
        if not ps_name:
            ps_name = file.stem
        try:
            last_modified = int(file.stat().st_mtime)
        except OSError:
            last_modified = 0
        info = FSFontInfo(
            file=file,
            font_format=FontFormat.PFB,
            post_script_name=ps_name,
            cid_system_info=None,
            us_weight_class=0,
            s_family_class=0,
            ul_code_page_range1=0,
            ul_code_page_range2=0,
            mac_style=0,
            panose=None,
            parent=self,
            font_hash="",
            last_modified=last_modified,
        )
        self._font_info_list.append(info)


__all__ = ["FileSystemFontProvider"]
