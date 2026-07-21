"""Common functionality for embedding TrueType fonts.

Mirrors ``org.apache.pdfbox.pdmodel.font.TrueTypeEmbedder`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/TrueTypeEmbedder.java``
lines 51-389).

Abstract base for :class:`PDTrueTypeFontEmbedder` (Type 1-encoded
TrueType) and :class:`PDCIDFontType2Embedder` (CID-keyed TrueType).
Handles:

* fsType-driven embedding/subsetting permission checks (Java line
  146-185).
* :class:`PDFontDescriptor` construction from OS/2 + head + hhea +
  post tables (Java line 190-287).
* Subset workflow — collect Unicode code points via
  :meth:`add_to_subset`, then run :meth:`subset` to invoke fontTools'
  ``Subsetter`` and call :meth:`build_subset` on the concrete subclass.

**Library-first:** the actual subsetting work is delegated to
``fontTools.subset.Subsetter``. We never reimplement glyph reachability
or CFF table rewriting ourselves.
"""

from __future__ import annotations

import io
from abc import abstractmethod
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSDictionary, COSName

from .pd_font_descriptor import PDFontDescriptor
from .subsetter import Subsetter

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


# Tables the PDF spec mandates be kept (Java line 58-61). All others are
# stripped by the subsetter.
_REQUIRED_TABLES: tuple[str, ...] = (
    "head",
    "hhea",
    "loca",
    "maxp",
    "cvt ",
    "prep",
    "glyf",
    "hmtx",
    "fpgm",
    "gasp",  # Windows ClearType
)

# Tables whose bytes must be preserved verbatim (i.e. *not* subset) when
# embedding a TrueType font in a PDF. fontTools' ``Options.no_subset_tables``
# takes a list of 4-byte SFNT tags; entries on this list survive the
# subsetting pass with their original bytes (modulo glyph-index renumber
# upstream of them, which only affects glyf/loca/hmtx).
#
# The default set is what *every* TTF-embedded font needs to round-trip
# safely through a PDF reader: the descriptor metadata tables (head, hhea,
# maxp, name, OS/2, post) which downstream code consults via the font
# descriptor's `/FontFile2` field. These tables are not glyph-index
# dependent and don't need to be rebuilt by the subsetter.
_DEFAULT_NO_SUBSET_TABLES: tuple[str, ...] = (
    "head",
    "hhea",
    "maxp",
    "name",
    "OS/2",
    "post",
)

# Additional tables to preserve verbatim for CID-keyed (Type0/CIDFontType2)
# embeddings: the PostScript hinting bytecode tables (cvt, fpgm, prep)
# that drive the rasteriser at low resolution. CID embeddings are
# generally produced from larger, more aggressively hinted CJK fonts
# where dropping the hinting tables would cause visible rasterisation
# degradation at body-text point sizes.
_CID_NO_SUBSET_TABLES: tuple[str, ...] = _DEFAULT_NO_SUBSET_TABLES + (
    "cmap",
    "cvt ",
    "fpgm",
    "prep",
)

_BASE25 = "BCDEFGHIJKLMNOPQRSTUVWXYZ"

_ITALIC = 1
_OBLIQUE = 512


class TrueTypeEmbedder(Subsetter):
    """Shared TTF embedding machinery.

    Mirrors upstream abstract class (Java line 51-389).
    """

    def __init__(
        self,
        document: PDDocument,
        dict_: COSDictionary,
        ttf: Any,
        embed_subset: bool,
    ) -> None:
        # Mirror upstream constructor body (Java line 77-120). ``ttf`` is
        # a fontTools ``TTFont`` instance — close enough to upstream's
        # ``TrueTypeFont`` for the metadata accessors we care about.
        self._document: PDDocument = document
        self._embed_subset: bool = embed_subset
        self._ttf: Any = ttf
        self.font_descriptor: PDFontDescriptor = self._create_font_descriptor(ttf)
        if not self.is_embedding_permitted(ttf):
            raise OSError("This font does not permit embedding")
        # PDFBOX-6210: insertion-ordered (upstream switched ``HashSet`` ->
        # ``LinkedHashSet``) so the ToUnicode builder can prefer the code
        # point actually used first in the document when several code
        # points share one glyph. A plain dict is Python's ordered set.
        self._subset_code_points: dict[int, None] = {}
        self._all_glyph_ids: set[int] = set()
        # Tables whose bytes should be preserved verbatim through the
        # fontTools subsetter (mirrors ``TTFSubsetter.no_subset_tables``).
        # Initialised to the conservative default; CID-keyed subclasses
        # (PDCIDFontType2Embedder) widen this to include PostScript
        # hinting tables. Callers can also tweak it through
        # :meth:`set_no_subset_tables`.
        self._no_subset_tables: tuple[str, ...] = _DEFAULT_NO_SUBSET_TABLES
        self._dict: COSDictionary = dict_
        if not embed_subset:
            # Full embedding (Java line 89-114): stream the original TTF
            # bytes into a font program.
            self._build_full_font_file(ttf)
        dict_.set_name(COSName.BASE_FONT, self._get_font_name(ttf))

    # ---------- subclass hooks ----------

    @abstractmethod
    def build_subset(
        self,
        ttf_subset: io.BufferedIOBase,
        tag: str,
        gid_to_cid: dict[int, int],
    ) -> None:
        """Re-build the font subset (subclass-specific).

        Mirrors upstream abstract ``buildSubset`` (Java line 359-360).
        """

    # ---------- Subsetter interface ----------

    def add_to_subset(self, code_point: int) -> None:
        """Register *code_point* for inclusion in the subset.

        Mirrors upstream ``addToSubset`` (Java line 299-302).
        """
        self._subset_code_points[code_point] = None

    def get_subset_code_points(self) -> tuple[int, ...]:
        """Return the code points passed to :meth:`add_to_subset`, i.e. the
        code points actually used in the document, in first-occurrence order.

        Used when building the ToUnicode CMap to map a glyph back to the
        code point that was really typed (PDFBOX-6210). Mirrors upstream
        ``getSubsetCodePoints`` (Java line 311-314).
        """
        return tuple(self._subset_code_points)

    def add_glyph_ids(self, glyph_ids: set[int]) -> None:
        """Register glyph IDs for inclusion in the subset.

        Mirrors upstream ``addGlyphIds`` (Java line 303-306).
        """
        self._all_glyph_ids.update(glyph_ids)

    def set_no_subset_tables(self, table_names: tuple[str, ...] | list[str]) -> None:
        """Override the list of tables to preserve verbatim through subsetting.

        Mirrors :meth:`TTFSubsetter.set_no_subset_tables` on the fontbox
        layer. Pass a sequence of 4-byte SFNT table tags (e.g.
        ``("head", "hhea", "name", "OS/2", "post")``) — those tables are
        excluded from fontTools' subset pass and round-trip with their
        original bytes intact (modulo any glyph-index renumber needed
        for inter-table consistency).

        Use cases:

        * CID embeddings of PostScript-hinted CJK fonts where dropping
          the hinting bytecode (``cvt ``/``fpgm``/``prep``) degrades
          rendering at body-text sizes — keep them verbatim.
        * Custom subsetting policies driven by tooling that needs to
          retain specific opaque tables.
        """
        self._no_subset_tables = tuple(table_names)

    def get_no_subset_tables(self) -> tuple[str, ...]:
        """Return the active no-subset table list.

        See :meth:`set_no_subset_tables` for semantics.
        """
        return self._no_subset_tables

    def subset(self) -> None:
        """Compute the subset using fontTools.

        Mirrors upstream ``subset()`` (Java line 309-346). Library-first:
        delegates to :class:`fontTools.subset.Subsetter`.
        """
        if not self.is_subsetting_permitted(self._ttf):
            raise OSError("This font does not permit subsetting")
        if not self._embed_subset:
            raise RuntimeError("Subsetting is disabled")
        try:
            from fontTools.subset import Options
            from fontTools.subset import Subsetter as FTSubsetter
        except ImportError as ex:
            raise OSError("fontTools is required for subsetting") from ex
        options = Options()
        # Restrict to the PDF-spec-required tables (Java line 58-61).
        options.layout_features = []
        # Honour the per-font-subclass no-subset policy. Default is the
        # conservative ``_DEFAULT_NO_SUBSET_TABLES`` list; CID-keyed
        # embedders widen this to retain hinting bytecode. Union with
        # fontTools' own default so we never accidentally drop tables
        # whose subset behavior fontTools handles internally (e.g.
        # ``loca`` / ``avar``).
        options.no_subset_tables = list(
            dict.fromkeys(
                [*options.no_subset_tables, *self._no_subset_tables]
            )
        )
        subsetter = FTSubsetter(options=options)
        if self._subset_code_points:
            subsetter.populate(unicodes=list(self._subset_code_points))
        elif self._all_glyph_ids:
            subsetter.populate(gids=list(self._all_glyph_ids))
        else:
            subsetter.populate(unicodes=[])
        subsetter.subset(self._ttf)
        out = io.BytesIO()
        self._ttf.save(out)
        out.seek(0)
        # Compute deterministic 6-char tag from the GID mapping.
        gid_to_cid = self._compute_gid_to_cid()
        tag = self.get_tag(gid_to_cid)
        self.build_subset(out, tag, gid_to_cid)

    def needs_subset(self) -> bool:
        """Return ``True`` if subsetting is enabled.

        Mirrors upstream ``needsSubset`` (Java line 351-354).
        """
        return self._embed_subset

    # ---------- helpers ----------

    @staticmethod
    def get_tag(gid_to_cid: dict[int, int]) -> str:
        """Return a deterministic 6-letter subset tag, suffixed with ``"+"``.

        Mirrors upstream ``getTag`` (Java line 365-388).
        """
        # Java uses ``gidToCid.hashCode()`` which is deterministic for
        # ``HashMap``. Python ``dict.__hash__`` doesn't exist, so we
        # use a stable hash over sorted (k, v) tuples.
        num = abs(hash(tuple(sorted(gid_to_cid.items())))) % (10**18)
        sb: list[str] = []
        while num != 0 and len(sb) < 6:
            div, mod = divmod(num, 25)
            sb.append(_BASE25[mod])
            num = div
        while len(sb) < 6:
            sb.insert(0, "A")
        return "".join(sb) + "+"

    def get_font_descriptor(self) -> PDFontDescriptor:
        """Return the constructed :class:`PDFontDescriptor`.

        Mirrors upstream ``getFontDescriptor`` (Java line 292-295).
        """
        return self.font_descriptor

    # ---------- permission checks ----------

    @staticmethod
    def is_embedding_permitted(ttf: Any) -> bool:
        """Return ``True`` if the TTF's fsType permits embedding.

        Mirrors upstream ``isEmbeddingPermitted`` (Java line 146-167).
        """
        try:
            os2 = ttf["OS/2"]
        except KeyError:
            return True
        fs_type = int(getattr(os2, "fsType", 0))
        masked = fs_type & 0x000F
        if masked == 0x0002:  # RESTRICTED_LICENSE_EMBEDDING
            return False
        # BITMAP_EMBEDDING_ONLY (0x0200) — also blocks outline embedding.
        return not (fs_type & 0x0200)

    @staticmethod
    def is_subsetting_permitted(ttf: Any) -> bool:
        """Return ``True`` if the TTF's fsType permits subsetting.

        Mirrors upstream ``isSubsettingPermitted`` (Java line 172-185).
        """
        try:
            os2 = ttf["OS/2"]
        except KeyError:
            return True
        fs_type = int(getattr(os2, "fsType", 0))
        # NO_SUBSETTING bit (0x0100) — disables subsetting permission.
        return not (fs_type & 0x0100)

    # ---------- descriptor construction ----------

    def create_font_descriptor(self, ttf: Any) -> PDFontDescriptor:
        """Build a :class:`PDFontDescriptor` from the TTF tables.

        Mirrors upstream ``createFontDescriptor`` (Java line 190-287).
        """
        return self._create_font_descriptor(ttf)

    def _create_font_descriptor(self, ttf: Any) -> PDFontDescriptor:
        """Build a :class:`PDFontDescriptor` from the TTF tables.

        Mirrors upstream ``createFontDescriptor`` (Java line 190-287).
        """
        font_name = self._get_font_name(ttf)
        try:
            os2 = ttf["OS/2"]
        except KeyError as ex:
            raise OSError(f"os2 table is missing in font {font_name}") from ex
        try:
            post = ttf["post"]
        except KeyError as ex:
            raise OSError(f"post table is missing in font {font_name}") from ex
        fd = PDFontDescriptor()
        fd.set_font_name(font_name)
        try:
            hhea = ttf["hhea"]
            number_of_hmetrics = int(getattr(hhea, "numberOfHMetrics", 0))
            ascender = float(getattr(hhea, "ascent", 0) or 0)
            descender = float(getattr(hhea, "descent", 0) or 0)
        except KeyError:
            number_of_hmetrics = 0
            ascender = 0.0
            descender = 0.0
        is_fixed_pitch = int(getattr(post, "isFixedPitch", 0) or 0)
        fd.set_fixed_pitch(is_fixed_pitch > 0 or number_of_hmetrics == 1)
        fs_selection = int(getattr(os2, "fsSelection", 0) or 0)
        fd.set_italic((fs_selection & (_ITALIC | _OBLIQUE)) != 0)
        family_class = int(getattr(os2, "sFamilyClass", 0) or 0) >> 8
        if family_class in {3, 4, 5, 7, 1}:
            fd.set_serif(True)
        elif family_class == 10:
            fd.set_script(True)
        fd.set_font_weight(float(getattr(os2, "usWeightClass", 0) or 0))
        fd.set_symbolic(True)
        fd.set_non_symbolic(False)
        fd.set_italic_angle(float(getattr(post, "italicAngle", 0) or 0))
        # FontBBox
        try:
            head = ttf["head"]
            units_per_em = int(getattr(head, "unitsPerEm", 1000) or 1000)
            scaling = 1000.0 / units_per_em
            from pypdfbox.pdmodel.pd_rectangle import PDRectangle

            rect = PDRectangle()
            rect.set_lower_left_x(float(getattr(head, "xMin", 0) or 0) * scaling)
            rect.set_lower_left_y(float(getattr(head, "yMin", 0) or 0) * scaling)
            rect.set_upper_right_x(float(getattr(head, "xMax", 0) or 0) * scaling)
            rect.set_upper_right_y(float(getattr(head, "yMax", 0) or 0) * scaling)
            fd.set_font_bounding_box(rect)
            fd.set_ascent(ascender * scaling)
            fd.set_descent(descender * scaling)
            os2_version = float(getattr(os2, "version", 0) or 0)
            if os2_version >= 1.2:
                fd.set_cap_height(
                    float(getattr(os2, "sCapHeight", 0) or 0) * scaling
                )
                fd.set_x_height(float(getattr(os2, "sxHeight", 0) or 0) * scaling)
            try:
                width = rect.get_width()
                fd.set_stem_v(width * 0.13)
            except (AttributeError, TypeError):
                pass
        except (KeyError, ImportError):
            pass
        return fd

    @staticmethod
    def _get_font_name(ttf: Any) -> str:
        """Return the PostScript name (name ID 6)."""
        try:
            name_table = ttf["name"]
            return name_table.getDebugName(6) or ""
        except (KeyError, AttributeError):
            return ""

    def build_font_file2(self, ttf_stream: Any) -> None:
        """Embed *ttf_stream* (raw TTF bytes) as ``/FontFile2``.

        Mirrors upstream ``buildFontFile2`` (Java line 122-145). Accepts
        either a binary file-like object or :class:`bytes`.
        """
        from pypdfbox.pdmodel.common import PDStream

        data = ttf_stream.read() if hasattr(ttf_stream, "read") else bytes(ttf_stream)
        if data[:4] == b"ttcf":
            raise OSError("Full embedding of TrueType font collections not supported")
        stream = PDStream(self._document, io.BytesIO(data), COSName.FLATE_DECODE)
        stream.get_cos_object().set_long(COSName.get_pdf_name("Length1"), len(data))
        self.font_descriptor.set_font_file2(stream)

    def _build_full_font_file(self, ttf: Any) -> None:
        """Embed the full TTF as a /FontFile2 stream."""
        from pypdfbox.pdmodel.common import PDStream

        buf = io.BytesIO()
        try:
            ttf.save(buf)
        except (OSError, AttributeError):
            return
        data = buf.getvalue()
        if data[:4] == b"ttcf":
            raise OSError("Full embedding of TrueType font collections not supported")
        stream = PDStream(self._document, io.BytesIO(data), COSName.FLATE_DECODE)
        stream.get_cos_object().set_long(COSName.get_pdf_name("Length1"), len(data))
        self.font_descriptor.set_font_file2(stream)

    def _compute_gid_to_cid(self) -> dict[int, int]:
        """Return a deterministic GID -> CID mapping for tag derivation.

        After fontTools subsets, the surviving glyphs renumber. Without
        accessing fontTools' subsetter internals we approximate by
        mapping subset glyph IDs back to themselves; the tag is
        deterministic over the GID set which is what upstream actually
        depends on for cache invalidation.
        """
        try:
            num = int(self._ttf["maxp"].numGlyphs)
        except KeyError:
            num = 0
        return {gid: gid for gid in range(num)}


__all__ = ["TrueTypeEmbedder"]
