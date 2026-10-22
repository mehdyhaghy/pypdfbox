from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .abstract_glyph_layout_processor import AbstractGlyphLayoutProcessor
    from .content_stream_for_glyph_layout_interface import ContentStreamForGlyphLayoutInterface
    from .default_resource_cache_create_impl import DefaultResourceCacheCreateImpl
    from .glyph_layout_processor_interface import GlyphLayoutProcessorInterface
    from .glyphs_and_positions import GlyphsAndPositions
    from .missing_resource_exception import MissingResourceException
    from .page_iterator import PageIterator
    from .page_layout import PageLayout
    from .page_mode import PageMode
    from .pd_abstract_content_stream import PDAbstractContentStream
    from .pd_developer_extension import PDDeveloperExtension
    from .pd_document import PDDocument
    from .pd_document_catalog import PDDocumentCatalog
    from .pd_document_information import PDDocumentInformation
    from .pd_document_name_destination_dictionary import PDDocumentNameDestinationDictionary
    from .pd_document_name_dictionary import PDDocumentNameDictionary
    from .pd_form_content_stream import PDFormContentStream
    from .pd_page import PDPage
    from .pd_page_label_range import PDPageLabelRange
    from .pd_page_labels import PDPageLabels
    from .pd_page_tree import PDPageTree
    from .pd_pattern_content_stream import PDPatternContentStream
    from .pd_rectangle import PDRectangle
    from .pd_resources import PDResources
    from .pd_viewer_preferences import PDViewerPreferences
    from .resource_cache import ResourceCache
    from .resource_cache_create_function import ResourceCacheCreateFunction
    from .resource_cache_factory import ResourceCacheFactory
    from .search_context import SearchContext

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AbstractGlyphLayoutProcessor": ".abstract_glyph_layout_processor",
        "ContentStreamForGlyphLayoutInterface": ".content_stream_for_glyph_layout_interface",
        "DefaultResourceCacheCreateImpl": ".default_resource_cache_create_impl",
        "GlyphLayoutProcessorInterface": ".glyph_layout_processor_interface",
        "GlyphsAndPositions": ".glyphs_and_positions",
        "MissingResourceException": ".missing_resource_exception",
        "PageIterator": ".page_iterator",
        "PageLayout": ".page_layout",
        "PageMode": ".page_mode",
        "PDAbstractContentStream": ".pd_abstract_content_stream",
        "PDDeveloperExtension": ".pd_developer_extension",
        "PDDocument": ".pd_document",
        "PDDocumentCatalog": ".pd_document_catalog",
        "PDDocumentInformation": ".pd_document_information",
        "PDDocumentNameDestinationDictionary": ".pd_document_name_destination_dictionary",
        "PDDocumentNameDictionary": ".pd_document_name_dictionary",
        "PDFormContentStream": ".pd_form_content_stream",
        "PDPage": ".pd_page",
        "PDPageLabelRange": ".pd_page_label_range",
        "PDPageLabels": ".pd_page_labels",
        "PDPageTree": ".pd_page_tree",
        "PDPatternContentStream": ".pd_pattern_content_stream",
        "PDRectangle": ".pd_rectangle",
        "PDResources": ".pd_resources",
        "PDViewerPreferences": ".pd_viewer_preferences",
        "ResourceCache": ".resource_cache",
        "ResourceCacheCreateFunction": ".resource_cache_create_function",
        "ResourceCacheFactory": ".resource_cache_factory",
        "SearchContext": ".search_context",
    },
)

__all__ = [
    "AbstractGlyphLayoutProcessor",
    "ContentStreamForGlyphLayoutInterface",
    "DefaultResourceCacheCreateImpl",
    "GlyphLayoutProcessorInterface",
    "GlyphsAndPositions",
    "MissingResourceException",
    "PDAbstractContentStream",
    "PDDeveloperExtension",
    "PDDocument",
    "PDDocumentCatalog",
    "PDDocumentInformation",
    "PDDocumentNameDestinationDictionary",
    "PDDocumentNameDictionary",
    "PDFormContentStream",
    "PDPage",
    "PDPageLabelRange",
    "PDPageLabels",
    "PDPageTree",
    "PDPatternContentStream",
    "PDRectangle",
    "PDResources",
    "PDViewerPreferences",
    "PageIterator",
    "PageLayout",
    "PageMode",
    "ResourceCache",
    "ResourceCacheCreateFunction",
    "ResourceCacheFactory",
    "SearchContext",
]
