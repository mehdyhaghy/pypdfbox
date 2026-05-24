"""``PDFBox`` top-level command dispatcher class port.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/PDFBox.java
    (lines 37-84)

Upstream is a picocli ``Runnable`` that registers all subcommands.
The Python port registers the same subcommand names so callers can do
``PDFBox.main(["merge", ...])`` end-to-end.
"""
from __future__ import annotations

import sys

from pypdfbox.tools.decompress_objectstreams import DecompressObjectstreams
from pypdfbox.tools.decrypt_tool import Decrypt
from pypdfbox.tools.encrypt_tool import Encrypt
from pypdfbox.tools.export_fdf import ExportFDF
from pypdfbox.tools.export_xfdf import ExportXFDF
from pypdfbox.tools.extract_images import ExtractImages
from pypdfbox.tools.extract_text import ExtractText
from pypdfbox.tools.extract_xmp import ExtractXMP
from pypdfbox.tools.image_to_pdf import ImageToPDF
from pypdfbox.tools.import_fdf import ImportFDF
from pypdfbox.tools.import_xfdf import ImportXFDF
from pypdfbox.tools.overlay_pdf import OverlayPDF
from pypdfbox.tools.pdf_merger import PDFMerger
from pypdfbox.tools.pdf_split import PDFSplit
from pypdfbox.tools.pdf_to_image import PDFToImage
from pypdfbox.tools.print_pdf import PrintPDF
from pypdfbox.tools.text_to_pdf import TextToPDF
from pypdfbox.tools.version_tool import Version
from pypdfbox.tools.write_decoded_doc import WriteDecodedDoc


def _help(args: list[str] | None = None) -> int:
    """Mirror of upstream picocli ``CommandLine.HelpCommand``.

    ``pdfbox help`` lists the known subcommands; ``pdfbox help <cmd>``
    prints the help for that subcommand by re-invoking it with
    ``--help``.
    """
    if not args:
        sys.stdout.write(
            "Usage: pdfbox [COMMAND] [OPTIONS]\n\nCommands:\n"
        )
        for name in sorted(_SUBCOMMANDS):
            sys.stdout.write(f"  {name}\n")
        sys.stdout.write("  help\n")
        return 0
    name = args[0]
    cls = _SUBCOMMANDS.get(name)
    if cls is None:
        sys.stderr.write(f"Unknown command: {name}\n")
        return 2
    try:
        return int(cls.main(["--help"]) or 0)
    except SystemExit as exc:
        return int(exc.code or 0)


class _Help:
    """Adapter so ``help`` slots into the ``cls.main(args)`` dispatch shape."""

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        return _help(args or [])


def _debug_class():
    """Lazy import of :class:`PDFDebugger` so headless / Tk-less environments
    can still ``import pypdfbox.tools.pdf_box`` without paying the Tk cost.

    Upstream registers ``debug`` only when ``GraphicsEnvironment.isHeadless()``
    returns ``false``. pypdfbox keeps the subcommand always registered so
    callers can invoke ``pdfbox debug …`` from the CLI; the import error
    surfaces only when the command is actually executed.
    """
    from pypdfbox.debugger.pd_debugger import PDFDebugger  # noqa: PLC0415

    return PDFDebugger


class _Debug:
    """Adapter that lazy-loads the debugger class on dispatch."""

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        return int(_debug_class().main(args) or 0)


_SUBCOMMANDS = {
    "debug": _Debug,
    "decrypt": Decrypt,
    "encrypt": Encrypt,
    "decode": WriteDecodedDoc,
    "export:images": ExtractImages,
    "export:xmp": ExtractXMP,
    "export:text": ExtractText,
    "export:fdf": ExportFDF,
    "export:xfdf": ExportXFDF,
    "import:fdf": ImportFDF,
    "import:xfdf": ImportXFDF,
    "overlay": OverlayPDF,
    "print": PrintPDF,
    "render": PDFToImage,
    "merge": PDFMerger,
    "split": PDFSplit,
    "fromimage": ImageToPDF,
    "fromtext": TextToPDF,
    "version": Version,
    "help": _Help,
    # Extras (no upstream counterpart but useful for parity with PDFBox 3.x);
    # ``decompress`` corresponds to the (in 4.0) ``DecompressObjectstreams``
    # helper that upstream PDFBox keeps as a standalone main without
    # registering as a top-level subcommand.
    "decompress": DecompressObjectstreams,
}


class PDFBox:
    """Top-level CLI dispatcher, mirroring picocli's ``PDFBox``."""

    def run(self) -> None:
        # Upstream throws picocli.CommandLine.ParameterException — we
        # use SystemExit so argparse + cli machinery can handle it.
        raise SystemExit("Error: Subcommand required")

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        if args is None:
            args = sys.argv[1:]
        if not args:
            sys.stderr.write("Error: Subcommand required\n")
            return 2
        name, *rest = args
        cls = _SUBCOMMANDS.get(name)
        if cls is None:
            sys.stderr.write(f"Unknown command: {name}\n")
            return 2
        return int(cls.main(rest) or 0)


def _console_main() -> None:
    """Console-script entry point for the ``pdfbox`` script.

    pyproject.toml's ``[project.scripts]`` requires a zero-arg callable
    that handles its own ``sys.exit``; :meth:`PDFBox.main` returns the
    int exit code instead. This thin wrapper bridges the two.
    """
    sys.exit(PDFBox.main(sys.argv[1:]))


if __name__ == "__main__":  # pragma: no cover — module-as-script entrypoint
    sys.exit(PDFBox.main(sys.argv[1:]))
