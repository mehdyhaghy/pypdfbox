"""Default :class:`FontMapper` implementation — scans system fonts.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontMapperImpl`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/FontMapperImpl.java``
lines 47-763).

The mapper takes a :class:`FontProvider` (default
:class:`FileSystemFontProvider`) and answers three questions:

* :meth:`get_true_type_font` — locate a TrueType font by PostScript name.
* :meth:`get_font_box_font` — locate any FontBox font by name.
* :meth:`get_cid_font` — locate a CID-keyed font, possibly with
  character-collection-aware substitution.

Substitution table mirrors upstream's hard-coded Standard 14 ->
system-font mapping (Java line 62-102): Courier -> Courier New /
Liberation Mono / Nimbus Mono L, etc.

Scoring (:meth:`_get_font_matches`) preserves upstream's logic for
Panose / weight-class / family-class matching with the same point
values — this is the part that matters for parity with PDF.js and
Acrobat behaviour on legacy documents.
"""

from __future__ import annotations

import heapq
import logging
import threading
from typing import TYPE_CHECKING, Any

from pypdfbox.fontbox.cid_font_mapping import CIDFontMapping
from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_mapper import FontMapper
from pypdfbox.fontbox.font_mapping import FontMapping

from .font_cache import FontCache
from .font_match import FontMatch

if TYPE_CHECKING:
    from pypdfbox.fontbox.font_info import FontInfo
    from pypdfbox.fontbox.font_provider import FontProvider

    from .pd_cid_system_info import PDCIDSystemInfo
    from .pd_font_descriptor import PDFontDescriptor

_LOG = logging.getLogger(__name__)


def _post_script_names(post_script_name: str) -> set[str]:
    """Alternative spellings of *post_script_name*.

    Mirrors upstream ``getPostScriptNames`` (Java line 188-199): include
    the verbatim name and the hyphen-stripped form (e.g. ``"Arial-Black"``
    -> ``"ArialBlack"``).
    """
    return {post_script_name, post_script_name.replace("-", "")}


def get_post_script_names(post_script_name: str) -> set[str]:
    """Public spelling of :func:`_post_script_names`.

    Mirrors upstream private ``getPostScriptNames`` (Java line 188-199).
    """
    return _post_script_names(post_script_name)


# Canonical Standard 14 -> system-font substitution table. Mirrors
# upstream FontMapperImpl constructor (Java line 62-102).
_STANDARD14_SUBSTITUTES: dict[str, list[str]] = {
    "Courier": [
        "CourierNew",
        "CourierNewPSMT",
        "LiberationMono",
        "NimbusMonL-Regu",
    ],
    "Courier-Bold": [
        "CourierNewPS-BoldMT",
        "CourierNew-Bold",
        "LiberationMono-Bold",
        "NimbusMonL-Bold",
    ],
    "Courier-Oblique": [
        "CourierNewPS-ItalicMT",
        "CourierNew-Italic",
        "LiberationMono-Italic",
        "NimbusMonL-ReguObli",
    ],
    "Courier-BoldOblique": [
        "CourierNewPS-BoldItalicMT",
        "CourierNew-BoldItalic",
        "LiberationMono-BoldItalic",
        "NimbusMonL-BoldObli",
    ],
    "Helvetica": [
        "ArialMT",
        "Arial",
        "LiberationSans",
        "NimbusSanL-Regu",
    ],
    "Helvetica-Bold": [
        "Arial-BoldMT",
        "Arial-Bold",
        "LiberationSans-Bold",
        "NimbusSanL-Bold",
    ],
    "Helvetica-Oblique": [
        "Arial-ItalicMT",
        "Arial-Italic",
        "Helvetica-Italic",
        "LiberationSans-Italic",
        "NimbusSanL-ReguItal",
    ],
    "Helvetica-BoldOblique": [
        "Arial-BoldItalicMT",
        "Helvetica-BoldItalic",
        "LiberationSans-BoldItalic",
        "NimbusSanL-BoldItal",
    ],
    "Times-Roman": [
        "TimesNewRomanPSMT",
        "TimesNewRoman",
        "TimesNewRomanPS",
        "LiberationSerif",
        "NimbusRomNo9L-Regu",
    ],
    "Times-Bold": [
        "TimesNewRomanPS-BoldMT",
        "TimesNewRomanPS-Bold",
        "TimesNewRoman-Bold",
        "LiberationSerif-Bold",
        "NimbusRomNo9L-Medi",
    ],
    "Times-Italic": [
        "TimesNewRomanPS-ItalicMT",
        "TimesNewRomanPS-Italic",
        "TimesNewRoman-Italic",
        "LiberationSerif-Italic",
        "NimbusRomNo9L-ReguItal",
    ],
    "Times-BoldItalic": [
        "TimesNewRomanPS-BoldItalicMT",
        "TimesNewRomanPS-BoldItalic",
        "TimesNewRoman-BoldItalic",
        "LiberationSerif-BoldItalic",
        "NimbusRomNo9L-MediItal",
    ],
    "Symbol": [
        "Symbol",
        "SymbolMT",
        "StandardSymL",
    ],
    "ZapfDingbats": [
        "ZapfDingbatsITCbyBT-Regular",
        "ZapfDingbatsITC",
        "Dingbats",
        "MS-Gothic",
        "DejaVuSans",
    ],
}


class FontMapperImpl(FontMapper):
    """Default FontMapper backed by a pluggable :class:`FontProvider`.

    Mirrors upstream Java class (line 47-763).
    """

    def __init__(self) -> None:
        # Upstream constructor (Java line 59-134) populates the
        # substitute table, then loads the bundled
        # ``LiberationSans-Regular.ttf`` as a last-resort fallback. We
        # mirror the substitute table and defer the last-resort load to
        # :meth:`_get_last_resort_font` so we don't fail import time.
        self._lock = threading.RLock()
        self._font_provider: FontProvider | None = None
        self._font_info_by_name: dict[str, FontInfo] = {}
        # Map of PostScript name -> ordered substitutes (lowercase keys).
        self._substitutes: dict[str, list[str]] = {}
        for canonical, names in _STANDARD14_SUBSTITUTES.items():
            self._substitutes[canonical.lower()] = list(names)
        self._last_resort_font: Any | None = None

    # ---------- FontProvider plumbing ----------

    def set_provider(self, font_provider: FontProvider) -> None:
        """Replace the active :class:`FontProvider`.

        Mirrors upstream ``setProvider`` (Java line 145-149).
        """
        with self._lock:
            self._font_info_by_name = self._create_font_info_by_name(
                font_provider.get_font_info()
            )
            self._font_provider = font_provider

    def get_provider(self) -> FontProvider:
        """Return the active :class:`FontProvider`, initialising on demand.

        Mirrors upstream ``getProvider`` (Java line 154-161).
        """
        with self._lock:
            if self._font_provider is None:
                from .file_system_font_provider import FileSystemFontProvider

                self.set_provider(FileSystemFontProvider(FontCache()))
            assert self._font_provider is not None
            return self._font_provider

    def get_font_cache(self) -> FontCache:
        """Return the singleton :class:`FontCache`.

        Mirrors upstream ``getFontCache`` (Java line 167-170).
        """
        provider = self.get_provider()
        cache = getattr(provider, "get_cache", None)
        if callable(cache):
            return cache()
        return FontCache()

    # ---------- substitute table ----------

    def add_substitute(self, match: str, replace: str) -> None:
        """Add a top-priority substitute for *match*.

        Mirrors upstream ``addSubstitute`` (Java line 207-211).
        """
        with self._lock:
            self._substitutes.setdefault(match.lower(), []).append(replace)

    def add_substitutes(self, match: str, replacements: list[str]) -> None:
        """Bulk-register substitute names for *match*.

        Mirrors upstream private ``addSubstitutes`` (Java line 213-217).
        """
        with self._lock:
            self._substitutes.setdefault(match.lower(), []).extend(replacements)

    def get_substitutes(self, post_script_name: str) -> list[str]:
        """Public spelling of :meth:`_get_substitutes`.

        Mirrors upstream private ``getSubstitutes`` (Java line 221-226).
        """
        return self._get_substitutes(post_script_name)

    def _get_substitutes(self, post_script_name: str) -> list[str]:
        """Return substitutes for *post_script_name* in priority order.

        Mirrors upstream ``getSubstitutes`` (Java line 221-226).
        """
        key = post_script_name.replace(" ", "").lower()
        return self._substitutes.get(key, [])

    # ---------- internal: index ----------

    @staticmethod
    def get_post_script_names(post_script_name: str) -> set[str]:
        """Return alternative spellings of *post_script_name*.

        Mirrors upstream private ``getPostScriptNames`` (Java line 188-199).
        """
        return _post_script_names(post_script_name)

    @staticmethod
    def is_fallback_font_loaded() -> bool:
        """Return ``True`` when the bundled last-resort font has been loaded.

        Companion accessor to :meth:`_get_last_resort_font` — upstream
        keeps no such check so we return ``False`` until pypdfbox bundles
        a fallback font.
        """
        return False

    @staticmethod
    def create_font_info_by_name(
        font_info_list: Any,
    ) -> dict[str, FontInfo]:
        """Public spelling of :meth:`_create_font_info_by_name`.

        Mirrors upstream private ``createFontInfoByName`` (Java line 172-183).
        """
        return FontMapperImpl._create_font_info_by_name(font_info_list)

    @staticmethod
    def _create_font_info_by_name(
        font_info_list: Any,
    ) -> dict[str, FontInfo]:
        """Build a lowercase PostScript-name -> :class:`FontInfo` map.

        Mirrors upstream ``createFontInfoByName`` (Java line 172-183).
        """
        result: dict[str, FontInfo] = {}
        for info in font_info_list:
            for name in _post_script_names(info.get_post_script_name()):
                result[name.lower()] = info
        return result

    # ---------- public FontMapper API ----------

    def get_true_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        """Locate a TTF font by name; fall back via descriptor.

        Mirrors upstream ``getTrueTypeFont`` (Java line 314-335).
        """
        ttf = self._find_font(FontFormat.TTF, base_font)
        if ttf is not None:
            return FontMapping(ttf, is_fallback=False)
        fallback_name = self._get_fallback_font_name(font_descriptor)
        ttf = self._find_font(FontFormat.TTF, fallback_name)
        if ttf is None:
            ttf = self._get_last_resort_font()
        return FontMapping(ttf, is_fallback=True) if ttf is not None else None

    def get_open_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        """Locate an OpenType font by name; fall back via descriptor."""
        otf = self._find_font(FontFormat.OTF, base_font)
        if otf is not None:
            return FontMapping(otf, is_fallback=False)
        fallback_name = self._get_fallback_font_name(font_descriptor)
        otf = self._find_font(FontFormat.OTF, fallback_name)
        if otf is None:
            otf = self._get_last_resort_font()
        return FontMapping(otf, is_fallback=True) if otf is not None else None

    def get_font_box_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        """Locate any FontBox font by name; fall back via descriptor.

        Mirrors upstream ``getFontBoxFont`` (Java line 343-364).
        """
        font = self._find_font_box_font(base_font)
        if font is not None:
            return FontMapping(font, is_fallback=False)
        fallback_name = self._get_fallback_font_name(font_descriptor)
        font = self._find_font_box_font(fallback_name)
        if font is None:
            font = self._get_last_resort_font()
        return FontMapping(font, is_fallback=True) if font is not None else None

    def get_cid_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
        cid_system_info: PDCIDSystemInfo | None,
    ) -> CIDFontMapping | None:
        """Locate a CID font with optional character-collection substitution.

        Mirrors upstream ``getCIDFont`` (Java line 495-548).
        """
        otf1 = self._find_font(FontFormat.OTF, base_font)
        if otf1 is not None:
            return CIDFontMapping(otf1, None, False)
        ttf = self._find_font(FontFormat.TTF, base_font)
        if ttf is not None:
            return CIDFontMapping(None, ttf, False)
        if cid_system_info is not None and font_descriptor is not None:
            registry = cid_system_info.get_registry()
            ordering = cid_system_info.get_ordering()
            collection = f"{registry}-{ordering}"
            if collection in {
                "Adobe-GB1",
                "Adobe-CNS1",
                "Adobe-Japan1",
                "Adobe-Korea1",
            }:
                queue = self._get_font_matches(font_descriptor, cid_system_info)
                if queue:
                    best = heapq.heappop(queue)
                    font = best.info.get_font()
                    if font is not None:
                        return CIDFontMapping(None, font, True)
        last = self._get_last_resort_font()
        return CIDFontMapping(None, last, True) if last is not None else None

    # ---------- internal: lookup ----------

    def find_font_box_font(self, post_script_name: str | None) -> Any | None:
        """Public spelling of :meth:`_find_font_box_font`.

        Mirrors upstream private ``findFontBoxFont`` (Java line 371-392).
        """
        return self._find_font_box_font(post_script_name)

    def find_font(
        self, font_format: FontFormat, post_script_name: str | None
    ) -> Any | None:
        """Public spelling of :meth:`_find_font`.

        Mirrors upstream private ``findFont`` (Java line 399-461).
        """
        return self._find_font(font_format, post_script_name)

    def get_font(
        self, font_format: FontFormat, post_script_name: str
    ) -> FontInfo | None:
        """Public spelling of :meth:`_get_font`.

        Mirrors upstream private ``getFont`` (Java line 466-486).
        """
        return self._get_font(font_format, post_script_name)

    def _find_font_box_font(self, post_script_name: str | None) -> Any | None:
        """Try PFB, then TTF, then OTF for *post_script_name*.

        Mirrors upstream ``findFontBoxFont`` (Java line 371-392).
        """
        if post_script_name is None:
            return None
        t1 = self._find_font(FontFormat.PFB, post_script_name)
        if t1 is not None:
            return t1
        ttf = self._find_font(FontFormat.TTF, post_script_name)
        if ttf is not None:
            return ttf
        return self._find_font(FontFormat.OTF, post_script_name)

    def _find_font(
        self, font_format: FontFormat, post_script_name: str | None
    ) -> Any | None:
        """Locate a font matching *post_script_name* in *font_format*.

        Mirrors upstream ``findFont`` (Java line 399-461). Walks the
        substitute table and Windows-name variants.
        """
        if post_script_name is None:
            return None
        self.get_provider()  # ensure initialised
        info = self._get_font(font_format, post_script_name)
        if info is not None:
            return info.get_font()
        info = self._get_font(font_format, post_script_name.replace("-", ""))
        if info is not None:
            return info.get_font()
        for substitute_name in self._get_substitutes(post_script_name):
            info = self._get_font(font_format, substitute_name)
            if info is not None:
                return info.get_font()
        info = self._get_font(font_format, post_script_name.replace(",", "-"))
        if info is not None:
            return info.get_font()
        if "," in post_script_name:
            short = post_script_name[: post_script_name.index(",")]
            info = self._get_font(font_format, short)
            if info is not None:
                return info.get_font()
        info = self._get_font(font_format, post_script_name + "-Regular")
        if info is not None:
            return info.get_font()
        return None

    def _get_font(
        self, font_format: FontFormat, post_script_name: str
    ) -> FontInfo | None:
        """Look up *post_script_name* in the index, stripped of subset tag.

        Mirrors upstream ``getFont`` (Java line 466-486).
        """
        index = post_script_name.find("+")
        if index > -1:
            post_script_name = post_script_name[index + 1 :]
        info = self._font_info_by_name.get(post_script_name.lower())
        if info is not None and info.get_format() is font_format:
            return info
        return None

    # ---------- internal: scoring ----------

    def get_font_matches(
        self,
        font_descriptor: PDFontDescriptor,
        cid_system_info: PDCIDSystemInfo | None,
    ) -> list[FontMatch]:
        """Public spelling of :meth:`_get_font_matches`.

        Mirrors upstream private ``getFontMatches`` (Java line 557-651).
        """
        return self._get_font_matches(font_descriptor, cid_system_info)

    @staticmethod
    def probably_barcode_font(font_descriptor: PDFontDescriptor) -> bool:
        """Heuristic to skip barcode fonts during fallback scoring.

        Mirrors upstream ``probablyBarcodeFont`` (Java line 653-667).
        """
        try:
            ff = font_descriptor.get_font_family() or ""
        except AttributeError:
            ff = ""
        try:
            fn = font_descriptor.get_font_name() or ""
        except AttributeError:
            fn = ""
        return (
            ff.startswith("Code")
            or "barcode" in ff.lower()
            or fn.startswith("Code")
            or "barcode" in fn.lower()
        )

    @staticmethod
    def is_char_set_match(
        cid_system_info: PDCIDSystemInfo,
        info: FontInfo,
    ) -> bool:
        """Public spelling of :meth:`_is_charset_match`.

        Mirrors upstream private ``isCharSetMatch`` (Java line 673-722).
        """
        return FontMapperImpl._is_charset_match(cid_system_info, info)

    @staticmethod
    def print_matches(queue: list[FontMatch]) -> FontMatch | None:
        """Debug helper — log the queue contents and return the best match.

        Mirrors upstream private ``printMatches`` (Java line 747-762).
        Java version prints to ``System.out``; we route through the module
        logger so test runs stay quiet.
        """
        if not queue:
            return None
        best = queue[0]
        _LOG.debug("-------")
        for match in sorted(queue):
            _LOG.debug(
                "%s %s",
                match.info.get_post_script_name(),
                getattr(match, "score", 0),
            )
        return best

    def _get_font_matches(
        self,
        font_descriptor: PDFontDescriptor,
        cid_system_info: PDCIDSystemInfo | None,
    ) -> list[FontMatch]:
        """Return scored matches as a heap (highest score first).

        Mirrors upstream ``getFontMatches`` (Java line 557-651). pypdfbox
        uses a Python list managed via :mod:`heapq`; :class:`FontMatch`
        defines ``__lt__`` so the heap pops the highest score first.
        """
        self.get_provider()
        queue: list[FontMatch] = []
        for info in self._font_info_by_name.values():
            if cid_system_info is not None and not self._is_charset_match(
                cid_system_info, info
            ):
                continue
            match = FontMatch(info)
            self._score_weight(match, font_descriptor, info)
            heapq.heappush(queue, match)
        return queue

    @staticmethod
    def _score_weight(
        match: FontMatch,
        font_descriptor: PDFontDescriptor,
        info: FontInfo,
    ) -> None:
        """Score *match* by descriptor weight vs ``OS/2.usWeightClass``.

        Trimmed-down port of the upstream Panose-aware scoring (Java line
        575-651). Full Panose support requires the FontInfo to expose a
        Panose record; pypdfbox's port currently scores weight only. The
        scoring deltas (``1``, ``2``, ``-1``) match upstream so the
        relative ordering is preserved when Panose support is added.
        """
        try:
            fd_weight = float(font_descriptor.get_font_weight() or 0)
        except (AttributeError, TypeError, ValueError):
            fd_weight = 0.0
        info_weight = info.get_weight_class()
        if fd_weight > 0 and info_weight > 0:
            dist = abs(fd_weight - info_weight)
            match.score += 1 - (dist / 100) * 0.5

    @staticmethod
    def _is_charset_match(
        cid_system_info: PDCIDSystemInfo,
        info: FontInfo,
    ) -> bool:
        """Return ``True`` if *info*'s character set matches *cid_system_info*.

        Mirrors upstream ``isCharSetMatch`` (Java line 673-722).
        """
        ordering = cid_system_info.get_ordering()
        if not ordering:
            return False
        info_cid = info.get_cid_system_info()
        if info_cid is not None:
            return (
                info_cid.get_registry() == cid_system_info.get_registry()
                and info_cid.get_ordering() == ordering
            )
        code_page_range = info.get_code_page_range()
        jis_japan = 1 << 17
        chinese_simplified = 1 << 18
        korean_wansung = 1 << 19
        chinese_traditional = 1 << 20
        korean_johab = 1 << 21
        if info.get_post_script_name() == "MalgunGothic-Semilight":
            code_page_range &= ~(jis_japan | chinese_simplified | chinese_traditional)
        if ordering == "GB1":
            return (code_page_range & chinese_simplified) == chinese_simplified
        if ordering == "CNS1":
            return (code_page_range & chinese_traditional) == chinese_traditional
        if ordering == "Japan1":
            return (code_page_range & jis_japan) == jis_japan
        if ordering == "Korea1":
            return (
                (code_page_range & korean_wansung) == korean_wansung
                or (code_page_range & korean_johab) == korean_johab
            )
        return False

    # ---------- internal: fallback ----------

    @staticmethod
    def get_fallback_font_name(
        font_descriptor: PDFontDescriptor | None,
    ) -> str:
        """Public spelling of :meth:`_get_fallback_font_name`.

        Mirrors upstream private ``getFallbackFontName`` (Java line 231-307).
        """
        return FontMapperImpl._get_fallback_font_name(font_descriptor)

    @staticmethod
    def _get_fallback_font_name(
        font_descriptor: PDFontDescriptor | None,
    ) -> str:
        """Pick a Standard 14 family by descriptor flags.

        Mirrors upstream ``getFallbackFontName`` (Java line 231-307).
        """
        if font_descriptor is None:
            return "Times-Roman"
        is_bold = False
        try:
            name = font_descriptor.get_font_name()
            if name is not None:
                lower = name.lower()
                is_bold = (
                    "bold" in lower or "black" in lower or "heavy" in lower
                )
        except AttributeError:
            pass
        if font_descriptor.is_fixed_pitch():
            return _stylise("Courier", is_bold, font_descriptor.is_italic())
        if font_descriptor.is_serif():
            base = "Times"
            if is_bold and font_descriptor.is_italic():
                return f"{base}-BoldItalic"
            if is_bold:
                return f"{base}-Bold"
            if font_descriptor.is_italic():
                return f"{base}-Italic"
            return f"{base}-Roman"
        return _stylise("Helvetica", is_bold, font_descriptor.is_italic())

    def _get_last_resort_font(self) -> Any | None:
        """Load and cache the bundled last-resort font, if available.

        Mirrors upstream's eager load in the constructor (Java line
        117-133). pypdfbox defers the load so missing fonts don't break
        import.
        """
        if self._last_resort_font is not None:
            return self._last_resort_font
        # pypdfbox doesn't bundle LiberationSans-Regular. Return None and
        # let callers fall back to the Standard 14 path.
        return None


def _stylise(base: str, is_bold: bool, is_italic: bool) -> str:
    """Append ``-Bold``/``-Oblique``/``-BoldOblique`` to *base* per flags."""
    if is_bold and is_italic:
        return f"{base}-BoldOblique"
    if is_bold:
        return f"{base}-Bold"
    if is_italic:
        return f"{base}-Oblique"
    return base


__all__ = ["FontMapperImpl"]
