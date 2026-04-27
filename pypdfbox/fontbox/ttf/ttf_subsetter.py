"""TrueType font subsetter.

Mirrors :class:`org.apache.fontbox.ttf.TTFSubsetter` at the public-method
level. Upstream walks ``glyf``/``loca``/``hmtx``/``cmap``/``post`` by hand
to produce a subset font (~600 LOC). Re-implementing that in Python
would be redundant: TTF subsetting is exactly what the (MIT-licensed)
``fontTools.subset`` library exists for, so we wrap it instead.

Public surface kept compatible with upstream:

* ``TTFSubsetter(ttf, tables=None)`` constructor.
* ``add(unicode)`` / ``add_all(iterable)`` / ``add_glyph_ids(set)``.
* ``set_prefix(str)`` — six-letter random tag prepended to the
  PostScript name (PDF 32000-1 §9.6.4 subset-font naming convention).
* ``write_to_stream(out)`` — emit the subset font bytes; or
  :meth:`to_bytes` to grab them as a ``bytes`` buffer.

GID 0 (``.notdef``) is always retained, matching upstream behaviour.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont


# Default set of tables upstream's ``TrueTypeEmbedder`` keeps when
# subsetting a font for PDF embedding. ``fontTools.subset`` already
# trims to a sensible PDF-friendly set by default; this list is what
# upstream callers pass through ``TTFSubsetter(ttf, tables)`` and is
# preserved here so the constructor signature stays compatible.
_DEFAULT_KEEP_TABLES = (
    "head",
    "hhea",
    "loca",
    "maxp",
    "cvt ",
    "prep",
    "glyf",
    "hmtx",
    "fpgm",
    "gasp",
)


class TTFSubsetter:
    """Subsetter for TrueType (TTF) fonts.

    Wraps ``fontTools.subset.Subsetter``: callers register Unicode
    codepoints (and optionally raw glyph IDs), then ``write_to_stream``
    flushes a freshly-built TTF binary to the supplied output. Each
    instance owns its own working :class:`fontTools.ttLib.TTFont`, so
    the source :class:`TrueTypeFont` is left untouched.
    """

    def __init__(
        self,
        ttf: TrueTypeFont,
        tables: list[str] | None = None,
    ) -> None:
        self._ttf = ttf
        # ``None`` means "let fontTools decide" (its default keep set is
        # already tuned for PDF embedding). An explicit list — typically
        # the upstream ``TrueTypeEmbedder`` set above — is preserved as
        # a hint passed through ``with_tables`` on the underlying
        # subsetter options.
        self._keep_tables: list[str] | None = list(tables) if tables else None

        # Codepoints / glyph IDs accumulated until flush. We do NOT
        # resolve unicode -> gid eagerly; ``fontTools.subset`` does that
        # itself when ``populate(unicodes=...)`` runs, and matches the
        # font's selected cmap exactly.
        self._unicodes: set[int] = set()
        self._glyph_ids: set[int] = {0}  # always keep .notdef

        self._prefix: str | None = None

    # ---------- registration API ------------------------------------------

    def add(self, unicode_codepoint: int) -> None:
        """Register a Unicode codepoint to keep in the subset.

        Mirrors upstream ``TTFSubsetter.add(int)``. Unknown codepoints
        (those that map to GID 0 in the font's cmap) are still recorded
        — fontTools silently skips them at flush time, matching upstream
        behaviour where unmapped codepoints contribute nothing.
        """
        self._unicodes.add(int(unicode_codepoint))

    def add_all(self, codepoints: Iterable[int]) -> None:
        """Register a batch of Unicode codepoints. Mirrors upstream
        ``TTFSubsetter.addAll(Set<Integer>)``."""
        for cp in codepoints:
            self._unicodes.add(int(cp))

    def add_glyph_ids(self, glyph_ids: Iterable[int]) -> None:
        """Register raw glyph IDs to keep, bypassing the cmap.

        Useful when the caller already knows the GIDs (e.g. from a CID
        font) and wants to preserve glyphs that aren't reachable through
        the chosen Unicode cmap subtable.
        """
        for gid in glyph_ids:
            self._glyph_ids.add(int(gid))

    # ---------- options ---------------------------------------------------

    def set_prefix(self, prefix: str) -> None:
        """Set the six-letter subset tag prepended to the PostScript name.

        PDF 32000-1 §9.6.4 specifies that a subsetted embedded font's
        ``/BaseFont`` is the original PostScript name with a six
        uppercase ASCII letter tag plus ``+`` prepended (e.g.
        ``ABCDEF+Helvetica``). This method records the tag; it is
        applied to ``name`` table records during :meth:`write_to_stream`.
        """
        self._prefix = prefix

    # ---------- emission --------------------------------------------------

    def write_to_stream(self, out: IO[bytes]) -> None:
        """Emit the subset font bytes to ``out``.

        Equivalent to upstream ``TTFSubsetter.writeToStream(OutputStream)``.
        Internally:

        1. Loads the source font into a fresh :class:`fontTools.ttLib.TTFont`
           (so we don't disturb the parent :class:`TrueTypeFont` cache).
        2. Configures ``fontTools.subset.Subsetter`` with the requested
           Unicode codepoints and explicit GIDs, then runs
           ``subset(ttfont)``.
        3. Optionally rewrites the PostScript / family name records to
           prepend the subset prefix.
        4. Saves the result to a buffer, then copies it into ``out``.
        """
        out.write(self.to_bytes())

    def to_bytes(self) -> bytes:
        """Return the subset font as a ``bytes`` buffer."""
        # Lazy imports — fontTools is a heavy import and this method is
        # only invoked when a caller actually wants subset output.
        import fontTools.subset as ft_subset  # noqa: PLC0415
        import fontTools.ttLib as ttLib  # noqa: PLC0415

        # Build a fresh in-memory copy of the source font so subsetting
        # doesn't perturb the cached fontTools instance the parent
        # TrueTypeFont may still be using for accessor calls.
        raw = self._ttf._read_all_bytes(self._ttf._data)  # noqa: SLF001
        tt = ttLib.TTFont(io.BytesIO(raw))

        options = ft_subset.Options()
        # Match upstream's "embed for PDF" posture: keep hinting bytes
        # (fpgm/prep/cvt) and per-glyph names; drop layout features the
        # PDF renderer doesn't consult.
        options.notdef_outline = True
        options.recalc_bounds = True
        options.recalc_timestamp = False
        options.canonical_order = True
        options.glyph_names = True
        options.legacy_kern = True
        options.name_IDs = ["*"]
        options.name_legacy = True
        options.name_languages = ["*"]
        options.hinting = True
        # Drop the layout tables PDFBox itself drops when subsetting;
        # they aren't consulted by the PDF rendering pipeline and bloat
        # the embedded font.
        options.layout_features = []
        options.drop_tables += ["DSIG", "BASE", "JSTF", "GDEF", "GSUB", "GPOS"]

        # Upstream's ``tables`` constructor argument is a hint listing
        # which optional tables to retain (e.g. ``cvt ``/``prep``/``fpgm``
        # for hinting). fontTools' default keep set already retains
        # those, so we record the hint on the instance for callers but
        # don't translate it into ``no_subset_tables`` — that flag
        # disables subsetting, which would leave ``hmtx``/``glyf`` stale
        # relative to the new glyph order. The hint is preserved purely
        # for upstream-API parity.
        _ = self._keep_tables

        subsetter = ft_subset.Subsetter(options=options)
        subsetter.populate(
            unicodes=sorted(self._unicodes),
            glyphs=[],
            gids=sorted(self._glyph_ids),
        )
        subsetter.subset(tt)

        if self._prefix:
            self._apply_prefix(tt, self._prefix)

        buf = io.BytesIO()
        tt.save(buf)
        return buf.getvalue()

    # ---------- helpers ---------------------------------------------------

    @staticmethod
    def _apply_prefix(tt: Any, prefix: str) -> None:
        """Rewrite the subset's ``name`` table records to prepend the
        six-letter PDF subset tag (per PDF 32000-1 §9.6.4).

        Upstream applies the prefix to nameID 6 (PostScript name); we
        also touch nameID 4 (full name) so PDF readers' font-pickers
        show the tagged name consistently. nameID 1 (family) and nameID
        16/17 (typographic family/subfamily) intentionally stay
        un-prefixed — they describe the font *family*, which the subset
        still belongs to.
        """
        if "name" not in tt:
            return
        name_table = tt["name"]
        targets = (4, 6)  # full name, PostScript name
        for record in list(name_table.names):
            if record.nameID not in targets:
                continue
            current = record.toUnicode()
            if not current:
                continue
            # Only prepend if not already tagged — calling write twice
            # mustn't double-prefix.
            if (
                len(current) >= 7
                and current[6] == "+"
                and current[:6].isalpha()
                and current[:6].isupper()
            ):
                continue
            tagged = f"{prefix}+{current}"
            record.string = tagged


__all__ = ["TTFSubsetter"]
