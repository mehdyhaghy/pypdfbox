"""Port of ``org.apache.pdfbox.examples.pdmodel.ExtractEmbeddedFiles`` (lines 42-198).

Extracts all embedded files from a PDF document.
"""

from __future__ import annotations

import sys
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
        # TODO: full extraction requires PDComplexFileSpecification +
        # PDEmbeddedFile + PDAnnotationFileAttachment binding.
        raise NotImplementedError(
            "ExtractEmbeddedFiles awaits complex file-specification + "
            "annotation.file-attachment plumbing.",
        )

    @staticmethod
    def extract_files_from_page(page: Any, directory_path: str) -> None:
        """Mirrors ``extractFilesFromPage(PDPage, String)`` (line 83)."""
        raise NotImplementedError(
            "extract_files_from_page awaits PDAnnotationFileAttachment plumbing.",
        )

    @staticmethod
    def extract_files_from_ef_tree(ef_tree: Any, directory_path: str) -> None:
        """Mirrors ``extractFilesFromEFTree(PDNameTreeNode, String)`` (line 104)."""
        raise NotImplementedError(
            "extract_files_from_ef_tree awaits PDNameTreeNode traversal.",
        )

    @staticmethod
    def extract_files(
        names: dict[str, Any] | None, directory_path: str,
    ) -> None:
        """Mirrors ``extractFiles(Map, String)`` (line 125)."""
        if names is None:
            return
        for filename, file_spec in names.items():
            embedded_file = ExtractEmbeddedFiles.get_embedded_file(file_spec)
            ExtractEmbeddedFiles.extract_file(
                filename, embedded_file, directory_path,
            )

    @staticmethod
    def extract_file(
        filename: str, embedded_file: Any, directory_path: str,
    ) -> None:
        """Mirrors ``extractFile(String, PDEmbeddedFile, String)`` (line 139)."""
        if embedded_file is None:
            return
        from pathlib import Path

        out = Path(directory_path) / filename
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
