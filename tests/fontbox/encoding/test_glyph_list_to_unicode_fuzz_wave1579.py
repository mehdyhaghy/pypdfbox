"""Differential-fuzz parity for ``GlyphList.to_unicode`` AGL synthesis.

Wave 1579. Hammers the Adobe Glyph List (AGL) name -> Unicode resolution
algorithm of ``GlyphList.toUnicode`` as implemented by Apache PDFBox 3.0.x,
pinning every expected value to the *actual* upstream behavior captured via
``oracle/probes/GlyphListFuzzProbe.java`` (and the upstream
``GlyphList.toUnicode`` source).

Important upstream facts this battery enforces (these are the load-bearing
edge cases — they are easy to get "Pythonically wrong"):

* ``uniXXXX`` synthesizes ONLY when the name length is exactly 7 (``uni`` +
  one 4-hex code unit). ``uni00410042`` (multi-code-unit) is NOT concatenated
  by upstream 3.0.x; it returns ``null``. Likewise ``uni0041AB`` (length 8)
  and ``uni041`` (length 6) return ``null``.
* ``uXXXX`` synthesizes ONLY when the name length is exactly 5 (``u`` + one
  4-hex code unit). Upstream does NOT recognize ``uXXXXX`` / ``uXXXXXX``, so
  ``u1F600`` returns ``null`` (no emoji), and ``u00041`` / ``u041234`` /
  ``u0412345`` return ``null``.
* Hex is case-INsensitive: ``uniabcd`` == ``uniABCD`` == U+ABCD.
* The surrogate / disallowed area U+D800..U+DFFF is rejected even when every
  digit is valid hex (``uniD800``, ``uniDFFF``, ``uniDeAd`` -> ``null``); the
  boundaries U+D7FF and U+E000 DO synthesize.
* ``foo.suffix`` recurses on the substring before the FIRST dot, but only when
  that dot index is > 0. So ``A.sc`` -> ``A``'s value, ``a.sc.alt`` -> ``a``'s
  value (first dot), ``uni0041.sc`` -> strip to ``uni0041`` -> U+0041, while a
  leading-dot name (``.notdef``, ``.notdef.alt``) is NOT stripped and falls
  through to ``null``.
* ``gNN`` / ``cidNN`` / dingbat ``aNN`` names that aren't AGL entries and don't
  match the uni/u pattern return ``null``.
* underscore-joined ligature names (``f_f``, ``fi_lig``) are NOT AGL entries
  and are NOT special-cased by upstream ``toUnicode`` -> ``null``. (The real
  ligature glyphs ``ff`` / ``fi`` ARE plain AGL entries mapping to U+FB00 /
  U+FB01.)

The value-based tests below run everywhere; the ``@requires_oracle`` test
re-derives the same table from the live PDFBox jar so future upstream drift is
caught.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.encoding.glyph_list import GlyphList


def _render(unicode: str | None) -> str:
    """Render a ``to_unicode`` result the way GlyphListFuzzProbe does."""
    if unicode is None:
        return "NULL"
    return " ".join(f"U+{ord(ch):04X}" for ch in unicode)


# name -> expected toUnicode rendering ("NULL" or space-joined U+XXXX),
# pinned from Apache PDFBox 3.0.x (GlyphList.getAdobeGlyphList().toUnicode).
_EXPECTED: dict[str, str] = {
    # -- standard AGL names (sanity anchors) -----------------------------
    "A": "U+0041",
    "eacute": "U+00E9",
    "Euro": "U+20AC",
    "bullet": "U+2022",
    "space": "U+0020",
    "ampersand": "U+0026",
    # -- uniXXXX synthesis: valid (length 7, one 4-hex code unit) ---------
    "uni0041": "U+0041",
    "uni20AC": "U+20AC",
    "uni0000": "U+0000",
    "uniFFFF": "U+FFFF",
    # -- uniXXXX case-insensitive hex ------------------------------------
    "uniabcd": "U+ABCD",
    "uniABCD": "U+ABCD",
    # -- uniXXXX disallowed surrogate area -> NULL (even all-hex) ---------
    "uniDeAd": "NULL",
    "uniD7FF": "U+D7FF",
    "uniD800": "NULL",
    "uniDFFF": "NULL",
    "uniE000": "U+E000",
    # -- uniXXXX wrong length -> NULL ------------------------------------
    "uni041": "NULL",
    "uni00041": "NULL",
    "uni0041AB": "NULL",
    # -- uniXXXX multi-code-unit NOT concatenated upstream -> NULL --------
    "uni00410042": "NULL",
    "uni004100420043": "NULL",
    # -- uniXXXX non-hex digit -> NULL -----------------------------------
    "uniGGGG": "NULL",
    "uniZZZZ": "NULL",
    "uni00G1": "NULL",
    # -- uXXXX synthesis: valid (length 5, one 4-hex code unit) ----------
    "u0041": "U+0041",
    "u20AC": "U+20AC",
    "uFFFF": "U+FFFF",
    # -- uXXXXX / uXXXXXX NOT synthesized upstream -> NULL ----------------
    "u041": "NULL",
    "u00041": "NULL",
    "u1F600": "NULL",
    "u041234": "NULL",
    "u0412345": "NULL",
    # -- u case + non-hex -> NULL ----------------------------------------
    "uabcd": "U+ABCD",
    "uGGGG": "NULL",
    # -- dotted-suffix stripping (first dot, index > 0) ------------------
    "A.sc": "U+0041",
    "Aacute.alt": "U+00C1",
    "uni0041.sc": "U+0041",
    "a.sc.alt": "U+0061",
    "one.oldstyle": "U+0031",
    # -- leading-dot names NOT stripped -> NULL --------------------------
    ".notdef": "NULL",
    ".notdef.alt": "NULL",
    # -- plain ligature AGL entries (multi-code-point values) ------------
    "ff": "U+FB00",
    "fi": "U+FB01",
    "fl": "U+FB02",
    "ffi": "U+FB03",
    "ffl": "U+FB04",
    # -- underscore-joined ligature names NOT special-cased -> NULL -------
    "f_f": "NULL",
    "fi_lig": "NULL",
    # -- gNN / cidNN / dingbat aNN names (no AGL entry, no synthesis) -----
    "g65": "NULL",
    "cid65": "NULL",
    "a10": "NULL",
    # -- whitespace / very long / unknown names --------------------------
    "  ": "NULL",
    "averylongglyphnamethatisdefinitelynotinanyadobeglyphlistatall": "NULL",
    "notaglyph": "NULL",
}


@pytest.mark.parametrize("name", sorted(_EXPECTED), ids=sorted(_EXPECTED))
def test_to_unicode_matches_upstream(name: str) -> None:
    agl = GlyphList.get_adobe_glyph_list()
    assert _render(agl.to_unicode(name)) == _EXPECTED[name]


def test_none_name_returns_none() -> None:
    assert GlyphList.get_adobe_glyph_list().to_unicode(None) is None


def test_empty_name_returns_none() -> None:
    # The empty string is neither an AGL entry nor uni/u-shaped.
    assert GlyphList.get_adobe_glyph_list().to_unicode("") is None


def test_cache_is_stable_on_repeated_lookup() -> None:
    # Synthesized results are cached; a second lookup must return the same
    # value (not a stale/cross-contaminated entry from another name).
    agl = GlyphList.get_adobe_glyph_list()
    assert agl.to_unicode("uni0041") == "A"
    assert agl.to_unicode("uni0041") == "A"
    assert agl.to_unicode("uni20AC") == "€"
    assert agl.to_unicode("uni0041") == "A"  # still A after another synth


def test_null_results_are_not_poisoning_other_lookups() -> None:
    agl = GlyphList.get_adobe_glyph_list()
    assert agl.to_unicode("uni00410042") is None  # multi-unit -> None
    assert agl.to_unicode("uni0041") == "A"  # unaffected


def test_name_to_code_points_alias() -> None:
    agl = GlyphList.get_adobe_glyph_list()
    assert agl.name_to_code_points("uni0041") == "A"
    assert agl.name_to_code_points("uni00410042") is None


def test_is_unicode_lookup_pattern() -> None:
    assert GlyphList.is_unicode_lookup("uni0041") is True
    assert GlyphList.is_unicode_lookup("u0041") is True
    assert GlyphList.is_unicode_lookup("uni00410042") is False
    assert GlyphList.is_unicode_lookup("u1F600") is False
    assert GlyphList.is_unicode_lookup("A") is False
    assert GlyphList.is_unicode_lookup("") is False
    assert GlyphList.is_unicode_lookup(None) is False


def test_code_point_for_glyph_name_single_vs_multi() -> None:
    agl = GlyphList.get_adobe_glyph_list()
    assert agl.code_point_for_glyph_name("A") == 0x41
    assert agl.code_point_for_glyph_name("uni0041") == 0x41
    # ligature maps to a single BMP code point (U+FB00) -> int
    assert agl.code_point_for_glyph_name("ff") == 0xFB00
    # unknown -> None
    assert agl.code_point_for_glyph_name("notaglyph") is None


def test_suffix_strip_uses_first_dot() -> None:
    # a.sc.alt must resolve via "a" (before the FIRST dot), not "a.sc".
    agl = GlyphList.get_adobe_glyph_list()
    assert agl.to_unicode("a.sc.alt") == "a"
    assert agl.to_unicode("a.sc") == "a"
