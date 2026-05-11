"""Port of ``org.apache.pdfbox.examples.pdmodel.ExtractTTFFonts`` (lines 60-330).

Extracts all TrueType fonts embedded in a PDF document.
"""

from __future__ import annotations

import sys
from typing import Any


class ExtractTTFFonts:
    """Mirrors ``ExtractTTFFonts`` (final class)."""

    _PASSWORD: str = "-password"
    _PREFIX: str = "-prefix"
    _ADDKEY: str = "-addkey"

    def __init__(self) -> None:
        self._font_counter: int = 1
        self._font_set: set[object] = set()
        self._current_page: int = 0

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 82)."""
        argv = argv if argv is not None else []
        extractor = ExtractTTFFonts()
        extractor.extract_fonts(argv)

    def extract_fonts(self, argv: list[str]) -> None:
        """Mirrors ``extractFonts`` (line 88)."""
        del argv
        # TODO: needs PDCIDFont(Type2) + PDFontDescriptor.font_file2 +
        # resources.get_font / get_xobject / get_pattern / get_ext_g_state
        # surface — comprehensive font traversal pipeline.
        raise NotImplementedError(
            "ExtractTTFFonts awaits PDCIDFont + PDFontDescriptor + "
            "PDResources nested font traversal.",
        )

    def process_resources(
        self, resources: Any, prefix: str, add_key: bool,
    ) -> None:
        """Mirrors ``processResources`` (line 188)."""
        raise NotImplementedError(
            "process_resources awaits PDResources font traversal.",
        )

    def process_resources_fonts(
        self, resources: Any, add_key: bool, prefix: str,
    ) -> None:
        """Mirrors ``processResourcesFonts`` (line 199)."""
        raise NotImplementedError(
            "process_resources_fonts awaits PDResources font traversal.",
        )

    def process_nested_resources(
        self, resources: Any, prefix: str, add_key: bool,
    ) -> None:
        """Mirrors ``processNestedResources`` (line 249)."""
        raise NotImplementedError(
            "process_nested_resources awaits PDResources font traversal.",
        )

    def write_font(self, fd: Any, name: str) -> None:
        """Mirrors ``writeFont(PDFontDescriptor, String)`` (line 287)."""
        raise NotImplementedError(
            "write_font awaits PDFontDescriptor.font_file2 accessor.",
        )

    def get_unique_file_name(self, prefix: str, suffix: str) -> str:
        """Mirrors ``getUniqueFileName(String, String)`` (line 304)."""
        from pathlib import Path

        counter = 0
        while True:
            tail = "" if counter == 0 else f"-{counter}"
            candidate = f"{prefix}{tail}.{suffix}"
            if not Path(candidate).exists():
                return candidate
            counter += 1

    @staticmethod
    def usage() -> None:
        """Mirrors ``usage()`` (line 320)."""
        sys.stderr.write(
            "Usage: ExtractTTFFonts [OPTIONS] <PDF file>\n"
            "  -password  <password>        Password to decrypt document\n"
            "  -prefix  <font-prefix>       Font prefix(default to pdf name)\n"
            "  -addkey                      add the internal font key to the file name\n"
            "  <PDF file>                   The PDF document to use\n",
        )
        raise SystemExit(1)
