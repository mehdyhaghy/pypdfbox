"""Tests for ``ExtractEmbeddedFiles``.

Exercises both the recursive name-tree walk and the per-page annotation
walk against fully in-memory PDFs built via the public PD API. Aims to
cover the missing branches identified by ``--cov-report=term-missing``:
the path-traversal guard, the ``main`` happy path, the annotation walk,
and the recursive ``extract_files_from_ef_tree`` descent through ``kids``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.examples.pdmodel.extract_embedded_files import (
    ExtractEmbeddedFiles,
)


def _build_pdf_with_embedded_files(out_path: Path) -> None:
    """Build a tiny PDF carrying a single attachment under
    ``/Catalog/Names/EmbeddedFiles`` (names-leaf form). The attachment
    payload is the bytestring ``b"hello"``."""
    from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (  # noqa: E501
        PDComplexFileSpecification,
    )
    from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import (
        PDEmbeddedFile,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_document_name_dictionary import (
        PDDocumentNameDictionary,
    )
    from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
        PDEmbeddedFilesNameTreeNode,
    )
    from pypdfbox.pdmodel.pd_page import PDPage

    with PDDocument() as doc:
        doc.add_page(PDPage())

        embedded = PDEmbeddedFile(doc, b"hello")
        embedded.set_subtype("text/plain")

        spec = PDComplexFileSpecification()
        spec.set_file("hello.txt")
        spec.set_file_unicode("hello.txt")
        spec.set_embedded_file(embedded)
        spec.set_embedded_file_unicode(embedded)

        ef_tree = PDEmbeddedFilesNameTreeNode()
        ef_tree.set_names({"hello.txt": spec})

        names = PDDocumentNameDictionary(doc.get_document_catalog())
        names.set_embedded_files(ef_tree)
        doc.get_document_catalog().set_names(names)

        doc.save(out_path)


def test_static_helper_can_be_instantiated_but_yields_no_state() -> None:
    # Mirrors the upstream private-ctor pattern: instantiation is allowed
    # (it's not annotated ``@staticmethod`` class), but the instance carries
    # no state.
    helper = ExtractEmbeddedFiles()
    assert helper is not None


def test_usage_writes_to_stderr(capsys) -> None:
    ExtractEmbeddedFiles.usage()
    err = capsys.readouterr().err
    assert "ExtractEmbeddedFiles" in err


def test_main_wrong_arg_count_raises_system_exit(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        ExtractEmbeddedFiles.main([])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "ExtractEmbeddedFiles" in err


def test_main_extracts_payload_to_directory(tmp_path: Path) -> None:
    in_pdf = tmp_path / "with_attachment.pdf"
    _build_pdf_with_embedded_files(in_pdf)

    ExtractEmbeddedFiles.main([str(in_pdf)])

    out = tmp_path / "hello.txt"
    assert out.exists()
    assert out.read_bytes() == b"hello"


def test_extract_files_handles_none() -> None:
    # Branch coverage: ``extract_files(None, ...)`` is the upstream early-out.
    ExtractEmbeddedFiles.extract_files(None, "/tmp")  # noqa: S108 - not used


def test_extract_files_skips_specs_without_embedded_payload(
    tmp_path: Path,
) -> None:
    class _NoEmbedded:
        def get_embedded_file_unicode(self):
            return None

        def get_embedded_file(self):
            return None

        def get_filename(self) -> str:
            return "ignored.bin"

    ExtractEmbeddedFiles.extract_files(
        {"ignored.bin": _NoEmbedded()}, str(tmp_path),
    )
    assert list(tmp_path.iterdir()) == []


def test_extract_files_uses_key_when_filename_missing(tmp_path: Path) -> None:
    class _Embedded:
        def to_byte_array(self) -> bytes:
            return b"keyed"

    class _NoFilename:
        # Deliberately omit ``get_filename`` so the fallback branch fires.
        def get_embedded_file(self):
            return _Embedded()

    ExtractEmbeddedFiles.extract_files(
        {"by-key.bin": _NoFilename()}, str(tmp_path),
    )
    assert (tmp_path / "by-key.bin").read_bytes() == b"keyed"


def test_extract_file_short_circuits_on_none() -> None:
    # Both arguments None — must return without raising.
    ExtractEmbeddedFiles.extract_file(None, None, "/tmp")  # noqa: S108
    ExtractEmbeddedFiles.extract_file("name", None, "/tmp")  # noqa: S108


def test_extract_file_falls_back_to_bytes(tmp_path: Path) -> None:
    # An ``embedded_file`` lacking ``to_byte_array`` is coerced via ``bytes()``.
    payload = bytearray(b"raw")
    ExtractEmbeddedFiles.extract_file("raw.bin", payload, str(tmp_path))
    assert (tmp_path / "raw.bin").read_bytes() == b"raw"


def test_get_embedded_file_returns_none_for_none() -> None:
    assert ExtractEmbeddedFiles.get_embedded_file(None) is None


def test_get_embedded_file_skips_getter_that_raises() -> None:
    class _Spec:
        def get_embedded_file_unicode(self):
            raise RuntimeError("nope")

        def get_embedded_file_dos(self):
            return None

        def get_embedded_file_mac(self):
            return None

        def get_embedded_file_unix(self):
            return None

        def get_embedded_file(self):
            return "fallback"

    # The unicode getter raises; the helper must continue and return the
    # later non-None result.
    assert ExtractEmbeddedFiles.get_embedded_file(_Spec()) == "fallback"


def test_get_embedded_file_returns_none_when_no_getter_succeeds() -> None:
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
            return None

    assert ExtractEmbeddedFiles.get_embedded_file(_Spec()) is None


def test_extract_files_from_ef_tree_returns_for_none_kids() -> None:
    class _Node:
        def get_names(self):
            return None

        def get_kids(self):
            return None

    # No names + no kids → silent early return.
    ExtractEmbeddedFiles.extract_files_from_ef_tree(_Node(), "/tmp")  # noqa: S108


def test_extract_files_from_ef_tree_descends_into_kids(tmp_path: Path) -> None:
    class _Embedded:
        def to_byte_array(self) -> bytes:
            return b"branch"

    class _Spec:
        def get_embedded_file_unicode(self):
            return _Embedded()

        def get_filename(self) -> str:
            return "branch.bin"

    class _LeafNode:
        def get_names(self):
            return {"branch.bin": _Spec()}

        def get_kids(self):
            return None

    class _BranchNode:
        def get_names(self):
            return None

        def get_kids(self):
            return [_LeafNode()]

    ExtractEmbeddedFiles.extract_files_from_ef_tree(
        _BranchNode(), str(tmp_path),
    )
    assert (tmp_path / "branch.bin").read_bytes() == b"branch"


def test_extract_files_from_page_skips_non_file_attachment_annotations(
    tmp_path: Path,
) -> None:
    from pypdfbox.pdmodel.pd_page import PDPage

    page = PDPage()  # no annotations at all
    ExtractEmbeddedFiles.extract_files_from_page(page, str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_extract_files_from_page_extracts_file_attachment(
    tmp_path: Path,
) -> None:
    from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (  # noqa: E501
        PDComplexFileSpecification,
    )
    from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import (
        PDEmbeddedFile,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (  # noqa: E501
        PDAnnotationFileAttachment,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    with PDDocument() as doc:
        page = PDPage()
        embedded = PDEmbeddedFile(doc, b"attached")
        spec = PDComplexFileSpecification()
        spec.set_file("attached.bin")
        spec.set_embedded_file(embedded)
        annot = PDAnnotationFileAttachment()
        annot.set_file(spec)
        page.set_annotations([annot])
        doc.add_page(page)

        ExtractEmbeddedFiles.extract_files_from_page(page, str(tmp_path))
        out = tmp_path / "attached.bin"
        assert out.exists()
        assert out.read_bytes() == b"attached"


def test_extract_files_from_page_skips_simple_file_spec(
    tmp_path: Path,
) -> None:
    from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (  # noqa: E501
        PDSimpleFileSpecification,
    )
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (  # noqa: E501
        PDAnnotationFileAttachment,
    )
    from pypdfbox.pdmodel.pd_page import PDPage

    page = PDPage()
    annot = PDAnnotationFileAttachment()
    annot.set_file(PDSimpleFileSpecification())
    page.set_annotations([annot])

    # PDSimpleFileSpecification is not a PDComplexFileSpecification, so the
    # extractor must skip it without raising.
    ExtractEmbeddedFiles.extract_files_from_page(page, str(tmp_path))
    assert list(tmp_path.iterdir()) == []
