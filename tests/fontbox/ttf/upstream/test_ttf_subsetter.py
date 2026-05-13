"""Ported upstream tests for :class:`TTFSubsetter`.

Translated from
``fontbox/src/test/java/org/apache/fontbox/ttf/TTFSubsetterTest.java``
(PDFBox 3.0). Skips the parts of upstream that do byte-for-byte
glyph-table comparison or rely on fonts we cannot redistribute under
Apache-2.0.

Tests retained:

* ``testEmptySubset`` (PDFBOX-2854): empty subset emits .notdef-only TTF.
* ``testEmptySubset2`` (PDFBOX-2854): same with explicit keep-tables list.
* ``testNonEmptySubset`` (PDFBOX-2854): one-glyph subset round-trips.
* ``testPDFBox3379``: partial-monospace left-side-bearing preservation,
  exercised against the bundled ``DejaVuSansMono.ttf`` fixture
  (Bitstream Vera license + DejaVu public-domain changes — Apache-2.0
  redistribution-compatible).
* ``testPDFBox3757``: subset with mixed codepoints round-trips through
  the cmap (we do not assert the exact ``post`` table glyph-name order,
  which is an upstream-specific detail of their handcrafted post-table
  builder; fontTools handles names internally).

Tests skipped (and why):

* ``testPDFBox3319`` — needs system-installed SimHei.
* ``testPDFBox5728`` — needs NotoMono-Regular.ttf (SIL OFL 1.1):
  the upstream Maven build downloads it on demand from
  ``https://issues.apache.org/jira/secure/attachment/13065025/NotoMono-Regular.ttf``
  (see ``fontbox/pom.xml``); SIL OFL 1.1 redistribution requires a
  separate per-font LICENSE / NOTICE outside Apache-2.0's permissive
  envelope, so we don't bundle it.
* ``testPDFBox6015`` — needs Keyboard.ttf, an Apple proprietary system
  font ("Copyright 1995-2007 by Apple Inc. All Rights Reserved"):
  upstream downloads it from
  ``https://issues.apache.org/jira/secure/attachment/13076859/Keyboard.ttf``
  at build time; Apple's font EULA forbids redistribution outside Apple
  software, so it stays out of our corpus.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "fontbox" / "ttf"
FIXTURE = FIXTURE_DIR / "LiberationSans-Regular.ttf"
DEJAVU_FIXTURE = FIXTURE_DIR / "DejaVuSansMono.ttf"


@pytest.fixture
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


@pytest.fixture
def dejavu_sans_mono() -> TrueTypeFont:
    if not DEJAVU_FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {DEJAVU_FIXTURE}")
    return TrueTypeFont.from_bytes(DEJAVU_FIXTURE.read_bytes())


def _ttlib(buf: bytes):
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    return ttLib.TTFont(io.BytesIO(buf))


def _name_to_gid(tt, name: str) -> int:
    order = tt.getGlyphOrder()
    return order.index(name) if name in order else 0


# ---------- ported tests --------------------------------------------------


def test_empty_subset(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-2854: empty subset retains only ``.notdef``."""
    subsetter = TTFSubsetter(liberation_sans)
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    assert tt["maxp"].numGlyphs == 1
    assert _name_to_gid(tt, ".notdef") == 0


def test_empty_subset2(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-2854 variant: empty subset with the upstream
    ``TrueTypeEmbedder`` keep-tables list."""
    tables = [
        "head",
        "hhea",
        "loca",
        "maxp",
        "cvt ",
        "prep",
        "glyf",
        "hmtx",
        "fpgm",
        "gasp",
    ]
    subsetter = TTFSubsetter(liberation_sans, tables)
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    assert tt["maxp"].numGlyphs == 1
    assert _name_to_gid(tt, ".notdef") == 0


def test_non_empty_subset(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-2854: one-glyph subset retains ``.notdef`` plus ``a``."""
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(ord("a"))
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    assert tt["maxp"].numGlyphs == 2
    assert _name_to_gid(tt, ".notdef") == 0
    assert _name_to_gid(tt, "a") == 1
    # Advance width must survive subsetting unchanged.
    full_metrics = liberation_sans._tt["hmtx"].metrics  # noqa: SLF001
    assert tt["hmtx"].metrics["a"][0] == full_metrics["a"][0]


def test_pdfbox_3757(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-3757: subset with mixed codepoints round-trips through
    the cmap. Upstream additionally asserts a specific glyph order in
    the ``post`` table; we drop that — fontTools owns ``post`` naming
    and the glyph-order detail is not part of the library-first
    contract."""
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(ord("Ö"))
    subsetter.add(0x200A)
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    tt = _ttlib(baos.getvalue())
    # .notdef + the requested glyphs + composite parts (O + dieresis).
    assert tt["maxp"].numGlyphs >= 3
    cmap = tt["cmap"].getBestCmap()
    assert ord("Ö") in cmap
    assert 0x200A in cmap


# ---------- intentionally skipped (system fonts not shipped) ------------


def _find_system_simhei() -> Path | None:
    """Probe the standard SimHei locations on macOS / Linux / Windows.

    Upstream's ``testPDFBox3319`` is a system-font test — it only runs
    when the host has SimHei installed. We mirror that conditional
    rather than hard-skipping, so the test exercises real coverage on
    machines where the font is present (e.g. a Windows host whose user
    profile carries the Microsoft-shipped SimHei, or a Linux box that
    has installed the ``ttf-mscorefonts-installer``-shipped CJK pack).
    """
    candidates = [
        Path("/Library/Fonts/SimHei.ttf"),
        Path("/System/Library/Fonts/SimHei.ttf"),
        Path("/System/Library/Fonts/Supplemental/SimHei.ttf"),
        Path.home() / "Library/Fonts/SimHei.ttf",
        Path("/usr/share/fonts/truetype/SimHei.ttf"),
        Path("/usr/share/fonts/SimHei.ttf"),
        Path("/usr/local/share/fonts/SimHei.ttf"),
        Path.home() / ".fonts/SimHei.ttf",
        Path("C:/Windows/Fonts/SimHei.ttf"),
        Path("C:/Windows/Fonts/simhei.ttf"),
    ]
    return next((p for p in candidates if p.exists()), None)


def test_pdfbox_3319_simhei() -> None:
    """PDFBOX-3319: subsetting a CJK font (SimHei) round-trips the
    Chinese codepoints through the cmap.

    Upstream loads the system-installed SimHei (``simhei.ttf``) and
    subsets a small set of CJK ideographs; we mirror that contract,
    asserting only the structural cmap round-trip (Java-specific
    byte-order details of the rewritten ``glyf`` table are out of
    scope for the library-first port). When SimHei is not installed
    on the host, the test stays skipped — matching upstream's
    ``Files.exists`` guard."""
    font_path = _find_system_simhei()
    if font_path is None:
        pytest.skip("PDFBOX-3319 needs system-installed SimHei font")
    font = TrueTypeFont.from_bytes(font_path.read_bytes())
    subsetter = TTFSubsetter(font)
    # Upstream picks a handful of common Chinese ideographs.
    sample_chars = ("中", "文", "字")  # 中, 文, 字
    for ch in sample_chars:
        subsetter.add(ord(ch))
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    subset = TrueTypeFont.from_bytes(baos.getvalue())
    cmap = subset.get_unicode_cmap_subtable()
    assert cmap is not None
    for ch in sample_chars:
        assert cmap.get_glyph_id(ord(ch)) != 0, (
            f"{ch!r} (U+{ord(ch):04X}) missing from SimHei subset"
        )


def test_pdfbox_3379_dejavu_mono(dejavu_sans_mono: TrueTypeFont) -> None:
    """PDFBOX-3379: subsetting a partially-monospaced font must preserve
    both the advance width and the left-side bearing of the glyphs that
    survive the subset.

    Ported from ``TTFSubsetterTest#testPDFBox3379()``. The upstream test
    asserts a specific glyph-order in the rewritten font (``.notdef``
    at 0, ``space`` at 1, ``A`` at 2, ``B`` at 3). fontTools owns the
    glyph-order layout in our backend, so we relax that to "the subset
    contains exactly these four glyphs"; the load-bearing contract is
    the upstream metric-preservation check (advance width + LSB
    unchanged for every surviving glyph), which we keep verbatim.
    """
    subsetter = TTFSubsetter(dejavu_sans_mono)
    subsetter.add(ord("A"))
    subsetter.add(ord(" "))
    subsetter.add(ord("B"))
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    subset = TrueTypeFont.from_bytes(baos.getvalue())

    assert subset.get_number_of_glyphs() == 4
    assert subset.name_to_gid(".notdef") == 0
    # All three named glyphs must round-trip into the subset.
    for name in ("space", "A", "B"):
        assert subset.name_to_gid(name) != 0, f"{name} missing from subset"

    full_hmtx = dejavu_sans_mono.get_horizontal_metrics()
    sub_hmtx = subset.get_horizontal_metrics()
    assert full_hmtx is not None
    assert sub_hmtx is not None
    for name in ("A", "B", "space"):
        full_gid = dejavu_sans_mono.name_to_gid(name)
        sub_gid = subset.name_to_gid(name)
        assert dejavu_sans_mono.get_advance_width(
            full_gid
        ) == subset.get_advance_width(sub_gid)
        assert full_hmtx.get_left_side_bearing(
            full_gid
        ) == sub_hmtx.get_left_side_bearing(sub_gid)


def test_pdfbox_5728_noto_mono() -> None:
    pytest.skip(
        "PDFBOX-5728 needs NotoMono-Regular.ttf (SIL OFL 1.1) — "
        "cannot redistribute under Apache-2.0; upstream downloads it at "
        "build time, see fontbox/pom.xml"
    )


def test_pdfbox_5230_force_invisible(liberation_sans: TrueTypeFont) -> None:
    """PDFBOX-5230: ``forceInvisible`` zeroes the glyph + advance width
    for the named codepoint without disturbing other added glyphs.

    Adapted to LiberationSans (the one font fixture we ship): the
    upstream test uses NotoSans + a ZWNJ codepoint, but the contract
    is the same — flag a codepoint invisible, the corresponding glyph
    in the subset must have zero advance and an empty contour."""
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(ord("A"))
    subsetter.add(ord("B"))
    # First flush: B has its normal width.
    baos = io.BytesIO()
    subsetter.write_to_stream(baos)
    sub_normal = TrueTypeFont.from_bytes(baos.getvalue())
    cmap = sub_normal.get_unicode_cmap_subtable()
    assert cmap is not None
    assert sub_normal.get_advance_width(cmap.get_glyph_id(ord("B"))) > 0

    # Second flush after force_invisible: B is now zero-width.
    subsetter.force_invisible(ord("B"))
    baos2 = io.BytesIO()
    subsetter.write_to_stream(baos2)
    sub_invisible = TrueTypeFont.from_bytes(baos2.getvalue())
    cmap2 = sub_invisible.get_unicode_cmap_subtable()
    assert cmap2 is not None
    assert sub_invisible.get_advance_width(cmap2.get_glyph_id(ord("A"))) > 0
    assert sub_invisible.get_advance_width(cmap2.get_glyph_id(ord("B"))) == 0


def test_pdfbox_6015_keyboard_ttf() -> None:
    pytest.skip(
        "PDFBOX-6015 needs Keyboard.ttf (Apple proprietary system font — "
        '"Copyright 1995-2007 by Apple Inc. All Rights Reserved"); Apple '
        "EULA forbids redistribution outside Apple software. Upstream "
        "downloads it at build time from "
        "https://issues.apache.org/jira/secure/attachment/13076859/Keyboard.ttf"
        " (see fontbox/pom.xml)."
    )
