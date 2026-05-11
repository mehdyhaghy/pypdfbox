"""Wave 1284 — sanity checks for example implementations.

Each test exercises the entry point with a tiny inline fixture, asserting
that the wired-up port reaches the expected output without raising.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox.examples.pdmodel.add_image_to_pdf import AddImageToPDF
from pypdfbox.examples.pdmodel.bengali_pdf_generation_hello_world import (
    BengaliPdfGenerationHelloWorld,
)
from pypdfbox.examples.pdmodel.extract_embedded_files import ExtractEmbeddedFiles
from pypdfbox.examples.pdmodel.extract_ttf_fonts import ExtractTTFFonts
from pypdfbox.pdmodel.pd_document import PDDocument


def test_add_image_to_pdf_drives_save(tmp_path: Path) -> None:
    in_pdf = tmp_path / "in.pdf"
    out_pdf = tmp_path / "out.pdf"
    # Create a 1-page input via the writer pipeline.
    with PDDocument() as doc:
        from pypdfbox.pdmodel.pd_page import PDPage

        doc.add_page(PDPage())
        doc.save(in_pdf)

    # The image path doesn't need to exist for the wiring test — instead we
    # verify the failure mode (FileNotFoundError) shows the bound code path
    # rather than the previous ``NotImplementedError``.
    import pytest

    with pytest.raises((FileNotFoundError, OSError)):
        AddImageToPDF().create_pdf_from_image(
            str(in_pdf), str(tmp_path / "missing.png"), str(out_pdf),
        )


def test_extract_embedded_files_path_traversal_guard(
    tmp_path: Path, capsys,
) -> None:
    # Asserting only the guard branch — pass a filename that resolves
    # outside ``directory_path`` and confirm the helper refuses without
    # raising.
    class _Embedded:
        def to_byte_array(self) -> bytes:
            return b"x"

    ExtractEmbeddedFiles.extract_file(
        "../escape.bin", _Embedded(), str(tmp_path),
    )
    err = capsys.readouterr().err
    assert "Ignoring" in err
    assert not (tmp_path.parent / "escape.bin").exists()


def test_extract_embedded_files_writes_normal_filename(
    tmp_path: Path,
) -> None:
    class _Embedded:
        def to_byte_array(self) -> bytes:
            return b"payload"

    ExtractEmbeddedFiles.extract_file(
        "data.bin", _Embedded(), str(tmp_path),
    )
    assert (tmp_path / "data.bin").read_bytes() == b"payload"


def test_extract_embedded_files_get_embedded_file_prefers_unicode() -> None:
    class _Spec:
        def get_embedded_file_unicode(self):
            return "unicode"

        def get_embedded_file(self):
            return "fallback"

    assert ExtractEmbeddedFiles.get_embedded_file(_Spec()) == "unicode"


def test_extract_embedded_files_get_embedded_file_falls_back() -> None:
    class _Spec:
        def get_embedded_file_unicode(self):
            return None

        def get_embedded_file_dos(self):
            return None

        def get_embedded_file_mac(self):
            return None

        def get_embedded_file_unix(self):
            return None

        def get_embedded_file(self):
            return "fallback"

    assert ExtractEmbeddedFiles.get_embedded_file(_Spec()) == "fallback"


def test_extract_ttf_fonts_get_unique_file_name(tmp_path: Path) -> None:
    extractor = ExtractTTFFonts()
    name = extractor.get_unique_file_name(str(tmp_path / "font"), "ttf")
    assert "font" in name
    # Counter should advance each call.
    second = extractor.get_unique_file_name(str(tmp_path / "font"), "ttf")
    assert second != name


def test_extract_ttf_fonts_write_font_none_descriptor(tmp_path: Path) -> None:
    # write_font(None, ...) must short-circuit without raising.
    ExtractTTFFonts().write_font(None, str(tmp_path / "x"))


def test_extract_ttf_fonts_process_resources_none() -> None:
    # process_resources(None, ...) is the documented short-circuit.
    ExtractTTFFonts().process_resources(None, "p", False)


def test_bengali_get_text_returns_list() -> None:
    # The Lohit resource is not bundled by default — verify the function
    # returns a (possibly empty) list rather than raising.
    result = BengaliPdfGenerationHelloWorld.get_bengali_text_from_file()
    assert isinstance(result, list)


def test_bengali_get_text_filters_comments(tmp_path: Path, monkeypatch) -> None:
    # Stage a fake resource dir; verify the env-var override picks it up
    # and that ``#`` lines are filtered.
    ttf_dir = tmp_path / "ttf"
    ttf_dir.mkdir()
    (ttf_dir / "bengali-samples.txt").write_text(
        "# header comment\nhello\nworld\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PYPDFBOX_RESOURCE_DIR", str(tmp_path))
    result = BengaliPdfGenerationHelloWorld.get_bengali_text_from_file()
    assert "hello" in result
    assert "world" in result
    assert "# header comment" not in result


def test_create_visual_signature_template_returns_bytes_io() -> None:
    from pypdfbox.examples.signature.create_visible_signature2 import (
        CreateVisibleSignature2,
    )
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    src = PDDocument()
    src.add_page(PDPage(PDRectangle(0, 0, 612, 792)))
    try:
        rect = PDRectangle(100, 100, 200, 50)
        signature = PDSignature()
        buf = CreateVisibleSignature2.create_visual_signature_template(
            src, 0, rect, signature,
        )
        assert isinstance(buf, io.BytesIO)
        data = buf.read()
        assert data.startswith(b"%PDF-")
    finally:
        src.close()
