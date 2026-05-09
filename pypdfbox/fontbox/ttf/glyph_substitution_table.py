from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class GlyphSubstitutionTable(TTFTable):
    """``GSUB`` — Glyph Substitution table.

    Mirrors ``org.apache.fontbox.ttf.GlyphSubstitutionTable`` at the
    *public API surface* level. The actual on-disk parsing of the GSUB
    table (script list, feature list, lookup list, coverage tables, the
    five lookup-subtable variants, etc.) is delegated to
    ``fontTools.ttLib`` (MIT-licensed) — re-implementing a complete GSUB
    decoder in pure Python would duplicate ~700 lines of upstream Java
    that fontTools already covers, including type-1/2/3/4/7 lookups and
    coverage formats 1 and 2.

    The two callers pypdfbox actually exercises today are
    :meth:`get_substitution` (used by PDType0Font during text encoding)
    and :meth:`get_supported_script_tags` (used by tooling that reports
    OpenType capabilities). Everything else is accessor-shaped, so the
    upstream surface stays reportable without porting the
    ``GsubData`` / ``ScriptFeature`` / ``LookupSubTable`` object graph.

    Deviation from upstream — see ``CHANGES.md``:

    * No ``GsubData`` projection. ``get_gsub_data`` / ``get_gsub_data(scriptTag)``
      return ``None`` because we do not port the bespoke
      ``org.apache.fontbox.ttf.model.*`` value classes; consumers that
      need a structured view should walk the underlying fontTools
      ``GSUB.table`` instead (exposed via :meth:`get_raw_table`).
    * Lookup application supports lookup type 1 (single substitution)
      only — that matches upstream's ``applyFeature`` which also gates
      on ``lookupType == 1`` and warns/skips otherwise. Higher-order
      lookups (multiple, alternate, ligature, contextual) are not
      applied during ``get_substitution`` for the same reason upstream
      doesn't apply them: the GID-in / GID-out signature can't express
      them.
    """

    TAG: str = "GSUB"

    def __init__(self) -> None:
        super().__init__()
        self._tag = self.TAG

        # fontTools-side handles, populated by ``populate_from_fonttools``.
        self._tt_font: Any | None = None
        self._gsub_table: Any | None = None
        # Glyph-order projection so single-substitution lookups (which
        # fontTools exposes as a ``{glyph_name: glyph_name}`` dict) can
        # be evaluated in GID space without re-reading the parent
        # ``TTFont`` on every call.
        self._glyph_order: list[str] = []
        self._glyph_name_to_gid: dict[str, int] = {}

        # Cached views derived from the fontTools structures. These
        # mirror upstream's ``scriptList`` / ``featureListTable`` /
        # ``lookupListTable`` private fields at the *shape* level
        # (a Set[str] of script tags, a list of feature-tag strings),
        # not the full LangSys / FeatureRecord / LookupTable graph.
        self._script_tags: list[str] = []
        self._feature_tags: list[str] = []

        # Substitute / un-substitute caches. Upstream uses these to keep
        # the lookup deterministic across repeated calls with the same
        # GID — see comment on ``getSubstitution`` in upstream.
        self._lookup_cache: dict[int, int] = {}
        self._reverse_lookup: dict[int, int] = {}

        # Tracks the last script we successfully resolved against, used
        # when upstream callers pass an indeterminate script tag (DFLT,
        # Inherit). Mirrors upstream ``lastUsedSupportedScript``.
        self._last_used_supported_script: str | None = None

    # ------------------------------------------------------------------
    # Population path
    # ------------------------------------------------------------------

    def populate_from_fonttools(self, tt_font: Any) -> None:
        """Bind this wrapper to a fontTools ``TTFont`` whose ``GSUB``
        table will back all queries.

        Called by :meth:`TrueTypeFont.get_gsub`. Kept as a method (not a
        classmethod) to mirror the populate-then-cache pattern used by
        :class:`HeaderTable` / :class:`DigitalSignatureTable`.
        """
        self._tt_font = tt_font
        gsub_wrapper = tt_font["GSUB"]
        # fontTools exposes the parsed structure on ``.table`` (an
        # ``otTables.GSUB`` instance). Hold a reference so callers that
        # want the upstream-equivalent raw view can reach it via
        # ``get_raw_table``.
        self._gsub_table = getattr(gsub_wrapper, "table", None)
        self._glyph_order = list(tt_font.getGlyphOrder())
        self._glyph_name_to_gid = {n: i for i, n in enumerate(self._glyph_order)}

        # Populate the shallow tag lists from the fontTools structures.
        # We use ``LinkedHashMap``-style dedup-with-order semantics to
        # match upstream — PDFBOX-6146 keeps the *first* occurrence on
        # duplicate script tags.
        seen_scripts: dict[str, None] = {}
        seen_features: dict[str, None] = {}
        if self._gsub_table is not None:
            sl = getattr(self._gsub_table, "ScriptList", None)
            if sl is not None:
                for sr in getattr(sl, "ScriptRecord", None) or []:
                    tag = str(sr.ScriptTag)
                    if tag not in seen_scripts:
                        seen_scripts[tag] = None
            fl = getattr(self._gsub_table, "FeatureList", None)
            if fl is not None:
                for fr in getattr(fl, "FeatureRecord", None) or []:
                    tag = str(fr.FeatureTag).strip()
                    seen_features.setdefault(tag, None)
        self._script_tags = list(seen_scripts.keys())
        self._feature_tags = list(seen_features.keys())
        self.initialized = True

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:  # noqa: ARG002
        """Stand-in for the upstream ``read`` slot.

        We don't decode GSUB from the raw byte stream — fontTools owns
        that path. Real population happens in
        :meth:`populate_from_fonttools`. This override exists purely so
        the abstract slot from :class:`TTFTable` is satisfied for
        callers that hold a reference typed as the base class.
        """
        # Intentionally empty — see class docstring + DigitalSignatureTable
        # for the same pattern.

    # ------------------------------------------------------------------
    # Public API surface (snake_case mirror of upstream method names)
    # ------------------------------------------------------------------

    def get_supported_script_tags(self) -> set[str]:
        """Set of OpenType script tags this GSUB carries records for.

        Mirrors ``GlyphSubstitutionTable.getSupportedScriptTags``.
        Upstream returns an unmodifiable view; we return a fresh
        ``set`` each call (Python sets aren't shareably-immutable, and
        copying a tag list is cheap).
        """
        return set(self._script_tags)

    def get_supported_feature_tags(self) -> list[str]:
        """List of feature tags present in this GSUB's FeatureList.

        Order matches the on-disk FeatureRecord order (which fontTools
        preserves). Not present on upstream — added so callers can
        introspect available features (`liga`, `dlig`, `sups`, ...)
        without reaching into ``get_raw_table``.
        """
        return list(self._feature_tags)

    def get_raw_table(self) -> Any | None:
        """The underlying ``fontTools.ttLib.tables.otTables.GSUB``
        instance, or ``None`` if no GSUB was present.

        Escape hatch for callers that need the full GSUB graph that
        upstream exposes via :class:`GsubData` — fontTools' object graph
        carries the same information, just under different attribute
        names. Not present on upstream.
        """
        return self._gsub_table

    def get_lookup_indices_for_feature(self, feature_tag: str) -> list[int]:
        """Return every lookup-index referenced by ``feature_tag``.

        A GSUB FeatureList may contain the same tag more than once for
        different scripts or language systems. Walk every matching
        FeatureRecord, preserve first-seen lookup order, and deduplicate
        repeated indices so callers can inspect "all lookups implementing
        this feature" without reaching into ``get_raw_table``.

        Not present on upstream; pypdfbox-only structural lookup helper
        matching the GPOS wrapper's helper of the same name.
        """
        if self._gsub_table is None:
            return []
        feature_list = getattr(self._gsub_table, "FeatureList", None)
        if feature_list is None:
            return []
        out: list[int] = []
        seen: set[int] = set()
        for record in getattr(feature_list, "FeatureRecord", None) or []:
            tag = str(getattr(record, "FeatureTag", "")).strip()
            if tag != feature_tag:
                continue
            feature = getattr(record, "Feature", None)
            if feature is None:
                continue
            for lookup_index in getattr(feature, "LookupListIndex", None) or []:
                lookup_index_i = int(lookup_index)
                if lookup_index_i in seen:
                    continue
                seen.add(lookup_index_i)
                out.append(lookup_index_i)
        return out

    def get_substitution(
        self,
        gid: int,
        script_tags: list[str] | tuple[str, ...] | None = None,
        enabled_features: list[str] | None = None,
    ) -> int:
        """Apply enabled GSUB single-substitution lookups to ``gid``.

        Mirrors ``GlyphSubstitutionTable.getSubstitution(int gid,
        String[] scriptTags, List<String> enabledFeatures)``. Returns
        the substituted GID, or ``gid`` itself if no enabled feature
        rewrites it.

        Behavior matches upstream's ``applyFeature``:

        * ``gid == -1`` short-circuits to ``-1`` (sentinel for "no
          glyph").
        * Substitutions are deterministic across repeated calls — the
          first lookup result for a given input GID is cached, so an
          indeterminate-script context can't yield two different
          substitutions for the same input.
        * Only **lookup type 1** (single substitution) is applied;
          types 2-4 (multiple / alternate / ligature) and 5-8 (context,
          chained, extension, reverse-chaining) are skipped because
          they don't fit the GID-in / GID-out signature. Upstream does
          the same — see the ``getLookupType() != 1`` skip in
          ``applyFeature``.
        * When ``enabled_features`` is ``None`` every feature on the
          resolved script is applied; otherwise only features whose
          tag appears in the list are applied, in the order specified.

        ``script_tags`` is a list of candidate OT script tags (typically
        the output of ``OpenTypeScript.getScriptTags`` upstream); the
        first one supported by the font is used. ``None`` or an empty
        list means "use whatever the GSUB's first script is".
        """
        if gid == -1:
            return -1
        if self._gsub_table is None:
            return gid

        cached = self._lookup_cache.get(gid)
        if cached is not None:
            return cached

        script_tag = self._select_script_tag(tuple(script_tags) if script_tags else ())
        feature_indices = self._collect_feature_indices(script_tag, enabled_features)
        if not feature_indices:
            self._lookup_cache[gid] = gid
            self._reverse_lookup[gid] = gid
            return gid

        feature_records = self._gsub_table.FeatureList.FeatureRecord
        lookups = self._gsub_table.LookupList.Lookup
        sgid = gid
        for fi in feature_indices:
            if fi < 0 or fi >= len(feature_records):
                continue
            for lookup_index in feature_records[fi].Feature.LookupListIndex:
                if lookup_index < 0 or lookup_index >= len(lookups):
                    continue
                lookup = lookups[lookup_index]
                if int(lookup.LookupType) != 1:
                    # Match upstream: only single-substitution lookups
                    # plug into the GID -> GID surface.
                    continue
                sgid = self._apply_single_lookup_in_gid_space(lookup, sgid)

        self._lookup_cache[gid] = sgid
        self._reverse_lookup[sgid] = gid
        return sgid

    def get_unsubstitution(self, sgid: int) -> int:
        """Reverse a previously-applied substitution.

        Mirrors ``GlyphSubstitutionTable.getUnsubstitution``. Only GIDs
        that have actually been seen as a substitution output of this
        instance can be reversed — bare GIDs are returned unchanged
        (upstream emits a warning and returns the input as-is).
        """
        original = self._reverse_lookup.get(sgid)
        if original is None:
            return sgid
        return original

    # ``GsubData`` is upstream's bespoke value class; we don't port it.
    # Returning ``None`` keeps the method available for callers that
    # already null-check the result (which upstream documents may
    # happen) without forcing them through an ``AttributeError``.
    def get_gsub_data(self, script_tag: str | None = None) -> None:  # noqa: ARG002
        """Always returns ``None`` — see deviation note in the class docstring."""
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _select_script_tag(self, tags: tuple[str, ...]) -> str | None:
        """Pick a script tag from the candidate list. Mirrors
        ``GlyphSubstitutionTable.selectScriptTag`` minus the
        ``OpenTypeScript`` constants we haven't ported yet — for
        ``DFLT`` / empty input we just fall back to the first available
        script, which is what upstream eventually does too via its
        ``lastUsedSupportedScript`` cache.
        """
        if not tags:
            if self._last_used_supported_script is not None:
                return self._last_used_supported_script
            return self._script_tags[0] if self._script_tags else None

        if len(tags) == 1:
            tag = tags[0]
            # Roughly approximate upstream's ``Inherited`` /
            # ``TAG_DEFAULT`` handling without depending on the as-yet-
            # unported OpenTypeScript constants.
            if tag in ("DFLT", "dflt") and tag not in self._script_tags:
                if self._last_used_supported_script is not None:
                    return self._last_used_supported_script
                if self._script_tags:
                    self._last_used_supported_script = self._script_tags[0]
                    return self._last_used_supported_script
                return tag

        for tag in tags:
            if tag in self._script_tags:
                self._last_used_supported_script = tag
                return tag
        return tags[0]

    def _collect_feature_indices(
        self,
        script_tag: str | None,
        enabled_features: list[str] | None,
    ) -> list[int]:
        """Return feature indices to apply, filtered by ``enabled_features``.

        Mirrors upstream's ``getLangSysTables`` + ``getFeatureRecords``
        flow: gather every (default + per-language) feature index for
        the chosen script, drop entries whose tag isn't in
        ``enabled_features``, and preserve the order ``enabled_features``
        specifies (so a caller can request `liga` to fire before `sups`,
        for example).
        """
        if script_tag is None or self._gsub_table is None:
            return []
        script_record = None
        for sr in self._gsub_table.ScriptList.ScriptRecord:
            if sr.ScriptTag == script_tag:
                script_record = sr
                break
        if script_record is None:
            return []

        feature_indices: list[int] = []
        seen: set[int] = set()

        def absorb(lang_sys: Any) -> None:
            if lang_sys is None:
                return
            required = int(getattr(lang_sys, "ReqFeatureIndex", 0xFFFF))
            if required != 0xFFFF and required not in seen:
                feature_indices.append(required)
                seen.add(required)
            for idx in getattr(lang_sys, "FeatureIndex", None) or []:
                idx_i = int(idx)
                if idx_i not in seen:
                    feature_indices.append(idx_i)
                    seen.add(idx_i)

        absorb(getattr(script_record.Script, "DefaultLangSys", None))
        for lsr in getattr(script_record.Script, "LangSysRecord", None) or []:
            absorb(lsr.LangSys)

        if enabled_features is None:
            return feature_indices

        feature_records = self._gsub_table.FeatureList.FeatureRecord

        def tag_for(fi: int) -> str | None:
            if fi < 0 or fi >= len(feature_records):
                return None
            return str(feature_records[fi].FeatureTag).strip()

        # Filter to enabled set, then re-sort to preserve the caller's
        # ordering preference (matches upstream's ``Comparator.comparing``
        # against ``enabledFeatures.indexOf``).
        filtered = [fi for fi in feature_indices if tag_for(fi) in enabled_features]
        # 'vrt2' supersedes 'vert' — drop 'vert' if both present.
        # Mirrors upstream containsFeature/removeFeature pair.
        if any(tag_for(fi) == "vrt2" for fi in filtered):
            filtered = [fi for fi in filtered if tag_for(fi) != "vert"]
        filtered.sort(key=lambda fi: enabled_features.index(tag_for(fi) or ""))
        return filtered

    def _apply_single_lookup_in_gid_space(self, lookup: Any, gid: int) -> int:
        """Apply a single-substitution (LookupType=1) ``lookup`` to ``gid``.

        Walks the lookup's subtables in order; returns the first
        rewritten GID (or ``gid`` if no subtable covers it), matching
        upstream's ``doLookup`` semantics. fontTools exposes the
        substitution map keyed by *glyph name*, so we round-trip GID
        through the cached glyph-order projection populated in
        :meth:`populate_from_fonttools`.
        """
        if gid < 0 or gid >= len(self._glyph_order):
            return gid
        src_name = self._glyph_order[gid]
        for subtable in lookup.SubTable or []:
            mapping = getattr(subtable, "mapping", None)
            if not mapping:
                continue
            # ``Format 1`` subtables expose ``Coverage`` + ``DeltaGlyphID``
            # rather than a pre-decompiled mapping; fontTools' subset
            # decompiler has already populated ``.mapping`` for both
            # formats by the time we read it here, so the format-1 vs
            # format-2 distinction is invisible at this layer.
            dst_name = mapping.get(src_name)
            if dst_name is None:
                continue
            dst_gid = self._glyph_name_to_gid.get(dst_name)
            if dst_gid is not None:
                return dst_gid
        return gid


__all__ = ["GlyphSubstitutionTable"]
