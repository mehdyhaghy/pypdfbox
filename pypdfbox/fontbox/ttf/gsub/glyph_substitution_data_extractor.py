from __future__ import annotations

import logging
from collections.abc import Mapping

from ..model.language import Language
from ..model.map_backed_gsub_data import MapBackedGsubData
from .feature_record import FeatureRecord
from .lang_sys_table import LangSysTable
from .lookup_subtable import (
    AlternateSetTable,
    LookupTypeAlternateSubstitutionFormat1,
    LookupTypeLigatureSubstitutionSubstFormat1,
    LookupTypeMultipleSubstitutionFormat1,
    LookupTypeSingleSubstFormat1,
    LookupTypeSingleSubstFormat2,
)
from .lookup_table import LookupTable
from .script_table import ScriptTable
from .script_table_details import ScriptTableDetails

LOG = logging.getLogger(__name__)


class GlyphSubstitutionDataExtractor:
    """Extract :class:`MapBackedGsubData` from a parsed GSUB table.

    Mirrors
    ``org.apache.fontbox.ttf.gsub.GlyphSubstitutionDataExtractor`` from
    upstream Apache PDFBox 3.0.x. The class walks the
    ScriptList/FeatureList/LookupList graph and materialises a
    ``feature_tag -> {glyph_run -> substitute_glyph_id}`` map. The
    glyph-run-to-substitute map is the shape :class:`MapBackedGsubData`
    expects on construction.

    The dispatch over :class:`LookupSubTable` subclasses mirrors
    upstream's chain of ``instanceof`` checks; the per-format helpers
    follow upstream byte-for-byte, including the spec-mandated
    short-circuits when the coverage / sub-table arrays disagree on
    length.
    """

    def get_gsub_data(
        self,
        script_list: Mapping[str, ScriptTable],
        feature_list_table_records: list[FeatureRecord] | tuple[FeatureRecord, ...],
        lookup_list_tables: list[LookupTable] | tuple[LookupTable, ...],
    ) -> MapBackedGsubData | None:
        """Build :class:`MapBackedGsubData` for the first matching language.

        Mirrors upstream ``getGsubData(Map, FeatureListTable,
        LookupListTable)`` — the helper iterates over the
        :class:`Language` enum in declaration order and picks the
        first :class:`Language` whose preferred script tag is present
        in ``script_list``. Returns ``None`` when no supported
        language has any of its script tags present (upstream returns
        ``GsubData.NO_DATA_FOUND``; the Python port keeps the
        existing ``gsub_data.GsubData.NO_DATA_FOUND`` sentinel
        separate so this method returns ``None`` for the new shape
        and callers can adapt).
        """
        script_table_details = self.get_supported_language(script_list)
        if script_table_details is None:
            return None
        return self.build_map_backed_gsub_data(
            feature_list_table_records,
            lookup_list_tables,
            script_table_details,
        )

    def get_gsub_data_for_script(
        self,
        script_name: str,
        script_table: ScriptTable,
        feature_list_table_records: list[FeatureRecord] | tuple[FeatureRecord, ...],
        lookup_list_tables: list[LookupTable] | tuple[LookupTable, ...],
    ) -> MapBackedGsubData:
        """Build :class:`MapBackedGsubData` for an explicit script tag.

        Mirrors the second upstream overload ``getGsubData(String,
        ScriptTable, FeatureListTable, LookupListTable)`` — the
        language is left as :attr:`Language.UNSPECIFIED` because we
        already know the script. Useful when only the structural
        contents of the GSUB table are of interest.
        """
        script_table_details = ScriptTableDetails(
            Language.UNSPECIFIED, script_name, script_table
        )
        return self.build_map_backed_gsub_data(
            feature_list_table_records,
            lookup_list_tables,
            script_table_details,
        )

    def build_map_backed_gsub_data(
        self,
        feature_list_table_records: list[FeatureRecord] | tuple[FeatureRecord, ...],
        lookup_list_tables: list[LookupTable] | tuple[LookupTable, ...],
        script_table_details: ScriptTableDetails,
    ) -> MapBackedGsubData:
        script_table = script_table_details.get_script_table()

        # ``LinkedHashMap`` upstream — Python ``dict`` preserves
        # insertion order from 3.7+, so feature traversal order
        # matches PDFBox exactly.
        gsub_data: dict[str, dict[tuple[int, ...], int]] = {}

        if script_table.get_default_lang_sys_table() is not None:
            self.populate_gsub_data(
                gsub_data,
                script_table.get_default_lang_sys_table(),
                feature_list_table_records,
                lookup_list_tables,
            )
        for lang_sys_table in script_table.get_lang_sys_tables().values():
            self.populate_gsub_data(
                gsub_data,
                lang_sys_table,
                feature_list_table_records,
                lookup_list_tables,
            )

        return MapBackedGsubData(
            script_table_details.get_language(),
            script_table_details.get_feature_name(),
            gsub_data,
        )

    @staticmethod
    def get_supported_language(
        script_list: Mapping[str, ScriptTable],
    ) -> ScriptTableDetails | None:
        for lang in Language:
            for script_name in lang.get_script_names():
                value = script_list.get(script_name)
                if value is not None:
                    LOG.debug("Language decided: %s %s", lang, script_name)
                    return ScriptTableDetails(lang, script_name, value)
        return None

    def populate_gsub_data(
        self,
        gsub_data: dict[str, dict[tuple[int, ...], int]],
        lang_sys_table: LangSysTable | None,
        feature_list_table_records: list[FeatureRecord] | tuple[FeatureRecord, ...],
        lookup_list_tables: list[LookupTable] | tuple[LookupTable, ...],
    ) -> None:
        if lang_sys_table is None:
            return
        for feature_index in lang_sys_table.get_feature_indices():
            if feature_index < len(feature_list_table_records):
                self.populate_gsub_data_from_feature(
                    gsub_data,
                    feature_list_table_records[feature_index],
                    lookup_list_tables,
                )

    def populate_gsub_data_from_feature(
        self,
        gsub_data: dict[str, dict[tuple[int, ...], int]],
        feature_record: FeatureRecord,
        lookup_list_tables: list[LookupTable] | tuple[LookupTable, ...],
    ) -> None:
        glyph_substitution_map: dict[tuple[int, ...], int] = {}
        feature_table = feature_record.get_feature_table()
        lookup_indices: tuple[int, ...] = ()
        if feature_table is not None:
            lookup_indices = feature_table.get_lookup_list_indices()
        for lookup_index in lookup_indices:
            if lookup_index < len(lookup_list_tables):
                self.extract_data(
                    glyph_substitution_map, lookup_list_tables[lookup_index]
                )

        LOG.debug(
            "*********** extracting GSUB data for the feature: %s, glyphSubstitutionMap: %s",
            feature_record.get_feature_tag(),
            glyph_substitution_map,
        )

        # Snapshot into an immutable view per feature — mirrors
        # ``Collections.unmodifiableMap`` upstream. ``types.MappingProxyType``
        # is the stdlib equivalent (no third-party dependency).
        from types import MappingProxyType

        gsub_data[feature_record.get_feature_tag()] = MappingProxyType(  # type: ignore[assignment]
            glyph_substitution_map
        )

    def extract_data(
        self,
        glyph_substitution_map: dict[tuple[int, ...], int],
        lookup_table: LookupTable,
    ) -> None:
        for lookup_sub_table in lookup_table.get_sub_tables():
            if isinstance(lookup_sub_table, LookupTypeLigatureSubstitutionSubstFormat1):
                self.extract_data_from_ligature_substitution_subst_format1_table(
                    glyph_substitution_map, lookup_sub_table
                )
            elif isinstance(lookup_sub_table, LookupTypeAlternateSubstitutionFormat1):
                self.extract_data_from_alternate_substitution_subst_format1_table(
                    glyph_substitution_map, lookup_sub_table
                )
            elif isinstance(lookup_sub_table, LookupTypeSingleSubstFormat1):
                self.extract_data_from_single_subst_table_format1_table(
                    glyph_substitution_map, lookup_sub_table
                )
            elif isinstance(lookup_sub_table, LookupTypeSingleSubstFormat2):
                self.extract_data_from_single_subst_table_format2_table(
                    glyph_substitution_map, lookup_sub_table
                )
            elif isinstance(lookup_sub_table, LookupTypeMultipleSubstitutionFormat1):
                self.extract_data_from_multiple_substitution_format1_table(
                    glyph_substitution_map, lookup_sub_table
                )
            else:
                # Usually skipped earlier in GlyphSubstitutionTable
                # parsing — log at debug only, matching upstream.
                LOG.debug(
                    "The type %s is not yet supported, will be ignored",
                    lookup_sub_table,
                )

    def extract_data_from_single_subst_table_format1_table(
        self,
        glyph_substitution_map: dict[tuple[int, ...], int],
        single_subst_table_format1: LookupTypeSingleSubstFormat1,
    ) -> None:
        coverage_object = single_subst_table_format1.get_coverage_object()
        for i in range(coverage_object.get_size()):
            coverage_glyph_id = coverage_object.get_glyph_id(i)
            substitute_glyph_id = (
                coverage_glyph_id + single_subst_table_format1.get_delta_glyph_id()
            )
            self.put_new_substitution_entry(
                glyph_substitution_map,
                substitute_glyph_id,
                [coverage_glyph_id],
            )

    def extract_data_from_single_subst_table_format2_table(
        self,
        glyph_substitution_map: dict[tuple[int, ...], int],
        single_subst_table_format2: LookupTypeSingleSubstFormat2,
    ) -> None:
        coverage_object = single_subst_table_format2.get_coverage_object()
        substitute_glyph_ids = single_subst_table_format2.get_substitute_glyph_ids()

        if coverage_object.get_size() != len(substitute_glyph_ids):
            LOG.warning(
                "The coverage table size (%d) should be the same as the count "
                "of the substituteGlyphIDs tables (%d)",
                coverage_object.get_size(),
                len(substitute_glyph_ids),
            )
            return

        for i in range(coverage_object.get_size()):
            coverage_glyph_id = coverage_object.get_glyph_id(i)
            substitute_glyph_id = int(substitute_glyph_ids[i])
            self.put_new_substitution_entry(
                glyph_substitution_map,
                substitute_glyph_id,
                [coverage_glyph_id],
            )

    def extract_data_from_multiple_substitution_format1_table(
        self,
        glyph_substitution_map: dict[tuple[int, ...], int],
        multiple_subst_format1_subtable: LookupTypeMultipleSubstitutionFormat1,
    ) -> None:
        coverage_object = multiple_subst_format1_subtable.get_coverage_object()
        sequence_tables = multiple_subst_format1_subtable.get_sequence_tables()
        if coverage_object.get_size() != len(sequence_tables):
            LOG.warning(
                "The coverage table size (%d) should be the same as the count "
                "of the sequence tables (%d)",
                coverage_object.get_size(),
                len(sequence_tables),
            )
            return
        # not implemented in 3.0 because the map value isn't a list;
        # implemented in 4.0 since PDFBOX-5648. Mirror upstream: keep
        # the size sanity check and exit.

    def extract_data_from_ligature_substitution_subst_format1_table(
        self,
        glyph_substitution_map: dict[tuple[int, ...], int],
        ligature_substitution_table: LookupTypeLigatureSubstitutionSubstFormat1,
    ) -> None:
        for ligature_set_table in ligature_substitution_table.get_ligature_set_tables():
            for ligature_table in ligature_set_table.get_ligature_tables():
                # ``LigatureTable`` only stores the *trailing* component
                # ids; the implicit first component is the coverage
                # glyph for this set. Upstream's ligature substitution
                # walks the coverage in lockstep with the set list, so
                # the implicit first component is already baked into
                # the runtime check. The data extractor preserves the
                # upstream behavior of recording only the trailing
                # components in the substitution map — callers join the
                # coverage glyph on the read side.
                self.extract_data_from_ligature_table(
                    glyph_substitution_map, ligature_table
                )

    def extract_data_from_alternate_substitution_subst_format1_table(
        self,
        glyph_substitution_map: dict[tuple[int, ...], int],
        alternate_substitution_format1: LookupTypeAlternateSubstitutionFormat1,
    ) -> None:
        coverage_object = alternate_substitution_format1.get_coverage_object()
        alternate_set_tables = alternate_substitution_format1.get_alternate_set_tables()

        if coverage_object.get_size() != len(alternate_set_tables):
            LOG.warning(
                "The coverage table size (%d) should be the same as the count "
                "of the atlternate set tables (%d)",
                coverage_object.get_size(),
                len(alternate_set_tables),
            )
            return

        for i in range(coverage_object.get_size()):
            coverage_glyph_id = coverage_object.get_glyph_id(i)
            sequence_table: AlternateSetTable = alternate_set_tables[i]

            # First alternate that differs from the coverage glyph wins
            # — matches upstream verbatim.
            for alternate_glyph_id in sequence_table.get_alternate_glyph_ids():
                if alternate_glyph_id != coverage_glyph_id:
                    self.put_new_substitution_entry(
                        glyph_substitution_map,
                        alternate_glyph_id,
                        [coverage_glyph_id],
                    )
                    break

    def extract_data_from_ligature_table(
        self,
        glyph_substitution_map: dict[tuple[int, ...], int],
        ligature_table,  # LigatureTable (avoid extra import)
    ) -> None:
        component_glyph_ids = list(ligature_table.get_component_glyph_ids())
        LOG.debug("glyphsToBeSubstituted: %s", component_glyph_ids)
        self.put_new_substitution_entry(
            glyph_substitution_map,
            ligature_table.get_ligature_glyph(),
            component_glyph_ids,
        )

    @staticmethod
    def put_new_substitution_entry(
        glyph_substitution_map: dict[tuple[int, ...], int],
        new_glyph: int,
        glyphs_to_be_substituted: list[int],
    ) -> None:
        key = tuple(glyphs_to_be_substituted)
        old_value = glyph_substitution_map.get(key)
        glyph_substitution_map[key] = new_glyph
        if old_value is not None:
            LOG.debug(
                "For the newGlyph: %d, newValue: %s is trying to override the oldValue: %d",
                new_glyph,
                glyphs_to_be_substituted,
                old_value,
            )


__all__ = ["GlyphSubstitutionDataExtractor"]
