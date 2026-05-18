"""
Command-line tools for pypdfbox. Mirrors ``org.apache.pdfbox.tools``.

Subcommands wired into ``pypdfbox.tools.cli``:

- ``info``               — print PDF metadata (version, page count, /Info dict)
- ``merge``              — concatenate input PDFs into one output
- ``split``              — split a PDF into per-page (or per-N-page) files
- ``version``            — print pypdfbox + Python + dependency versions
- ``decrypt``            — strip encryption from an encrypted PDF
- ``encrypt``            — apply Standard-handler encryption to a PDF
- ``extracttext``        — extract Unicode text content
- ``imagetopdf``         — pack images into a one-image-per-page PDF
- ``texttopdf``          — typeset a plain-text file onto a new PDF
- ``listbookmarks``      — print the outline / bookmark hierarchy
- ``pdfdebugger``        — Tkinter PDFDebugger (mirrors the upstream Swing port)
- ``writedecodedstream`` — rewrite a PDF with all streams decoded (filter pipeline)

Deferred to later clusters (each requires heavier subsystems):

- ``export:images``     — needs the image-decoding cluster (partial —
  JPEG / lossless extraction already ships)
- ``render``            — bundled rendering surface (the rendering cluster
  ships, but the CLI shortcut is not yet wired)
- ``overlay``           — needs PDFOverlay (pdmodel)

Entry point: ``pypdfbox.tools.cli:main`` — registered as the ``pypdfbox``
console script in ``pyproject.toml``.
"""
from __future__ import annotations

from .cli import main, run_cli

__all__ = ["main", "run_cli"]
