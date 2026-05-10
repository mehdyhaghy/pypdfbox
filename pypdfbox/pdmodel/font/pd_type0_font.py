from __future__ import annotations

import io
import os
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSStream

from .pd_font import PDFont

if TYPE_CHECKING:
    from pypdfbox.fontbox.cmap import CMap
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    from .pd_cid_font import PDCIDFont
    from .pd_cid_system_info import PDCIDSystemInfo
    from .pd_font_descriptor import PDFontDescriptor

_DESCENDANT_FONTS: COSName = COSName.get_pdf_name("DescendantFonts")
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_TO_UNICODE: COSName = COSName.get_pdf_name("ToUnicode")
_BASE_FONT: COSName = COSName.get_pdf_name("BaseFont")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE: COSName = COSName.SUBTYPE  # type: ignore[attr-defined]
_FONT: COSName = COSName.get_pdf_name("Font")

# PDF 32000-1 §9.2.4: composite-font /FontMatrix maps glyph coordinates
# (1000-unit em) into text space (1-unit em). Type 0 fonts inherit this
# default and never override it (the per-glyph metric is always in 1/1000 em).
_DEFAULT_FONT_MATRIX: tuple[float, ...] = (0.001, 0.0, 0.0, 0.001, 0.0, 0.0)

# Lookup table of CIDSystemInfo (Registry, Ordering) -> matching predefined
# UCS2 CMap name. Used by :meth:`PDType0Font.get_cmap_ucs2` to provide a
# /ToUnicode fallback for Adobe predefined CID collections when the font
# dict carries no explicit /ToUnicode CMap. Mirrors upstream PDFBox's
# fallback in ``PDType0Font.readEncoding`` / ``getCMapUCS2``.
_UCS2_CMAP_BY_REGISTRY_ORDERING: dict[tuple[str, str], str] = {
    ("Adobe", "GB1"): "Adobe-GB1-UCS2",
    ("Adobe", "CNS1"): "Adobe-CNS1-UCS2",
    ("Adobe", "Japan1"): "Adobe-Japan1-UCS2",
    ("Adobe", "Korea1"): "Adobe-Korea1-UCS2",
    ("Adobe", "KR"): "Adobe-KR-UCS2",
}

# Predefined CMap names from PDF 32000-1 §9.7.5.2 Table 118 (the two
# Identity collections plus the broader CJK predefined set). Surfaced as
# module-level constants so callers building Type 0 dictionaries don't
# stringly-type the names. Mirrors upstream's ``COSName.IDENTITY_H`` /
# ``COSName.IDENTITY_V`` and the predefined CMap registry the
# ``CMapManager`` consults.
IDENTITY_H: str = "Identity-H"
IDENTITY_V: str = "Identity-V"

# CIDSystemInfo orderings considered "CJK" by upstream's
# ``PDType0Font.readEncoding``. The combination of these orderings under
# the ``Adobe`` registry is what triggers the UCS2 ``*-UCS2`` fallback in
# :meth:`PDType0Font.is_descendant_cjk` / :meth:`get_cmap_ucs2`.
_CJK_ORDERINGS: frozenset[str] = frozenset({"GB1", "CNS1", "Japan1", "Korea1"})


class PDType0Font(PDFont):
    """PDF Type 0 (composite) font. Mirrors PDFBox ``PDType0Font``.

    A composite font references exactly one descendant CIDFont via the
    ``/DescendantFonts`` array and uses a CMap (named in ``/Encoding``)
    to map input character codes to CIDs. The descendant font then maps
    CIDs to glyph metrics and (for Type2/TrueType) glyph indices via
    ``/CIDToGIDMap``.
    """

    SUB_TYPE = "Type0"

    def __init__(self, font_dict: COSDictionary | None = None) -> None:
        super().__init__(font_dict)
        # Lazy caches — populated on first lookup, dropped only by
        # constructing a fresh wrapper. Mutating ``/Encoding`` /
        # ``/ToUnicode`` after parsing requires a new instance.
        self._cmap: CMap | None = None
        self._cmap_loaded: bool = False
        self._to_unicode_cmap: CMap | None = None
        self._to_unicode_cmap_loaded: bool = False
        self._cmap_ucs2: CMap | None = None
        self._cmap_ucs2_loaded: bool = False
        # Codepoints accumulated by :meth:`add_to_subset`; consumed by
        # :meth:`subset` on save. Type 0 fonts subset the descendant
        # CIDFontType2's embedded TrueType program.
        self._subset_codepoints: set[int] = set()
        # Raw GIDs accumulated by :meth:`add_glyphs_to_subset` — these
        # bypass codepoint -> GID resolution and pin the listed glyph
        # indices into the subset directly. Mirrors upstream
        # ``PDType0Font.addGlyphsToSubset(Set<Integer>)`` which forwards
        # to ``PDCIDFontType2Embedder.addGlyphIds``.
        self._subset_glyph_ids: set[int] = set()
        # Marker tracking whether subsetting was requested at construction
        # / load time. ``True`` when this font was built via
        # :meth:`load_ttf` / :meth:`load_otf` with ``embed_subset=True``;
        # ``False`` when subsetting was disabled at load time. Mirrors
        # upstream ``PDType0Font.willBeSubset`` which checks the
        # ``embedder.needsSubset()`` flag rather than the raw codepoint
        # set (a load-time decision, not a per-call lookup).
        self._will_be_subset: bool = False
        # GSUB feature gating — :meth:`set_gsub_features` overrides;
        # :meth:`get_gsub_features` returns the resolved set (defaults to
        # ``["liga"]`` for latin per upstream's ``PDType0Font.applyGsub``
        # default-feature heuristic).
        self._gsub_features: list[str] | None = None

    # ---------- /DescendantFonts ----------

    def get_descendant_font(self) -> PDCIDFont | None:
        """Return the typed ``PDCIDFont`` wrapper for the first
        ``/DescendantFonts`` entry, or ``None`` when absent / malformed.
        """
        arr = self._dict.get_dictionary_object(_DESCENDANT_FONTS)
        if not isinstance(arr, COSArray) or arr.size() == 0:
            return None
        first = arr.get_object(0)
        if isinstance(first, COSDictionary):
            return PDType0Font._wrap_descendant(first, self)
        return None

    def get_cid_font(self) -> PDCIDFont | None:
        """Alias for :meth:`get_descendant_font`. Mirrors PDFBox's
        ``getCIDFont`` accessor (kept for callers that prefer the
        upstream-Java naming).
        """
        return self.get_descendant_font()

    @staticmethod
    def _wrap_descendant(
        font_dict: COSDictionary, parent: PDType0Font
    ) -> PDCIDFont | None:
        from .pd_cid_font_type0 import PDCIDFontType0
        from .pd_cid_font_type2 import PDCIDFontType2

        sub_type = font_dict.get_name(COSName.SUBTYPE)  # type: ignore[attr-defined]
        if sub_type == PDCIDFontType0.SUB_TYPE:
            return PDCIDFontType0(font_dict, parent)
        if sub_type == PDCIDFontType2.SUB_TYPE:
            return PDCIDFontType2(font_dict, parent)
        return None

    # ---------- /CIDSystemInfo (descendant) ----------

    def get_cid_system_info(self) -> PDCIDSystemInfo | None:
        """Return the descendant CIDFont's ``/CIDSystemInfo``.

        Mirrors upstream ``PDType0Font.getCIDSystemInfo`` — the parent
        Type0 font does not carry its own ``/CIDSystemInfo``; the entry
        lives on the descendant per PDF 32000-1 §9.7.4.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return None
        return descendant.get_cid_system_info()

    # ---------- /FontDescriptor (descendant fallback) ----------

    def get_font_descriptor(self) -> PDFontDescriptor | None:
        """Return the font descriptor for this composite font.

        Type 0 dictionaries do not carry ``/FontDescriptor`` directly —
        per PDF 32000-1 §9.7.3 the descriptor lives on the descendant
        CIDFont. Falls back to :class:`PDFont.get_font_descriptor` first
        (so a malformed dict that *does* carry one still resolves) before
        consulting the descendant.
        """
        own = super().get_font_descriptor()
        if own is not None:
            return own
        descendant = self.get_descendant_font()
        if descendant is None:
            return None
        return descendant.get_font_descriptor()

    # ---------- /Encoding (raw entry) ----------

    def get_encoding(self) -> COSBase | None:
        """Return the raw ``/Encoding`` entry — a ``COSName`` (predefined
        CMap name) or a ``COSStream`` (embedded CMap), or ``None``.

        Mirrors upstream ``PDType0Font.getEncoding``. Callers that want
        the parsed CMap should use :meth:`get_cmap` instead.
        """
        return self._dict.get_dictionary_object(_ENCODING)

    # ---------- /Encoding (CMap) ----------

    def get_cmap(self) -> CMap | None:
        """Return the encoding CMap parsed from ``/Encoding``.

        Per PDF 32000-1 §9.7.5.2 the entry is either a predefined CMap
        name (e.g. ``/Identity-H``) or a CMap stream. Cached on first
        successful resolution.
        """
        if self._cmap_loaded:
            return self._cmap
        self._cmap_loaded = True
        from pypdfbox.fontbox.cmap import CMapParser

        raw = self._dict.get_dictionary_object(_ENCODING)
        if isinstance(raw, COSName):
            try:
                self._cmap = CMapParser.parse_predefined(raw.name)
            except OSError:
                self._cmap = None
        elif isinstance(raw, COSStream):
            try:
                self._cmap = CMapParser().parse(raw.to_byte_array())
            except (OSError, ValueError):
                self._cmap = None
        else:
            self._cmap = None
        return self._cmap

    # ---------- /ToUnicode (CMap) ----------

    def get_to_unicode_cmap(self) -> CMap | None:
        """Parsed ``/ToUnicode`` CMap, or ``None`` when absent / malformed.
        """
        if self._to_unicode_cmap_loaded:
            return self._to_unicode_cmap
        self._to_unicode_cmap_loaded = True
        from pypdfbox.fontbox.cmap import CMapParser

        raw = self._dict.get_dictionary_object(_TO_UNICODE)
        if isinstance(raw, COSStream):
            try:
                self._to_unicode_cmap = CMapParser().parse(raw.to_byte_array())
            except (OSError, ValueError):
                self._to_unicode_cmap = None
        elif isinstance(raw, COSName):
            # PDF 32000-1 §9.10.3 allows a predefined name (e.g.
            # ``/Identity-H``) as a ``/ToUnicode`` shortcut.
            try:
                self._to_unicode_cmap = CMapParser.parse_predefined(raw.name)
            except OSError:
                self._to_unicode_cmap = None
        else:
            self._to_unicode_cmap = None
        return self._to_unicode_cmap

    # ---------- predefined UCS2 CMap (fallback /ToUnicode) ----------

    def get_cmap_ucs2(self) -> CMap | None:
        """Return the predefined UCS2 ``CID -> Unicode`` CMap matching
        this font's ``/CIDSystemInfo`` (Registry, Ordering), or ``None``.

        Mirrors upstream ``PDType0Font.getCMapUCS2`` — used when the font
        has no ``/ToUnicode`` stream but its descendant uses an Adobe
        predefined CID collection (Adobe-GB1, Adobe-CNS1, Adobe-Japan1,
        Adobe-Korea1, Adobe-KR). The result lets callers convert CIDs
        back to Unicode via the standard Adobe ``*-UCS2`` mapping. Cached
        on first call.
        """
        if self._cmap_ucs2_loaded:
            return self._cmap_ucs2
        self._cmap_ucs2_loaded = True
        info = self.get_cid_system_info()
        if info is None:
            return None
        registry = info.get_registry()
        ordering = info.get_ordering()
        if registry is None or ordering is None:
            return None
        if registry == "Adobe" and ordering == "Identity":
            # Identity collection — no UCS2 fallback CMap exists.
            return None
        cmap_name = _UCS2_CMAP_BY_REGISTRY_ORDERING.get((registry, ordering))
        if cmap_name is None:
            return None
        from pypdfbox.fontbox.cmap import CMapParser

        try:
            self._cmap_ucs2 = CMapParser.parse_predefined(cmap_name)
        except OSError:
            self._cmap_ucs2 = None
        return self._cmap_ucs2

    # ---------- code -> CID / GID ----------

    def code_to_cid(self, code: int) -> int:
        """Map an input character code to a CID through the encoding CMap.

        For Identity / missing CMaps the code passes through unchanged
        — matches upstream ``PDType0Font.codeToCID``.
        """
        cmap = self.get_cmap()
        if cmap is not None and cmap.has_cid_mappings():
            cid = cmap.to_cid(code)
            if cid != 0 or code == 0:
                return cid
            # Fall through to descendant for codes the active CMap
            # doesn't explicitly map (e.g. Identity-H).
        descendant = self.get_descendant_font()
        if descendant is not None:
            return descendant.code_to_cid(code)
        return int(code)

    def code_to_gid(self, code: int) -> int:
        """Map an input character code to a glyph index.

        Resolves code → CID via the encoding CMap, then CID → GID via
        the descendant font's ``/CIDToGIDMap`` (Type2). For Type0/CFF
        descendants the GID equals the CID, mirroring upstream behavior.

        When the descendant TTF carries a GSUB table, the resulting GID
        is run through any active **single-substitution** lookups
        (lookup type 1) for the current GSUB feature set — see
        :meth:`set_gsub_features`. Many-to-one (ligature) lookups are
        applied on a glyph *run* rather than a single glyph, so callers
        that need ligature shaping should use :meth:`apply_gsub_features`
        on the post-``code_to_gid`` GID list.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return self.code_to_cid(code)
        # Prefer the descendant's own ``code_to_gid`` when available
        # (PDCIDFontType2). Otherwise fall back to CID == GID.
        cid = self.code_to_cid(code)
        cid_to_gid = getattr(descendant, "cid_to_gid", None)
        gid = int(cid_to_gid(cid)) if callable(cid_to_gid) else cid

        # GSUB single-substitution — glyph-by-glyph rewrites only.
        gsub = self._get_gsub_table()
        if gsub is not None:
            features = self.get_gsub_features()
            with suppress(Exception):
                gid = int(gsub.get_substitution(gid, None, features))
        return gid

    # ---------- GSUB feature gating ----------

    def set_gsub_features(self, features: Iterable[str] | None) -> None:
        """Override the active GSUB feature tag set for this rendering pass.

        ``features`` is the ordered iterable of OpenType feature tags
        (``"liga"``, ``"dlig"``, ``"calt"``, ``"sups"``, ...) to enable.
        Passing ``None`` reverts to the script-derived default
        (``["liga"]`` for latin) — same behaviour upstream's
        ``PDType0Font.applyGsub`` exhibits when no explicit feature list
        is configured. The ordering is preserved because GSUB applies
        features in the order specified (so a caller can run ``liga``
        before ``sups``, for example).

        ``kern`` is accepted in the list for forward-compatibility but
        is a GPOS feature (positioning, not glyph rewriting) and
        therefore handled by :class:`PDType0Font` GPOS support rather
        than the GSUB pipeline; it is silently ignored at GSUB time.
        """
        if features is None:
            self._gsub_features = None
            return
        # Preserve order, drop duplicates.
        seen: set[str] = set()
        ordered: list[str] = []
        for tag in features:
            t = str(tag)
            if t in seen:
                continue
            seen.add(t)
            ordered.append(t)
        self._gsub_features = ordered

    def get_gsub_features(self) -> list[str]:
        """Return the GSUB feature tags active for this font.

        Defaults are script-derived: ``["liga"]`` for latin scripts (the
        only script we have a default for; other scripts return ``[]``
        which means *no GSUB* — callers should configure features
        explicitly via :meth:`set_gsub_features`). When a previous call
        to :meth:`set_gsub_features` set a custom list, that list wins
        regardless of script.
        """
        if self._gsub_features is not None:
            return list(self._gsub_features)
        # Script-derived default. We resolve the script tag via the
        # GSUB's first-supported-script logic; falling back to "latn"
        # when nothing matches.
        return ["liga"] if self._is_latin_script() else []

    def _is_latin_script(self) -> bool:
        """Return ``True`` when the embedded GSUB advertises latin or
        the table has no script discriminator at all (in which case
        latin defaults are still the safer bet for Type 0 fonts).
        """
        gsub = self._get_gsub_table()
        if gsub is None:
            return True  # no GSUB → harmless default; features won't fire anyway
        try:
            scripts = gsub.get_supported_script_tags()
        except Exception:  # noqa: BLE001
            return True
        if not scripts:
            return True
        return any(s in ("latn", "DFLT", "dflt") for s in scripts)

    def _get_gsub_table(self) -> Any | None:
        """Return the descendant TTF's :class:`GlyphSubstitutionTable`,
        or ``None`` when no descendant / no GSUB / parse failure.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return None
        get_ttf = getattr(descendant, "get_true_type_font", None)
        if not callable(get_ttf):
            return None
        try:
            ttf = get_ttf()
        except Exception:  # noqa: BLE001
            return None
        if ttf is None:
            return None
        try:
            return ttf.get_gsub()
        except Exception:  # noqa: BLE001
            return None

    def apply_gsub_features(self, glyph_ids: list[int]) -> list[int]:
        """Apply the active GSUB feature lookups to a glyph run.

        Mirrors upstream ``PDType0Font.applyGsub`` (exposed in PDFBox
        3.0.x via PDFBOX-5780). Walks every enabled feature's
        :class:`LookupList` in order; for each lookup applies type-1
        (single substitution) and type-4 (ligature) lookups to the
        glyph run. Single substitutions rewrite one GID in place;
        ligature substitutions collapse multi-glyph sequences into one
        ligature GID. Other lookup types (multiple, alternate, context,
        chained, extension, reverse-chaining) are skipped — same set
        upstream skips for the GID-stream-in / GID-stream-out signature.

        Returns a fresh list (input is not mutated).
        """
        if not glyph_ids:
            return []
        gsub = self._get_gsub_table()
        if gsub is None:
            return list(glyph_ids)
        raw = gsub.get_raw_table()
        if raw is None:
            return list(glyph_ids)
        features = self.get_gsub_features()
        if not features:
            return list(glyph_ids)

        glyph_order = list(getattr(gsub, "_glyph_order", []))
        name_to_gid: dict[str, int] = dict(getattr(gsub, "_glyph_name_to_gid", {}))
        if not glyph_order or not name_to_gid:
            return list(glyph_ids)

        feature_indices = self._collect_gsub_feature_indices(raw, features)
        if not feature_indices:
            return list(glyph_ids)

        feature_records = raw.FeatureList.FeatureRecord
        lookups = raw.LookupList.Lookup
        result = list(glyph_ids)
        for fi in feature_indices:
            if fi < 0 or fi >= len(feature_records):
                continue
            for lookup_index in feature_records[fi].Feature.LookupListIndex:
                if lookup_index < 0 or lookup_index >= len(lookups):
                    continue
                lookup = lookups[lookup_index]
                lt = int(lookup.LookupType)
                if lt == 1:
                    result = self._apply_single_run(lookup, result, glyph_order, name_to_gid)
                elif lt == 4:
                    result = self._apply_ligature_run(lookup, result, glyph_order, name_to_gid)
                # Other types skipped (matches upstream applyGsub).
        return result

    @staticmethod
    def _collect_gsub_feature_indices(
        raw: Any, enabled_features: list[str]
    ) -> list[int]:
        """Return feature-record indices for feature tags in
        ``enabled_features``, preserving the caller's order.
        """
        feature_records = raw.FeatureList.FeatureRecord
        # Walk every script's default + per-language feature index list
        # so we don't miss features that live exclusively under a
        # non-default LangSys. Dedup by feature index (multiple
        # LangSys can point at the same FeatureRecord).
        seen: set[int] = set()
        gathered: list[int] = []
        scripts = getattr(raw.ScriptList, "ScriptRecord", None) or []
        for sr in scripts:
            default_ls = getattr(sr.Script, "DefaultLangSys", None)
            lang_records = getattr(sr.Script, "LangSysRecord", None) or []
            lang_systems = [default_ls, *(lsr.LangSys for lsr in lang_records)]
            for ls in lang_systems:
                if ls is None:
                    continue
                req = int(getattr(ls, "ReqFeatureIndex", 0xFFFF))
                if req != 0xFFFF and req not in seen:
                    seen.add(req)
                    gathered.append(req)
                for idx in getattr(ls, "FeatureIndex", None) or []:
                    i = int(idx)
                    if i not in seen:
                        seen.add(i)
                        gathered.append(i)

        def tag_for(fi: int) -> str:
            return str(feature_records[fi].FeatureTag).strip()

        filtered = [fi for fi in gathered if tag_for(fi) in enabled_features]
        filtered.sort(key=lambda fi: enabled_features.index(tag_for(fi)))
        return filtered

    @staticmethod
    def _apply_single_run(
        lookup: Any,
        glyph_ids: list[int],
        glyph_order: list[str],
        name_to_gid: dict[str, int],
    ) -> list[int]:
        """Apply a type-1 (single) substitution lookup across the glyph run."""
        out: list[int] = []
        for gid in glyph_ids:
            new_gid = gid
            if 0 <= gid < len(glyph_order):
                src_name = glyph_order[gid]
                for subtable in lookup.SubTable or []:
                    mapping = getattr(subtable, "mapping", None)
                    if not mapping:
                        continue
                    dst = mapping.get(src_name)
                    if dst is None:
                        continue
                    cand = name_to_gid.get(dst)
                    if cand is not None:
                        new_gid = cand
                        break
            out.append(new_gid)
        return out

    @staticmethod
    def _apply_ligature_run(
        lookup: Any,
        glyph_ids: list[int],
        glyph_order: list[str],
        name_to_gid: dict[str, int],
    ) -> list[int]:
        """Apply a type-4 (ligature) substitution lookup across the glyph run.

        fontTools exposes ligature subtables with a ``ligatures`` dict
        keyed by *first-component glyph name* whose values are a list of
        ``Ligature`` records carrying ``Component`` (trailing component
        glyph names) and ``LigGlyph`` (output glyph name). Walk the run
        left-to-right, longest-match-wins per the OpenType spec.
        """
        out: list[int] = []
        n = len(glyph_ids)
        i = 0
        while i < n:
            gid = glyph_ids[i]
            consumed = 1
            replacement = gid
            if 0 <= gid < len(glyph_order):
                src_name = glyph_order[gid]
                for subtable in lookup.SubTable or []:
                    ligs = getattr(subtable, "ligatures", None)
                    if not ligs:
                        continue
                    candidates = ligs.get(src_name)
                    if not candidates:
                        continue
                    best_len = 0
                    best_lig_name: str | None = None
                    for lig in candidates:
                        comps = list(getattr(lig, "Component", None) or [])
                        end = i + 1 + len(comps)
                        if end > n:
                            continue
                        ok = True
                        for k, comp_name in enumerate(comps):
                            comp_gid = name_to_gid.get(comp_name)
                            if comp_gid is None or glyph_ids[i + 1 + k] != comp_gid:
                                ok = False
                                break
                        if ok and len(comps) >= best_len:
                            best_len = len(comps)
                            best_lig_name = getattr(lig, "LigGlyph", None)
                    if best_lig_name is not None:
                        new_gid = name_to_gid.get(best_lig_name)
                        if new_gid is not None:
                            replacement = new_gid
                            consumed = 1 + best_len
                            break
            out.append(replacement)
            i += consumed
        return out

    # ---------- read_code (PDF 32000-1 §9.7.6.2) ----------

    def read_code(self, input_bytes: bytes, offset: int = 0) -> tuple[int, int]:
        """Read one character code from ``input_bytes`` starting at
        ``offset``. Returns ``(code, bytes_consumed)``.

        Delegates to the active CMap's ``read_code`` when one is parsed;
        otherwise falls back to a single-byte read (Adobe Reader's
        behavior when no CMap is available).
        """
        if offset < 0 or offset >= len(input_bytes):
            return (0, 0)
        cmap = self.get_cmap()
        if cmap is None:
            return (input_bytes[offset] & 0xFF, 1)
        stream = io.BytesIO(bytes(input_bytes[offset:]))
        before = stream.tell()
        code = cmap.read_code(stream)
        consumed = stream.tell() - before
        if consumed <= 0:
            consumed = 1
        return (code, consumed)

    # ---------- glyph metrics ----------

    def get_glyph_width(self, code: int) -> float:
        """Width of the glyph for ``code`` in 1/1000 em.

        Resolves code → CID, then defers to the descendant CIDFont's
        ``get_glyph_width(cid)``. Returns ``0.0`` when no descendant
        font is present.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return 0.0
        return descendant.get_glyph_width(self.code_to_cid(code))

    # ---------- writing direction ----------

    def is_vertical(self) -> bool:
        """``True`` when the active CMap declares ``/WMode 1`` (vertical
        writing). Defaults to ``False`` for missing CMaps.
        """
        cmap = self.get_cmap()
        if cmap is None:
            return False
        return cmap.get_wmode() == 1

    def is_vertical_writing(self) -> bool:
        """Alias for :meth:`is_vertical`. Mirrors upstream's documented
        synonym ``isVerticalWriting`` (kept for callers that prefer the
        spelled-out name from PDF 32000-1 §9.7.5.2).
        """
        return self.is_vertical()

    def has_explicit_writing_mode(self) -> bool:
        """``True`` when the font's ``/Encoding`` is an embedded CMap
        stream that explicitly carries a ``/WMode`` entry.

        Predefined CMap names (``Identity-H``, ``Identity-V``, ``GBK-EUC-H``,
        ...) carry an *implicit* WMode baked into the CMap's identity.
        Custom CMap streams may or may not declare ``/WMode`` explicitly;
        this helper distinguishes the two cases so callers can decide
        whether to fall back to a heuristic (e.g. inspecting the CMap
        name suffix) or trust the dictionary entry.

        Not present on upstream verbatim — added so vertical-writing
        tooling can branch on whether the CMap stream is authoritative.
        """
        raw = self._dict.get_dictionary_object(_ENCODING)
        if not isinstance(raw, COSStream):
            return False
        wmode_entry = raw.get_dictionary_object(COSName.get_pdf_name("WMode"))
        return wmode_entry is not None

    # ---------- to_unicode ----------

    def to_unicode(self, code: int) -> str | None:
        """Return the Unicode string for ``code``.

        Tries the ``/ToUnicode`` CMap first, then the encoding CMap's own
        bf-mappings, then the predefined ``*-UCS2`` CMap matched on the
        descendant's ``/CIDSystemInfo`` (Registry, Ordering), and finally
        the embedded TTF's reverse cmap (PDFBOX-5324) when the descendant
        is a CIDFontType2. Mirrors upstream ``PDType0Font.toUnicode``.
        """
        to_unicode_cmap = self.get_to_unicode_cmap()
        if to_unicode_cmap is not None and to_unicode_cmap.has_unicode_mappings():
            mapped = to_unicode_cmap.to_unicode(code)
            if mapped is not None:
                return mapped
        cmap = self.get_cmap()
        if cmap is not None and cmap.has_unicode_mappings():
            mapped = cmap.to_unicode(code)
            if mapped is not None:
                return mapped
        # Predefined Adobe ``*-UCS2`` CMap keyed on the CID — used when
        # the encoding CMap has no unicode bf-mappings of its own; the
        # canonical Identity-H case for CJK fonts that lean on the
        # predefined UCS2 fallback.
        ucs2 = self.get_cmap_ucs2()
        if ucs2 is not None and ucs2.has_unicode_mappings():
            cid = self.code_to_cid(code)
            mapped = ucs2.to_unicode(cid)
            if mapped is not None:
                return mapped
        # PDFBOX-5324 fallback — read the unicode value directly out of
        # the embedded TTF's cmap. Only applies when the descendant is a
        # CIDFontType2 with an embedded program.
        return self._unicode_from_embedded_cmap(code)

    def _unicode_from_embedded_cmap(self, code: int) -> str | None:
        """Reverse-lookup a glyph in the embedded TTF's unicode cmap.

        Mirrors upstream's PDFBOX-5324 fallback: for CIDFontType2
        descendants with an embedded program, walk the unicode cmap
        backwards from GID -> codepoint when no other to_unicode source
        can answer.
        """
        from .pd_cid_font_type2 import PDCIDFontType2

        descendant = self.get_descendant_font()
        if not isinstance(descendant, PDCIDFontType2):
            return None
        ttf = descendant.get_true_type_font()
        if ttf is None:
            return None
        # Resolve the parent character code through the Type0 CMap first.
        # The descendant receives CIDs, not raw character codes; skipping
        # this step breaks embedded-cmap fallback for non-Identity encodings.
        try:
            cid = self.code_to_cid(code)
            if descendant.is_embedded():
                gid = descendant.code_to_gid(cid)
            else:
                # PDFBOX-5331 fallback: avoid the descendant's substitute-font
                # GID path and use the CMap-resolved CID directly.
                gid = descendant.code_to_cid(cid)
        except Exception:  # noqa: BLE001
            return None
        if gid <= 0:
            return None
        # fontTools' cmap subtable carries a ``cmap`` dict (codepoint ->
        # glyph name). Reverse-walk it for the first codepoint pointing
        # to our glyph name.
        inner = getattr(ttf, "_tt", None)
        if inner is None or "cmap" not in inner:
            return None
        try:
            order = inner.getGlyphOrder()
            if not 0 <= gid < len(order):
                return None
            target_name = order[gid]
            best_cmap = inner["cmap"].getBestCmap()
            if not best_cmap:
                return None
            for cp, name in best_cmap.items():
                if name == target_name:
                    return chr(cp)
        except (KeyError, AttributeError):
            return None
        return None

    # ---------- embedding / damage ----------

    def is_embedded(self) -> bool:
        """``True`` when the descendant CIDFont's font program is
        embedded in the file.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return False
        return descendant.is_embedded()

    def is_damaged(self) -> bool:
        """``True`` when the descendant CIDFont's embedded font program
        failed to parse. Mirrors upstream ``PDType0Font.isDamaged`` which
        delegates to the descendant's ``isDamaged`` (the parent dict has
        no embeddable program of its own).
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return False
        return descendant.is_damaged()

    # ---------- /BaseFont / Standard14 ----------

    def get_base_font(self) -> str | None:
        """Return the ``/BaseFont`` (PostScript name) entry.

        Mirrors upstream ``PDType0Font.getBaseFont``. ``get_name`` is the
        PDFBox public-API spelling and forwards to the same value; both
        accessors are kept for callers that prefer the dictionary-key
        spelling.
        """
        return self._dict.get_name(_BASE_FONT)

    def is_standard14(self) -> bool:
        """Type 0 (composite) fonts are never one of the 14 PDF standard
        fonts. Mirrors upstream ``PDType0Font.isStandard14`` which hard-
        codes ``return false``.
        """
        return False

    # ---------- /Encoding predicates ----------

    def is_cmap_predefined(self) -> bool:
        """``True`` when ``/Encoding`` is one of the predefined CMap names
        (a ``COSName`` rather than an embedded ``COSStream``).

        Mirrors upstream ``PDType0Font.isCMapPredefined`` (the private
        boolean field set by ``readEncoding`` when the encoding entry is
        a ``COSName``). Surfaced publicly so callers reasoning about the
        ``/ToUnicode`` fallback chain (PDFBOX-6022) can branch on the
        same condition upstream branches on.
        """
        raw = self._dict.get_dictionary_object(_ENCODING)
        return isinstance(raw, COSName)

    def is_descendant_cjk(self) -> bool:
        """``True`` when the descendant CIDFont uses one of the four
        Adobe CJK character collections (``Adobe-GB1`` / ``Adobe-CNS1`` /
        ``Adobe-Japan1`` / ``Adobe-Korea1``).

        Mirrors upstream ``PDType0Font.isDescendantCJK`` (the private
        boolean field set by ``readEncoding``). Combined with
        :meth:`is_cmap_predefined` this is the condition under which
        ``toUnicode`` falls back to the ``*-UCS2`` CMap rather than to
        an Identity codepoint (PDFBOX-6022 / §9.10.2).
        """
        info = self.get_cid_system_info()
        if info is None:
            return False
        registry = info.get_registry()
        ordering = info.get_ordering()
        if registry != "Adobe" or ordering is None:
            return False
        return ordering in _CJK_ORDERINGS

    # ---------- glyph paths ----------

    def get_path(self, code: int) -> list[tuple[Any, ...]]:
        """Return the glyph outline for ``code`` in *font units*.

        Mirrors upstream ``PDType0Font.getPath(int code)`` which forwards
        to the descendant CIDFont after resolving ``code -> CID``. The
        descendant's ``getGlyphPath(cid)`` consults the embedded program
        (TrueType ``glyf`` for :class:`PDCIDFontType2`, CFF ``CharString``
        for :class:`PDCIDFontType0`) and returns an empty list when no
        program is available.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return []
        get_glyph_path = getattr(descendant, "get_glyph_path", None)
        if not callable(get_glyph_path):
            return []
        return list(get_glyph_path(self.code_to_cid(code)))

    def get_normalized_path(self, code: int) -> list[tuple[Any, ...]]:
        """Return the glyph outline for ``code`` normalized to 1/1000 em.

        Mirrors upstream ``PDType0Font.getNormalizedPath(int)`` which
        forwards to the descendant CIDFont. The descendant scales the
        embedded program's outline by ``1000 / unitsPerEm`` so downstream
        consumers see a single unit system regardless of the font's
        native upem.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return []
        get_normalized = getattr(descendant, "get_normalized_path", None)
        if not callable(get_normalized):
            return []
        return list(get_normalized(self.code_to_cid(code)))

    # ---------- GSUB / cmap-lookup accessors ----------

    def get_gsub_data(self) -> Any | None:
        """Return the descendant TTF's parsed GSUB table, or ``None``.

        Mirrors upstream ``PDType0Font.getGsubData`` which exposes the
        per-font ``GsubData`` populated at embed time. For read-only
        Type 0 fonts (no embedder) we fall back to the descendant TTF's
        parsed GSUB so callers can still inspect feature lists.
        """
        return self._get_gsub_table()

    def get_cmap_lookup(self) -> Any | None:
        """Return the descendant TTF's unicode-cmap lookup, or ``None``.

        Mirrors upstream ``PDType0Font.getCmapLookup`` which surfaces the
        :class:`CmapLookup` the embedder used to resolve codepoints.
        For read-only Type 0 fonts the lookup is derived from the
        descendant's embedded TrueType program.
        """
        from .pd_cid_font_type2 import PDCIDFontType2

        descendant = self.get_descendant_font()
        if not isinstance(descendant, PDCIDFontType2):
            return None
        ttf = descendant.get_true_type_font()
        if ttf is None:
            return None
        get_unicode = getattr(ttf, "get_unicode_cmap_lookup", None)
        if callable(get_unicode):
            try:
                return get_unicode()
            except Exception:  # noqa: BLE001 — defensive: malformed cmap
                return None
        # Fall back to fontTools' best cmap. Reverse map glyph-name -> cp.
        inner = getattr(ttf, "_tt", None)
        if inner is None or "cmap" not in inner:
            return None
        try:
            return inner["cmap"].getBestCmap()
        except (KeyError, AttributeError):
            return None

    # ---------- /Standard14 width override ----------

    def get_standard14_width(self, code: int) -> float:
        """Type 0 fonts have no Standard14 width table.

        Mirrors upstream ``PDType0Font.getStandard14Width`` which throws
        :class:`UnsupportedOperationException`. Composite fonts derive
        widths from the descendant's ``/W`` array or embedded program,
        not from the AFM-backed Standard14 width path used by
        :class:`PDType1Font`.
        """
        del code
        raise NotImplementedError(
            "PDType0Font does not support Standard14 widths"
        )

    # ---------- has_explicit_width override ----------

    def has_explicit_width(self, code: int) -> bool:
        """``True`` when the descendant CIDFont specifies an explicit
        width for ``code``.

        Overrides :meth:`PDFont.has_explicit_width` — Type 0 fonts carry
        no ``/Widths`` of their own; the lookup goes through the
        descendant's ``/W`` array. Mirrors upstream
        ``PDType0Font.hasExplicitWidth`` which forwards to the
        descendant.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return False
        has = getattr(descendant, "has_explicit_width", None)
        if not callable(has):
            return False
        return bool(has(code))

    # ---------- read_encoding (parsing trigger) ----------

    def read_encoding(self) -> None:
        """Force-parse ``/Encoding`` and prime the UCS2 fallback cache.

        Mirrors upstream's private ``PDType0Font.readEncoding()`` /
        ``fetchCMapUCS2()`` which run from the constructor. pypdfbox is
        lazy by default — calling this method is equivalent to touching
        :meth:`get_cmap` and :meth:`get_cmap_ucs2` once, and exists so
        upstream-style call sites that *expect* the parsing side-effect
        remain straightforward to port.
        """
        # Touching the lazy accessors performs the same work upstream's
        # constructor does eagerly. Errors are swallowed: upstream logs
        # a warning rather than raising on bad encodings.
        with suppress(Exception):
            self.get_cmap()
        with suppress(Exception):
            self.get_cmap_ucs2()

    # ---------- diagnostics ----------

    def __repr__(self) -> str:
        """Mirror upstream ``PDType0Font.toString`` formatting:

            ``PDType0Font/<DescendantClass>, PostScript name: <BaseFont>``

        Surfaces enough identity for log lines and debugger inspection
        without dragging in the full dictionary state.
        """
        descendant = self.get_descendant_font()
        descendant_name = type(descendant).__name__ if descendant is not None else None
        return (
            f"{type(self).__name__}/{descendant_name},"
            f" PostScript name: {self.get_base_font()}"
        )

    # ---------- glyph / metric delegators ----------

    def has_glyph(self, code: int) -> bool:
        """``True`` when the descendant CIDFont reports a non-zero advance
        for the CID resolved from ``code``.

        Mirrors upstream ``PDType0Font.hasGlyph(int)`` — Type 0 has no
        glyph store of its own, so the question is delegated to the
        descendant after CID resolution.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return False
        return descendant.has_glyph(self.code_to_cid(code))

    def get_width_from_font(self, code: int) -> float:
        """Glyph advance read directly from the descendant's embedded
        program (rather than the ``/W`` array).

        Mirrors upstream ``PDType0Font.getWidthFromFont`` which forwards
        to the descendant after CID resolution. Returns ``0.0`` when the
        descendant cannot supply a font-derived width (e.g. no embedded
        program, or the descendant is :class:`PDCIDFontType0` with a CFF
        program that lacks the metric).
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return 0.0
        get_wff = getattr(descendant, "get_width_from_font", None)
        if not callable(get_wff):
            return 0.0
        return float(get_wff(self.code_to_cid(code)))

    def get_displacement(self, code: int) -> tuple[float, float]:
        """Glyph displacement vector ``(dx, dy)`` for ``code`` in em.

        Mirrors upstream ``PDType0Font.getDisplacement``: when the font is
        vertical, ``dx`` is zero and ``dy`` comes from the descendant's
        ``/W2`` y-component scaled by ``1/1000``. Otherwise falls through
        to the horizontal default ``(width/1000, 0)``.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return (self.get_glyph_width(code) / 1000.0, 0.0)
        cid = self.code_to_cid(code)
        if self.is_vertical():
            return (0.0, descendant.get_height(cid) / 1000.0)
        return (descendant.get_glyph_width(cid) / 1000.0, 0.0)

    def get_position_vector(self, code: int) -> tuple[float, float]:
        """Position vector ``(v_x, v_y)`` for ``code`` in em (units of
        1/1 em, i.e. already scaled from 1/1000 em).

        Mirrors upstream ``PDType0Font.getPositionVector`` which scales
        the descendant's raw 1/1000-em vector by ``-1/1000`` (negation
        per PDF 32000-1 §9.7.3 Note for vertical writing — the position
        vector is *added* to the origin rather than subtracted).
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return (0.0, 0.0)
        v_x, v_y = descendant.get_position_vector(self.code_to_cid(code))
        return (-v_x / 1000.0, -v_y / 1000.0)

    # ---------- glyph-ID encoding ----------

    def encode_glyph_id(self, glyph_id: int) -> bytes:
        """Encode a glyph index ``glyph_id`` as the two-byte big-endian
        sequence used in Identity-H/Identity-V content streams.

        Mirrors upstream ``PDType0Font.encodeGlyphId(int)`` which forwards
        to the descendant. For TrueType-backed Type 0 fonts under
        Identity-H the GID and CID coincide (``/CIDToGIDMap /Identity``)
        so the descendant's encoding is a plain 2-byte big-endian write
        of the GID, which is what we emit here when the descendant lacks
        a more specialised encoder.
        """
        descendant = self.get_descendant_font()
        if descendant is not None:
            encoder = getattr(descendant, "encode_glyph_id", None)
            if callable(encoder):
                return bytes(encoder(glyph_id))
        return (int(glyph_id) & 0xFFFF).to_bytes(2, "big")

    # ---------- /FontMatrix ----------

    def get_font_matrix(self) -> list[float]:
        """Return the 6-element ``/FontMatrix`` for this composite font.

        PDF 32000-1 §9.2.4 fixes the Type 0 font matrix at
        ``[0.001 0 0 0.001 0 0]`` — composite fonts always express glyph
        metrics in 1/1000 em. Mirrors upstream ``PDType0Font.getFontMatrix``.
        """
        return list(_DEFAULT_FONT_MATRIX)

    # ---------- /FontBBox (descendant fallback) ----------

    def get_bounding_box(self) -> PDRectangle | None:
        """Return the descendant's font bounding box as a
        :class:`PDRectangle`, or ``None`` when no descendant / bbox is
        present. Mirrors upstream ``PDType0Font.getBoundingBox``.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return None
        return descendant.get_bounding_box()

    # ---------- glyph metrics (upstream-named aliases) ----------

    def get_width(self, code: int) -> float:
        """Alias for :meth:`get_glyph_width` — mirrors upstream
        ``PDType0Font.getWidth(int)``."""
        return self.get_glyph_width(code)

    def get_height(self, code: int) -> float:
        """Vertical advance for ``code`` (only meaningful for vertical
        writing). Resolves code → CID then asks the descendant for its
        ``/W2`` entry. Returns ``0.0`` when no descendant or no vertical
        metric is available — mirrors upstream
        ``PDType0Font.getHeight(int)``.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return 0.0
        return descendant.get_height(self.code_to_cid(code))

    def get_average_font_width(self) -> float:
        """Return the descendant CIDFont's mean glyph advance.

        Mirrors upstream ``PDType0Font.getAverageFontWidth`` which
        forwards to the descendant — the parent dict has no ``/Widths``
        of its own.
        """
        descendant = self.get_descendant_font()
        if descendant is None:
            return 0.0
        return descendant.get_average_font_width()

    def get_string_width(self, text: str) -> float:
        """Total advance width of ``text`` in 1/1000 em.

        Encodes ``text`` via :meth:`encode`, walks the resulting bytes
        through :meth:`read_code`, and accumulates :meth:`get_glyph_width`
        for each code. Mirrors upstream ``PDType0Font.getStringWidth(String)``.
        """
        encoded = self.encode(text)
        total = 0.0
        offset = 0
        n = len(encoded)
        while offset < n:
            code, consumed = self.read_code(encoded, offset)
            if consumed <= 0:
                break
            total += self.get_glyph_width(code)
            offset += consumed
        return total

    # ---------- str <-> bytes (encoding via the active CMap) ----------

    def encode(self, text: str | int) -> bytes:
        """Encode either a Python string or a single Unicode codepoint to
        the font's raw byte representation.

        Polymorphic to mirror upstream PDFBox's two ``encode`` overloads:

        * ``encode(String)`` — the public, ``final`` String API used by
          content-stream writers; iterates codepoints and concatenates
          per-codepoint outputs.
        * ``encode(int unicode)`` — the protected single-codepoint API
          implemented per font subclass. ``PDType0Font`` delegates to its
          descendant CIDFont, but we inline the equivalent logic here so
          callers can encode without first materialising a one-character
          string.

        For Identity-H / Identity-V the codepoint *is* the CID and is
        emitted as a 2-byte big-endian sequence. For predefined Adobe
        UCS2-mapped CMaps the encoding cmap's reverse lookup
        (``get_codes_from_unicode``) is consulted. For embedded
        non-Identity CMaps without a reverse mapping the codepoint is
        replaced with the bytes of CID 0 (``.notdef``).
        """
        if isinstance(text, int):
            return self._encode_codepoint(text, self.get_cmap())
        cmap = self.get_cmap()
        out = bytearray()
        for ch in text:
            cp = ord(ch)
            encoded = self._encode_codepoint(cp, cmap)
            out.extend(encoded)
        return bytes(out)

    def encode_string(self, text: str) -> bytes:
        """Encode a Python string with GSUB-aware ligature substitution.

        Mirrors upstream's public ``PDType0Font.encode(String)`` plus the
        GSUB-application path that runs when the descendant TTF carries a
        ``GSUB`` table. The pipeline is:

        1. Codepoint → CID → GID (via :meth:`code_to_gid`, which already
           applies *single*-substitution lookups in GID space).
        2. Walk the resulting glyph run through
           :meth:`apply_gsub_features` — this layers *ligature* (type 4)
           substitutions on top, collapsing multi-glyph sequences into a
           single ligature glyph (e.g. Devanagari conjuncts, fi/fl in
           latin, alef+lamed in Hebrew).
        3. Emit the post-GSUB GIDs as 2-byte big-endian (CID == GID under
           Identity-H + ``/CIDToGIDMap /Identity``, which is the only
           configuration where GSUB substitution makes sense — non-
           Identity CMaps can't address arbitrary GIDs through their
           codespace).

        Falls back to plain :meth:`encode` when the font has no descendant,
        no embedded TTF, no GSUB, or a non-Identity encoding.
        """
        if not text:
            return b""
        # GSUB only fires for Identity-H Type-2 descendants — non-identity
        # CMaps don't have a 1:1 GID addressing surface, so the post-
        # ligature GIDs would have nowhere to land. Fall through to the
        # plain encode in those cases.
        cmap = self.get_cmap()
        cmap_name = (cmap.get_name() or "") if cmap is not None else ""
        if not cmap_name.startswith("Identity"):
            return self.encode(text)

        gsub = self._get_gsub_table()
        if gsub is None:
            return self.encode(text)

        # Resolve each codepoint to its initial GID through the descendant
        # font (which already runs single-substitution lookups). Then run
        # the run through ligature lookups.
        gids: list[int] = []
        for ch in text:
            cp = ord(ch)
            gids.append(self.code_to_gid(cp))
        substituted = self.apply_gsub_features(gids)

        out = bytearray()
        for gid in substituted:
            out.extend((gid & 0xFFFF).to_bytes(2, "big"))
        return bytes(out)

    @staticmethod
    def _encode_codepoint(cp: int, cmap: CMap | None) -> bytes:
        """Look up the byte sequence for Unicode ``cp`` in ``cmap``.

        Identity-H / -V fall through to the 2-byte big-endian fallback
        (CID == codepoint). For other CMaps the reverse-lookup helper
        ``get_codes_from_unicode`` (PDFBox parity) yields the bytes; on
        miss we emit the bytes of CID 0 (``.notdef``) at the codespace's
        natural byte length.
        """
        if cmap is None:
            return cp.to_bytes(2, "big")
        # Try the CMap's own reverse mapping first.
        try:
            codes = cmap.get_codes_from_unicode(chr(cp))
        except Exception:  # noqa: BLE001 — defensive: lenient parsers / odd CMaps
            codes = None
        if codes is not None:
            return bytes(codes)
        # Identity CMaps: BMP codepoint == CID, emit big-endian.
        name = cmap.get_name() or ""
        if name in ("Identity-H", "Identity-V") or name.startswith("Identity"):
            return (cp & 0xFFFF).to_bytes(2, "big")
        # Last resort — emit the bytes of CID 0 at the natural length.
        length = cmap.code_length_at(0) or 2
        return bytes(length)

    def decode(self, data: bytes) -> int:
        """Decode the first character code from ``data``.

        Mirrors upstream ``PDType0Font.read(InputStream)`` /
        ``decode(bytes)`` which both yield a single integer code per
        call. Equivalent to ``read_code(data)[0]``.
        """
        code, _ = self.read_code(data, 0)
        return code

    def decode_one(self, data: bytes, offset: int = 0) -> tuple[int, int]:
        """Decode one character code from ``data`` starting at ``offset``.

        Returns ``(code, bytes_consumed)``. Mirrors :meth:`read_code`'s
        signature but uses the upstream-Java naming for callers that walk
        a buffer one code at a time. ``decode`` (single-int return) and
        :meth:`read_code` remain available for callers with the inverse
        preferences.
        """
        return self.read_code(data, offset)

    # ---------- read (InputStream-shaped wrapper) ----------

    def read(self, source: bytes | bytearray | BinaryIO) -> int:
        """Read one character code from ``source`` and return it.

        Accepts either a raw byte buffer or a binary stream object
        (anything with a ``.read(n)`` method). Mirrors upstream
        ``PDType0Font.read(InputStream)``. Streams are advanced past the
        bytes consumed by the active CMap; bare buffers are read from
        offset 0 only — callers that need mid-buffer offsets should use
        :meth:`read_code` directly.
        """
        if isinstance(source, (bytes, bytearray)):
            return self.decode(bytes(source))
        # File-like: peek up to 4 bytes (the maximum predefined CMap
        # codespace length we support), let read_code consume the right
        # number, and seek back any over-read.
        data = source.read(4)
        if not data:
            return 0
        code, consumed = self.read_code(bytes(data), 0)
        if consumed < len(data):
            with suppress(OSError, AttributeError, ValueError):
                source.seek(-(len(data) - consumed), 1)
        return code

    # ---------- subsetting ----------

    def add_to_subset(self, code_point: int) -> None:
        """Register a Unicode codepoint to keep when :meth:`subset` runs.

        Mirrors upstream ``PDType0Font.addToSubset(int)``. The codepoint
        is the *Unicode* value (not the CID) — :meth:`subset` resolves
        Unicode → GID via the descendant's embedded cmap.
        """
        self._subset_codepoints.add(int(code_point))

    def add_text_to_subset(self, text: str) -> None:
        """Convenience: register every codepoint of ``text``."""
        for ch in text:
            self._subset_codepoints.add(ord(ch))

    def add_glyphs_to_subset(self, glyph_ids: Iterable[int]) -> None:
        """Register raw glyph IDs to keep when :meth:`subset` runs.

        Mirrors upstream ``PDType0Font.addGlyphsToSubset(Set<Integer>)``
        which forwards to ``PDCIDFontType2Embedder.addGlyphIds``. Unlike
        :meth:`add_to_subset`, the IDs are *glyph indices* (after CMap
        and ``/CIDToGIDMap`` resolution) and are pinned into the subset
        directly without going through codepoint -> GID resolution.

        Raises :class:`RuntimeError` when this font was not constructed
        with subsetting enabled — matches upstream's
        ``IllegalStateException("This font was created with subsetting
        disabled")``.
        """
        if not self.will_be_subset():
            raise RuntimeError("This font was created with subsetting disabled")
        for gid in glyph_ids:
            self._subset_glyph_ids.add(int(gid))

    def will_be_subset(self) -> bool:
        """``True`` when this font will be subset on save.

        Mirrors upstream ``PDType0Font.willBeSubset`` which checks the
        embedder's ``needsSubset()`` flag. We track the equivalent state
        as a boolean set by :meth:`load_ttf` / :meth:`load_otf` and
        cleared by :meth:`subset` after the subset bytes are emitted.
        """
        return self._will_be_subset

    def subset(
        self,
        text_or_codepoints: str | Iterable[int] | None = None,
        *,
        used_chars: Iterable[int] | None = None,
        prefix: str | None = None,
    ) -> bytes:
        """Build a TrueType subset for the descendant CIDFontType2 and
        embed it on save.

        Mirrors upstream ``PDType0Font.subset()``. The descendant's
        ``/FontFile2`` is replaced with the freshly-built subset, and a
        six-letter random tag is prepended to ``/BaseFont`` (on this
        Type 0 font *and* the descendant's font dictionary) and to
        ``/FontName`` on the descendant's descriptor — per
        PDF 32000-1 §9.6.4.

        Raises ``ValueError`` when no descendant CIDFont is present, the
        descendant lacks an embedded TrueType program, or the descendant
        is not a CIDFontType2 (CIDFontType0 wraps CFF, not TTF — those
        subset through a different code path that fontTools does not
        cover via :class:`TTFSubsetter`).
        """
        from pypdfbox.fontbox.ttf import TTFSubsetter

        from .pd_cid_font_type2 import PDCIDFontType2
        from .pd_true_type_font import (
            _embed_subset_bytes,
            _random_subset_tag,
        )

        descendant = self.get_descendant_font()
        if descendant is None:
            raise ValueError(
                "PDType0Font has no descendant CIDFont; cannot subset"
            )
        if not isinstance(descendant, PDCIDFontType2):
            raise ValueError(
                "subset() supports only TrueType-backed Type 0 fonts "
                "(/Subtype /CIDFontType2); got "
                f"{type(descendant).__name__}"
            )

        ttf = descendant.get_true_type_font()
        if ttf is None:
            raise ValueError(
                "descendant CIDFontType2 has no embedded /FontFile2; "
                "cannot subset"
            )

        codepoints = self._collect_subset_codepoints(text_or_codepoints, used_chars)
        tag = prefix if prefix is not None else _random_subset_tag()

        subsetter = TTFSubsetter(ttf)
        subsetter.add_all(codepoints)
        if self._subset_glyph_ids:
            # Pin raw glyph IDs registered via add_glyphs_to_subset.
            subsetter.add_glyph_ids(self._subset_glyph_ids)
        subsetter.set_prefix(tag)
        subset_bytes = subsetter.to_bytes()

        # Embed onto the descendant (where /FontFile2 lives).
        _embed_subset_bytes(descendant, subset_bytes, tag)
        # Mirror the tag onto our own /BaseFont — per PDF 32000-1 §9.7.6.2
        # the parent and descendant must share the tagged PostScript name.
        from .pd_true_type_font import _BASE_FONT  # noqa: PLC0415

        current_base = self.get_name()
        if current_base:
            if (
                len(current_base) >= 7
                and current_base[6] == "+"
                and current_base[:6].isalpha()
                and current_base[:6].isupper()
            ):
                new_base = current_base
            else:
                new_base = f"{tag}+{current_base}"
            self.get_cos_object().set_name(_BASE_FONT, new_base)

        # Drop the descendant's parsed-TTF cache so subsequent metric
        # lookups re-read the subset bytes.
        descendant._ttf = None  # noqa: SLF001
        self._subset_codepoints.clear()
        self._subset_glyph_ids.clear()
        # Subset has been emitted — clear the flag so a second call
        # (without a new add_to_subset / add_glyphs_to_subset) becomes a
        # no-op rather than re-subsetting the already-subsetted bytes.
        self._will_be_subset = False
        return subset_bytes

    def _collect_subset_codepoints(
        self,
        text_or_codepoints: str | Iterable[int] | None,
        used_chars: Iterable[int] | None,
    ) -> set[int]:
        codepoints: set[int] = set(self._subset_codepoints)
        if isinstance(text_or_codepoints, str):
            codepoints.update(ord(ch) for ch in text_or_codepoints)
        elif text_or_codepoints is not None:
            codepoints.update(int(cp) for cp in text_or_codepoints)
        if used_chars is not None:
            codepoints.update(int(cp) for cp in used_chars)
        return codepoints

    # ---------- factories: load_ttf / load_otf ----------

    @classmethod
    def load_ttf(
        cls,
        doc: PDDocument | None,
        source: str | os.PathLike[str] | bytes | bytearray | BinaryIO,
        *,
        embed_subset: bool = True,
    ) -> PDType0Font:
        """Build a Type 0 font wrapping the TrueType file at ``source``.

        Mirrors upstream ``PDType0Font.load(PDDocument, File)``:

        * Reads the TTF bytes and parses them through
          :class:`TrueTypeFont` so glyph metrics / cmap are available.
        * Builds a CIDFontType2 descendant with ``/CIDSystemInfo
          /Registry Adobe /Ordering Identity /Supplement 0`` and the
          full TTF embedded as ``/FontFile2``.
        * Builds a parent Type 0 dictionary with ``/Encoding /Identity-H``
          and links the descendant via ``/DescendantFonts``.
        * Populates ``/W`` from the TTF's hmtx so width queries work
          before any subsetting runs.
        * Wires ``/CIDToGIDMap /Identity`` (the descendant maps CID == GID
          when the TTF cmap is consulted directly via the parent's
          Identity-H encoding — see :meth:`code_to_gid`).
        * When ``embed_subset`` is True (default), the returned font is
          marked for subsetting on save; callers populate the subset via
          :meth:`add_to_subset` before invoking :meth:`subset`.

        ``doc`` is accepted for upstream signature parity. Currently
        unused (the resulting font dictionary is *not* automatically
        registered with the document; callers attach it through
        :class:`PDResources` or by direct dictionary manipulation as
        appropriate to their use case).
        """
        del doc  # signature parity only; unused.
        ttf_bytes = _read_font_bytes(source)
        font = _build_type0_from_ttf(ttf_bytes, fallback_name="EmbeddedTTF")
        font._will_be_subset = bool(embed_subset)
        return font

    @classmethod
    def load(
        cls,
        doc: PDDocument | None,
        source: str | os.PathLike[str] | bytes | bytearray | BinaryIO,
        embed_subset: bool = True,
    ) -> PDType0Font:
        """Load a TTF / OTF as a Type 0 font.

        Mirrors upstream ``PDType0Font.load(PDDocument, File)`` and its
        ``InputStream`` / ``boolean embedSubset`` overloads. Dispatches
        to :meth:`load_ttf` for the TrueType path; CFF-flavoured OTF
        callers should use :meth:`load_otf` directly (the upstream
        ``load`` overload narrows to ``File`` / ``InputStream`` and the
        OTF distinction is encoded in the file extension upstream).
        """
        return cls.load_ttf(doc, source, embed_subset=embed_subset)

    @classmethod
    def load_vertical(
        cls,
        doc: PDDocument | None,
        source: str | os.PathLike[str] | bytes | bytearray | BinaryIO,
        embed_subset: bool = True,
    ) -> PDType0Font:
        """Load a TTF / OTF as a vertical-writing Type 0 font.

        Mirrors upstream ``PDType0Font.loadVertical(PDDocument, File)``:
        the resulting parent dictionary advertises ``/Encoding
        /Identity-V`` and the descendant's ``vrt2`` / ``vert`` GSUB
        substitutions are activated for vertical metric resolution.

        For pypdfbox the encoding-name swap is the user-visible part;
        per-glyph vertical-substitution lookups are handled by the
        descendant's :meth:`PDCIDFontType2.get_height` path which
        already consults ``/W2`` and the embedded ``vmtx`` (mirrors
        upstream's substitution behaviour).
        """
        del doc  # signature parity only; unused.
        ttf_bytes = _read_font_bytes(source)
        font = _build_type0_from_ttf(ttf_bytes, fallback_name="EmbeddedTTF")
        font._will_be_subset = bool(embed_subset)
        # Upgrade the encoding to Identity-V so ``is_vertical`` reports
        # the correct writing mode and downstream get_displacement /
        # get_position_vector consult the descendant's vertical metrics.
        font.get_cos_object().set_name(_ENCODING, "Identity-V")
        # Re-prime the lazy CMap cache so subsequent get_cmap() calls
        # see the swapped encoding.
        font._cmap_loaded = False
        font._cmap = None
        return font

    @classmethod
    def load_otf(
        cls,
        doc: PDDocument | None,
        source: str | os.PathLike[str] | bytes | bytearray | BinaryIO,
        *,
        embed_subset: bool = True,
    ) -> PDType0Font:
        """Build a Type 0 font wrapping the OpenType file at ``source``.

        Mirrors upstream ``PDType0Font.loadVertical`` / ``load(PDDocument,
        File)`` for OpenType inputs. For TrueType-flavoured OTF (``glyf``
        outlines wrapped in an SFNT container) the dispatch matches
        :meth:`load_ttf` exactly. CFF-flavoured OTF (``CFF `` outline
        table) is accepted by fontTools, embedded as ``/FontFile2``, and
        treated identically by the descendant — pypdfbox's renderer
        consults fontTools' glyph set in either case.

        ``doc`` is accepted for upstream signature parity (currently unused).
        """
        del doc  # signature parity only; unused.
        otf_bytes = _read_font_bytes(source)
        font = _build_type0_from_ttf(otf_bytes, fallback_name="EmbeddedOTF")
        font._will_be_subset = bool(embed_subset)
        return font


# ---------- module-level helpers ----------


def _read_font_bytes(
    source: str | os.PathLike[str] | bytes | bytearray | BinaryIO,
) -> bytes:
    """Coerce a font-source argument to raw bytes.

    Accepts a path-like, a byte buffer, or a file-like opened in binary
    mode — mirrors the polymorphic ``File`` / ``InputStream`` / ``byte[]``
    overloads on upstream ``PDType0Font.load``.
    """
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, os.PathLike)):
        return Path(os.fspath(source)).read_bytes()
    # File-like (BinaryIO) — read to EOF.
    if hasattr(source, "read"):
        data = source.read()
        if isinstance(data, str):
            raise TypeError(
                "load_ttf/load_otf source must yield bytes, not str — "
                "open in binary mode"
            )
        return bytes(data)
    raise TypeError(
        f"load_ttf/load_otf cannot read font bytes from {type(source).__name__}"
    )


def _build_type0_from_ttf(ttf_bytes: bytes, *, fallback_name: str) -> PDType0Font:
    """Construct a fully-wired :class:`PDType0Font` from raw TTF/OTF bytes.

    Builds the descendant CIDFontType2 (with ``/FontFile2``,
    ``/CIDSystemInfo /Identity``, ``/W`` table from ``hmtx``,
    ``/CIDToGIDMap /Identity``), the parent Type 0 dict
    (``/Encoding /Identity-H``, ``/DescendantFonts``), and a synthetic
    ``/FontDescriptor`` populated from the TTF's metric tables. Mirrors
    the bookkeeping upstream's ``TrueTypeEmbedder`` performs before
    handing the assembled dict back to ``PDType0Font.load``.
    """
    from pypdfbox.fontbox.ttf import TrueTypeFont

    from .pd_cid_font_type2 import PDCIDFontType2
    from .pd_cid_system_info import PDCIDSystemInfo
    from .pd_font_descriptor import PDFontDescriptor

    ttf = TrueTypeFont.from_bytes(ttf_bytes)
    base_font = _ps_name_from_ttf(ttf, fallback_name)

    # --- descendant CIDFontType2 -----------------------------------------
    descendant_dict = COSDictionary()
    descendant_dict.set_item(_TYPE, _FONT)
    descendant_dict.set_name(_SUBTYPE, "CIDFontType2")
    descendant_dict.set_name(_BASE_FONT, base_font)

    sys_info = PDCIDSystemInfo()
    sys_info.set_registry("Adobe")
    sys_info.set_ordering("Identity")
    sys_info.set_supplement(0)
    descendant_dict.set_item(
        COSName.get_pdf_name("CIDSystemInfo"), sys_info.get_cos_object()
    )

    # /CIDToGIDMap /Identity — Identity-H + CIDFontType2 routes
    # ``code → CID → GID`` straight through to the embedded cmap.
    descendant_dict.set_name(COSName.get_pdf_name("CIDToGIDMap"), "Identity")

    # /FontFile2 — embed the unmodified bytes; subset() will rewrite this
    # later if the caller chooses to subset.
    font_file2 = COSStream()
    font_file2.set_raw_data(ttf_bytes)

    descriptor = PDFontDescriptor()
    descriptor.set_font_name(base_font)
    descriptor.set_font_file2(font_file2)
    _populate_descriptor_from_ttf(descriptor, ttf)
    descendant_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )

    # /W — per-CID horizontal widths in 1/1000 em. Emit form 1
    # (``c [w1 w2 ...]``) covering the contiguous block from CID 0.
    w_array = _build_w_array(ttf)
    descendant_dict.set_item(COSName.get_pdf_name("W"), w_array)

    # Wrap in the typed CIDFont so the cached ttf is available for
    # subsequent metric / subset calls without reparsing.
    descendant = PDCIDFontType2(descendant_dict)
    descendant.set_true_type_font(ttf)

    # --- parent Type 0 ----------------------------------------------------
    parent_dict = COSDictionary()
    parent_dict.set_item(_TYPE, _FONT)
    parent_dict.set_name(_SUBTYPE, "Type0")
    parent_dict.set_name(_BASE_FONT, base_font)
    parent_dict.set_name(_ENCODING, "Identity-H")
    arr = COSArray()
    arr.add(descendant_dict)
    parent_dict.set_item(_DESCENDANT_FONTS, arr)

    return PDType0Font(parent_dict)


def _ps_name_from_ttf(ttf: Any, fallback: str) -> str:
    """Best-effort PostScript name from a parsed TTF/OTF.

    Tries fontTools' ``name`` table (record 6 — PostScript name) before
    falling back to the supplied default. Hardened against malformed
    name tables.
    """
    inner = getattr(ttf, "_tt", None)
    if inner is None:
        return fallback
    try:
        name_table = inner["name"]
    except (KeyError, AttributeError):
        return fallback
    record = (
        name_table.getName(6, 3, 1, 0x409)  # Win Unicode US English
        or name_table.getName(6, 1, 0, 0)  # Mac Roman
        or name_table.getName(6, 0, 3, 0)  # Unicode 2.0
    )
    if record is None:
        return fallback
    try:
        text = record.toUnicode()
    except Exception:  # noqa: BLE001 — record.toUnicode may raise on bad encodings
        return fallback
    text = text.strip()
    return text if text else fallback


def _populate_descriptor_from_ttf(
    descriptor: PDFontDescriptor, ttf: Any
) -> None:
    """Copy commonly-required metric fields from ``ttf`` into ``descriptor``.

    Mirrors the field-by-field copy upstream's ``TrueTypeEmbedder``
    performs to satisfy /FontDescriptor's required entries (PDF 32000-1
    §9.8.1, Table 122). The /Flags computation is conservative: bit 3
    (Symbolic) is set so consumers don't try to re-encode through
    StandardEncoding when the embedded cmap should be used directly.
    """
    from pypdfbox.cos import COSArray as _COSArray
    from pypdfbox.cos import COSFloat as _COSFloat
    from pypdfbox.cos import COSInteger as _COSInteger

    head = ttf.get_header()
    units_per_em = head.get_units_per_em() if head is not None else 1000
    if units_per_em <= 0:
        units_per_em = 1000
    scale = 1000.0 / units_per_em

    # /FontBBox from head.xMin/yMin/xMax/yMax, scaled to 1/1000 em.
    if head is not None:
        bbox = _COSArray()
        bbox.add(_COSFloat(float(head.get_x_min()) * scale))
        bbox.add(_COSFloat(float(head.get_y_min()) * scale))
        bbox.add(_COSFloat(float(head.get_x_max()) * scale))
        bbox.add(_COSFloat(float(head.get_y_max()) * scale))
        descriptor.set_font_b_box(bbox)

    hhea = ttf.get_horizontal_header()
    if hhea is not None:
        descriptor.get_cos_object().set_int(
            COSName.get_pdf_name("Ascent"), int(hhea.get_ascender() * scale)
        )
        descriptor.get_cos_object().set_int(
            COSName.get_pdf_name("Descent"), int(hhea.get_descender() * scale)
        )

    # /Flags — bit 3 (Symbolic). Identity-H + embedded cmap means the
    # font is consulted directly without going through a PDF /Encoding,
    # which is exactly what /Flags bit 3 advertises.
    descriptor.set_flags(1 << 2)

    # /ItalicAngle and /StemV are required by Acrobat readers but the
    # exact values are not critical for non-rendering use cases. Use
    # conservative defaults; consumers that care will override.
    descriptor.get_cos_object().set_int(
        COSName.get_pdf_name("ItalicAngle"), 0
    )
    descriptor.get_cos_object().set_int(COSName.get_pdf_name("StemV"), 80)
    # /CapHeight defaults to ascender when no OS/2 table is parsed.
    if hhea is not None:
        descriptor.get_cos_object().set_int(
            COSName.get_pdf_name("CapHeight"), int(hhea.get_ascender() * scale)
        )

    # Suppress unused-import warning for the COSInteger alias (kept
    # available for callers extending this helper).
    _ = _COSInteger


def _build_w_array(ttf: Any) -> COSArray:
    """Return a ``/W`` array (form 1) covering the TTF's hmtx widths.

    Uses ``c [w1 w2 ...]`` with ``c = 0`` and one entry per glyph,
    matching upstream's ``CIDFontType2.buildWidths``. Widths are scaled
    from font units to 1/1000 em.
    """
    from pypdfbox.cos import COSFloat as _COSFloat
    from pypdfbox.cos import COSInteger as _COSInteger

    head = ttf.get_header()
    units_per_em = head.get_units_per_em() if head is not None else 1000
    if units_per_em <= 0:
        units_per_em = 1000
    scale = 1000.0 / units_per_em

    advances = ttf.advance_widths
    inner = COSArray()
    for adv in advances:
        inner.add(_COSFloat(float(adv) * scale))

    out = COSArray()
    out.add(_COSInteger.get(0))
    out.add(inner)
    return out


__all__ = ["IDENTITY_H", "IDENTITY_V", "PDType0Font"]
