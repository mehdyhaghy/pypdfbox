"""Port of ``org.apache.pdfbox.examples.pdmodel.ExtractTTFFonts`` (lines 60-330).

Extracts all TrueType fonts embedded in a PDF document.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any


class ExtractTTFFonts:
    """Mirrors ``ExtractTTFFonts`` (final class)."""

    _PASSWORD: str = "-password"
    _PREFIX: str = "-prefix"
    _ADDKEY: str = "-addkey"

    def __init__(self) -> None:
        self._font_counter: int = 1
        self._font_set: set[int] = set()
        self._current_page: int = 0

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 82)."""
        argv = argv if argv is not None else []
        extractor = ExtractTTFFonts()
        extractor.extract_fonts(argv)

    def extract_fonts(self, argv: list[str]) -> None:
        """Mirrors ``extractFonts`` (line 88)."""
        if len(argv) < 1 or len(argv) > 4:
            ExtractTTFFonts.usage()
            return  # pragma: no cover — usage() raises SystemExit; parity mirror

        pdf_file: str | None = None
        password = ""
        prefix: str | None = None
        add_key = False
        i = 0
        while i < len(argv):
            token = argv[i]
            if token == self._PASSWORD:
                i += 1
                if i >= len(argv):
                    ExtractTTFFonts.usage()
                    return  # pragma: no cover — usage() raises SystemExit; parity mirror
                password = argv[i]
            elif token == self._PREFIX:
                i += 1
                if i >= len(argv):
                    ExtractTTFFonts.usage()
                    return  # pragma: no cover — usage() raises SystemExit; parity mirror
                prefix = argv[i]
            elif token == self._ADDKEY:
                add_key = True
            else:
                if pdf_file is None:
                    pdf_file = token
            i += 1

        if pdf_file is None:
            ExtractTTFFonts.usage()
            return  # pragma: no cover — usage() raises SystemExit; parity mirror

        if prefix is None and len(pdf_file) > 4:
            prefix = pdf_file[:-4]

        from pypdfbox.loader import Loader
        from pypdfbox.pdmodel.pd_document import PDDocument

        with Loader.load_pdf(Path(pdf_file), password) as cos_doc:
            document = PDDocument(cos_doc)
            acro_form = document.get_document_catalog().get_acro_form()
            if acro_form is not None:
                self.process_resources(
                    acro_form.get_default_resources(), prefix, add_key,
                )
            page_tree = document.get_pages()
            for page in page_tree:
                self._current_page = page_tree.index_of(page) + 1
                self.process_resources(
                    page.get_resources(), prefix, add_key,
                )
                for annotation in page.get_annotations():
                    nas = annotation.get_normal_appearance_stream()
                    if nas is not None:
                        self.process_resources(
                            nas.get_resources(), prefix, add_key,
                        )
                    appearance = annotation.get_appearance()
                    if appearance is None:
                        continue
                    nae = appearance.get_normal_appearance()
                    if nae is None:
                        continue
                    if nae.is_stream():
                        nas = nae.get_appearance_stream()
                        if nas is not None:
                            self.process_resources(
                                nas.get_resources(), prefix, add_key,
                            )
                    elif nae.is_sub_dictionary():
                        for stream in nae.get_sub_dictionary().values():
                            self.process_resources(
                                stream.get_resources(), prefix, add_key,
                            )

    def process_resources(
        self, resources: Any, prefix: str | None, add_key: bool,
    ) -> None:
        """Mirrors ``processResources`` (line 188)."""
        if resources is None:
            return
        self.process_resources_fonts(resources, add_key, prefix)
        self.process_nested_resources(resources, prefix, add_key)

    def process_resources_fonts(
        self, resources: Any, add_key: bool, prefix: str | None,
    ) -> None:
        """Mirrors ``processResourcesFonts`` (line 199)."""
        from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
        from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
        from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

        for key in resources.get_font_names():
            font = resources.get_font(key)
            if font is None:
                continue
            try:
                font_name = font.get_name()
            except AttributeError:
                font_name = None
            sys.stdout.write(
                f"{font_name if font_name is not None else '(null)'} "
                f"on page {self._current_page}\n",
            )
            cos = font.get_cos_object()
            cos_id = id(cos)
            if cos_id in self._font_set:
                continue
            self._font_set.add(cos_id)

            descriptor = None
            if isinstance(font, PDTrueTypeFont):
                descriptor = font.get_font_descriptor()
            elif isinstance(font, PDType0Font):
                descendant = font.get_descendant_font()
                if isinstance(descendant, PDCIDFontType2):
                    descriptor = descendant.get_font_descriptor()

            if descriptor is None:
                continue

            base = prefix if prefix is not None else "font"
            key_str = key.get_name() if hasattr(key, "get_name") else str(key)
            seed = f"{base}_{key_str}" if add_key else base
            name = self.get_unique_file_name(seed, "ttf")
            self.write_font(descriptor, name)

    def process_nested_resources(
        self, resources: Any, prefix: str | None, add_key: bool,
    ) -> None:
        """Mirrors ``processNestedResources`` (line 249)."""
        from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
        from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import (
            PDTilingPattern,
        )

        for name in resources.get_xobject_names():
            xobject = resources.get_xobject(name)
            if isinstance(xobject, PDFormXObject):
                self.process_resources(
                    xobject.get_resources(), prefix, add_key,
                )

        for name in resources.get_pattern_names():
            pattern = resources.get_pattern(name)
            if isinstance(pattern, PDTilingPattern):
                self.process_resources(
                    pattern.get_resources(), prefix, add_key,
                )

        for name in resources.get_ext_g_state_names():
            ext_g_state = resources.get_ext_g_state(name)
            if ext_g_state is None:
                continue
            soft_mask = (
                ext_g_state.get_soft_mask_typed()
                if hasattr(ext_g_state, "get_soft_mask_typed")
                else None
            )
            if soft_mask is None:
                continue
            group = soft_mask.get_group()
            if group is not None and hasattr(group, "get_resources"):
                self.process_resources(
                    group.get_resources(), prefix, add_key,
                )

    def write_font(self, fd: Any, name: str) -> None:
        """Mirrors ``writeFont(PDFontDescriptor, String)`` (line 287)."""
        if fd is None:
            return
        ff2_stream = fd.get_font_file2()
        if ff2_stream is None:
            return
        out_path = Path(name + ".ttf")
        sys.stdout.write(f"Writing font: {out_path}\n")
        with out_path.open("wb") as out_fh:
            src = ff2_stream.create_input_stream()
            try:
                shutil.copyfileobj(src, out_fh)
            finally:
                close = getattr(src, "close", None)
                if callable(close):
                    close()

    def get_unique_file_name(self, prefix: str, suffix: str) -> str:
        """Mirrors ``getUniqueFileName(String, String)`` (line 304).

        Walks the ``-1, -2, …`` suffix sequence until the candidate file does
        not exist (upstream Java semantics).
        """
        while True:
            unique = f"{prefix}-{self._font_counter}"
            self._font_counter += 1
            if not Path(unique + "." + suffix).exists():
                return unique

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
