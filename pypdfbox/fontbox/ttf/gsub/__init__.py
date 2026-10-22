from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .compound_character_tokenizer import CompoundCharacterTokenizer
    from .default_gsub_worker import DefaultGsubWorker
    from .feature_record import FeatureRecord
    from .feature_table import FeatureTable
    from .glyph_array_splitter import GlyphArraySplitter
    from .glyph_array_splitter_regex_impl import GlyphArraySplitterRegexImpl
    from .glyph_substitution_data_extractor import GlyphSubstitutionDataExtractor
    from .gsub_data import GsubData
    from .gsub_worker import GsubWorker
    from .gsub_worker_factory import GsubWorkerFactory
    from .gsub_worker_for_aalt import GsubWorkerForAALT
    from .gsub_worker_for_bengali import GsubWorkerForBengali
    from .gsub_worker_for_devanagari import GsubWorkerForDevanagari
    from .gsub_worker_for_dflt import GsubWorkerForDflt
    from .gsub_worker_for_gujarati import GsubWorkerForGujarati
    from .gsub_worker_for_latin import GsubWorkerForLatin
    from .gsub_worker_for_smcp import GsubWorkerForSMCP
    from .gsub_worker_for_tamil import GsubWorkerForTamil
    from .lang_sys_table import LangSysTable
    from .lookup_subtable import (
        AlternateSetTable,
        ChainedClassRule,
        ChainedClassRuleSet,
        ChainedSequenceRule,
        ChainedSequenceRuleSet,
        ClassDefinitionTable,
        ClassRule,
        ClassRuleSet,
        CoverageTable,
        LigatureSetTable,
        LigatureTable,
        LookupSubTable,
        LookupTypeAlternateSubstitutionFormat1,
        LookupTypeChainedContextualSubstitutionFormat1,
        LookupTypeChainedContextualSubstitutionFormat2,
        LookupTypeChainedContextualSubstitutionFormat3,
        LookupTypeContextualSubstitutionFormat1,
        LookupTypeContextualSubstitutionFormat2,
        LookupTypeContextualSubstitutionFormat3,
        LookupTypeExtensionSubstitutionFormat1,
        LookupTypeLigatureSubstitutionSubstFormat1,
        LookupTypeMultipleSubstitutionFormat1,
        LookupTypeReverseChainedContextualSubstitutionFormat1,
        LookupTypeSingleSubstFormat1,
        LookupTypeSingleSubstFormat2,
        SequenceRule,
        SequenceRuleSet,
        SequenceTable,
        SubstitutionLookupRecord,
        apply_lookup_table,
    )
    from .lookup_table import LookupTable
    from .script_table import ScriptTable
    from .script_table_details import ScriptTableDetails

__getattr__, __dir__ = _attach(
    __name__,
    {
        "CompoundCharacterTokenizer": ".compound_character_tokenizer",
        "DefaultGsubWorker": ".default_gsub_worker",
        "FeatureRecord": ".feature_record",
        "FeatureTable": ".feature_table",
        "GlyphArraySplitter": ".glyph_array_splitter",
        "GlyphArraySplitterRegexImpl": ".glyph_array_splitter_regex_impl",
        "GlyphSubstitutionDataExtractor": ".glyph_substitution_data_extractor",
        "GsubData": ".gsub_data",
        "GsubWorker": ".gsub_worker",
        "GsubWorkerFactory": ".gsub_worker_factory",
        "GsubWorkerForAALT": ".gsub_worker_for_aalt",
        "GsubWorkerForBengali": ".gsub_worker_for_bengali",
        "GsubWorkerForDevanagari": ".gsub_worker_for_devanagari",
        "GsubWorkerForDflt": ".gsub_worker_for_dflt",
        "GsubWorkerForGujarati": ".gsub_worker_for_gujarati",
        "GsubWorkerForLatin": ".gsub_worker_for_latin",
        "GsubWorkerForSMCP": ".gsub_worker_for_smcp",
        "GsubWorkerForTamil": ".gsub_worker_for_tamil",
        "LangSysTable": ".lang_sys_table",
        "AlternateSetTable": ".lookup_subtable",
        "ChainedClassRule": ".lookup_subtable",
        "ChainedClassRuleSet": ".lookup_subtable",
        "ChainedSequenceRule": ".lookup_subtable",
        "ChainedSequenceRuleSet": ".lookup_subtable",
        "ClassDefinitionTable": ".lookup_subtable",
        "ClassRule": ".lookup_subtable",
        "ClassRuleSet": ".lookup_subtable",
        "CoverageTable": ".lookup_subtable",
        "LigatureSetTable": ".lookup_subtable",
        "LigatureTable": ".lookup_subtable",
        "LookupSubTable": ".lookup_subtable",
        "LookupTypeAlternateSubstitutionFormat1": ".lookup_subtable",
        "LookupTypeChainedContextualSubstitutionFormat1": ".lookup_subtable",
        "LookupTypeChainedContextualSubstitutionFormat2": ".lookup_subtable",
        "LookupTypeChainedContextualSubstitutionFormat3": ".lookup_subtable",
        "LookupTypeContextualSubstitutionFormat1": ".lookup_subtable",
        "LookupTypeContextualSubstitutionFormat2": ".lookup_subtable",
        "LookupTypeContextualSubstitutionFormat3": ".lookup_subtable",
        "LookupTypeExtensionSubstitutionFormat1": ".lookup_subtable",
        "LookupTypeLigatureSubstitutionSubstFormat1": ".lookup_subtable",
        "LookupTypeMultipleSubstitutionFormat1": ".lookup_subtable",
        "LookupTypeReverseChainedContextualSubstitutionFormat1": ".lookup_subtable",
        "LookupTypeSingleSubstFormat1": ".lookup_subtable",
        "LookupTypeSingleSubstFormat2": ".lookup_subtable",
        "SequenceRule": ".lookup_subtable",
        "SequenceRuleSet": ".lookup_subtable",
        "SequenceTable": ".lookup_subtable",
        "SubstitutionLookupRecord": ".lookup_subtable",
        "apply_lookup_table": ".lookup_subtable",
        "LookupTable": ".lookup_table",
        "ScriptTable": ".script_table",
        "ScriptTableDetails": ".script_table_details",
    },
)

__all__ = [
    "AlternateSetTable",
    "ChainedClassRule",
    "ChainedClassRuleSet",
    "ChainedSequenceRule",
    "ChainedSequenceRuleSet",
    "ClassDefinitionTable",
    "ClassRule",
    "ClassRuleSet",
    "CompoundCharacterTokenizer",
    "CoverageTable",
    "DefaultGsubWorker",
    "FeatureRecord",
    "FeatureTable",
    "GlyphArraySplitter",
    "GlyphArraySplitterRegexImpl",
    "GlyphSubstitutionDataExtractor",
    "GsubData",
    "GsubWorker",
    "GsubWorkerFactory",
    "GsubWorkerForAALT",
    "GsubWorkerForBengali",
    "GsubWorkerForDevanagari",
    "GsubWorkerForDflt",
    "GsubWorkerForGujarati",
    "GsubWorkerForLatin",
    "GsubWorkerForSMCP",
    "GsubWorkerForTamil",
    "LangSysTable",
    "LigatureSetTable",
    "LigatureTable",
    "LookupSubTable",
    "LookupTable",
    "LookupTypeAlternateSubstitutionFormat1",
    "LookupTypeChainedContextualSubstitutionFormat1",
    "LookupTypeChainedContextualSubstitutionFormat2",
    "LookupTypeChainedContextualSubstitutionFormat3",
    "LookupTypeContextualSubstitutionFormat1",
    "LookupTypeContextualSubstitutionFormat2",
    "LookupTypeContextualSubstitutionFormat3",
    "LookupTypeExtensionSubstitutionFormat1",
    "LookupTypeLigatureSubstitutionSubstFormat1",
    "LookupTypeMultipleSubstitutionFormat1",
    "LookupTypeReverseChainedContextualSubstitutionFormat1",
    "LookupTypeSingleSubstFormat1",
    "LookupTypeSingleSubstFormat2",
    "ScriptTable",
    "ScriptTableDetails",
    "SequenceRule",
    "SequenceRuleSet",
    "SequenceTable",
    "SubstitutionLookupRecord",
    "apply_lookup_table",
]
