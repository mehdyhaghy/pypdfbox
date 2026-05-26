"""Live Apache PDFBox differential parity tests for the glyph-name lists.

Runs the ``GlyphListProbe`` Java probe (``oracle/probes/GlyphListProbe.java``,
compiled against the pinned pdfbox-app-3.0.7 jar) over a battery of glyph
names against both the Adobe Glyph List (AGL) and the Zapf Dingbats list, then
asserts pypdfbox's :meth:`GlyphList.to_unicode` produces the identical Unicode
sequence (or ``None``) for every name.

In PDFBox 3.0.x the glyph list lives at
``org.apache.pdfbox.pdmodel.font.encoding.GlyphList`` (the FontBox encoding
package was folded into ``pdmodel.font.encoding``); the two singletons are
``getAdobeGlyphList()`` and ``getZapfDingbats()``. pypdfbox keeps it under the
mirrored ``pypdfbox.fontbox.encoding`` path.

The battery covers: common AGL names; the algorithmic ``uniXXXX`` / ``uXXXX``
synthesis (including the strict upstream length gating that makes ``u1F600``,
``u00041`` and multi-code-point ``uni...`` runs resolve to ``null``);
ligatures (``ff`` / ``ffi`` / ``fi``); ``.notdef``; ``name.suffix`` stripping;
multi-code-point AGL entries; surrogate-area rejection; and unknown names
(-> null). Java PDFBox is the reference; where pypdfbox diverged the
production code was fixed (see CHANGES.md / wave 1417).

Decorated ``@requires_oracle`` so they skip cleanly on machines without
Java + the jar — a developer-machine parity check, not a hard CI gate.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import logging

from pypdfbox.fontbox.encoding.glyph_list import GlyphList
from tests.oracle.harness import requires_oracle, run_probe_text

# Glyph-name battery exercised against BOTH lists. Order is irrelevant — the
# probe and pypdfbox are both queried name-by-name and compared per name.
_BATTERY: tuple[str, ...] = (
    # -- common AGL names ------------------------------------------------
    "A",
    "space",
    "bullet",
    "eacute",
    "Euro",
    "period",
    "zero",
    "Aacute",
    # -- algorithmic uniXXXX (length 7, one 4-hex code point) ------------
    "uni0041",
    "uni20AC",
    "uniABCD",
    "uniFFFF",
    "uni0000",
    # -- algorithmic uXXXX (length 5, one 4-hex code point) --------------
    "u0041",
    "u20AC",
    # -- u-forms upstream does NOT synthesize (wrong length) -> null -----
    "u1F600",
    "u00041",
    "u000041",
    "u041",
    # -- multi-code-point uni runs upstream does NOT synthesize -> null --
    "uni004100420043",
    "uni00410042",
    # -- ligatures (multi-code-point AGL values) -------------------------
    "ff",
    "ffi",
    "fi",
    "ffl",
    "fl",
    # -- surrogate / disallowed code area -> null ------------------------
    "uD800",
    "uniD800",
    "uDFFF",
    "uniDC00",
    # -- .notdef ---------------------------------------------------------
    ".notdef",
    # -- name.suffix stripping (foo.suffix -> foo) -----------------------
    "a.sc",
    "A.sc",
    "Lcommaaccent.alt",
    "space.alt",
    "g123.alt",
    "ff.alt",
    # -- multi-code-point named AGL entries ------------------------------
    "Lcommaaccent",
    "Dz",
    "ffi",
    "Tcommaaccent",
    # -- unknown names -> null -------------------------------------------
    "fi_lig",
    "foobarbaz",
    "notaglyph",
    "",
)


def _format(unicode: str | None) -> str:
    """Render a to_unicode result the same way GlyphListProbe.java does.

    ``None`` -> ``"NULL"``; otherwise space-separated ``U+XXXX`` (uppercase,
    >=4 hex digits) per Unicode scalar.
    """
    if unicode is None:
        return "NULL"
    return " ".join(f"U+{ord(c):04X}" for c in unicode)


def _oracle_lines(list_id: str) -> dict[str, str]:
    """Run the probe for ``list_id`` and parse ``name -> value`` lines."""
    out = run_probe_text("GlyphListProbe", list_id, *_BATTERY)
    result: dict[str, str] = {}
    for line in out.splitlines():
        if not line:
            continue
        name, _, value = line.partition(" -> ")
        result[name] = value
    return result


def _py_value(glyph_list: GlyphList, name: str) -> str:
    return _format(glyph_list.to_unicode(name))


@requires_oracle
def test_adobe_glyph_list_to_unicode_matches_pdfbox(caplog):
    """pypdfbox AGL to_unicode == PDFBox getAdobeGlyphList().toUnicode."""
    # Synthesis of disallowed/out-of-range names logs a warning; mirror
    # upstream behaviour without polluting the captured log at WARNING.
    caplog.set_level(logging.ERROR, logger="pypdfbox.fontbox.encoding.glyph_list")
    oracle = _oracle_lines("adobe")
    glyph_list = GlyphList.get_adobe_glyph_list()
    # The empty string is dropped by the probe (printf prints a line, but the
    # name token is empty) — assert it explicitly and exclude from the diff.
    assert glyph_list.to_unicode("") is None
    mismatches = {
        name: (_py_value(glyph_list, name), oracle.get(name))
        for name in _BATTERY
        if name and _py_value(glyph_list, name) != oracle.get(name)
    }
    assert not mismatches, f"AGL to_unicode diverges from PDFBox: {mismatches}"


@requires_oracle
def test_zapf_dingbats_to_unicode_matches_pdfbox(caplog):
    """pypdfbox Zapf to_unicode == PDFBox getZapfDingbats().toUnicode."""
    caplog.set_level(logging.ERROR, logger="pypdfbox.fontbox.encoding.glyph_list")
    oracle = _oracle_lines("zapf")
    glyph_list = GlyphList.get_zapf_dingbats()
    assert glyph_list.to_unicode("") is None
    mismatches = {
        name: (_py_value(glyph_list, name), oracle.get(name))
        for name in _BATTERY
        if name and _py_value(glyph_list, name) != oracle.get(name)
    }
    assert not mismatches, f"Zapf to_unicode diverges from PDFBox: {mismatches}"


@requires_oracle
def test_zapf_specific_glyph_names_match_pdfbox(caplog):
    """The Zapf-only ``aNN`` glyph names resolve identically to PDFBox."""
    caplog.set_level(logging.ERROR, logger="pypdfbox.fontbox.encoding.glyph_list")
    names = [f"a{n}" for n in range(1, 50)]
    out = run_probe_text("GlyphListProbe", "zapf", *names)
    oracle = {}
    for line in out.splitlines():
        if not line:
            continue
        name, _, value = line.partition(" -> ")
        oracle[name] = value
    glyph_list = GlyphList.get_zapf_dingbats()
    mismatches = {
        name: (_py_value(glyph_list, name), oracle.get(name))
        for name in names
        if _py_value(glyph_list, name) != oracle.get(name)
    }
    assert not mismatches, f"Zapf aNN names diverge from PDFBox: {mismatches}"
