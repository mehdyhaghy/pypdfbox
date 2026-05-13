"""Bundled binary resources (fonts, ICC profiles, …) shipped with the wheel.

Mirrors the spirit of upstream PDFBox's
``pdfbox/src/main/resources/org/apache/pdfbox/resources/`` tree: keep the
ancillary data that ships *inside* the package separate from source code
so :func:`importlib.resources.files` lookups remain stable across
installed vs editable installs.

Currently houses:

* :mod:`pypdfbox.resources.ttf` — the 12 Liberation TTFs used as
  Standard 14 substitution targets when a PDF references one of the
  canonical PostScript names (Helvetica / Times / Courier families)
  without embedding the font program. See
  :mod:`pypdfbox.pdmodel.font.standard14_fonts` for the mapping logic.
"""
