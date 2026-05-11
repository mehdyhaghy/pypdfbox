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
    # Wave 1286.3: AddAnnotations.main() now drives a full annotation
    # pipeline. The wrong-arg-count usage gate raises ``SystemExit(1)``.
    assert hasattr(add_annotations, "AddAnnotations")
    with pytest.raises(SystemExit):
        add_annotations.AddAnnotations.main([])


def test_add_image_to_pdf_class_exists() -> None:
    # Wave 1284: AddImageToPDF.main() now drives a real load/draw/save
    # pipeline. Verify the class is wired and that wrong arg counts hit
    # the usage gate without raising.
    assert hasattr(add_image_to_pdf, "AddImageToPDF")
    # 0 args → usage gate; should not raise.
    add_image_to_pdf.AddImageToPDF.main([])


def test_add_javascript_class_exists() -> None:
    # Wave 1285.1: AddJavascript.main() now sets a JS open-action and
    # saves. Hitting the usage gate (wrong arg count) is the offline-safe
    # way to assert the class is wired.
    assert hasattr(add_javascript, "AddJavascript")
    add_javascript.AddJavascript.main([])


def test_add_metadata_from_doc_info_class_exists() -> None:
    # Wave 1286.2: AddMetadataFromDocInfo.main() now drives a real XMP
    # population + metadata-stream save pipeline. Wrong arg count hits
    # the usage gate (prints to stderr and returns without raising).
    assert hasattr(add_metadata_from_doc_info, "AddMetadataFromDocInfo")
    add_metadata_from_doc_info.AddMetadataFromDocInfo.main([])


def test_bengali_pdf_generation_hello_world_class_exists() -> None:
    # Wave 1286: BengaliPdfGenerationHelloWorld.main() is implemented
    # against a Helvetica fallback when the Lohit-Bengali corpus / TTF
    # are absent. The usage gate (zero args) still raises SystemExit.
    assert hasattr(
        bengali_pdf_generation_hello_world,
        "BengaliPdfGenerationHelloWorld",
    )
    with pytest.raises(SystemExit):
        bengali_pdf_generation_hello_world.BengaliPdfGenerationHelloWorld.main(
            [],
        )


def test_create_gradient_shading_pdf_stub() -> None:
    # Wave 1286.3: CreateGradientShadingPDF.main() now drives a real
    # axial + radial + Gouraud shading pipeline. With zero args the
    # usage gate prints to stderr and returns without raising.
    assert hasattr(create_gradient_shading_pdf, "CreateGradientShadingPDF")
    create_gradient_shading_pdf.CreateGradientShadingPDF.main([])


def test_create_patterns_pdf_stub(tmp_path, monkeypatch) -> None:
    # Wave 1286.3: CreatePatternsPDF.main() now drives a real colored +
    # uncolored tiling pattern pipeline. Without args, the example writes
    # ``patterns.pdf`` in the cwd — chdir into tmp_path so the side-effect
    # file lands somewhere disposable.
    assert hasattr(create_patterns_pdf, "CreatePatternsPDF")
    monkeypatch.chdir(tmp_path)
    create_patterns_pdf.CreatePatternsPDF.main(None)
    assert (tmp_path / "patterns.pdf").exists()


def test_create_pdfa_class_exists() -> None:
    # Wave 1286: CreatePDFA.main() now drives a full XMPBox + sRGB ICC
    # output-intent pipeline. With a missing TTF arg, the font loader
    # raises OSError; we exercise the usage gate here.
    assert hasattr(create_pdfa, "CreatePDFA")
    with pytest.raises(SystemExit):
        create_pdfa.CreatePDFA.main([])


def test_create_portable_collection_class_exists() -> None:
    # Wave 1286: CreatePortableCollection.do_it() now builds a real
    # collection schema. Zero args hits the usage gate.
    assert hasattr(create_portable_collection, "CreatePortableCollection")
    create_portable_collection.CreatePortableCollection.main([])


def test_create_separation_color_box_stub(tmp_path, monkeypatch) -> None:
    # Wave 1286.3: CreateSeparationColorBox.main() now drives a real
    # /Separation + PDFunctionType2 tint-transform pipeline. Without args,
    # the example writes ``gold.pdf`` in the cwd — chdir into tmp_path so
    # the side-effect file lands somewhere disposable.
    assert hasattr(create_separation_color_box, "CreateSeparationColorBox")
    monkeypatch.chdir(tmp_path)
    create_separation_color_box.CreateSeparationColorBox.main(None)
    assert (tmp_path / "gold.pdf").exists()


def test_embedded_files_class_exists() -> None:
    # Wave 1285.1: EmbeddedFiles.do_it() now builds a real attachment.
    # Usage-gate path: zero args triggers usage() without raising.
    assert hasattr(embedded_files, "EmbeddedFiles")
    embedded_files.EmbeddedFiles.main([])


def test_embedded_fonts_class_exists() -> None:
    # Wave 1286: EmbeddedFonts.main() now drives a Helvetica fallback
    # pipeline. The actual round-trip is exercised in the dedicated
    # ``test_examples_wave1286`` module.
    assert hasattr(embedded_fonts, "EmbeddedFonts")


def test_embedded_multiple_fonts_main_requires_fonts() -> None:
    # Wave 1286: EmbeddedMultipleFonts.main() now drives a real
    # fallback chain when font paths are supplied; without any paths it
    # raises NotImplementedError (the deferred-fixture rationale).
    assert hasattr(embedded_multiple_fonts, "EmbeddedMultipleFonts")
    with pytest.raises(NotImplementedError):
        embedded_multiple_fonts.EmbeddedMultipleFonts.main(None)


def test_embedded_vertical_fonts_main_requires_ttf() -> None:
    # Wave 1286: EmbeddedVerticalFonts.main() raises
    # NotImplementedError when ipag.ttf is absent from the cwd; the
    # full round-trip lives in ``test_examples_wave1286`` against a
    # user-supplied font path.
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


def test_extract_metadata_class_exists() -> None:
    # Wave 1286.2: ExtractMetadata.main() now drives a real XMP-parsing
    # / PDDocumentInformation fallback pipeline. The usage gate (zero
    # args) raises ``SystemExit(1)``.
    assert hasattr(extract_metadata, "ExtractMetadata")
    with pytest.raises(SystemExit):
        extract_metadata.ExtractMetadata.main([])


def test_extract_ttf_fonts_class_exists() -> None:
    # Wave 1284: ExtractTTFFonts.main() now drives the full font walk.
    # With no args, ``usage()`` triggers and raises ``SystemExit(1)``.
    assert hasattr(extract_ttf_fonts, "ExtractTTFFonts")
    with pytest.raises(SystemExit):
        extract_ttf_fonts.ExtractTTFFonts.main([])


def test_print_urls_class_exists() -> None:
    # Wave 1285.1: PrintURLs.main() now drives a real PDFTextStripperByArea
    # extraction. Wrong arg count hits the usage gate without raising.
    assert hasattr(print_urls, "PrintURLs")
    print_urls.PrintURLs.main([])


def test_rubber_stamp_with_image_class_exists() -> None:
    # Wave 1286.2: RubberStampWithImage.do_it() now drives a real
    # PDImageXObject + PDFormXObject + PDAppearanceDictionary pipeline.
    # Hitting the usage gate (zero args) prints to stderr without raising.
    assert hasattr(rubber_stamp_with_image, "RubberStampWithImage")
    rubber_stamp_with_image.RubberStampWithImage.main([])


def test_show_text_with_positioning_class_exists(
    tmp_path, monkeypatch,
) -> None:
    # Wave 1286.2: ShowTextWithPositioning.do_it() now drives a real
    # PDPageContentStream pipeline. ``main(None)`` writes ``justify-
    # example.pdf`` in the cwd; chdir into ``tmp_path`` so the side-
    # effect file lands somewhere disposable.
    assert hasattr(show_text_with_positioning, "ShowTextWithPositioning")
    monkeypatch.chdir(tmp_path)
    show_text_with_positioning.ShowTextWithPositioning.main(None)
    assert (tmp_path / "justify-example.pdf").exists()


def test_superimpose_page_class_exists() -> None:
    # Wave 1285.1: SuperimposePage.main() now drives LayerUtility +
    # PDPageContentStream.draw_form. With zero args the usage gate
    # triggers ``SystemExit(1)``.
    assert hasattr(superimpose_page, "SuperimposePage")
    with pytest.raises(SystemExit):
        superimpose_page.SuperimposePage.main([])
