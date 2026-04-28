from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class GlyphPositioningTable(TTFTable):
    """``GPOS`` — Glyph Positioning table.

    Mirrors ``org.apache.fontbox.ttf.GlyphPositioningTable`` at the
    *public API surface* level. The actual on-disk parsing of the GPOS
    table (script list, feature list, lookup list, the nine lookup
    subtable variants, and the ``ValueRecord`` shape) is delegated to
    ``fontTools.ttLib`` (MIT-licensed) — re-implementing a complete GPOS
    decoder in pure Python would duplicate a significant chunk of
    upstream Java that fontTools already covers comprehensively, and
    upstream PDFBox 3.0 itself does *not* ship a complete GPOS reader
    (it stops at script/feature inventory and a "kern-feature only"
    convenience). We follow the same shape: shallow accessors over the
    ScriptList / FeatureList / LookupList plus a kerning-pair convenience
    on top of lookup type 2.

    Lookup-type coverage exposed here:

    * Type 1 — Single adjustment (``ValueRecord`` per coverage glyph)
    * Type 2 — Pair adjustment (kerning) — Format 1 (per-glyph pair sets)
      and Format 2 (class-based) — see :meth:`get_kerning`
    * Type 3 — Cursive attachment (entry/exit anchors)
    * Type 4 — Mark-to-base attachment
    * Type 5 — Mark-to-ligature attachment
    * Type 6 — Mark-to-mark attachment
    * Type 7 — Contextual positioning (rule-based, three sub-formats)
    * Type 8 — Chained contextual positioning (three sub-formats)
    * Type 9 — Extension positioning (transparent — fontTools inlines
      the wrapped subtable, so type-9 lookups surface as their wrapped
      type at this layer)

    The lookup-type taxonomy is exposed as a numeric ``LOOKUP_TYPE_*``
    constant set on this class; consumers walking the raw structure
    (via :meth:`get_raw_table`) get the same numbers fontTools writes.

    Deviations from upstream — see ``CHANGES.md``:

    * No ``GposData`` projection. Upstream stops short of one too;
      callers needing structured access reach for :meth:`get_raw_table`.
    * Application of contextual / chained / mark-attachment lookups
      against a glyph stream is not exposed (would require porting the
      full positioning engine — out of scope for the current PDF text
      use-cases). The accessors that *are* exposed (script tags, feature
      tags, kerning pair lookup) cover the entire surface upstream
      PDFBox 3.0 actually invokes.
    """

    TAG: str = "GPOS"

    # OpenType GPOS lookup-type constants (mirrors the OT spec § GPOS Header).
    LOOKUP_TYPE_SINGLE_ADJUSTMENT: int = 1
    LOOKUP_TYPE_PAIR_ADJUSTMENT: int = 2
    LOOKUP_TYPE_CURSIVE_ATTACHMENT: int = 3
    LOOKUP_TYPE_MARK_TO_BASE: int = 4
    LOOKUP_TYPE_MARK_TO_LIGATURE: int = 5
    LOOKUP_TYPE_MARK_TO_MARK: int = 6
    LOOKUP_TYPE_CONTEXTUAL: int = 7
    LOOKUP_TYPE_CHAINED_CONTEXTUAL: int = 8
    LOOKUP_TYPE_EXTENSION: int = 9

    def __init__(self) -> None:
        super().__init__()
        self._tag = self.TAG

        # fontTools-side handles, populated by :meth:`populate_from_fonttools`.
        self._tt_font: Any | None = None
        self._gpos_table: Any | None = None
        # Glyph-order projection so pair-adjustment lookups (which
        # fontTools exposes keyed by *glyph name*) can be evaluated in
        # GID space without re-reading the parent ``TTFont`` per call.
        self._glyph_order: list[str] = []
        self._glyph_name_to_gid: dict[str, int] = {}

        # Cached views derived from the fontTools structures. These
        # mirror upstream's ``scriptList`` / ``featureListTable`` /
        # ``lookupListTable`` private fields at the *shape* level
        # (a list[str] of script tags, a list[str] of feature tags),
        # not the full LangSys / FeatureRecord / LookupTable graph.
        self._script_tags: list[str] = []
        self._feature_tags: list[str] = []

        # Cached GID-keyed kerning map populated lazily on first
        # :meth:`get_kerning` call. ``None`` = "not yet built".
        # Built across every lookup type 2 subtable in the GPOS, both
        # format 1 (pair-set) and format 2 (class-based) — matches the
        # behaviour of upstream's ``kern`` feature consumer which
        # iterates every applicable pair-adjustment lookup.
        self._kerning_pairs: dict[tuple[int, int], int] | None = None

    # ------------------------------------------------------------------
    # Population path
    # ------------------------------------------------------------------

    def populate_from_fonttools(self, tt_font: Any) -> None:
        """Bind this wrapper to a fontTools ``TTFont`` whose ``GPOS``
        table will back all queries.

        Called by :meth:`TrueTypeFont.get_gpos`. Kept as a method (not a
        classmethod) to mirror the populate-then-cache pattern used by
        :class:`GlyphSubstitutionTable` / :class:`DigitalSignatureTable`.
        """
        self._tt_font = tt_font
        gpos_wrapper = tt_font["GPOS"]
        # fontTools exposes the parsed structure on ``.table`` (an
        # ``otTables.GPOS`` instance). Hold a reference so callers that
        # want the upstream-equivalent raw view can reach it via
        # :meth:`get_raw_table`.
        self._gpos_table = getattr(gpos_wrapper, "table", None)
        self._glyph_order = list(tt_font.getGlyphOrder())
        self._glyph_name_to_gid = {n: i for i, n in enumerate(self._glyph_order)}

        # Populate shallow tag lists from the fontTools structures.
        # Use ``LinkedHashMap``-style dedup-with-order semantics to
        # match upstream — first occurrence wins on duplicate tags.
        seen_scripts: dict[str, None] = {}
        seen_features: dict[str, None] = {}
        if self._gpos_table is not None:
            sl = getattr(self._gpos_table, "ScriptList", None)
            if sl is not None:
                for sr in getattr(sl, "ScriptRecord", None) or []:
                    tag = str(sr.ScriptTag)
                    if tag not in seen_scripts:
                        seen_scripts[tag] = None
            fl = getattr(self._gpos_table, "FeatureList", None)
            if fl is not None:
                for fr in getattr(fl, "FeatureRecord", None) or []:
                    tag = str(fr.FeatureTag).strip()
                    seen_features.setdefault(tag, None)
        self._script_tags = list(seen_scripts.keys())
        self._feature_tags = list(seen_features.keys())
        self.initialized = True

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:  # noqa: ARG002
        """Stand-in for the upstream ``read`` slot.

        We don't decode GPOS from the raw byte stream — fontTools owns
        that path. Real population happens in
        :meth:`populate_from_fonttools`. This override exists purely so
        the abstract slot from :class:`TTFTable` is satisfied for
        callers that hold a reference typed as the base class.
        """
        # Intentionally empty — see GlyphSubstitutionTable for the same
        # pattern.

    # ------------------------------------------------------------------
    # Public API surface (snake_case mirror of upstream method names)
    # ------------------------------------------------------------------

    def get_supported_script_tags(self) -> set[str]:
        """Set of OpenType script tags this GPOS carries records for.

        Mirrors ``GlyphPositioningTable.getSupportedScriptTags``.
        Upstream returns an unmodifiable view; we return a fresh
        ``set`` each call (Python sets aren't shareably-immutable, and
        copying a tag list is cheap).
        """
        return set(self._script_tags)

    def get_supported_feature_tags(self) -> list[str]:
        """List of feature tags present in this GPOS's FeatureList.

        Order matches the on-disk FeatureRecord order (which fontTools
        preserves). Typical entries include ``kern``, ``mark``,
        ``mkmk``, ``cpsp``, ``size``. Not present on upstream — added so
        callers can introspect available features without reaching into
        :meth:`get_raw_table`.
        """
        return list(self._feature_tags)

    def get_lookup_count(self) -> int:
        """Number of lookups in this GPOS's LookupList (0 if absent)."""
        if self._gpos_table is None:
            return 0
        ll = getattr(self._gpos_table, "LookupList", None)
        if ll is None:
            return 0
        return len(getattr(ll, "Lookup", None) or [])

    def get_lookup_types(self) -> list[int]:
        """Per-lookup ``LookupType`` integer in directory order.

        Useful for callers that want to know what positioning behaviour
        the font advertises — e.g. spotting a mark-attachment lookup
        for a complex script. Not present on upstream; pypdfbox-only
        introspection helper.
        """
        if self._gpos_table is None:
            return []
        ll = getattr(self._gpos_table, "LookupList", None)
        if ll is None:
            return []
        return [int(lk.LookupType) for lk in (getattr(ll, "Lookup", None) or [])]

    # ------------------------------------------------------------------
    # OT-aliased structural accessors
    # ------------------------------------------------------------------
    #
    # Upstream PDFBox's ``GlyphPositioningTable`` keeps the on-disk
    # OpenType structures (ScriptList, FeatureList, LookupList) as
    # private fields without exposing them — callers only get the
    # derived tag/inventory views. We surface the underlying fontTools
    # structures so consumers that need full access (e.g. positioning
    # engine ports, OpenType introspection tools) don't have to reach
    # through ``get_raw_table()``. These return the raw fontTools
    # objects (``otTables.ScriptList`` etc.) so attribute access matches
    # the OT spec field names exactly.

    def get_script_list(self) -> Any | None:
        """Underlying ``otTables.ScriptList`` (or ``None`` when absent).

        The returned object exposes a ``ScriptRecord`` list whose
        entries each carry a ``ScriptTag`` plus a ``Script`` with a
        ``DefaultLangSys`` and a ``LangSysRecord`` list. Walk this when
        per-language feature selection matters (e.g. enabling Turkish
        ``i`` dotted-i handling under the ``latn`` script).

        Not present on upstream; pypdfbox-only structural accessor.
        """
        if self._gpos_table is None:
            return None
        return getattr(self._gpos_table, "ScriptList", None)

    def get_feature_list(self) -> Any | None:
        """Underlying ``otTables.FeatureList`` (or ``None`` when absent).

        Carries an indexed ``FeatureRecord`` list — each record's
        ``FeatureTag`` is the four-byte feature identifier (``kern``,
        ``mark``, ``mkmk``, ...) and ``Feature.LookupListIndex`` is the
        list of lookup indices that implement that feature. The index
        position is what ``ScriptList``'s LangSys entries point into.

        Not present on upstream; pypdfbox-only structural accessor.
        """
        if self._gpos_table is None:
            return None
        return getattr(self._gpos_table, "FeatureList", None)

    def get_lookup_list(self) -> Any | None:
        """Underlying ``otTables.LookupList`` (or ``None`` when absent).

        Carries an indexed ``Lookup`` list — each entry has a
        ``LookupType`` (1..9 per OT § GPOS Header — see
        ``LOOKUP_TYPE_*`` constants on this class), a ``LookupFlag``
        bitfield (right-to-left, ignore-base / ligature / mark, mark
        filtering), and an ordered ``SubTable`` list whose entries
        are the actual positioning records.

        Not present on upstream; pypdfbox-only structural accessor.
        """
        if self._gpos_table is None:
            return None
        return getattr(self._gpos_table, "LookupList", None)

    def get_lookup(self, lookup_index: int) -> Any | None:
        """Return the ``otTables.Lookup`` at ``lookup_index`` (or
        ``None`` for an out-of-range / missing-table query).

        Index space matches ``FeatureRecord.Feature.LookupListIndex`` —
        feed those values straight in.

        Not present on upstream; pypdfbox-only structural accessor.
        """
        ll = self.get_lookup_list()
        if ll is None:
            return None
        lookups = getattr(ll, "Lookup", None) or []
        if lookup_index < 0 or lookup_index >= len(lookups):
            return None
        return lookups[lookup_index]

    def get_lookup_subtables(self, lookup_index: int) -> list[Any]:
        """Return the ordered ``SubTable`` list for the lookup at
        ``lookup_index``, or an empty list if the index is out of
        range / the table is absent.

        Subtable shape varies with ``LookupType``:

        * Type 1 — ``SinglePos`` (Format 1 single ValueRecord, Format 2
          per-coverage-glyph ValueRecord array).
        * Type 2 — ``PairPos`` (Format 1 PairSet of PairValueRecord,
          Format 2 Class1×Class2 matrix).
        * Type 3 — ``CursivePos`` (entry/exit anchors per coverage glyph).
        * Type 4 — ``MarkBasePos`` (mark + base anchor arrays).
        * Type 5 — ``MarkLigPos`` (mark + per-component ligature anchors).
        * Type 6 — ``MarkMarkPos`` (mark1 + mark2 anchor arrays).
        * Type 7 — ``ContextPos`` (rule-based, three sub-formats).
        * Type 8 — ``ChainContextPos`` (chained, three sub-formats).
        * Type 9 — ``ExtensionPos`` (transparently inlined by fontTools).

        Not present on upstream; pypdfbox-only structural accessor.
        Mirrors the request shape of upstream's GSUB-side
        ``LookupTable.getSubTables`` (gsub package).
        """
        lookup = self.get_lookup(lookup_index)
        if lookup is None:
            return []
        return list(getattr(lookup, "SubTable", None) or [])

    def get_feature_record(self, feature_index: int) -> Any | None:
        """Return the ``otTables.FeatureRecord`` at ``feature_index``,
        or ``None`` for out-of-range / missing-table queries.

        Index space matches ``LangSys.FeatureIndex`` and
        ``LangSys.ReqFeatureIndex`` — feed those values straight in.

        Not present on upstream; pypdfbox-only structural accessor.
        """
        fl = self.get_feature_list()
        if fl is None:
            return None
        records = getattr(fl, "FeatureRecord", None) or []
        if feature_index < 0 or feature_index >= len(records):
            return None
        return records[feature_index]

    def get_lookup_indices_for_feature(self, feature_tag: str) -> list[int]:
        """Return every lookup-index referenced by a feature whose tag
        matches ``feature_tag``.

        A single feature tag can appear in multiple FeatureRecords
        (e.g. ``kern`` once for Latin, once for Hebrew); we union the
        ``LookupListIndex`` lists across every match while preserving
        the order of first appearance and deduplicating repeats. This
        is the same shape the OT processing pipeline uses when a tag
        gates "every lookup that implements this feature regardless
        of script".

        Not present on upstream; pypdfbox-only structural accessor.
        """
        fl = self.get_feature_list()
        if fl is None:
            return []
        out: list[int] = []
        seen: set[int] = set()
        for fr in getattr(fl, "FeatureRecord", None) or []:
            tag = str(getattr(fr, "FeatureTag", "")).strip()
            if tag != feature_tag:
                continue
            feature = getattr(fr, "Feature", None)
            if feature is None:
                continue
            for li in getattr(feature, "LookupListIndex", None) or []:
                li_i = int(li)
                if li_i in seen:
                    continue
                seen.add(li_i)
                out.append(li_i)
        return out

    def get_raw_table(self) -> Any | None:
        """The underlying ``fontTools.ttLib.tables.otTables.GPOS``
        instance, or ``None`` if no GPOS was present.

        Escape hatch for callers that need the full GPOS graph
        (ScriptList, FeatureList, LookupList with full ValueRecord and
        anchor-point access). fontTools' object graph carries the same
        information upstream's hypothetical ``GposData`` projection
        would — just under the OT-spec attribute names. Not present on
        upstream.
        """
        return self._gpos_table

    # ------------------------------------------------------------------
    # Kerning convenience (lookup type 2)
    # ------------------------------------------------------------------

    def get_kerning(self, left_gid: int, right_gid: int) -> int:
        """Return the kerning adjustment (in font units) for the pair
        ``(left_gid, right_gid)``, or ``0`` when no GPOS pair-adjustment
        lookup covers it.

        Returns the **X-advance adjustment on the left glyph** which is
        the only positioning component the legacy ``kern`` table can
        express and the only one PDFBox actually consumes for text
        layout. Other ``ValueRecord`` components (X/Y placement, Y
        advance, contextual offsets) are present in :meth:`get_raw_table`
        but not surfaced here — matching upstream's ``KerningTable``-
        equivalent shape and PDF text-rendering semantics where pure
        advance-width tweaks are the only observable effect.

        Sentinel ``-1`` for either input short-circuits to ``0`` (no
        glyph -> no kern), mirroring how upstream's ``KerningSubtable``
        handles ``GID == -1``.
        """
        if left_gid == -1 or right_gid == -1:
            return 0
        if self._gpos_table is None:
            return 0
        if self._kerning_pairs is None:
            self._kerning_pairs = self._build_kerning_pairs()
        return self._kerning_pairs.get((left_gid, right_gid), 0)

    def has_kerning(self) -> bool:
        """``True`` iff the GPOS contains at least one type-2 lookup
        with at least one non-zero pair-adjustment X-advance.

        Lighter than enumerating :meth:`get_kerning` against every pair;
        useful for callers that just want to know whether to bother
        consulting GPOS at all. pypdfbox-only convenience.
        """
        if self._gpos_table is None:
            return False
        if self._kerning_pairs is None:
            self._kerning_pairs = self._build_kerning_pairs()
        return any(v != 0 for v in self._kerning_pairs.values())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_kerning_pairs(self) -> dict[tuple[int, int], int]:
        """Walk every lookup-type-2 subtable and project pair adjustments
        onto a ``{(left_gid, right_gid): x_advance}`` dict.

        Handles both PairAdjustment formats:

        * Format 1 — ``Coverage`` + per-glyph ``PairSet`` of
          ``PairValueRecord``\\ s. Direct GID-pair to ValueRecord.
        * Format 2 — ``Coverage`` + ``ClassDef1`` + ``ClassDef2`` +
          two-dimensional ``Class1Record / Class2Record`` matrix. Every
          coverage glyph in class ``c1`` paired against every glyph in
          ``ClassDef2`` mapped to class ``c2`` gets the matrix entry's
          ValueRecord. Class-0 in ``ClassDef2`` is the "everything not
          assigned" bucket per the OT spec.

        Lookup type 9 (extension) is transparent at this layer because
        fontTools resolves the wrapped subtable into the regular shape
        before we see it.

        Type 7 / 8 (contextual / chained) pair-adjustment effects are
        intentionally not unpacked — they require running the full
        positioning engine across a glyph stream. Same shape as
        upstream's stop-short coverage.
        """
        pairs: dict[tuple[int, int], int] = {}
        ll = getattr(self._gpos_table, "LookupList", None)
        if ll is None:
            return pairs
        for lk in getattr(ll, "Lookup", None) or []:
            if int(lk.LookupType) != self.LOOKUP_TYPE_PAIR_ADJUSTMENT:
                continue
            for sub in getattr(lk, "SubTable", None) or []:
                fmt = int(getattr(sub, "Format", 0))
                if fmt == 1:
                    self._absorb_pair_format1(sub, pairs)
                elif fmt == 2:
                    self._absorb_pair_format2(sub, pairs)
                # Other formats are non-spec and silently ignored —
                # matches upstream's "skip unknown subtable" pattern.
        return pairs

    def _absorb_pair_format1(
        self,
        sub: Any,
        pairs: dict[tuple[int, int], int],
    ) -> None:
        """Project a Format-1 PairPos subtable onto the GID-pair map."""
        coverage = getattr(sub, "Coverage", None)
        pair_sets = getattr(sub, "PairSet", None)
        if coverage is None or pair_sets is None:
            return
        cov_glyphs = getattr(coverage, "glyphs", None) or []
        for first_name, ps in zip(cov_glyphs, pair_sets):
            left_gid = self._glyph_name_to_gid.get(first_name)
            if left_gid is None:
                continue
            for pvr in getattr(ps, "PairValueRecord", None) or []:
                second_name = getattr(pvr, "SecondGlyph", None)
                if second_name is None:
                    continue
                right_gid = self._glyph_name_to_gid.get(second_name)
                if right_gid is None:
                    continue
                x_adv = self._extract_x_advance(getattr(pvr, "Value1", None))
                if x_adv != 0:
                    # Last write wins on duplicates — matches upstream's
                    # "later subtable overrides earlier" semantics for
                    # the same lookup feature.
                    pairs[(left_gid, right_gid)] = x_adv

    def _absorb_pair_format2(
        self,
        sub: Any,
        pairs: dict[tuple[int, int], int],
    ) -> None:
        """Project a Format-2 (class-based) PairPos subtable onto the
        GID-pair map.

        Materialises the Class1×Class2 matrix into individual GID pairs.
        That can blow up by a factor of (coverage_size × class2_glyphs)
        for very large fonts, but real-world GPOS class matrices are
        sparse — most entries have a zero ValueRecord which we skip
        before storing. For pathological fonts this is still cheaper
        than re-walking the matrix on every kerning query.
        """
        coverage = getattr(sub, "Coverage", None)
        class_def_1 = getattr(sub, "ClassDef1", None)
        class_def_2 = getattr(sub, "ClassDef2", None)
        class_1_records = getattr(sub, "Class1Record", None)
        if coverage is None or class_def_1 is None or class_def_2 is None:
            return
        if class_1_records is None:
            return

        cov_glyphs = getattr(coverage, "glyphs", None) or []
        # ClassDef2.classDefs is a {glyph_name: class_index} dict in
        # fontTools; class 0 is implicit ("not in the dict").
        cd1 = getattr(class_def_1, "classDefs", None) or {}
        cd2 = getattr(class_def_2, "classDefs", None) or {}

        # Reverse-index ClassDef2 so we can enumerate every glyph in a
        # given class without scanning the dict per cell. Class-0 glyphs
        # are everything in the font *not* listed in cd2 — but
        # PairPosFormat2 only kerns coverage-glyph + cd2-listed-glyph,
        # so we don't need to materialise class-0's universe.
        class2_to_glyphs: dict[int, list[str]] = {}
        for gname, cidx in cd2.items():
            class2_to_glyphs.setdefault(int(cidx), []).append(gname)

        for first_name in cov_glyphs:
            left_gid = self._glyph_name_to_gid.get(first_name)
            if left_gid is None:
                continue
            c1 = int(cd1.get(first_name, 0))
            if c1 < 0 or c1 >= len(class_1_records):
                continue
            class_2_records = getattr(class_1_records[c1], "Class2Record", None)
            if class_2_records is None:
                continue
            for c2_idx, c2_rec in enumerate(class_2_records):
                x_adv = self._extract_x_advance(getattr(c2_rec, "Value1", None))
                if x_adv == 0:
                    continue
                for second_name in class2_to_glyphs.get(c2_idx, ()):
                    right_gid = self._glyph_name_to_gid.get(second_name)
                    if right_gid is None:
                        continue
                    pairs[(left_gid, right_gid)] = x_adv

    @staticmethod
    def _extract_x_advance(value_record: Any) -> int:
        """Return the ``XAdvance`` field of a fontTools ``ValueRecord``,
        or ``0`` when the record is missing or doesn't carry one.

        The OT ``ValueFormat`` mask determines which fields a
        ``ValueRecord`` actually contains. fontTools sets only the
        formats that are present, so a missing attribute -> the field
        wasn't in the on-disk record -> 0. We mirror that contract.
        """
        if value_record is None:
            return 0
        return int(getattr(value_record, "XAdvance", 0) or 0)


__all__ = ["GlyphPositioningTable"]
