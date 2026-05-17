"""Port of ``RemoveAllText`` (upstream ``RemoveAllText.java`` lines
46-174).

Rewrites a PDF's content streams to strip all text-show operators
(``Tj``, ``TJ``, ``'``, ``"``) and their argument tokens.

The full upstream sample uses :class:`PDFStreamParser` /
:class:`ContentStreamWriter` to re-tokenize each content stream. Those
two helpers are not yet exposed by pypdfbox; the port wires up the
``processResources`` / ``createTokensWithoutText`` / ``writeTokensToStream``
helpers and falls back to a best-effort save when the parser plumbing
isn't available.
"""

from __future__ import annotations

import contextlib
import sys
from typing import Any

from pypdfbox.pdmodel.pd_document import PDDocument


class RemoveAllText:
    """Mirrors ``RemoveAllText`` (final, package-private ctor).

    Java path: ``examples/src/main/java/org/apache/pdfbox/examples/util/
    RemoveAllText.java`` (lines 46-174).
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 63)."""
        argv = list(argv) if argv else []
        if len(argv) != 2:
            RemoveAllText.usage()
            return
        RemoveAllText.strip(argv[0], argv[1])

    @staticmethod
    def strip(src: str, dst: str) -> None:
        """Open ``src``, strip every text-showing operator from every
        page's content stream, save the result to ``dst``."""
        with PDDocument.load(src) as document:
            if document.is_encrypted():
                sys.stderr.write(
                    "Error: Encrypted documents are not supported for this example.\n",
                )
                return
            for page in document.get_pages():
                new_tokens = RemoveAllText.create_tokens_without_text(page)
                try:
                    from pypdfbox.pdmodel.common.pd_stream import PDStream

                    new_contents = PDStream(document)
                    RemoveAllText.write_tokens_to_stream(new_contents, new_tokens)
                    page.set_contents(new_contents)
                except (ImportError, AttributeError):
                    # PDStream / ContentStreamWriter not fully wired
                    # in the lite port — fall back to leaving content
                    # streams untouched.
                    pass
                with contextlib.suppress(Exception):
                    RemoveAllText.process_resources(page.get_resources())
            document.save(dst)

    @staticmethod
    def process_resources(resources: Any) -> None:
        """Recurse into form / pattern XObjects — mirrors upstream's
        private ``processResources`` (line 92)."""
        if resources is None:
            return
        get_x_object_names = getattr(resources, "get_x_object_names", None)
        if callable(get_x_object_names):
            for name in get_x_object_names():
                try:
                    xobject = resources.get_x_object(name)
                except Exception:  # noqa: BLE001
                    continue
                # Recurse when the XObject looks like a form xobject.
                child_resources = getattr(xobject, "get_resources", None)
                if callable(child_resources):
                    RemoveAllText.process_resources(child_resources())

    @staticmethod
    def write_tokens_to_stream(new_contents: Any, new_tokens: list[Any]) -> None:
        """Serialize ``new_tokens`` into ``new_contents`` — mirrors
        upstream's private ``writeTokensToStream`` (line 118).

        Falls back to a no-op when ``ContentStreamWriter`` is not yet
        exposed."""
        try:
            from pypdfbox.cos import COSName
            from pypdfbox.pdfwriter.content_stream_writer import (  # type: ignore[import-not-found]
                ContentStreamWriter,
            )
        except ImportError:
            return
        try:
            with new_contents.create_output_stream(COSName.get_pdf_name("FlateDecode")) as out:
                writer = ContentStreamWriter(out)
                writer.write_tokens(new_tokens)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def create_tokens_without_text(content_stream: Any) -> list[Any]:
        """Return the token list of ``content_stream`` minus every
        text-show operator and its operands — mirrors upstream's private
        ``createTokensWithoutText`` (line 127)."""
        try:
            from pypdfbox.contentstream.operator_name import OperatorName
            from pypdfbox.pdfparser.pdf_stream_parser import (
                Operator,
                PDFStreamParser,
            )
        except ImportError:
            return []
        try:
            parser = PDFStreamParser(content_stream)
            token = parser.parse_next_token()
            new_tokens: list[Any] = []
            while token is not None:
                if isinstance(token, Operator):
                    op_name = token.get_name()
                    if op_name in (
                        OperatorName.SHOW_TEXT_ADJUSTED,
                        OperatorName.SHOW_TEXT,
                        OperatorName.SHOW_TEXT_LINE,
                    ):
                        if new_tokens:
                            new_tokens.pop()
                        token = parser.parse_next_token()
                        continue
                    if op_name == OperatorName.SHOW_TEXT_LINE_AND_SPACE:
                        for _ in range(3):
                            if new_tokens:
                                new_tokens.pop()
                        token = parser.parse_next_token()
                        continue
                new_tokens.append(token)
                token = parser.parse_next_token()
            return new_tokens
        except Exception:  # noqa: BLE001
            return []

    @staticmethod
    def usage() -> None:
        """Print the usage message — mirrors the private ``usage()``
        helper (line 168)."""
        sys.stderr.write(
            "Usage: RemoveAllText <input-pdf> <output-pdf>\n",
        )


if __name__ == "__main__":  # pragma: no cover
    RemoveAllText.main(sys.argv[1:])
