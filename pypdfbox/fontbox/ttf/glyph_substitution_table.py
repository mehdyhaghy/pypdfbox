from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .table.common.coverage_table_format1 import CoverageTableFormat1
from .table.common.coverage_table_format2 import CoverageTableFormat2
from .table.common.range_record import RangeRecord
from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream

_LOG = logging.getLogger(__name__)


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

    # OpenType GSUB lookup-type constants (mirrors the OT spec § GSUB Header).
    # Surface them so callers walking :meth:`get_lookup_types` /
    # :meth:`get_lookup` don't have to hard-code magic integers; matches the
    # ``LOOKUP_TYPE_*`` constant style of :class:`GlyphPositioningTable`.
    LOOKUP_TYPE_SINGLE: int = 1
    LOOKUP_TYPE_MULTIPLE: int = 2
    LOOKUP_TYPE_ALTERNATE: int = 3
    LOOKUP_TYPE_LIGATURE: int = 4
    LOOKUP_TYPE_CONTEXT: int = 5
    LOOKUP_TYPE_CHAINING_CONTEXT: int = 6
    LOOKUP_TYPE_EXTENSION_SUBSTITUTION: int = 7
    LOOKUP_TYPE_REVERSE_CHAINING_CONTEXTUAL_SINGLE: int = 8

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

    def get_lookup_count(self) -> int:
        """Number of lookups in this GSUB's LookupList (0 if absent).

        Mirrors the count upstream stores on
        ``LookupListTable.getLookupCount()`` — pypdfbox-only convenience
        accessor over the fontTools ``LookupList``.
        """
        if self._gsub_table is None:
            return 0
        ll = getattr(self._gsub_table, "LookupList", None)
        if ll is None:
            return 0
        return len(getattr(ll, "Lookup", None) or [])

    def get_lookup_types(self) -> list[int]:
        """Per-lookup ``LookupType`` integer in directory order.

        Useful for callers that want to know what substitution behaviour
        the font advertises (single / multiple / alternate / ligature /
        chaining / extension). Not present on upstream — mirrors the same
        introspection helper exposed by :class:`GlyphPositioningTable`.
        """
        if self._gsub_table is None:
            return []
        ll = getattr(self._gsub_table, "LookupList", None)
        if ll is None:
            return []
        return [int(lk.LookupType) for lk in (getattr(ll, "Lookup", None) or [])]

    # ------------------------------------------------------------------
    # OT-aliased structural accessors
    # ------------------------------------------------------------------
    #
    # Upstream PDFBox's ``GlyphSubstitutionTable`` keeps the on-disk
    # OpenType structures (``scriptList``, ``featureListTable``,
    # ``lookupListTable``) as private fields without exposing them —
    # callers only get the derived tag/inventory views and the projected
    # ``GsubData``. We surface the underlying fontTools structures so
    # consumers that need full access (substitution engine ports,
    # OpenType introspection tools) don't have to reach through
    # :meth:`get_raw_table`.

    def get_script_list(self) -> Any | None:
        """Underlying ``otTables.ScriptList`` (or ``None`` when absent).

        Each ``ScriptRecord`` carries a ``ScriptTag`` plus a ``Script``
        with a ``DefaultLangSys`` and a ``LangSysRecord`` list. Walk this
        when per-language feature selection matters.

        Not present on upstream; pypdfbox-only structural accessor that
        mirrors the GPOS-side accessor of the same name.
        """
        if self._gsub_table is None:
            return None
        return getattr(self._gsub_table, "ScriptList", None)

    def get_feature_list(self) -> Any | None:
        """Underlying ``otTables.FeatureList`` (or ``None`` when absent).

        Carries an indexed ``FeatureRecord`` list — each record's
        ``FeatureTag`` is the four-byte feature identifier (``liga``,
        ``dlig``, ``sups``, ...) and ``Feature.LookupListIndex`` is the
        list of lookup indices that implement that feature.

        Not present on upstream; pypdfbox-only structural accessor.
        """
        if self._gsub_table is None:
            return None
        return getattr(self._gsub_table, "FeatureList", None)

    def get_lookup_list(self) -> Any | None:
        """Underlying ``otTables.LookupList`` (or ``None`` when absent).

        Carries an indexed ``Lookup`` list — each entry has a
        ``LookupType`` (1..8 per OT § GSUB Header — see
        ``LOOKUP_TYPE_*`` constants on this class), a ``LookupFlag``
        bitfield, and an ordered ``SubTable`` list whose entries carry
        the actual substitution records.

        Not present on upstream; pypdfbox-only structural accessor.
        """
        if self._gsub_table is None:
            return None
        return getattr(self._gsub_table, "LookupList", None)

    def get_lookup(self, lookup_index: int) -> Any | None:
        """Return the ``otTables.Lookup`` at ``lookup_index`` (or
        ``None`` for out-of-range / missing-table queries).

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
        ``lookup_index``, or an empty list when out of range / absent.

        Subtable shape varies with ``LookupType``:

        * Type 1 — ``SingleSubst`` (Format 1 ``DeltaGlyphID``,
          Format 2 explicit substitute-glyph array)
        * Type 2 — ``MultipleSubst`` (one-to-many sequence)
        * Type 3 — ``AlternateSubst`` (alternate glyph set)
        * Type 4 — ``LigatureSubst`` (many-to-one ligature)
        * Type 5 — ``ContextSubst`` (rule-based, three sub-formats)
        * Type 6 — ``ChainContextSubst`` (chained, three sub-formats)
        * Type 7 — ``ExtensionSubst`` (transparently inlined by
          fontTools — surfaces as the wrapped type at this layer)
        * Type 8 — ``ReverseChainSingleSubst`` (right-to-left)

        Not present on upstream; pypdfbox-only structural accessor.
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

    def get_lang_sys_tables(self, script_tag: str) -> list[Any]:
        """Return every ``LangSys`` table for ``script_tag`` — both the
        ``DefaultLangSys`` (when present) and the per-language entries.

        Mirrors upstream's private ``getLangSysTables(String)``; surfaced
        here as a public snake_case helper so callers can enumerate the
        language systems available for a given script without reaching
        through :meth:`get_script_list`. Returns ``[]`` when the script
        tag isn't supported by this font.
        """
        if self._gsub_table is None:
            return []
        sl = getattr(self._gsub_table, "ScriptList", None)
        if sl is None:
            return []
        for sr in getattr(sl, "ScriptRecord", None) or []:
            if str(sr.ScriptTag) != script_tag:
                continue
            script = getattr(sr, "Script", None)
            if script is None:
                return []
            result: list[Any] = []
            # Upstream always lists per-language entries first when no
            # default is present; when a default exists it appends the
            # default after the per-language list. Match that ordering
            # (see ``getLangSysTables`` in GlyphSubstitutionTable.java).
            for lsr in getattr(script, "LangSysRecord", None) or []:
                ls = getattr(lsr, "LangSys", None)
                if ls is not None:
                    result.append(ls)
            default_ls = getattr(script, "DefaultLangSys", None)
            if default_ls is not None:
                result.append(default_ls)
            return result
        return []

    def get_feature_records(
        self,
        lang_sys_tables: list[Any] | tuple[Any, ...],
        enabled_features: list[str] | None = None,
    ) -> list[Any]:
        """Return ``FeatureRecord`` entries reachable from the supplied
        ``lang_sys_tables``, optionally filtered by ``enabled_features``.

        Mirrors upstream's private ``getFeatureRecords(Collection,
        List<String>)`` — surfaced as a public snake_case helper for
        callers that want the same selection without reimplementing the
        traversal. Behaviour:

        * Required features (``ReqFeatureIndex != 0xFFFF``) are always
          included — even when not in ``enabled_features``.
        * When ``enabled_features`` is ``None`` every reachable feature
          is returned.
        * ``vrt2`` supersedes ``vert`` — when both are present ``vert``
          is dropped (matches the OT spec note upstream encodes via
          ``containsFeature``/``removeFeature``).
        * Result ordering follows ``enabled_features`` index order when
          a filter list is supplied (matches upstream's
          ``Comparator.comparing(...indexOf)``).
        """
        if self._gsub_table is None or not lang_sys_tables:
            return []
        fl = getattr(self._gsub_table, "FeatureList", None)
        if fl is None:
            return []
        feature_records = getattr(fl, "FeatureRecord", None) or []
        if not feature_records:
            return []

        result: list[Any] = []
        for ls in lang_sys_tables:
            if ls is None:
                continue
            required = int(getattr(ls, "ReqFeatureIndex", 0xFFFF))
            if required != 0xFFFF and required < len(feature_records):
                result.append(feature_records[required])
            for fi in getattr(ls, "FeatureIndex", None) or []:
                fi_i = int(fi)
                if fi_i >= len(feature_records):
                    continue
                tag = str(feature_records[fi_i].FeatureTag).strip()
                if enabled_features is None or tag in enabled_features:
                    result.append(feature_records[fi_i])

        # 'vrt2' supersedes 'vert' — drop 'vert' when both are present.
        tags_in_result = [str(fr.FeatureTag).strip() for fr in result]
        if "vrt2" in tags_in_result:
            result = [
                fr for fr in result if str(fr.FeatureTag).strip() != "vert"
            ]

        if enabled_features is not None and len(result) > 1:
            result.sort(
                key=lambda fr: enabled_features.index(
                    str(fr.FeatureTag).strip()
                )
                if str(fr.FeatureTag).strip() in enabled_features
                else len(enabled_features),
            )

        return result

    def select_script_tag(self, script_tags: list[str] | tuple[str, ...]) -> str | None:
        """Public mirror of upstream's private ``selectScriptTag``.

        Picks the best supported OT script tag from a candidate list
        and updates the internal ``last_used_supported_script`` hint.
        Returns ``None`` only when the table has no script records and
        no candidates were supplied.
        """
        return self._select_script_tag(tuple(script_tags))

    def get_last_used_supported_script(self) -> str | None:
        """Return the most recent script tag :meth:`select_script_tag`
        successfully resolved against, or ``None`` if no resolution has
        happened yet.

        Mirrors upstream's private ``lastUsedSupportedScript`` field —
        useful for tooling that wants to inspect script-detection state
        between calls.
        """
        return self._last_used_supported_script

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

    # ------------------------------------------------------------------
    # Public mirrors of upstream private substitution helpers
    # ------------------------------------------------------------------

    def apply_feature(self, feature_record: Any, gid: int) -> int:
        """Apply every type-1 lookup attached to ``feature_record`` to
        ``gid`` and return the resulting (possibly-rewritten) GID.

        Mirrors upstream's private ``applyFeature(FeatureRecord, int)``
        — surfaced as a public snake_case helper so callers that have
        already isolated the feature record they want (e.g. via
        :meth:`get_feature_record`) can apply it directly without going
        through :meth:`get_substitution`'s script/feature selection.

        Skips lookups whose ``LookupType != 1`` (matches upstream's
        ``getLookupType() != 1`` skip).
        """
        if self._gsub_table is None or feature_record is None:
            return gid
        ll = getattr(self._gsub_table, "LookupList", None)
        if ll is None:
            return gid
        lookups = getattr(ll, "Lookup", None) or []
        feature = getattr(feature_record, "Feature", None)
        if feature is None:
            return gid
        result = gid
        for lookup_index in getattr(feature, "LookupListIndex", None) or []:
            li = int(lookup_index)
            if li < 0 or li >= len(lookups):
                continue
            lookup = lookups[li]
            if int(getattr(lookup, "LookupType", 0)) != self.LOOKUP_TYPE_SINGLE:
                continue
            result = self.do_lookup(lookup, result)
        return result

    def do_lookup(self, lookup_table: Any, gid: int) -> int:
        """Apply a single ``LookupTable`` to ``gid`` and return the
        possibly-rewritten GID.

        Mirrors upstream's private ``doLookup(LookupTable, int)`` —
        surfaced as a public snake_case helper for callers that want to
        evaluate one lookup in isolation. Walks the lookup's subtables
        in order and returns the first match's substitute GID; returns
        ``gid`` unchanged when no subtable covers the input.

        Only single-substitution (LookupType=1) lookups produce a
        rewritten GID — see the class docstring for why higher-order
        lookups can't fit the GID-in / GID-out signature.
        """
        if lookup_table is None:
            return gid
        if int(getattr(lookup_table, "LookupType", 0)) != self.LOOKUP_TYPE_SINGLE:
            return gid
        return self._apply_single_lookup_in_gid_space(lookup_table, gid)

    # ------------------------------------------------------------------
    # FeatureRecord list helpers (mirror upstream private utilities)
    # ------------------------------------------------------------------

    @staticmethod
    def contains_feature(feature_records: list[Any], feature_tag: str) -> bool:
        """Return ``True`` if any record in ``feature_records`` has
        ``FeatureTag == feature_tag``.

        Mirrors upstream's private
        ``containsFeature(List<FeatureRecord>, String)`` (Java line 793).
        Surfaced as a static helper so the same predicate can be used
        against fontTools ``FeatureRecord`` objects pulled out of
        :meth:`get_feature_list` without re-deriving it.
        """
        for fr in feature_records:
            tag = str(getattr(fr, "FeatureTag", "")).strip()
            if tag == feature_tag:
                return True
        return False

    @staticmethod
    def remove_feature(feature_records: list[Any], feature_tag: str) -> None:
        """Remove every entry from ``feature_records`` whose
        ``FeatureTag == feature_tag`` (in-place mutation).

        Mirrors upstream's private
        ``removeFeature(List<FeatureRecord>, String)`` (Java line 799).
        Used together with :meth:`contains_feature` to implement the
        ``vrt2`` supersedes ``vert`` rule when consumers build their own
        feature lists.
        """
        i = 0
        while i < len(feature_records):
            tag = str(getattr(feature_records[i], "FeatureTag", "")).strip()
            if tag == feature_tag:
                feature_records.pop(i)
            else:
                i += 1

    # ------------------------------------------------------------------
    # Upstream private SFNT-table readers (fontTools-delegated)
    # ------------------------------------------------------------------
    #
    # Upstream PDFBox implements GSUB by walking the SFNT byte stream
    # itself: ``readScriptList`` parses the ScriptList block at a given
    # offset, ``readCoverageTable`` decodes Coverage formats 1 and 2 from
    # the same stream, and so on. We delegate that decoding to
    # ``fontTools.ttLib`` (MIT) per the class docstring — the ``GSUB``
    # table arrives already parsed via ``populate_from_fonttools`` —
    # which means there is no ``TTFDataStream`` byte position to read
    # from when these methods are invoked.
    #
    # The methods below preserve the upstream public surface (so parity
    # tooling can detect them) but raise :class:`NotImplementedError` to
    # signal the deviation to any caller that strays into the byte-level
    # parsing path. Callers that want structured access should use the
    # snake_case structural accessors (:meth:`get_script_list`,
    # :meth:`get_feature_list`, :meth:`get_lookup_list`,
    # :meth:`get_lookup`, :meth:`get_lookup_subtables`,
    # :meth:`get_lang_sys_tables`, :meth:`get_feature_records`) which
    # return the equivalent fontTools structures.

    def read_script_list(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readScriptList(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L132-164).

        Returns an ordered ``{script_tag: script_table_dict}`` mapping
        where each value has the shape returned by
        :meth:`read_script_table`. Implements PDFBOX-6146 (skip duplicate
        script tags) and the implausible-offset short-circuit upstream
        applies.
        """
        data.seek(offset)
        script_count = data.read_unsigned_short()
        script_tags: list[str] = []
        script_offsets: list[int] = []
        result: dict[str, Any] = {}
        for i in range(script_count):
            script_tags.append(data.read_string(4))
            script_offsets.append(data.read_unsigned_short())
            if script_offsets[i] < data.get_current_position() - offset:
                _LOG.error(
                    "scriptOffsets[%d]: %d implausible: data.getCurrentPosition()"
                    " - offset = %d",
                    i,
                    script_offsets[i],
                    data.get_current_position() - offset,
                )
                return result
        for i in range(script_count):
            if script_tags[i] in result:
                continue
            result[script_tags[i]] = self.read_script_table(
                data, offset + script_offsets[i]
            )
        return result

    def read_script_table(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readScriptTable(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L166-208).

        Returns ``{"default_lang_sys": dict | None, "lang_sys_tables":
        {tag: dict}}`` where each LangSys entry has the shape returned
        by :meth:`read_lang_sys_table`.
        """
        data.seek(offset)
        default_lang_sys_offset = data.read_unsigned_short()
        lang_sys_count = data.read_unsigned_short()
        lang_sys_tags: list[str] = []
        lang_sys_offsets: list[int] = []
        empty: dict[str, Any] = {
            "default_lang_sys": None,
            "lang_sys_tables": {},
        }
        for i in range(lang_sys_count):
            lang_sys_tags.append(data.read_string(4))
            lang_sys_offsets.append(data.read_unsigned_short())
            if lang_sys_offsets[i] < data.get_current_position() - offset:
                _LOG.error(
                    "langSysOffsets[%d]: %d implausible: data.getCurrentPosition()"
                    " - offset = %d",
                    i,
                    lang_sys_offsets[i],
                    data.get_current_position() - offset,
                )
                return empty
            if i > 0 and lang_sys_tags[i] < lang_sys_tags[i - 1]:
                _LOG.error(
                    "LangSysRecords not alphabetically sorted by LangSys tag:"
                    " %s < %s",
                    lang_sys_tags[i],
                    lang_sys_tags[i - 1],
                )
                return empty

        default_lang_sys_table: dict[str, Any] | None = None
        if default_lang_sys_offset != 0:
            default_lang_sys_table = self.read_lang_sys_table(
                data, offset + default_lang_sys_offset
            )
        lang_sys_tables: dict[str, Any] = {}
        for i in range(lang_sys_count):
            lang_sys_tables[lang_sys_tags[i]] = self.read_lang_sys_table(
                data, offset + lang_sys_offsets[i]
            )
        return {
            "default_lang_sys": default_lang_sys_table,
            "lang_sys_tables": lang_sys_tables,
        }

    def read_lang_sys_table(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readLangSysTable(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L210-223).

        Returns ``{"lookup_order": int, "required_feature_index": int,
        "feature_index_count": int, "feature_indices": list[int]}``.
        """
        data.seek(offset)
        lookup_order = data.read_unsigned_short()
        required_feature_index = data.read_unsigned_short()
        feature_index_count = data.read_unsigned_short()
        feature_indices = [
            data.read_unsigned_short() for _ in range(feature_index_count)
        ]
        return {
            "lookup_order": lookup_order,
            "required_feature_index": required_feature_index,
            "feature_index_count": feature_index_count,
            "feature_indices": feature_indices,
        }

    def read_feature_list(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readFeatureList(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L225-262).

        Returns ``{"feature_count": int, "feature_records":
        [(tag, feature_table_dict), ...]}``.
        """
        data.seek(offset)
        feature_count = data.read_unsigned_short()
        feature_tags: list[str] = []
        feature_offsets: list[int] = []
        for i in range(feature_count):
            tag = data.read_string(4)
            feature_tags.append(tag)
            if i > 0 and feature_tags[i] < feature_tags[i - 1]:
                if feature_tags[i].isalnum() and feature_tags[i - 1].isalnum():
                    _LOG.debug(
                        "FeatureRecord array not alphabetically sorted by"
                        " FeatureTag: %s < %s",
                        feature_tags[i],
                        feature_tags[i - 1],
                    )
                else:
                    _LOG.warning(
                        "FeatureRecord array not alphabetically sorted by"
                        " FeatureTag: %s < %s",
                        feature_tags[i],
                        feature_tags[i - 1],
                    )
                    return {"feature_count": 0, "feature_records": []}
            feature_offsets.append(data.read_unsigned_short())
        feature_records: list[tuple[str, dict[str, Any]]] = []
        for i in range(feature_count):
            feature_table = self.read_feature_table(
                data, offset + feature_offsets[i]
            )
            feature_records.append((feature_tags[i], feature_table))
        return {
            "feature_count": feature_count,
            "feature_records": feature_records,
        }

    def read_feature_table(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readFeatureTable(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L264-275).

        Returns ``{"feature_params": int, "lookup_index_count": int,
        "lookup_list_indices": list[int]}``.
        """
        data.seek(offset)
        feature_params = data.read_unsigned_short()
        lookup_index_count = data.read_unsigned_short()
        lookup_list_indices = [
            data.read_unsigned_short() for _ in range(lookup_index_count)
        ]
        return {
            "feature_params": feature_params,
            "lookup_index_count": lookup_index_count,
            "lookup_list_indices": lookup_list_indices,
        }

    def read_lookup_list(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readLookupList(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L277-307).

        Returns ``{"lookup_count": int, "lookup_tables": list[dict]}``.
        Each entry has the shape produced by :meth:`read_lookup_table`.
        Mirrors upstream's PDFBOX-6146 dedup of duplicate lookup offsets.
        """
        data.seek(offset)
        lookup_count = data.read_unsigned_short()
        lookups: list[int] = []
        original_data_size = data.get_original_data_size()
        for i in range(lookup_count):
            lookups.append(data.read_unsigned_short())
            if lookups[i] == 0:
                _LOG.error(
                    "lookups[%d] is 0 at offset %d",
                    i,
                    data.get_current_position() - 2,
                )
            elif offset + lookups[i] > original_data_size:
                _LOG.error(
                    "%d > %d", offset + lookups[i], original_data_size
                )
        lookup_tables: list[dict[str, Any]] = []
        lookup_cache: dict[int, dict[str, Any]] = {}
        for i in range(lookup_count):
            cached = lookup_cache.get(lookups[i])
            if cached is None:
                cached = self.read_lookup_table(data, offset + lookups[i])
                lookup_cache[lookups[i]] = cached
            lookup_tables.append(cached)
        return {
            "lookup_count": lookup_count,
            "lookup_tables": lookup_tables,
        }

    def read_lookup_subtable(
        self,
        data: TTFDataStream,
        offset: int,
        lookup_type: int,
    ) -> Any:
        """Mirror upstream ``readLookupSubtable(TTFDataStream, long, int)``
        (GlyphSubstitutionTable.java L309-343).

        Dispatches to the type-specific subtable reader. Returns
        ``None`` for unsupported lookup types (5/6/8/etc.) — upstream
        emits a debug log and returns null.
        """
        if lookup_type == 1:
            return self.read_single_lookup_sub_table(data, offset)
        if lookup_type == 2:
            return self.read_multiple_substitution_subtable(data, offset)
        if lookup_type == 3:
            return self.read_alternate_substitution_subtable(data, offset)
        if lookup_type == 4:
            return self.read_ligature_substitution_subtable(data, offset)
        _LOG.debug(
            "Type %d GSUB lookup table is not supported and will be ignored",
            lookup_type,
        )
        return None

    def read_lookup_table(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readLookupTable(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L347-424).

        Returns ``{"lookup_type": int, "lookup_flag": int,
        "mark_filtering_set": int, "sub_tables": list}``. Mirrors the
        upstream LookupType 7 Extension Substitution unwrap which
        promotes the inner ``extensionLookupType`` into ``lookup_type``.
        """
        data.seek(offset)
        lookup_type = data.read_unsigned_short()
        lookup_flag = data.read_unsigned_short()
        sub_table_count = data.read_unsigned_short()
        sub_table_offsets: list[int] = []
        original_data_size = data.get_original_data_size()
        for i in range(sub_table_count):
            sub_offset = data.read_unsigned_short()
            sub_table_offsets.append(sub_offset)
            if sub_offset == 0:
                _LOG.error(
                    "subTableOffsets[%d] is 0 at offset %d",
                    i,
                    data.get_current_position() - 2,
                )
                return {
                    "lookup_type": lookup_type,
                    "lookup_flag": lookup_flag,
                    "mark_filtering_set": 0,
                    "sub_tables": [],
                }
            if offset + sub_offset > original_data_size:
                _LOG.error(
                    "%d > %d", offset + sub_offset, original_data_size
                )
                return {
                    "lookup_type": lookup_type,
                    "lookup_flag": lookup_flag,
                    "mark_filtering_set": 0,
                    "sub_tables": [],
                }
        mark_filtering_set = (
            data.read_unsigned_short() if (lookup_flag & 0x0010) != 0 else 0
        )

        sub_tables: list[Any] = [None] * sub_table_count
        if lookup_type in (1, 2, 3, 4):
            for i in range(sub_table_count):
                sub_tables[i] = self.read_lookup_subtable(
                    data, offset + sub_table_offsets[i], lookup_type
                )
        elif lookup_type == 7:
            for i in range(sub_table_count):
                data.seek(offset + sub_table_offsets[i])
                subst_format = data.read_unsigned_short()
                if subst_format != 1:
                    _LOG.error(
                        "The expected SubstFormat for ExtensionSubstFormat1"
                        " subtable is %d but should be 1 at offset %d",
                        subst_format,
                        offset + sub_table_offsets[i],
                    )
                    continue
                extension_lookup_type = data.read_unsigned_short()
                if lookup_type != 7 and lookup_type != extension_lookup_type:
                    _LOG.error(
                        "extensionLookupType changed from %d to %d at"
                        " offset %d",
                        lookup_type,
                        extension_lookup_type,
                        offset + sub_table_offsets[i] + 2,
                    )
                    continue
                lookup_type = extension_lookup_type
                extension_offset = data.read_unsigned_int()
                extension_address = (
                    offset + sub_table_offsets[i] + extension_offset
                )
                sub_tables[i] = self.read_lookup_subtable(
                    data, extension_address, extension_lookup_type
                )
        else:
            _LOG.debug(
                "Type %d GSUB lookup table is not supported and will be"
                " ignored",
                lookup_type,
            )
        return {
            "lookup_type": lookup_type,
            "lookup_flag": lookup_flag,
            "mark_filtering_set": mark_filtering_set,
            "sub_tables": sub_tables,
        }

    def read_single_lookup_sub_table(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any] | None:
        """Mirror upstream ``readSingleLookupSubTable(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L426-459).

        Format 1 returns ``{"subst_format": 1, "coverage_table":
        CoverageTable, "delta_glyph_id": int}``. Format 2 returns
        ``{"subst_format": 2, "coverage_table": CoverageTable,
        "substitute_glyph_ids": list[int]}``. Returns ``None`` for
        unknown formats.
        """
        data.seek(offset)
        subst_format = data.read_unsigned_short()
        if subst_format == 1:
            coverage_offset = data.read_unsigned_short()
            delta_glyph_id = data.read_signed_short()
            coverage_table = self.read_coverage_table(
                data, offset + coverage_offset
            )
            return {
                "subst_format": subst_format,
                "coverage_table": coverage_table,
                "delta_glyph_id": delta_glyph_id,
            }
        if subst_format == 2:
            coverage_offset = data.read_unsigned_short()
            glyph_count = data.read_unsigned_short()
            substitute_glyph_ids = [
                data.read_unsigned_short() for _ in range(glyph_count)
            ]
            coverage_table = self.read_coverage_table(
                data, offset + coverage_offset
            )
            return {
                "subst_format": subst_format,
                "coverage_table": coverage_table,
                "substitute_glyph_ids": substitute_glyph_ids,
            }
        _LOG.warning("Unknown substFormat: %d", subst_format)
        return None

    def read_multiple_substitution_subtable(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readMultipleSubstitutionSubtable(TTFDataStream,
        long)`` (GlyphSubstitutionTable.java L461-499).

        Returns ``{"subst_format": 1, "coverage_table": CoverageTable,
        "sequence_tables": [{"glyph_count": int,
        "substitute_glyph_ids": list[int]}, ...]}``.
        """
        data.seek(offset)
        subst_format = data.read_unsigned_short()
        if subst_format != 1:
            raise OSError(
                "The expected SubstFormat for LigatureSubstitutionTable is 1"
            )
        coverage = data.read_unsigned_short()
        sequence_count = data.read_unsigned_short()
        sequence_offsets = [
            data.read_unsigned_short() for _ in range(sequence_count)
        ]
        coverage_table = self.read_coverage_table(data, offset + coverage)
        if sequence_count != coverage_table.get_size():
            raise OSError(
                "According to the OpenTypeFont specifications, the coverage"
                " count should be equal to the no. of SequenceTables"
            )
        sequence_tables: list[dict[str, Any]] = []
        for i in range(sequence_count):
            data.seek(offset + sequence_offsets[i])
            glyph_count = data.read_unsigned_short()
            substitute_glyph_ids = data.read_unsigned_short_array(glyph_count)
            sequence_tables.append(
                {
                    "glyph_count": glyph_count,
                    "substitute_glyph_ids": substitute_glyph_ids,
                }
            )
        return {
            "subst_format": subst_format,
            "coverage_table": coverage_table,
            "sequence_tables": sequence_tables,
        }

    def read_alternate_substitution_subtable(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readAlternateSubstitutionSubtable(TTFDataStream,
        long)`` (GlyphSubstitutionTable.java L501-542).

        Returns ``{"subst_format": 1, "coverage_table": CoverageTable,
        "alternate_set_tables": [{"glyph_count": int,
        "alternate_glyph_ids": list[int]}, ...]}``.
        """
        data.seek(offset)
        subst_format = data.read_unsigned_short()
        if subst_format != 1:
            raise OSError(
                "The expected SubstFormat for AlternateSubstitutionTable is 1"
            )
        coverage = data.read_unsigned_short()
        alt_set_count = data.read_unsigned_short()
        alternate_offsets = [
            data.read_unsigned_short() for _ in range(alt_set_count)
        ]
        coverage_table = self.read_coverage_table(data, offset + coverage)
        if alt_set_count != coverage_table.get_size():
            raise OSError(
                "According to the OpenTypeFont specifications, the coverage"
                " count should be equal to the no. of AlternateSetTable"
            )
        alternate_set_tables: list[dict[str, Any]] = []
        for i in range(alt_set_count):
            data.seek(offset + alternate_offsets[i])
            glyph_count = data.read_unsigned_short()
            alternate_glyph_ids = data.read_unsigned_short_array(glyph_count)
            alternate_set_tables.append(
                {
                    "glyph_count": glyph_count,
                    "alternate_glyph_ids": alternate_glyph_ids,
                }
            )
        return {
            "subst_format": subst_format,
            "coverage_table": coverage_table,
            "alternate_set_tables": alternate_set_tables,
        }

    def read_ligature_substitution_subtable(
        self, data: TTFDataStream, offset: int
    ) -> dict[str, Any]:
        """Mirror upstream ``readLigatureSubstitutionSubtable(TTFDataStream,
        long)`` (GlyphSubstitutionTable.java L544-587).

        Returns ``{"subst_format": 1, "coverage_table": CoverageTable,
        "ligature_set_tables": list[dict]}``. Each ligature_set_table
        entry has the shape produced by :meth:`read_ligature_set_table`.
        """
        data.seek(offset)
        subst_format = data.read_unsigned_short()
        if subst_format != 1:
            raise OSError(
                "The expected SubstFormat for LigatureSubstitutionTable is 1"
            )
        coverage = data.read_unsigned_short()
        lig_set_count = data.read_unsigned_short()
        ligature_offsets = [
            data.read_unsigned_short() for _ in range(lig_set_count)
        ]
        coverage_table = self.read_coverage_table(data, offset + coverage)
        if lig_set_count != coverage_table.get_size():
            raise OSError(
                "According to the OpenTypeFont specifications, the coverage"
                " count should be equal to the no. of LigatureSetTables"
            )
        ligature_set_tables: list[dict[str, Any]] = []
        for i in range(lig_set_count):
            coverage_glyph_id = coverage_table.get_glyph_id(i)
            ligature_set_tables.append(
                self.read_ligature_set_table(
                    data, offset + ligature_offsets[i], coverage_glyph_id
                )
            )
        return {
            "subst_format": subst_format,
            "coverage_table": coverage_table,
            "ligature_set_tables": ligature_set_tables,
        }

    def read_ligature_set_table(
        self,
        data: TTFDataStream,
        ligature_set_table_location: int,
        coverage_glyph_id: int,
    ) -> dict[str, Any]:
        """Mirror upstream ``readLigatureSetTable(TTFDataStream, long, int)``
        (GlyphSubstitutionTable.java L589-612).

        Returns ``{"ligature_count": int, "ligature_tables":
        list[dict]}``; each ligature_table entry has the shape produced
        by :meth:`read_ligature_table`.
        """
        data.seek(ligature_set_table_location)
        ligature_count = data.read_unsigned_short()
        ligature_offsets = [
            data.read_unsigned_short() for _ in range(ligature_count)
        ]
        ligature_tables: list[dict[str, Any]] = []
        for ligature_offset in ligature_offsets:
            ligature_tables.append(
                self.read_ligature_table(
                    data,
                    ligature_set_table_location + ligature_offset,
                    coverage_glyph_id,
                )
            )
        return {
            "ligature_count": ligature_count,
            "ligature_tables": ligature_tables,
        }

    def read_ligature_table(
        self,
        data: TTFDataStream,
        ligature_table_location: int,
        coverage_glyph_id: int,
    ) -> dict[str, Any]:
        """Mirror upstream ``readLigatureTable(TTFDataStream, long, int)``
        (GlyphSubstitutionTable.java L614-642).

        Returns ``{"ligature_glyph": int, "component_count": int,
        "component_glyph_ids": list[int]}``. The first component is the
        coverage glyph id (per the OT spec — the coverage glyph isn't
        stored in the table itself, it's implied).
        """
        data.seek(ligature_table_location)
        ligature_glyph = data.read_unsigned_short()
        component_count = data.read_unsigned_short()
        if component_count > 100:
            raise OSError(
                f"componentCount in ligature table is {component_count},"
                " font likely corrupt"
            )
        component_glyph_ids = [0] * component_count
        if component_count > 0:
            component_glyph_ids[0] = coverage_glyph_id
        for i in range(1, component_count):
            component_glyph_ids[i] = data.read_unsigned_short()
        return {
            "ligature_glyph": ligature_glyph,
            "component_count": component_count,
            "component_glyph_ids": component_glyph_ids,
        }

    def read_coverage_table(
        self, data: TTFDataStream, offset: int
    ) -> CoverageTableFormat1 | CoverageTableFormat2:
        """Mirror upstream ``readCoverageTable(TTFDataStream, long)``
        (GlyphSubstitutionTable.java L644-677).

        Dispatches by coverage format byte to either
        :class:`CoverageTableFormat1` (glyph-array) or
        :class:`CoverageTableFormat2` (range-record). Raises
        :class:`OSError` for unknown formats.
        """
        data.seek(offset)
        coverage_format = data.read_unsigned_short()
        if coverage_format == 1:
            glyph_count = data.read_unsigned_short()
            glyph_array = [
                data.read_unsigned_short() for _ in range(glyph_count)
            ]
            return CoverageTableFormat1(coverage_format, glyph_array)
        if coverage_format == 2:
            range_count = data.read_unsigned_short()
            range_records = [
                self.read_range_record(data) for _ in range(range_count)
            ]
            return CoverageTableFormat2(coverage_format, range_records)
        raise OSError(f"Unknown coverage format: {coverage_format}")

    def read_range_record(self, data: TTFDataStream) -> RangeRecord:
        """Mirror upstream ``readRangeRecord(TTFDataStream)``
        (GlyphSubstitutionTable.java L956-962).

        Reads the (start_glyph_id, end_glyph_id, start_coverage_index)
        triple used by Coverage Format 2.
        """
        start_glyph_id = data.read_unsigned_short()
        end_glyph_id = data.read_unsigned_short()
        start_coverage_index = data.read_unsigned_short()
        return RangeRecord(
            start_glyph_id=start_glyph_id,
            end_glyph_id=end_glyph_id,
            start_coverage_index=start_coverage_index,
        )


__all__ = ["GlyphSubstitutionTable"]
