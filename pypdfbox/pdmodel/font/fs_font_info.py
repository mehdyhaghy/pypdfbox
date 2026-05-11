"""File-system :class:`FontInfo` record used by FileSystemFontProvider.

Mirrors ``org.apache.pdfbox.pdmodel.font.FileSystemFontProvider.FSFontInfo``
(PDFBox 3.0, ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/
FileSystemFontProvider.java`` lines 72-317).

Upstream Java declares ``FSFontInfo`` as a private inner class of
:class:`FileSystemFontProvider`. pypdfbox lifts it to a top-level
module so tests can construct fixtures without touching the scanner
itself.

The record extends :class:`FontInfo` (the abstract metadata shape used
by :class:`FontMapperImpl`) with file-system specifics:

* ``file`` — the absolute :class:`pathlib.Path` of the on-disk font.
* ``hash`` — a checksum of the font bytes (used to invalidate the
  on-disk cache when the file changes without a mtime bump).
* ``last_modified`` — Unix mtime, used together with ``hash`` to detect
  cache staleness.

The actual font program is loaded lazily via :meth:`get_font`. fontTools
is library-first for the parse (it handles TTF / OTF / TTC / OTC). The
loader caches the result via the parent provider's :class:`FontCache`
so concurrent renders don't re-parse identical fonts.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo

if TYPE_CHECKING:
    from pypdfbox.fontbox.font_box_font import FontBoxFont

    from .cid_system_info import CIDSystemInfo
    from .file_system_font_provider import FileSystemFontProvider
    from .pd_font_descriptor import PDPanoseClassification


class FSFontInfo(FontInfo):
    """On-disk :class:`FontInfo` — wraps a font file with cached metadata.

    Mirrors upstream Java (line 72-317).
    """

    def __init__(
        self,
        file: Path | str,
        font_format: FontFormat,
        post_script_name: str,
        cid_system_info: CIDSystemInfo | None,
        us_weight_class: int,
        s_family_class: int,
        ul_code_page_range1: int,
        ul_code_page_range2: int,
        mac_style: int,
        panose: bytes | None,
        parent: FileSystemFontProvider | None,
        font_hash: str,
        last_modified: int,
    ) -> None:
        # Upstream constructor (Java line 88-107). Java stores ``File``;
        # Python uses :class:`pathlib.Path` since that's the idiomatic
        # type for on-disk paths in the stdlib.
        self._file: Path = Path(file)
        self._format: FontFormat = font_format
        self._post_script_name: str = post_script_name
        self._cid_system_info: CIDSystemInfo | None = cid_system_info
        self._us_weight_class: int = us_weight_class
        self._s_family_class: int = s_family_class
        self._ul_code_page_range1: int = ul_code_page_range1
        self._ul_code_page_range2: int = ul_code_page_range2
        self._mac_style: int = mac_style
        # Upstream wraps the 10-byte ``panose`` array in a
        # ``PDPanoseClassification`` when length >= 10. Mirror that here.
        if panose is not None and len(panose) >= 10:
            from .pd_font_descriptor import PDPanoseClassification

            self._panose: PDPanoseClassification | None = PDPanoseClassification(
                panose
            )
        else:
            self._panose = None
        self._parent: FileSystemFontProvider | None = parent
        self._hash: str = font_hash
        self._last_modified: int = last_modified

    # ---------- FontInfo abstract methods (Java line 109-195) ----------

    def get_post_script_name(self) -> str:
        return self._post_script_name

    def get_format(self) -> FontFormat:
        return self._format

    def get_cid_system_info(self) -> CIDSystemInfo | None:
        return self._cid_system_info

    def get_font(self) -> FontBoxFont | None:
        """Lazily load and cache the font program.

        Mirrors upstream synchronized ``getFont()`` (Java line 134-159).
        Returns ``None`` if the font cannot be opened — upstream logs a
        warning and continues.
        """
        if self._parent is not None:
            cached = self._parent.get_cache().get_font(self)
            if cached is not None:
                return cached
        font = self._load_font()
        if font is not None and self._parent is not None:
            self._parent.get_cache().add_font(self, font)
        return font

    def get_family_class(self) -> int:
        return self._s_family_class

    def get_weight_class(self) -> int:
        return self._us_weight_class

    def get_code_page_range1(self) -> int:
        return self._ul_code_page_range1

    def get_code_page_range2(self) -> int:
        return self._ul_code_page_range2

    def get_mac_style(self) -> int:
        return self._mac_style

    def get_panose(self) -> PDPanoseClassification | None:
        return self._panose

    # ---------- file-system specifics ----------

    @property
    def file(self) -> Path:
        """Return the absolute path of the on-disk font."""
        return self._file

    @property
    def font_hash(self) -> str:
        """Return the cached checksum of the font bytes."""
        return self._hash

    @property
    def last_modified(self) -> int:
        """Return the Unix mtime captured when the cache was built."""
        return self._last_modified

    def get_true_type_font(self, post_script_name: str, file: Path) -> Any | None:
        """Load a TrueType font by *post_script_name* from *file*.

        Mirrors upstream private ``getTrueTypeFont`` (Java line 203-220).
        Returns ``None`` on I/O failure rather than raising.
        """
        try:
            return self.read_true_type_font(post_script_name, file)
        except Exception:  # noqa: BLE001
            return None

    def read_true_type_font(self, post_script_name: str, file: Path) -> Any | None:
        """Parse and return a TTF (or selected entry of a TTC).

        Mirrors upstream private ``readTrueTypeFont`` (Java line 222-252).
        Library-first: delegates to fontTools.
        """
        try:
            from fontTools.ttLib import TTCollection, TTFont
        except ImportError:
            return None
        name = Path(file).name.lower()
        if name.endswith((".ttc", ".otc")):
            ttc = TTCollection(str(file))
            for font in ttc.fonts:
                try:
                    ps_name = font["name"].getDebugName(6)
                except KeyError:
                    continue
                if ps_name == post_script_name:
                    return font
            raise OSError(f"Font {post_script_name} not found in {file}")
        return TTFont(str(file))

    def get_otf_font(self, post_script_name: str, file: Path) -> Any | None:
        """Load an OpenType font by *post_script_name* from *file*.

        Mirrors upstream private ``getOTFFont`` (Java line 254-297).
        """
        try:
            return self.read_true_type_font(post_script_name, file)
        except Exception:  # noqa: BLE001
            return None

    def get_type1_font(self, post_script_name: str, file: Path) -> Any | None:
        """Load a Type 1 PFB font.

        Mirrors upstream private ``getType1Font`` (Java line 299-317).
        """
        try:
            from fontTools.t1Lib import T1Font
        except ImportError:
            return None
        try:
            return T1Font(str(file))
        except Exception:  # noqa: BLE001
            return None

    def _load_font(self) -> Any | None:
        """Parse the font file using fontTools.

        Returns ``None`` (matching upstream's null-on-error contract) if
        the file cannot be parsed.
        """
        # Library-first: fontTools handles TTF/OTF/PFB. fontTools raises
        # ``TTLibError`` (subclass of ``Exception``, not ``OSError``) for
        # parse failures; catch broadly so the upstream null-on-error
        # contract is preserved.
        try:
            if self._format is FontFormat.TTF or self._format is FontFormat.OTF:
                return self._load_truetype()
            if self._format is FontFormat.PFB:
                return self._load_type1()
        except Exception:  # noqa: BLE001
            return None
        return None

    def _load_truetype(self) -> Any | None:
        """Parse a TTF / OTF / TTC font with fontTools."""
        try:
            from fontTools.ttLib import TTCollection, TTFont
        except ImportError:
            return None
        name = self._file.name.lower()
        if name.endswith((".ttc", ".otc")):
            try:
                ttc = TTCollection(str(self._file))
            except Exception:  # noqa: BLE001
                return None
            for font in ttc.fonts:
                try:
                    name_table = font["name"]
                except KeyError:
                    continue
                ps_name = name_table.getDebugName(6)
                if ps_name == self._post_script_name:
                    return font
            return None
        try:
            return TTFont(str(self._file))
        except Exception:  # noqa: BLE001
            return None

    def _load_type1(self) -> Any | None:
        """Parse a Type 1 PFB font."""
        try:
            from fontTools.t1Lib import T1Font
        except ImportError:
            return None
        try:
            return T1Font(str(self._file))
        except Exception:  # noqa: BLE001
            return None

    def to_string(self) -> str:
        """Return base FontInfo string plus file / hash / mtime.

        Mirrors upstream ``toString()`` (Java line 197-201).
        """
        base = FontInfo.to_string(self)
        return f"{base} {self._file} {self._hash} {self._last_modified}"

    def __str__(self) -> str:
        # Mirror upstream ``toString()`` (Java line 197-201): include the
        # base FontInfo string plus file / hash / mtime.
        return self.to_string()


__all__ = ["FSFontInfo"]
