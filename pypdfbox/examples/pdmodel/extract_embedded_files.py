"""Port of ``org.apache.pdfbox.examples.pdmodel.ExtractEmbeddedFiles`` (lines 42-198).

Extracts all embedded files from a PDF document.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


class ExtractEmbeddedFiles:
    """Mirrors ``ExtractEmbeddedFiles`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 55)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            ExtractEmbeddedFiles.usage()
            raise SystemExit(1)

        from pypdfbox.loader import Loader
        from pypdfbox.pdmodel.pd_document import PDDocument
        from pypdfbox.pdmodel.pd_document_name_dictionary import (
            PDDocumentNameDictionary,
        )

        pdf_file = Path(argv[0])
        directory_path = str(pdf_file.resolve().parent)
        with Loader.load_pdf(pdf_file) as cos_doc:
            document = PDDocument(cos_doc)
            names_dict = PDDocumentNameDictionary(
                document.get_document_catalog(),
            )
            ef_tree = names_dict.get_embedded_files()
            if ef_tree is not None:
                ExtractEmbeddedFiles.extract_files_from_ef_tree(
                    ef_tree, directory_path,
                )

            for page in document.get_pages():
                ExtractEmbeddedFiles.extract_files_from_page(
                    page, directory_path,
                )

    @staticmethod
    def extract_files_from_page(page: Any, directory_path: str) -> None:
        """Mirrors ``extractFilesFromPage(PDPage, String)`` (line 83)."""
        from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (  # noqa: E501
            PDComplexFileSpecification,
        )
        from pypdfbox.pdmodel.interactive.annotation.pd_annotation_file_attachment import (  # noqa: E501
            PDAnnotationFileAttachment,
        )

        for annotation in page.get_annotations():
            if not isinstance(annotation, PDAnnotationFileAttachment):
                continue
            file_spec = annotation.get_file()
            if not isinstance(file_spec, PDComplexFileSpecification):
                continue
            embedded_file = ExtractEmbeddedFiles.get_embedded_file(file_spec)
            if embedded_file is not None:
                ExtractEmbeddedFiles.extract_file(
                    file_spec.get_filename(), embedded_file, directory_path,
                )

    @staticmethod
    def extract_files_from_ef_tree(ef_tree: Any, directory_path: str) -> None:
        """Mirrors ``extractFilesFromEFTree(PDNameTreeNode, String)`` (line 104).

        Recursively descends the embedded-files name tree (PDF 32000-1
        §7.7.4) and emits each leaf's complex file specification to
        ``extract_files``. Mirror upstream depth-first walk.
        """
        names = ef_tree.get_names()
        if names is not None:
            ExtractEmbeddedFiles.extract_files(names, directory_path)
            return
        kids = ef_tree.get_kids()
        if kids is None:
            return
        for node in kids:
            ExtractEmbeddedFiles.extract_files_from_ef_tree(
                node, directory_path,
            )

    @staticmethod
    def extract_files(
        names: dict[str, Any] | None, directory_path: str,
    ) -> None:
        """Mirrors ``extractFiles(Map, String)`` (line 125)."""
        if names is None:
            return
        for _key, file_spec in names.items():
            embedded_file = ExtractEmbeddedFiles.get_embedded_file(file_spec)
            if embedded_file is None:
                continue
            filename = (
                file_spec.get_filename()
                if hasattr(file_spec, "get_filename")
                else _key
            )
            ExtractEmbeddedFiles.extract_file(
                filename, embedded_file, directory_path,
            )

    @staticmethod
    def extract_file(
        filename: str, embedded_file: Any, directory_path: str,
    ) -> None:
        """Mirrors ``extractFile(String, PDEmbeddedFile, String)`` (line 139).

        Refuses to write outside ``directory_path`` (path-traversal guard
        copied from upstream L144-150).
        """
        if embedded_file is None or filename is None:
            return
        out = Path(directory_path) / filename
        parent_canonical = str(out.resolve().parent)
        directory_canonical = str(Path(directory_path).resolve())
        if (
            parent_canonical != directory_canonical
            and not parent_canonical.startswith(
                directory_canonical + os.sep,
            )
        ):
            sys.stderr.write(
                f"Ignoring {filename} (different directory)\n",
            )
            return
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = embedded_file.to_byte_array()
        except AttributeError:
            payload = bytes(embedded_file)
        out.write_bytes(payload)

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (line 194)."""
        sys.stderr.write("Usage: ExtractEmbeddedFiles <input-pdf>\n")

    @staticmethod
    def get_embedded_file(file_spec: Any) -> Any:
        """Mirrors ``getEmbeddedFile`` (line 164)."""
        if file_spec is None:
            return None
        for attr in (
            "get_embedded_file_unicode",
            "get_embedded_file_dos",
            "get_embedded_file_mac",
            "get_embedded_file_unix",
            "get_embedded_file",
        ):
            getter = getattr(file_spec, attr, None)
            if getter is None:
                continue
            try:
                result = getter()
            except Exception:  # noqa: BLE001
                result = None
            if result is not None:
                return result
        return None
