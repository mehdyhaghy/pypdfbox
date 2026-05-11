"""Port of ``org.apache.pdfbox.examples.pdmodel.BengaliPdfGenerationHelloWorld`` (lines 44-206).

Lays out a Bengali Lohit-font text sample across one or more A4 pages.

Wave 1286 deviation
-------------------
Upstream bundles ``Lohit-Bengali.ttf`` and a multi-line
``bengali-samples.txt`` corpus inside the PDFBox jar. We don't
redistribute the TTF (project policy bans bundling external fonts) and
the corpus is fetched opportunistically (see
:meth:`get_bengali_text_from_file`). When the corpus is missing, we
fall back to a short hard-coded Bengali sample so ``main()`` still
produces a non-empty PDF; when the font is missing, we fall back to
Standard-14 Helvetica, which lacks Bengali coverage — the resulting
PDF therefore renders the Bengali codepoints as ``.notdef`` glyphs (or
silently drops them) but stays well-formed. Pass a TTF path as the
second argument to ``main()`` for upstream-faithful rendering.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# Fallback sample shown when the bundled corpus is not on the local
# filesystem. "এ একটি পরীক্ষা" — "this is a test" in Bengali.
_FALLBACK_SAMPLE: list[str] = ["এ একটি পরীক্ষা"]


def _read_bengali_lines(path: Path) -> list[str]:
    """Read ``path`` as UTF-8 and drop lines beginning with ``#``.

    Helper for :func:`BengaliPdfGenerationHelloWorld.get_bengali_text_from_file`
    — mirrors the upstream comment filter (L196-199).
    """
    lines: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            if line.startswith("#"):
                continue
            lines.append(line)
    return lines


class BengaliPdfGenerationHelloWorld:
    """Mirrors ``BengaliPdfGenerationHelloWorld`` (line 44)."""

    LINE_GAP: int = 5
    LOHIT_BENGALI_TTF: str = "/org/apache/pdfbox/resources/ttf/Lohit-Bengali.ttf"
    TEXT_SOURCE_FILE: str = "/org/apache/pdfbox/resources/ttf/bengali-samples.txt"
    FONT_SIZE: int = 20
    MARGIN: int = 20

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 56).

        Required positional argument: output PDF path. Optional second
        positional argument: path to a Bengali-shaping TTF (e.g.
        ``Lohit-Bengali.ttf``). When the TTF path is omitted the demo
        falls back to Standard-14 Helvetica — see the module docstring
        for the deviation.
        """
        argv = argv if argv is not None else []
        if len(argv) < 1:
            sys.stderr.write(
                "usage: BengaliPdfGenerationHelloWorld <output-file> "
                "[<ttf-file>]\n",
            )
            raise SystemExit(1)
        filename = argv[0]
        ttf_path = Path(argv[1]) if len(argv) >= 2 else None
        sys.stdout.write(
            f"The generated pdf filename is: {filename}\n",
        )

        lines = BengaliPdfGenerationHelloWorld.get_bengali_text_from_file()
        if not lines:
            lines = list(_FALLBACK_SAMPLE)

        with PDDocument() as doc:
            font: PDFont
            if ttf_path is not None and ttf_path.is_file():
                font = PDType0Font.load(doc, ttf_path)
            else:
                # Helvetica fallback. Bengali codepoints won't render
                # correctly, but the file stays well-formed.
                font = make_standard14_type1_font(FontName.HELVETICA)

            rectangle = BengaliPdfGenerationHelloWorld.get_page_size()
            workable_page_width = (
                rectangle.get_width()
                - 2 * BengaliPdfGenerationHelloWorld.MARGIN
            )
            workable_page_height = (
                rectangle.get_height()
                - 2 * BengaliPdfGenerationHelloWorld.MARGIN
            )

            try:
                width_aligned = (
                    BengaliPdfGenerationHelloWorld
                    .get_re_aligned_text_based_on_page_width(
                        lines, font, workable_page_width,
                    )
                )
                paged_texts = (
                    BengaliPdfGenerationHelloWorld
                    .get_re_aligned_text_based_on_page_height(
                        width_aligned, font, workable_page_height,
                    )
                )
            except (ValueError, KeyError, OSError, TypeError, AttributeError):
                # Width-aware reflow needs the font to encode every
                # codepoint *and* expose a /FontDescriptor /FontBBox.
                # The Helvetica fallback satisfies neither — degrade to
                # one line per source line so the demo still emits a
                # valid PDF.
                paged_texts = [lines]

            for lines_for_page in paged_texts:
                page = PDPage(BengaliPdfGenerationHelloWorld.get_page_size())
                doc.add_page(page)

                with PDPageContentStream(doc, page) as contents:
                    contents.begin_text()
                    contents.set_font(
                        font, BengaliPdfGenerationHelloWorld.FONT_SIZE,
                    )
                    contents.new_line_at_offset(
                        rectangle.get_lower_left_x()
                        + BengaliPdfGenerationHelloWorld.MARGIN,
                        rectangle.get_upper_right_y()
                        - BengaliPdfGenerationHelloWorld.MARGIN,
                    )

                    for line in lines_for_page:
                        try:
                            contents.show_text(line)
                        except (ValueError, KeyError, OSError, TypeError):
                            # Fallback: render an ASCII placeholder so the
                            # leading still advances the cursor and the
                            # output PDF stays well-formed.
                            contents.show_text("[skipped]")
                        contents.new_line_at_offset(
                            0,
                            -(
                                BengaliPdfGenerationHelloWorld.FONT_SIZE
                                + BengaliPdfGenerationHelloWorld.LINE_GAP
                            ),
                        )

                    contents.end_text()

            doc.save(filename)

    @staticmethod
    def get_page_size() -> PDRectangle:
        """Mirrors ``getPageSize()`` (line 175)."""
        return PDRectangle.A4

    @staticmethod
    def get_re_aligned_text_based_on_page_height(
        original_lines: list[str],
        font: PDFont,
        workable_page_height: float,
    ) -> list[list[str]]:
        """Mirrors ``getReAlignedTextBasedOnPageHeight`` (line 110).

        Splits a flat list of lines into page-sized chunks based on the
        font's bounding-box height multiplied by ``FONT_SIZE`` plus the
        leading gap.
        """
        bbox = font.get_font_descriptor().get_font_bounding_box()
        new_line_height = (
            bbox.get_height() / 1000
            * BengaliPdfGenerationHelloWorld.FONT_SIZE
            + BengaliPdfGenerationHelloWorld.LINE_GAP
        )
        realigned: list[list[str]] = []
        consumed_height = 0.0
        lines_in_a_page: list[str] = []
        for line in original_lines:
            if new_line_height + consumed_height < workable_page_height:
                consumed_height += new_line_height
            else:
                consumed_height = new_line_height
                realigned.append(lines_in_a_page)
                lines_in_a_page = []
            lines_in_a_page.append(line)
        realigned.append(lines_in_a_page)
        return realigned

    @staticmethod
    def get_re_aligned_text_based_on_page_width(
        original_lines: list[str],
        font: PDFont,
        workable_page_width: float,
    ) -> list[str]:
        """Mirrors ``getReAlignedTextBasedOnPageWidth`` (line 137).

        Walks ``original_lines`` token-by-token (whitespace-delimited,
        keeping the delimiter — mirrors Java's
        ``StringTokenizer(line, " ", true)``) and emits a flat list of
        page-width-fitting chunks.
        """
        uniformly_wide: list[str] = []
        consumed_width = 0.0
        sb: list[str] = []
        for line in original_lines:
            new_token_width = 0.0
            tokens = _tokenize_keep_separators(line, " ")
            for token in tokens:
                new_token_width = (
                    font.get_string_width(token) / 1000
                    * BengaliPdfGenerationHelloWorld.FONT_SIZE
                )
                if new_token_width + consumed_width < workable_page_width:
                    consumed_width += new_token_width
                else:
                    uniformly_wide.append("".join(sb))
                    consumed_width = new_token_width
                    sb = []
                sb.append(token)
            uniformly_wide.append("".join(sb))
            consumed_width = new_token_width
            sb = []
        return uniformly_wide

    @staticmethod
    def get_bengali_text_from_file() -> list[str]:
        """Mirrors ``getBengaliTextFromFile()`` (line 180).

        Upstream reads the resource from the classpath
        (``/org/apache/pdfbox/resources/ttf/bengali-samples.txt``). The
        pypdfbox port does not bundle the upstream resource jar — we
        look up the file via ``importlib.resources`` against
        ``pypdfbox.examples.pdmodel.resources``, then fall back to
        ``$PYPDFBOX_RESOURCE_DIR`` (if set), and finally to the upstream
        repository path under the Python source tree. Returns an empty
        list when no candidate exists so the caller (``main()``) can
        short-circuit gracefully. Lines beginning with ``#`` are
        filtered out, mirroring upstream L196-199.
        """
        import os

        candidates: list[Path] = []

        # Search-strategy 1: bundled package data.
        try:
            from importlib import resources as _resources

            ref = _resources.files(
                "pypdfbox.examples.pdmodel",
            ).joinpath("resources/ttf/bengali-samples.txt")
            if ref.is_file():
                with _resources.as_file(ref) as path:
                    return _read_bengali_lines(path)
        except (ModuleNotFoundError, FileNotFoundError, AttributeError):
            pass

        # Search-strategy 2: env-var override (pypdfbox extension).
        env_dir = os.environ.get("PYPDFBOX_RESOURCE_DIR")
        if env_dir:
            candidates.append(
                Path(env_dir) / "ttf" / "bengali-samples.txt",
            )

        # Search-strategy 3: walk a few parents looking for a checked-out
        # PDFBox tree (developer convenience for the example).
        here = Path(__file__).resolve()
        for parent in (*here.parents[:6], Path("/tmp/pdfbox")):
            candidates.append(
                parent / "examples" / "src" / "main" / "resources"
                / "org" / "apache" / "pdfbox" / "resources" / "ttf"
                / "bengali-samples.txt",
            )

        for path in candidates:
            if path.is_file():
                return _read_bengali_lines(path)
        return []


def _tokenize_keep_separators(text: str, sep: str) -> list[str]:
    """Mimic Java's ``StringTokenizer(text, sep, true)``: keep the
    separator characters as their own tokens. Bengali shaping relies on
    word-level chunks, so this matters for the width-aware reflow.
    """
    if not text:
        return []
    tokens: list[str] = []
    current: list[str] = []
    for ch in text:
        if ch in sep:
            if current:
                tokens.append("".join(current))
                current = []
            tokens.append(ch)
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens
