from __future__ import annotations

from importlib import import_module

import pytest

EXPECTED_EXPORTS: dict[str, tuple[str, ...]] = {
    "pypdfbox": (
        "Loader",
        "PDDocument",
        "PDDocumentCatalog",
        "PDPage",
        "PDPageTree",
        "PDRectangle",
        "PDResources",
    ),
    "pypdfbox.pdmodel": (
        "DefaultResourceCacheCreateImpl",
        "MissingResourceException",
        "PDAbstractContentStream",
        "PDDeveloperExtension",
        "PDDocument",
        "PDDocumentCatalog",
        "PDDocumentInformation",
        "PDDocumentNameDestinationDictionary",
        "PDDocumentNameDictionary",
        "PDPage",
        "PDPageLabelRange",
        "PDPageLabels",
        "PDPageTree",
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
    ),
    "pypdfbox.fontbox": (
        "CIDFontMapping",
        "DefaultFontMapper",
        "EncodedFont",
        "Encoding",
        "FontBoxFont",
        "FontFormat",
        "FontInfo",
        "FontMapper",
        "FontMappers",
        "FontMapping",
        "FontProvider",
        "GlyphList",
        "MacExpertEncoding",
        "MacRomanEncoding",
        "Standard14FontWrapper",
        "StandardEncoding",
        "SymbolEncoding",
        "WinAnsiEncoding",
        "ZapfDingbatsEncoding",
    ),
    "pypdfbox.pdfwriter": (
        "COSStandardOutputStream",
        "COSWriter",
        "COSWriterXRefEntry",
        "CompressParameters",
        "ContentStreamWriter",
    ),
    "pypdfbox.pdfparser": (
        "BaseParser",
        "BruteForceParser",
        "COSParser",
        "EndstreamFilterStream",
        "FDFParser",
        "ObjectNumbers",
        "Operator",
        "PDFObjectStreamParser",
        "PDFParseError",
        "PDFParser",
        "PDFStreamParser",
        "PDFXRefStream",
        "PDFXrefStreamParser",
        "XrefEntry",
        "XrefTrailerObj",
        "XrefTrailerResolver",
        "XrefType",
    ),
    "pypdfbox.multipdf": (
        "AcroFormMergeMode",
        "DocumentMergeMode",
        "KCloner",
        "LayerUtility",
        "Overlay",
        "PDFCloneUtility",
        "PDFMergerUtility",
        "PageExtractor",
        "Position",
        "Splitter",
    ),
    "pypdfbox.rendering": (
        "GlyphCache",
        "GroupGraphics",
        "ImageType",
        "PDFRenderer",
        "PageDrawer",
        "PageDrawerParameters",
        "RenderDestination",
        "SoftMask",
        "SoftPaintContext",
        "TilingPaint",
        "TilingPaintFactory",
        "TilingPaintParameter",
        "TransparencyGroup",
    ),
    "pypdfbox.text": (
        "AngleCollector",
        "FilteredTextStripper",
        "LegacyPDFStreamEngine",
        "LineItem",
        "PDFMarkedContentExtractor",
        "PDFTextStripper",
        "PDFTextStripperByArea",
        "PositionWrapper",
        "TextMetrics",
        "TextPosition",
        "TextPositionComparator",
        "WordWithTextPositions",
        "get_angle",
    ),
}


@pytest.mark.parametrize(("module_name", "expected"), EXPECTED_EXPORTS.items())
def test_package_all_exports_are_bound(
    module_name: str, expected: tuple[str, ...]
) -> None:
    module = import_module(module_name)

    exported = module.__dict__["__all__"]

    assert isinstance(exported, list)
    assert tuple(exported) == expected
    for name in expected:
        assert getattr(module, name) is not None
