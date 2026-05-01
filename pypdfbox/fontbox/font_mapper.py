"""Font mapper — locate non-embedded fonts by PostScript name.

Mirrors ``org.apache.pdfbox.pdmodel.font.FontMapper`` (interface) and
``org.apache.pdfbox.pdmodel.font.FontMapperImpl`` (default
implementation) from PDFBox 3.0.

Upstream Java is in the ``pdfbox`` Maven module rather than ``fontbox``;
we host the port under :mod:`pypdfbox.fontbox` because there is no
inverse-dependency problem in Python. Callers reach the singleton via
:class:`pypdfbox.fontbox.font_mappers.FontMappers`.

Default implementation
----------------------

The full upstream ``FontMapperImpl`` walks the OS font directories via
``FileSystemFontProvider``, parses every TTF/OTF/PFB it finds and ranks
candidates by descriptor flags (panose, weight, italic angle, family
name). That implementation is several thousand lines and pulls in a
real-time TTF scanner.

The pypdfbox port (CHANGES tracked separately) trims the default mapper
down to the **Standard 14 path**: any of the 14 canonical PostScript
names (or registered alias) resolves to the bundled AFM metrics and
returns a thin :class:`Standard14FontWrapper` adapter that satisfies
:class:`FontBoxFont`. Anything outside the Standard 14 returns ``None``
for ``get_true_type_font`` / ``get_open_type_font`` and a fallback
mapping (Helvetica/Helvetica-Bold/Helvetica-Oblique/Helvetica-BoldOblique
chosen by descriptor flags) for ``get_font_box_font``.

Apps that need full system-font enumeration are expected to plug in
their own :class:`FontMapper` via
:func:`FontMappers.set <pypdfbox.fontbox.font_mappers.FontMappers.set>`.
That replacement-friendly model matches upstream — even Java callers
swap mappers when they want different substitution behaviour.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from .cid_font_mapping import CIDFontMapping
from .font_box_font import FontBoxFont
from .font_mapping import FontMapping

if TYPE_CHECKING:
    # Avoid an import cycle: ``pdmodel.font`` depends on ``fontbox``
    # for encodings, so we pull PDFontDescriptor / Standard14Fonts in
    # at type-check time only and resolve them lazily inside
    # :class:`DefaultFontMapper`.
    from pypdfbox.pdmodel.font.pd_cid_system_info import PDCIDSystemInfo
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor


class FontMapper(ABC):
    """Locate non-embedded fonts by PostScript name.

    Mirrors the upstream Java interface
    ``org.apache.pdfbox.pdmodel.font.FontMapper``. Three abstract
    methods, one per font kind:

    - :meth:`get_true_type_font` — TrueType/OTF outline font
    - :meth:`get_open_type_font` — CFF-flavoured OpenType (subset of TT)
    - :meth:`get_font_box_font`  — any FontBox font (TT / Type1 / CFF)

    Subclasses are responsible for caching their results — upstream
    docstring recommends ``SoftReference<FontBoxFont>``; in Python a
    plain dict + :mod:`weakref.WeakValueDictionary` works.
    """

    @abstractmethod
    def get_true_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        """Locate a TrueType font by PostScript name (or substitute).

        Mirrors upstream
        ``FontMapping<TrueTypeFont> getTrueTypeFont(String, PDFontDescriptor)``.
        Returns ``None`` when no candidate is found at all (caller is
        expected to fall back to a different font kind or raise).
        """

    @abstractmethod
    def get_open_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        """Locate a CFF-flavoured OpenType font (or substitute).

        Mirrors upstream
        ``FontMapping<OpenTypeFont> getOpenTypeFont(String, PDFontDescriptor)``.

        Note: upstream 3.0 actually exposes this method on
        ``FontMapperImpl`` directly (the method is reachable through the
        ``CIDFontMapping`` machinery rather than the interface itself).
        We surface it on the ABC for parity with the more common shape
        users actually call.
        """

    @abstractmethod
    def get_font_box_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[FontBoxFont] | None:
        """Locate any FontBox font (TT / Type1 / CFF) by PostScript name.

        Mirrors upstream
        ``FontMapping<FontBoxFont> getFontBoxFont(String, PDFontDescriptor)``.
        Used as the universal fallback path when the caller doesn't
        care which on-disk format ends up serving the metrics.
        """

    def get_cid_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
        cid_system_info: PDCIDSystemInfo | None,
    ) -> CIDFontMapping | None:
        """Locate a CFF CID-keyed font (or substitute), if available.

        Mirrors upstream abstract
        ``CIDFontMapping getCIDFont(String, PDFontDescriptor, PDCIDSystemInfo)``.
        Upstream Java declares this abstract on the interface; pypdfbox
        keeps it concrete with a default ``None`` return (recorded in
        CHANGES.md) so existing :class:`FontMapper` subclasses don't
        spontaneously become abstract again. Real CID-aware mappers
        override it; the bundled :class:`DefaultFontMapper` cannot
        materialise CID fonts without an on-disk font scanner and so
        inherits the default ``None``.
        """
        del base_font, font_descriptor, cid_system_info
        return None

    # ---------- camelCase aliases (porting parity) ----------

    # Mirror the upstream Java method names so existing call sites that
    # were ported verbatim continue to work without renaming. The
    # snake_case methods above are the canonical pypdfbox spellings.

    def getTrueTypeFont(  # noqa: N802 - upstream Java name
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        return self.get_true_type_font(base_font, font_descriptor)

    def getOpenTypeFont(  # noqa: N802 - upstream Java name
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        return self.get_open_type_font(base_font, font_descriptor)

    def getFontBoxFont(  # noqa: N802 - upstream Java name
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[FontBoxFont] | None:
        return self.get_font_box_font(base_font, font_descriptor)


# ---------------------------------------------------------------------------
# Standard14 adapter — implements the FontBoxFont protocol over AfmMetrics.
# ---------------------------------------------------------------------------


class Standard14FontWrapper:
    """Thin adapter exposing :class:`FontBoxFont` over an AFM.

    Used by :class:`DefaultFontMapper` so a Standard 14 lookup returns
    something the rest of the rendering / text-extraction stack can
    treat the same way as a real TrueType / Type1 font.

    The wrapper carries no glyph outlines — :meth:`get_path` returns an
    empty path. Callers that need actual outlines for these names must
    install a richer mapper that resolves them to a real font program
    (the bundled AFMs intentionally don't ship outlines; PDF readers
    are expected to draw the Standard 14 from system fonts).
    """

    __slots__ = ("_name", "_metrics")

    def __init__(self, name: str, metrics: Any) -> None:
        # ``metrics`` is an :class:`AfmMetrics`, but we don't import the
        # type here to avoid the import cycle described in the module
        # docstring. The wrapper only uses the duck-typed accessors
        # ``get_glyph_width`` / ``has_glyph`` / ``get_font_metrics``.
        self._name: str = name
        self._metrics = metrics

    # ---------- FontBoxFont protocol ----------

    def get_name(self) -> str:
        return self._name

    def get_font_bbox(self) -> tuple[int, int, int, int]:
        bbox = self._metrics.get_font_metrics().get("FontBBox", (0, 0, 0, 0))
        return tuple(int(v) for v in bbox)  # type: ignore[return-value]

    def get_font_matrix(self) -> list[float]:
        # Type 1 / Standard 14 default font matrix — 1/1000 em scale.
        return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    def get_path(self, name: str) -> list[tuple[Any, ...]]:
        # AFMs don't ship outlines. Return an empty path — callers that
        # need real glyph outlines must install a real font mapper.
        del name
        return []

    def get_width(self, name: str) -> float:
        return float(self._metrics.get_glyph_width(name))

    def has_glyph(self, name: str) -> bool:
        return bool(self._metrics.has_glyph(name))

    # ---------- diagnostics ----------

    def __repr__(self) -> str:
        return f"Standard14FontWrapper({self._name!r})"


# ---------------------------------------------------------------------------
# Default mapper.
# ---------------------------------------------------------------------------


# Style-fallback table for unknown PostScript names. Picks a Helvetica
# variant by descriptor flags (italic / fixed-pitch / serif). Mirrors
# the spirit of the upstream "fallback" branch in ``FontMapperImpl``,
# pared down to Standard 14 because that's all the default mapper can
# materialise without scanning the OS font directories.
_FLAG_FIXED_PITCH = 1 << 0
_FLAG_SERIF = 1 << 1
_FLAG_ITALIC = 1 << 6


class DefaultFontMapper(FontMapper):
    """Standard-14-only font mapper.

    Resolution rules:

    1. If ``base_font`` resolves to a Standard 14 canonical name (direct
       or via :meth:`Standard14Fonts.get_mapped_font_name`), return a
       non-fallback :class:`FontMapping` over the bundled AFM.
    2. Otherwise pick a Helvetica variant from
       ``font_descriptor.flags`` (italic / fixed-pitch) and return it
       as a *fallback* mapping. ``font_descriptor=None`` chooses
       plain Helvetica.

    ``get_true_type_font`` / ``get_open_type_font`` cannot be satisfied
    with AFMs alone (no on-disk outline data), so they return ``None``.
    ``get_font_box_font`` always returns *something* — that is the
    universal-fallback branch upstream callers depend on.
    """

    def __init__(self) -> None:
        # In-process cache — ``Standard14FontWrapper`` is cheap, but we
        # avoid building duplicates so identity tests in callers stay
        # stable across calls.
        self._cache: dict[str, Standard14FontWrapper] = {}

    # ---------- helpers ----------

    @staticmethod
    def _resolve_standard14(name: str) -> str | None:
        # Local import — see module docstring on the import cycle.
        from pypdfbox.pdmodel.font.standard14_fonts import Standard14Fonts

        return Standard14Fonts.get_mapped_font_name(name)

    def _wrapper_for(self, canonical: str) -> Standard14FontWrapper:
        existing = self._cache.get(canonical)
        if existing is not None:
            return existing
        from pypdfbox.pdmodel.font.afm_loader import load_standard14

        metrics = load_standard14(canonical)
        wrapper = Standard14FontWrapper(canonical, metrics)
        self._cache[canonical] = wrapper
        return wrapper

    @staticmethod
    def _fallback_canonical(font_descriptor: PDFontDescriptor | None) -> str:
        """Pick a Standard 14 canonical name based on descriptor flags."""
        flags = 0
        if font_descriptor is not None:
            try:
                flags = int(font_descriptor.get_flags())
            except (AttributeError, TypeError, ValueError):
                flags = 0
        is_italic = bool(flags & _FLAG_ITALIC)
        is_fixed = bool(flags & _FLAG_FIXED_PITCH)
        is_serif = bool(flags & _FLAG_SERIF)
        if is_fixed:
            if is_italic:
                return "Courier-Oblique"
            return "Courier"
        if is_serif:
            if is_italic:
                return "Times-Italic"
            return "Times-Roman"
        if is_italic:
            return "Helvetica-Oblique"
        return "Helvetica"

    # ---------- FontMapper API ----------

    def get_true_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        # The default mapper can't materialise a real TrueTypeFont
        # without scanning system fonts. Upstream callers that hit a
        # ``None`` here are expected to fall through to
        # :meth:`get_font_box_font`.
        del base_font, font_descriptor
        return None

    def get_open_type_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[Any] | None:
        # Same rationale as ``get_true_type_font`` — no system-font
        # scanner in the default mapper.
        del base_font, font_descriptor
        return None

    def get_font_box_font(
        self,
        base_font: str,
        font_descriptor: PDFontDescriptor | None,
    ) -> FontMapping[FontBoxFont] | None:
        canonical = self._resolve_standard14(base_font)
        if canonical is not None:
            wrapper = self._wrapper_for(canonical)
            return FontMapping(wrapper, is_fallback=False)
        # Style-driven fallback. We always succeed — the universal
        # fallback contract is what upstream callers depend on.
        fallback_canonical = self._fallback_canonical(font_descriptor)
        wrapper = self._wrapper_for(fallback_canonical)
        return FontMapping(wrapper, is_fallback=True)


__all__ = [
    "DefaultFontMapper",
    "FontMapper",
    "Standard14FontWrapper",
]
