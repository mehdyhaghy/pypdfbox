"""Bundled Liberation TTFs for Standard 14 font substitution.

When a PDF references one of the 14 Standard PostScript names (Helvetica,
Times-Roman, Courier, …) **without** embedding the font program (no
``/FontFile``, no ``/FontFile3``), the renderer falls back to a metric-
compatible Liberation TTF carried in this package:

* ``LiberationSans*``    — Helvetica family (Regular / Bold / Italic /
  BoldItalic) — metric-compatible with Arial / Helvetica.
* ``LiberationSerif*``   — Times-Roman family — metric-compatible with
  Times New Roman / Times.
* ``LiberationMono*``    — Courier family — metric-compatible with
  Courier New / Courier.

The two remaining Standard 14 names (Symbol, ZapfDingbats) have no
Liberation equivalent — for those the renderer continues to fall back
to the placeholder rectangle.

The fonts are redistributed under the SIL Open Font License 1.1; see
:file:`LICENSE.txt` in this directory and the root :file:`NOTICE` for
the full attribution chain (Google + Red Hat + Liberation Reserved Font
Name preserved).
"""
