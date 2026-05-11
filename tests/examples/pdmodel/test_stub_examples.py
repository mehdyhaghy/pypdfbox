"""Sanity tests for examples whose ``main()`` is a structural stub.

Each test imports the module, asserts the upstream class exists with the
correct name, and confirms ``main()`` raises ``NotImplementedError`` when
invoked with arguments that drive past the usage gate.
"""

from __future__ import annotations

import pytest

from pypdfbox.examples.pdmodel import (
    add_annotations,
    add_image_to_pdf,
    add_javascript,
    add_metadata_from_doc_info,
    bengali_pdf_generation_hello_world,
    create_gradient_shading_pdf,
    create_patterns_pdf,
    create_pdfa,
    create_portable_collection,
    create_separation_color_box,
    embedded_files,
    embedded_fonts,
    embedded_multiple_fonts,
    embedded_vertical_fonts,
    extract_embedded_files,
    extract_metadata,
    extract_ttf_fonts,
    print_urls,
    rubber_stamp_with_image,
    show_text_with_positioning,
    superimpose_page,
)


def test_add_annotations_stub() -> None:
    assert hasattr(add_annotations, "AddAnnotations")
    with pytest.raises(NotImplementedError):
        add_annotations.AddAnnotations.main(["out.pdf"])


def test_add_image_to_pdf_class_exists() -> None:
    # Wave 1284: AddImageToPDF.main() now drives a real load/draw/save
    # pipeline. Verify the class is wired and that wrong arg counts hit
    # the usage gate without raising.
    assert hasattr(add_image_to_pdf, "AddImageToPDF")
    # 0 args → usage gate; should not raise.
    add_image_to_pdf.AddImageToPDF.main([])


def test_add_javascript_stub() -> None:
    assert hasattr(add_javascript, "AddJavascript")
    with pytest.raises(NotImplementedError):
        add_javascript.AddJavascript.main(["in.pdf", "out.pdf"])


def test_add_metadata_from_doc_info_stub() -> None:
    assert hasattr(add_metadata_from_doc_info, "AddMetadataFromDocInfo")
    with pytest.raises(NotImplementedError):
        add_metadata_from_doc_info.AddMetadataFromDocInfo.main(
            ["in.pdf", "out.pdf"],
        )


def test_bengali_pdf_generation_hello_world_stub() -> None:
    assert hasattr(
        bengali_pdf_generation_hello_world,
        "BengaliPdfGenerationHelloWorld",
    )
    with pytest.raises(NotImplementedError):
        bengali_pdf_generation_hello_world.BengaliPdfGenerationHelloWorld.main(
            ["out.pdf"],
        )


def test_create_gradient_shading_pdf_stub() -> None:
    assert hasattr(create_gradient_shading_pdf, "CreateGradientShadingPDF")
    with pytest.raises(NotImplementedError):
        create_gradient_shading_pdf.CreateGradientShadingPDF.main(["out.pdf"])


def test_create_patterns_pdf_stub() -> None:
    assert hasattr(create_patterns_pdf, "CreatePatternsPDF")
    with pytest.raises(NotImplementedError):
        create_patterns_pdf.CreatePatternsPDF.main(None)


def test_create_pdfa_stub() -> None:
    assert hasattr(create_pdfa, "CreatePDFA")
    with pytest.raises(NotImplementedError):
        create_pdfa.CreatePDFA.main(["out.pdf", "msg", "font.ttf"])


def test_create_portable_collection_stub() -> None:
    assert hasattr(create_portable_collection, "CreatePortableCollection")
    with pytest.raises(NotImplementedError):
        create_portable_collection.CreatePortableCollection.main(["out.pdf"])


def test_create_separation_color_box_stub() -> None:
    assert hasattr(create_separation_color_box, "CreateSeparationColorBox")
    with pytest.raises(NotImplementedError):
        create_separation_color_box.CreateSeparationColorBox.main(None)


def test_embedded_files_stub() -> None:
    assert hasattr(embedded_files, "EmbeddedFiles")
    with pytest.raises(NotImplementedError):
        embedded_files.EmbeddedFiles.main(["out.pdf"])


def test_embedded_fonts_stub() -> None:
    assert hasattr(embedded_fonts, "EmbeddedFonts")
    with pytest.raises(NotImplementedError):
        embedded_fonts.EmbeddedFonts.main(None)


def test_embedded_multiple_fonts_stub() -> None:
    assert hasattr(embedded_multiple_fonts, "EmbeddedMultipleFonts")
    with pytest.raises(NotImplementedError):
        embedded_multiple_fonts.EmbeddedMultipleFonts.main(None)


def test_embedded_vertical_fonts_stub() -> None:
    assert hasattr(embedded_vertical_fonts, "EmbeddedVerticalFonts")
    with pytest.raises(NotImplementedError):
        embedded_vertical_fonts.EmbeddedVerticalFonts.main(None)


def test_extract_embedded_files_class_exists() -> None:
    # Wave 1284: ExtractEmbeddedFiles.main() now drives a real
    # NameTreeNode + PDAnnotationFileAttachment walk. Hitting the usage
    # gate (wrong arg count) is the safe way to assert the class wires up.
    assert hasattr(extract_embedded_files, "ExtractEmbeddedFiles")
    with pytest.raises(SystemExit):
        extract_embedded_files.ExtractEmbeddedFiles.main([])


def test_extract_metadata_stub() -> None:
    assert hasattr(extract_metadata, "ExtractMetadata")
    with pytest.raises(NotImplementedError):
        extract_metadata.ExtractMetadata.main(["in.pdf"])


def test_extract_ttf_fonts_class_exists() -> None:
    # Wave 1284: ExtractTTFFonts.main() now drives the full font walk.
    # With no args, ``usage()`` triggers and raises ``SystemExit(1)``.
    assert hasattr(extract_ttf_fonts, "ExtractTTFFonts")
    with pytest.raises(SystemExit):
        extract_ttf_fonts.ExtractTTFFonts.main([])


def test_print_urls_stub() -> None:
    assert hasattr(print_urls, "PrintURLs")
    with pytest.raises(NotImplementedError):
        print_urls.PrintURLs.main(["in.pdf"])


def test_rubber_stamp_with_image_stub() -> None:
    assert hasattr(rubber_stamp_with_image, "RubberStampWithImage")
    with pytest.raises(NotImplementedError):
        rubber_stamp_with_image.RubberStampWithImage.main(
            ["in.pdf", "out.pdf", "img.jpg"],
        )


def test_show_text_with_positioning_stub() -> None:
    assert hasattr(show_text_with_positioning, "ShowTextWithPositioning")
    with pytest.raises(NotImplementedError):
        show_text_with_positioning.ShowTextWithPositioning.main(None)


def test_superimpose_page_stub() -> None:
    assert hasattr(superimpose_page, "SuperimposePage")
    with pytest.raises(NotImplementedError):
        superimpose_page.SuperimposePage.main(["src.pdf", "dst.pdf"])
