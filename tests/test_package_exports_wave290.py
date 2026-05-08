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
        "MissingResourceException",
        "PDDocument",
        "PDDeveloperExtension",
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
        "PageLayout",
        "PageMode",
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
        "COSParser",
        "EndstreamFilterStream",
        "Operator",
        "PDFParseError",
        "PDFParser",
        "PDFStreamParser",
        "XrefEntry",
        "XrefTrailerResolver",
        "XrefType",
    ),
    "pypdfbox.multipdf": (
        "AcroFormMergeMode",
        "DocumentMergeMode",
        "LayerUtility",
        "Overlay",
        "PDFCloneUtility",
        "PDFMergerUtility",
        "PageExtractor",
        "Position",
        "Splitter",
    ),
    "pypdfbox.rendering": (
        "ImageType",
        "PDFRenderer",
        "RenderDestination",
    ),
    "pypdfbox.text": (
        "AngleCollector",
        "FilteredTextStripper",
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
