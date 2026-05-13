"""Bundled TTFs for Standard 14 font substitution.

When a PDF references one of the 14 Standard PostScript names (Helvetica,
Times-Roman, Courier, Symbol, ZapfDingbats) **without** embedding the
font program (no ``/FontFile``, no ``/FontFile3``), the renderer falls
back to a bundled substitute TTF carried in this package:

* ``LiberationSans*``    — Helvetica family (Regular / Bold / Italic /
  BoldItalic) — metric-compatible with Arial / Helvetica.
* ``LiberationSerif*``   — Times-Roman family — metric-compatible with
  Times New Roman / Times.
* ``LiberationMono*``    — Courier family — metric-compatible with
  Courier New / Courier.
* ``DejaVuSans.ttf``     — Symbol & ZapfDingbats fallback. DejaVu Sans
  carries the full Zapf Dingbats Unicode block (U+2700-U+27BF) and the
  Greek-letter + math-operator portions of Adobe Symbol (84% glyph
  coverage; the remaining PUA-encoded variants are visually inert).

License chain:

* Liberation TTFs — redistributed under the SIL Open Font License 1.1
  (see :file:`LICENSE.txt`).
* DejaVu Sans — Bitstream Vera Fonts terms (BSD-style, no advertising
  clause) for the base outlines; DejaVu changes are in the public domain
  (see :file:`LICENSE-DejaVu.txt`).

The root :file:`NOTICE` carries the full upstream attribution chain
(Google + Red Hat + Liberation Reserved Font Name; Bitstream Vera +
Tavmjong Bah + DejaVu project).
"""
