"""Port of ``org.apache.pdfbox.examples.pdmodel.AddMetadataFromDocInfo`` (lines 42-112).

Mirrors the upstream example that copies document-info entries into the XMP
metadata stream.
"""

from __future__ import annotations

import sys


class AddMetadataFromDocInfo:
    """Mirrors ``AddMetadataFromDocInfo`` (final, utility class)."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 57)."""
        argv = argv if argv is not None else []
        if len(argv) != 2:
            AddMetadataFromDocInfo.usage()
            return
        # TODO: XMPBox schema helpers (AdobePDFSchema, XMPBasicSchema,
        # DublinCoreSchema, XmpSerializer) are not yet wired into pypdfbox's
        # examples surface. The example is a structural stub until the XMP
        # binding lands.
        raise NotImplementedError(
            "AddMetadataFromDocInfo requires XMPBox schema serialization; "
            "port pending xmpbox.schema bindings.",
        )

    @staticmethod
    def usage() -> None:
        sys.stderr.write(
            "Usage: AddMetadataFromDocInfo <input-pdf> <output-pdf>\n",
        )
