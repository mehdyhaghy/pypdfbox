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

_SUBCOMMANDS = {
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


if __name__ == "__main__":
    sys.exit(PDFBox.main(sys.argv[1:]))
