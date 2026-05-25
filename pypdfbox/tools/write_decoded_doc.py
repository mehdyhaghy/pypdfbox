"""``WriteDecodedDoc`` class port — saves a PDF with all streams decoded.

Upstream Java reference:
    pdfbox/tools/src/main/java/org/apache/pdfbox/tools/WriteDecodedDoc.java
    (lines 46-178)
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from pypdfbox.cos import COSDocument
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_stream import COSStream
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.common.pd_stream import PDStream
from pypdfbox.pdmodel.pd_document import PDDocument


@contextlib.contextmanager
def _open_doc(infile, password):  # noqa: ANN001
    """Open ``infile`` and yield a :class:`PDDocument`. See
    :func:`pypdfbox.tools.extract_text._open_doc`."""
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


class WriteDecodedDoc:
    def __init__(self) -> None:
        self.password: str | None = None
        self.skip_images: bool = False
        self.infile: Path | None = None
        self.outfile: Path | None = None

    def do_it(
        self,
        in_path: str | Path,
        out_path: str | Path,
        password: str | None,
        skip_images: bool,
    ) -> None:
        """Mirror of ``WriteDecodedDoc.doIt`` (upstream WriteDecodedDoc.java:82)."""
        with _open_doc(in_path, password) as doc:
            doc.set_all_security_to_be_removed(True)
            cos_doc = doc.get_document()
            try:
                xref_keys = list(cos_doc.get_xref_table().keys())
            except AttributeError:
                xref_keys = []
            for key in xref_keys:
                obj = cos_doc.get_object_from_pool(key)
                if obj is not None:  # pragma: no branch
                    # Defensive: get_object_from_pool always returns a
                    # live COSBase for keys harvested from the xref
                    # table; the False arm has no live caller.
                    self.process_object(obj, skip_images)
            doc.get_document_catalog()
            with contextlib.suppress(AttributeError):
                cos_doc.set_is_xref_stream(False)
            doc.save(out_path)

    def process_object(self, cos_object, skip_images: bool) -> None:
        """Mirror of upstream private ``processObject``."""
        base = cos_object.get_object() if hasattr(cos_object, "get_object") else cos_object
        if not isinstance(base, COSStream):
            return
        stream = base
        if skip_images and stream.get_item(COSName.TYPE) == COSName.XOBJECT \
                and stream.get_item(COSName.SUBTYPE) == COSName.IMAGE:
            return
        try:
            data = PDStream(stream).to_byte_array()
            stream.remove_item(COSName.FILTER)
            with stream.create_output_stream() as out:
                out.write(data)
        except OSError as ex:
            key = getattr(cos_object, "get_key", lambda: "?")()
            sys.stderr.write(f"skip {key} obj: {ex}\n")

    def call(self) -> int:
        if self.infile is None:
            raise OSError("infile is required")
        if self.outfile is None:
            output_filename = self.calculate_output_filename(str(self.infile))
        else:
            output_filename = str(Path(self.outfile).resolve())
        try:
            self.do_it(self.infile, output_filename, self.password, self.skip_images)
        except OSError as ioe:
            sys.stderr.write(
                f"Error writing decoded PDF [{type(ioe).__name__}]: {ioe}\n"
            )
            return 4
        return 0

    @staticmethod
    def calculate_output_filename(filename: str) -> str:
        """Mirror of upstream private static ``calculateOutputFilename``."""
        base = filename[:-4] if filename.lower().endswith(".pdf") else filename
        return base + "_unc.pdf"

    @staticmethod
    def main(args: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="writedecodeddoc",
            description="Writes a PDF document with all streams decoded",
        )
        parser.add_argument("-password", default=None)
        parser.add_argument(
            "-skipImages", dest="skipImages", action="store_true", default=False,
        )
        parser.add_argument("inputfile")
        parser.add_argument("outputfile", nargs="?", default=None)
        ns = parser.parse_args(args)
        runner = WriteDecodedDoc()
        runner.password = ns.password
        runner.skip_images = ns.skipImages
        runner.infile = Path(ns.inputfile)
        runner.outfile = Path(ns.outputfile) if ns.outputfile else None
        return runner.call()


if __name__ == "__main__":
    sys.exit(WriteDecodedDoc.main(sys.argv[1:]))
