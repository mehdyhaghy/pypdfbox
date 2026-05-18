"""Wave 1354 coverage-boost agent A — tail-sweep examples + tools to 100%.

Targets the last 1-3 missing lines in ~20 example/tool modules. The bulk
are:

* Java-parity ``__init__(self): pass`` placeholders mirroring upstream's
  private no-arg constructors on utility classes — exercised by direct
  instantiation.
* ``raise OSError(...)`` guards for encrypted documents — driven through
  ``StandardProtectionPolicy`` with an empty user password (so
  ``PDDocument.load`` opens, but ``is_encrypted()`` still reports True).
* ``main([...])`` happy-paths missing from the existing usage-branch
  tests (e.g. ``EmbeddedFiles.main``).
* ``decrypt.run`` keystore + in-place PDInvalidPassword branches missed
  by wave 362 tests.

Truly defensive / unreachable lines were ``# pragma: no cover``-d at the
source rather than faked here (see ``CHANGES.md`` wave 1354 entry).
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from pypdfbox.examples.interactive.form.create_push_button import CreatePushButton
from pypdfbox.examples.interactive.form.create_simple_form_with_embedded_font import (
    CreateSimpleFormWithEmbeddedFont,
)
from pypdfbox.examples.interactive.form.field_remover import FieldRemover
from pypdfbox.examples.pdmodel.add_annotations import AddAnnotations
from pypdfbox.examples.pdmodel.add_javascript import AddJavascript
from pypdfbox.examples.pdmodel.create_blank_pdf import CreateBlankPDF
from pypdfbox.examples.pdmodel.create_page_labels import CreatePageLabels
from pypdfbox.examples.pdmodel.create_pdfa import CreatePDFA
from pypdfbox.examples.pdmodel.embedded_files import EmbeddedFiles
from pypdfbox.examples.pdmodel.extract_embedded_files import ExtractEmbeddedFiles
from pypdfbox.examples.pdmodel.hello_world import HelloWorld
from pypdfbox.examples.pdmodel.remove_first_page import RemoveFirstPage
from pypdfbox.examples.pdmodel.rubber_stamp import RubberStamp
from pypdfbox.examples.pdmodel.rubber_stamp_with_image import RubberStampWithImage
from pypdfbox.examples.pdmodel.show_color_boxes import ShowColorBoxes
from pypdfbox.examples.pdmodel.show_text_with_positioning import (
    ShowTextWithPositioning,
)
from pypdfbox.examples.pdmodel.superimpose_page import SuperimposePage
from pypdfbox.examples.signature.validation_time_stamp import ValidationTimeStamp
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.tools import cli, extracttext
from pypdfbox.tools import decrypt as decrypt_mod
from pypdfbox.tools.pdf_box import PDFBox
from pypdfbox.tools.pdf_merger import PDFMerger
from pypdfbox.tools.print_pdf import PrintPDF

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_blank_pdf(path: Path) -> None:
    """Save a one-page blank PDF to ``path``."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(str(path))
    finally:
        doc.close()


def _make_encrypted_pdf(path: Path) -> Path:
    """Build a single-page PDF with /Encrypt set but an empty user
    password — ``PDDocument.load(path)`` opens it, but
    ``is_encrypted()`` still reports True."""
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy(
                owner_password="owner",
                user_password="",
                permissions=AccessPermission(),
            ),
        )
        doc.save(str(path))
    finally:
        doc.close()
    return path


# ---------------------------------------------------------------------------
# Java-parity ``__init__(self): pass`` placeholders — direct instantiation
# ---------------------------------------------------------------------------


def test_create_push_button_constructor_is_callable() -> None:
    assert isinstance(CreatePushButton(), CreatePushButton)


def test_create_simple_form_with_embedded_font_constructor_is_callable() -> None:
    assert isinstance(
        CreateSimpleFormWithEmbeddedFont(), CreateSimpleFormWithEmbeddedFont,
    )


def test_add_annotations_constructor_is_callable() -> None:
    assert isinstance(AddAnnotations(), AddAnnotations)


def test_add_javascript_constructor_is_callable() -> None:
    assert isinstance(AddJavascript(), AddJavascript)


def test_create_blank_pdf_constructor_is_callable() -> None:
    assert isinstance(CreateBlankPDF(), CreateBlankPDF)


def test_create_page_labels_constructor_is_callable() -> None:
    assert isinstance(CreatePageLabels(), CreatePageLabels)


def test_hello_world_constructor_is_callable() -> None:
    assert isinstance(HelloWorld(), HelloWorld)


def test_remove_first_page_constructor_is_callable() -> None:
    assert isinstance(RemoveFirstPage(), RemoveFirstPage)


def test_rubber_stamp_constructor_is_callable() -> None:
    assert isinstance(RubberStamp(), RubberStamp)


def test_show_color_boxes_constructor_is_callable() -> None:
    assert isinstance(ShowColorBoxes(), ShowColorBoxes)


def test_show_text_with_positioning_constructor_is_callable() -> None:
    assert isinstance(ShowTextWithPositioning(), ShowTextWithPositioning)


def test_superimpose_page_constructor_is_callable() -> None:
    assert isinstance(SuperimposePage(), SuperimposePage)


# ---------------------------------------------------------------------------
# Encrypted-document raise-OSError branches
# ---------------------------------------------------------------------------


def test_add_javascript_main_raises_on_encrypted_input(tmp_path: Path) -> None:
    src = tmp_path / "enc.pdf"
    _make_encrypted_pdf(src)
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError, match="Encrypted documents are not supported"):
        AddJavascript.main([str(src), str(out)])


def test_remove_first_page_main_raises_on_encrypted_input(tmp_path: Path) -> None:
    src = tmp_path / "enc.pdf"
    _make_encrypted_pdf(src)
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError, match="Encrypted documents are not supported"):
        RemoveFirstPage.main([str(src), str(out)])


def test_rubber_stamp_main_raises_on_encrypted_input(tmp_path: Path) -> None:
    src = tmp_path / "enc.pdf"
    _make_encrypted_pdf(src)
    out = tmp_path / "out.pdf"
    with pytest.raises(OSError, match="Encrypted documents are not supported"):
        RubberStamp.main([str(src), str(out)])


def test_rubber_stamp_with_image_raises_on_encrypted_input(tmp_path: Path) -> None:
    src = tmp_path / "enc.pdf"
    _make_encrypted_pdf(src)
    out = tmp_path / "out.pdf"
    image_bytes = (tmp_path / "stamp.png")
    # 1x1 red PNG.
    image_bytes.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
        b"\x00\x00\x00\x05\x00\x01\xa5\xf6E@\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    rs = RubberStampWithImage()
    with pytest.raises(OSError, match="Encrypted documents are not supported"):
        rs.do_it_bytes(str(src), str(out), image_bytes.read_bytes())


# ---------------------------------------------------------------------------
# EmbeddedFiles.main + ExtractEmbeddedFiles.extract_files_from_page
# ---------------------------------------------------------------------------


def test_embedded_files_main_writes_when_single_arg(tmp_path: Path) -> None:
    """``main([out])`` falls through to ``do_it`` (line 99)."""
    out = tmp_path / "embedded.pdf"
    EmbeddedFiles.main([str(out)])
    assert out.exists()


def test_extract_embedded_files_skips_non_file_attachment_annotations(
    tmp_path: Path,
) -> None:
    """``extract_files_from_page`` must ``continue`` on annotations that
    aren't ``PDAnnotationFileAttachment`` (line 64)."""
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
        PDAnnotationLink,
    )

    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        link = PDAnnotationLink()
        page.add_annotation(link)
        # ``extract_files_from_page`` walks page.get_annotations() — drive
        # it directly with a page carrying a non-file-attachment annotation.
        ExtractEmbeddedFiles.extract_files_from_page(page, str(tmp_path))
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# CreatePDFA — descriptor.is_embedded() False raises RuntimeError
# ---------------------------------------------------------------------------


def test_create_pdfa_raises_when_font_descriptor_unembedded(
    tmp_path: Path,
) -> None:
    """Mock ``PDType0Font.load`` so the descriptor reports unembedded —
    drives the defensive raise at line 88."""
    from pypdfbox.examples.pdmodel import create_pdfa as create_pdfa_mod

    out = tmp_path / "out.pdf"
    fontfile = (
        Path(__file__).resolve().parents[2]
        / "pypdfbox" / "resources" / "ttf" / "DejaVuSans.ttf"
    )

    class _FakeDescriptor:
        def is_embedded(self) -> bool:
            return False

    class _FakeFont:
        def get_font_descriptor(self) -> _FakeDescriptor:
            return _FakeDescriptor()

    class _FakeType0:
        @staticmethod
        def load(_doc: object, _fontfile: object) -> _FakeFont:
            return _FakeFont()

    with (
        mock.patch.object(create_pdfa_mod, "PDType0Font", _FakeType0),
        pytest.raises(RuntimeError, match="PDF/A compliance requires"),
    ):
        CreatePDFA.main([str(out), "hello", str(fontfile)])


# ---------------------------------------------------------------------------
# FieldRemover.remove — nested field falls through to remove_recursive
# ---------------------------------------------------------------------------


def test_field_remover_falls_to_remove_recursive_for_nested(
    tmp_path: Path,
) -> None:
    """Build a form whose target field is nested under a non-terminal
    parent. ``remove`` walks the top-level ``fields`` list, finds no
    direct match, then falls into ``remove_recursive`` (line 86)."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

    src = tmp_path / "form.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        acro_form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(acro_form)
        parent = PDNonTerminalField(acro_form)
        parent.set_partial_name("Parent")
        leaf = PDTextField(acro_form)
        leaf.set_partial_name("Leaf")
        parent.set_children([leaf])
        acro_form.set_fields([parent])
        doc.save(str(src))
    finally:
        doc.close()

    dst = tmp_path / "out.pdf"
    assert FieldRemover().remove(str(src), str(dst), "Parent.Leaf") is True


# ---------------------------------------------------------------------------
# ValidationTimeStamp.sign_time_stamp delegates to add_signed_time_stamp
# ---------------------------------------------------------------------------


def test_validation_time_stamp_sign_time_stamp_passthrough() -> None:
    """``sign_time_stamp`` (line 38) is a one-line delegate."""
    vts = ValidationTimeStamp(None)
    assert vts.sign_time_stamp(b"signer-info") == b"signer-info"


def test_validation_time_stamp_sign_time_stamp_appends_token() -> None:
    def fake_transport(_req: bytes, _url: str, _hdr: dict[str, str]) -> bytes:
        return b"TOK"

    vts = ValidationTimeStamp(
        "http://tsa.test.invalid", transport=fake_transport,
    )
    assert vts.sign_time_stamp(b"signed") == b"signedTOK"


# ---------------------------------------------------------------------------
# decrypt.run — keystore OSError branch (lines 161-165) and in-place
# PDInvalidPasswordException branch (lines 222-223)
# ---------------------------------------------------------------------------


def test_decrypt_run_keystore_oserror_branch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """``_load_pkcs12_keystore`` raises ``FileNotFoundError`` (OSError
    subclass) when the keystore file doesn't exist — covers lines 161-165."""
    src = _make_encrypted_pdf(tmp_path / "enc.pdf")
    missing_keystore = tmp_path / "does-not-exist.p12"
    out = tmp_path / "out.pdf"
    rc = cli.run_cli(
        [
            "decrypt", "-i", str(src), "-o", str(out),
            "-keyStore", str(missing_keystore), "-password", "kspw",
        ],
    )
    assert rc == 4
    output = capsys.readouterr().out
    assert "Error decrypting document" in output


def test_decrypt_run_in_place_invalid_password_branch(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In-place decrypt (no ``-o``) where ``decrypt_pdf`` raises
    PDInvalidPasswordException after the probe succeeded — drives
    lines 222-223 (the non-``-o`` mirror of the existing wave 362 test)."""
    src = tmp_path / "enc.pdf"
    # Use empty user password so the probe load succeeds and is_encrypted()
    # is True, then mock the post-probe decrypt_pdf to fail late.
    _make_encrypted_pdf(src)

    def _fail(*_args: object, **_kwargs: object) -> None:
        raise PDInvalidPasswordException("late password failure")

    monkeypatch.setattr(decrypt_mod, "decrypt_pdf", _fail)

    # Owner password required to strip /Encrypt; the probe-load auto-
    # decrypts via the empty user password, but the owner check at
    # line 191 will block unless we set owner permission. Patch
    # ``is_owner_permission`` so we hit the in-place branch instead.
    from pypdfbox.pdmodel.encryption.access_permission import (
        AccessPermission as _AP,
    )
    monkeypatch.setattr(_AP, "is_owner_permission", lambda self: True)

    rc = cli.run_cli(["decrypt", "-i", str(src)])
    assert rc == 1
    out = capsys.readouterr().out
    assert "late password failure" in out


# ---------------------------------------------------------------------------
# extracttext.extract_embedded_pdfs — empty / missing tree short-circuits
# ---------------------------------------------------------------------------


def test_extract_embedded_pdfs_short_circuits_when_embedded_files_missing(
    tmp_path: Path,
) -> None:
    """Catalog has /Names but no /EmbeddedFiles — hits line 261 return."""
    import io

    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.pd_document_name_dictionary import (
        PDDocumentNameDictionary,
    )

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        # Force a /Names entry with no /EmbeddedFiles inside it.
        names_dict = COSDictionary()
        names = PDDocumentNameDictionary(doc.get_document_catalog())
        # Setting an unrelated entry ensures get_names() is non-None but
        # get_embedded_files() returns None.
        names.get_cos_object().set_item(COSName.get_pdf_name("Dests"), names_dict)
        doc.get_document_catalog().set_names(names)

        buf = io.StringIO()
        extracttext.extract_embedded_pdfs(doc, buf)
        assert buf.getvalue() == ""
    finally:
        doc.close()


def test_extract_embedded_pdfs_short_circuits_when_entries_empty(
    tmp_path: Path,
) -> None:
    """Embedded-files tree exists but is empty — hits line 264 return."""
    import io

    from pypdfbox.pdmodel.pd_document_name_dictionary import (
        PDDocumentNameDictionary,
    )
    from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
        PDEmbeddedFilesNameTreeNode,
    )

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        names = PDDocumentNameDictionary(doc.get_document_catalog())
        names.set_embedded_files(PDEmbeddedFilesNameTreeNode())
        doc.get_document_catalog().set_names(names)

        buf = io.StringIO()
        extracttext.extract_embedded_pdfs(doc, buf)
        assert buf.getvalue() == ""
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# print_pdf.show_available_printers — for-loop body when trays are non-empty
# ---------------------------------------------------------------------------


def test_print_pdf_show_available_printers_writes_each_tray(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Patch ``get_trays_from_print_service`` to return a non-empty list
    so the for-loop body (line 102) executes."""
    monkeypatch.setattr(
        PrintPDF, "get_trays_from_print_service",
        staticmethod(lambda _service: ["Tray-A", "Tray-B"]),
    )
    PrintPDF().show_available_printers()
    err = capsys.readouterr().err
    assert "Tray-A" in err
    assert "Tray-B" in err


# ---------------------------------------------------------------------------
# PDFBox dispatcher — run() raises SystemExit; main(None) reads sys.argv
# ---------------------------------------------------------------------------


def test_pdf_box_run_raises_system_exit() -> None:
    """Mirrors picocli's ``ParameterException`` when no subcommand is
    given (line 64)."""
    with pytest.raises(SystemExit, match="Subcommand required"):
        PDFBox().run()


def test_pdf_box_main_with_none_args_reads_sys_argv(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main(None)`` defaults to ``sys.argv[1:]`` (line 69) and then
    falls to the empty-args usage branch."""
    monkeypatch.setattr("sys.argv", ["pdf_box"])
    rc = PDFBox.main(None)
    assert rc == 2
    assert "Subcommand required" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# PDFMerger.call returns 0 on the happy path (line 51)
# ---------------------------------------------------------------------------


def test_pdf_merger_call_returns_zero_on_success(tmp_path: Path) -> None:
    """Two single-page PDFs merge into one. ``call`` returns 0 (line 51)."""
    a = tmp_path / "a.pdf"
    b = tmp_path / "b.pdf"
    _make_blank_pdf(a)
    _make_blank_pdf(b)
    out = tmp_path / "merged.pdf"

    merger = PDFMerger()
    merger.infiles = [a, b]
    merger.outfile = out
    assert merger.call() == 0
    assert out.exists()
