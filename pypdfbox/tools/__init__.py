"""
Command-line tools for pypdfbox. Mirrors ``org.apache.pdfbox.tools``.

Cluster #1 ships dependency-light subcommands that build only on the
io / cos / parser / writer / pdmodel core:

- ``info``               — print PDF metadata (version, page count, /Info dict)
- ``merge``              — concatenate input PDFs into one output
- ``split``              — split a PDF into per-page (or per-N-page) files
- ``version``            — print pypdfbox + Python + dependency versions
- ``decrypt``            — strip encryption (cluster #1 is no-op-on-unencrypted only)
- ``writedecodedstream`` — rewrite a PDF with all streams decoded (filter pipeline)

Deferred to later clusters (each requires heavier subsystems):

- ``encrypt``           — needs the security cluster (pdmodel #10)
- ``export:text``       — needs the text-extraction cluster
- ``export:images``     — needs the image-decoding cluster
- ``render``            — needs the rendering cluster
- ``overlay``           — needs PDFOverlay (pdmodel)
- ``debug``             — needs PDFDebugger (Swing-based; CLI-only port TBD)

Entry point: ``pypdfbox.tools.cli:main`` — registered as the ``pypdfbox``
console script in ``pyproject.toml``.
"""
from __future__ import annotations

from .cli import main, run_cli

__all__ = ["main", "run_cli"]
