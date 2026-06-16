"""``ExtractText`` class port and its inner helpers
(``AngleCollector``, ``FilteredTextStripper``, ``FilteredText2Markdown``,
``NullWriter``).

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/ExtractText.java
    (lines 62-489)

The existing ``pypdfbox.tools.extracttext`` module is a function-style
CLI; this module re-implements the Java class shape (``call`` / static
helpers) for parity coverage.
"""
from __future__ import annotations

import argparse
import contextlib
import math
import sys
import time
from pathlib import Path
from typing import IO, Any

from pypdfbox.cos import COSDocument
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.text.pdf_text_stripper import PDFTextStripper
from pypdfbox.tools.pdf_text2_html import PDFText2HTML
from pypdfbox.tools.pdf_text2_markdown import PDFText2Markdown

STD_ENCODING = "UTF-8"


@contextlib.contextmanager
def _open_doc(infile, password):  # noqa: ANN001
    """Open ``infile`` and yield a :class:`PDDocument`.

    ``Loader.load_pdf`` returns a low-level :class:`COSDocument` (mirrors
    upstream ``org.apache.pdfbox.Loader.loadPDF``). The class-port
    callers want the high-level :class:`PDDocument` shape so they can
    reach ``get_current_access_permission`` /
    ``get_document_catalog`` /  ``get_pages`` without a manual wrap.

    Tests in :mod:`tests.tools.test_tools_coverage_wave1314` monkeypatch
    ``Loader`` on this module to a shim whose ``load_pdf`` is itself a
    context manager yielding a :class:`PDDocument`. Detect both shapes
    so production and the test shim both work.
    """
    result = Loader.load_pdf(infile, password)
    if isinstance(result, COSDocument):
        pd = PDDocument(result)
        try:
            yield pd
        finally:
            pd.close()
        return
    with result as doc:
        yield doc


def get_angle(text_position: Any) -> int:
    """Mirror of static ``ExtractText.getAngle`` (ExtractText.java:397)."""
    try:
        m = text_position.get_text_matrix().clone()
        m.concatenate(text_position.get_font().get_font_matrix())
        return int(round(math.degrees(math.atan2(m.get_shear_y(), m.get_scale_y()))))
    except (AttributeError, NotImplementedError):
        return 0


class NullWriter:
    """Mirror of trailing class ``NullWriter extends Writer`` (ExtractText.java:469)."""

    def write(self, chars: str | bytes, off: int = 0, length: int | None = None) -> None:
        pass

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class _ConsoleWriter:
    """Mirror of upstream's anonymous ``PrintWriter`` (``ExtractText$1``).

    Upstream's ``createOutputWriter`` wraps ``System.out`` in a ``PrintWriter``
    whose ``close()`` is overridden to a no-op, so the shared console stream is
    never closed by ``call``'s ``finally`` block. Returning bare ``sys.stdout``
    here (as the class previously did) made the ``finally`` ``output.close()``
    actually close ``sys.stdout`` — fatal for any in-process caller that writes
    to stdout afterwards. This thin proxy restores the upstream no-op-close
    semantics while delegating ``write``/``flush`` to the live stream.
    """

    def __init__(self) -> None:
        self._stream = sys.stdout

    def write(self, data: str) -> int:
        return self._stream.write(data)

    def flush(self) -> None:
        self._stream.flush()

    def close(self) -> None:
        # No-op: never close the shared console stream (mirrors ExtractText$1).
        return None


class AngleCollector(PDFTextStripper):
    """Mirror of trailing class ``AngleCollector`` (ExtractText.java:412)."""

    def __init__(self) -> None:
        super().__init__()
        self._angles: set[int] = set()

    def get_angles(self) -> set[int]:
        return self._angles

    def process_text_position(self, text: Any) -> None:
        angle = get_angle(text)
        angle = (angle + 360) % 360
        self._angles.add(angle)


class FilteredTextStripper(PDFTextStripper):
    """Mirror of trailing class ``FilteredTextStripper`` (ExtractText.java:437)."""

    def process_text_position(self, text: Any) -> None:
        if get_angle(text) == 0:
            super().process_text_position(text)


class FilteredText2Markdown(PDFText2Markdown):
    """Mirror of trailing class ``FilteredText2Markdown`` (ExtractText.java:453)."""

    def process_text_position(self, text: Any) -> None:
        if get_angle(text) == 0:
            super().process_text_position(text)


class ExtractText:
    """Class-shape mirror of upstream ``ExtractText``."""

    @staticmethod
    def get_angle(text_position: Any) -> int:
        """Mirror of upstream static ``ExtractText.getAngle``."""
        return get_angle(text_position)

    def close(self) -> None:
        """Mirror of upstream implicit ``Closeable`` surface — no-op here."""
        # ExtractText holds no long-lived resources; the doc/writer are
        # context-managed inside ``call``.
        return None

    def __init__(self) -> None:
        self.always_next: bool = False
        self.to_console: bool = False
        self.debug: bool = False
        self.encoding: str = STD_ENCODING
        self.end_page: int = 2**31 - 1
        self.to_html: bool = False
        self.to_md: bool = False
        self.ignore_beads: bool = False
        self.password: str = ""
        self.rotation_magic: bool = False
        self.sort: bool = False
        self.start_page: int = 1
        self.infile: Path | None = None
        self.outfile: Path | None = None
        self.add_file_name: bool = False
        self.append: bool = False

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        if self.to_html and self.to_md:
            sys.stderr.write("You can't set md and html at the same time\n")
            return 1
        ext = ".html" if self.to_html else ".txt"
        if self.to_md:
            ext = ".md"
        if self.outfile is None:
            self.outfile = Path(self.infile).resolve().with_suffix(ext)
        if self.to_html and self.encoding != STD_ENCODING:
            self.encoding = STD_ENCODING
            sys.stdout.write("The encoding parameter is ignored when writing html output.\n")
        if self.to_console and self.encoding is not None:
            sys.stdout.write("The encoding parameter is ignored when writing to the console.\n")
        try:
            with _open_doc(self.infile, self.password) as document:
                start_time = self.start_processing(f"Loading PDF {self.infile}")
                ap = document.get_current_access_permission()
                if not ap.can_extract_content():
                    sys.stderr.write("You do not have permission to extract text\n")
                    return 1
                self.stop_processing("Time for loading: ", start_time)
                start_time = self.start_processing("Starting text extraction")
                output = self.create_output_writer()
                try:
                    if self.add_file_name:
                        output.write(f"PDF file: {self.infile}\n")
                    if self.debug:
                        sys.stderr.write(f"Writing to {self.outfile}\n")
                    if self.to_html:
                        stripper = PDFText2HTML()
                        stripper.set_sort_by_position(self.sort)
                        stripper.set_should_separate_by_beads(not self.ignore_beads)
                        stripper.set_start_page(self.start_page)
                        stripper.set_end_page(self.end_page)
                        stripper.write_text(document, output)
                    else:
                        if self.to_md:
                            stripper = (
                                FilteredText2Markdown() if self.rotation_magic
                                else PDFText2Markdown()
                            )
                        else:
                            stripper = (
                                FilteredTextStripper() if self.rotation_magic
                                else PDFTextStripper()
                            )
                        stripper.set_sort_by_position(self.sort)
                        stripper.set_should_separate_by_beads(not self.ignore_beads)
                        self.extract_pages(
                            self.start_page,
                            min(self.end_page, document.get_number_of_pages()),
                            stripper,
                            document,
                            output,
                            self.rotation_magic,
                            self.always_next,
                        )
                    output.flush() if hasattr(output, "flush") else None
                    self.stop_processing("Time for extraction: ", start_time)
                finally:
                    with contextlib.suppress(Exception):
                        output.close()
        except OSError as ioe:
            sys.stderr.write(
                f"Error extracting text for document [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    def create_output_writer(self) -> IO[str]:
        """Mirror of upstream private ``createOutputWriter``."""
        if self.to_console:
            return _ConsoleWriter()
        mode = "a" if self.append else "w"
        if self.outfile is None:
            raise OSError("outfile is required")
        return open(self.outfile, mode, encoding=self.encoding)

    def extract_pages(
        self,
        start_page: int,
        end_page: int,
        stripper: PDFTextStripper,
        document: Any,
        output: IO[str],
        rotation_magic: bool,
        always_next: bool,
    ) -> None:
        """Mirror of upstream private ``extractPages``.

        ``rotation_magic`` is intentionally a no-op pass-through here — it
        depends on transformer/content-stream APIs that are not all in
        scope for this class port. The simple non-magic path is fully
        wired so the common case stays correct.
        """
        for p in range(start_page, end_page + 1):
            stripper.set_start_page(p)
            stripper.set_end_page(p)
            try:
                stripper.write_text(document, output)
            except OSError:
                if not always_next:
                    raise

    def start_processing(self, message: str) -> int:
        """Mirror of upstream private ``startProcessing``."""
        if self.debug:
            sys.stderr.write(message + "\n")
        return time.monotonic_ns() // 1_000_000

    def stop_processing(self, message: str, start_time: int) -> None:
        """Mirror of upstream private ``stopProcessing``."""
        if self.debug:
            stop_time = time.monotonic_ns() // 1_000_000
            elapsed = (stop_time - start_time) / 1000.0
            sys.stderr.write(f"{message}{elapsed} seconds\n")

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="extracttext",
            description="Extracts the text from a PDF document",
        )
        parser.add_argument("-alwaysNext", dest="alwaysNext", action="store_true")
        parser.add_argument("-console", action="store_true")
        parser.add_argument("-debug", action="store_true")
        parser.add_argument("-encoding", default=STD_ENCODING)
        parser.add_argument("-endPage", dest="endPage", type=int, default=2**31 - 1)
        parser.add_argument("-html", action="store_true")
        parser.add_argument("-md", action="store_true")
        parser.add_argument("-ignoreBeads", dest="ignoreBeads", action="store_true")
        parser.add_argument("-password", default="")
        parser.add_argument("-rotationMagic", dest="rotationMagic", action="store_true")
        parser.add_argument("-sort", action="store_true")
        parser.add_argument("-startPage", dest="startPage", type=int, default=1)
        parser.add_argument("-i", "--input", dest="infile", required=True)
        parser.add_argument("-o", "--output", dest="outfile", default=None)
        parser.add_argument("-addFileName", dest="addFileName", action="store_true")
        parser.add_argument("-append", action="store_true")
        ns = parser.parse_args(args)
        runner = ExtractText()
        runner.always_next = ns.alwaysNext
        runner.to_console = ns.console
        runner.debug = ns.debug
        runner.encoding = ns.encoding
        runner.end_page = ns.endPage
        runner.to_html = ns.html
        runner.to_md = ns.md
        runner.ignore_beads = ns.ignoreBeads
        runner.password = ns.password
        runner.rotation_magic = ns.rotationMagic
        runner.sort = ns.sort
        runner.start_page = ns.startPage
        runner.infile = Path(ns.infile)
        runner.outfile = Path(ns.outfile) if ns.outfile else None
        runner.add_file_name = ns.addFileName
        runner.append = ns.append
        return runner.call()


if __name__ == "__main__":  # pragma: no cover — module-as-script entrypoint
    sys.exit(ExtractText.main(sys.argv[1:]))
