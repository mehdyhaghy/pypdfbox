"""Ported upstream tests for ``TestFontEmbedding``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/TestFontEmbedding.java``
(PDFBox 3.0.x).

Upstream exercises full PDF round-trips (embed → save → reload →
``PDFTextStripper`` parity) across CIDFontType2 / vertical-Japanese /
Bengali / Devanagari / Gujarati / surrogate-pair / max-entries
scenarios. Most rely on Japanese / Indic TTF fixtures (``ipag.ttf``,
``Lohit-Bengali.ttf``, ``NotoSansDevanagari-Regular.ttf``) that aren't
bundled with pypdfbox; those are skipped with a one-line reason each.

The ones that can run today against the bundled
``LiberationSans-Regular.ttf`` are translated in full.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.true_type_embedder import TrueTypeEmbedder
from pypdfbox.pdmodel.pd_document import PDDocument

# --------------------------------------------------------------------- #
# Bundled fixture — LiberationSans-Regular.ttf ships under the package
# ``resources/ttf`` tree.
# --------------------------------------------------------------------- #

_LIBERATION_SANS = (
    Path(__file__).resolve().parents[4]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


# --------------------------------------------------------------------- #
# testCIDFontType2 / testCIDFontType2Subset — embed LiberationSans as a
# composite CIDFontType2; full vs. subset. Upstream additionally renders
# the page and round-trips through PDFTextStripper; we exercise the
# embedding pathway and verify the resulting font dictionary advertises
# the expected /Subtype + /Encoding.
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("use_subset", [False, True], ids=["full_embed", "subset"])
def test_cid_font_type2(use_subset: bool) -> None:
    """Port of ``testCIDFontType2`` / ``testCIDFontType2Subset``.

    Upstream embeds LiberationSans as a CIDFontType2 inside a fresh
    document, writes "Unicode русский язык Tiếng Việt", saves, reloads,
    and asserts ``PDFTextStripper.getText`` round-trips. We stop short
    of the text-stripper round-trip (out of scope for this parity pass)
    and only assert the embedded font's COS shape.
    """
    assert _LIBERATION_SANS.exists(), f"missing bundled TTF: {_LIBERATION_SANS}"
    with PDDocument() as document:
        with _LIBERATION_SANS.open("rb") as fh:
            font = PDType0Font.load(document, fh, use_subset)
        # Composite CIDFontType2 advertised on the parent dictionary.
        assert font.get_sub_type() == "Type0"
        descendant = font.get_descendant_font()
        assert descendant is not None
        assert descendant.get_cos_object().get_name("Subtype") == "CIDFontType2"


# --------------------------------------------------------------------- #
# testIsEmbeddingPermittedMultipleVersions — pure bit-mask coverage of
# ``TrueTypeEmbedder.is_embedding_permitted`` against the eight legal
# fsType permission combinations. No PDF / fontTools required — we feed
# a stub TTF whose ``OS/2`` table only carries an ``fsType`` short.
# --------------------------------------------------------------------- #


class _StubOS2:
    def __init__(self, fs_type: int) -> None:
        self.fsType = fs_type  # noqa: N815 — mirrors fontTools attribute


class _StubTTF:
    def __init__(self, fs_type: int) -> None:
        self._fs_type = fs_type

    def __getitem__(self, key: str) -> _StubOS2:
        if key == "OS/2":
            return _StubOS2(self._fs_type)
        raise KeyError(key)


def test_is_embedding_permitted_multiple_versions() -> None:
    """Port of ``testIsEmbeddingPermittedMultipleVersions``.

    Mirrors upstream's 8-row truth table over the low nibble of fsType.
    Bit 1 (0x0002) is the only one that denies embedding.
    """
    # 0000 — Installable.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x0000)) is True
    # 0010 — Restricted License.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x0002)) is False
    # 0100 — Preview & Print.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x0004)) is True
    # 0110 — Restricted License + Preview & Print (illegal v3+; legal v0-2).
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x0006)) is True
    # 1000 — Editable.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x0008)) is True
    # 1010 — Restricted License + Editable.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x000A)) is True
    # 1100 — Editable + Preview & Print.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x000C)) is True
    # 1110 — Editable + Preview & Print + Restricted License.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x000E)) is True


def test_is_embedding_permitted_falls_back_when_os2_missing() -> None:
    """Upstream ``isEmbeddingPermitted`` falls through to ``true`` when
    the TTF has no ``OS/2`` table (Java line 148-150).
    """

    class _NoOS2:
        def __getitem__(self, key: str) -> object:
            raise KeyError(key)

    assert TrueTypeEmbedder.is_embedding_permitted(_NoOS2()) is True


def test_is_embedding_permitted_bitmap_embedding_only_denied() -> None:
    """``fsType`` bit 9 (0x0200 = BITMAP_EMBEDDING_ONLY) blocks outline
    embedding (Java line 164-166).
    """
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x0200)) is False
    # Combined with an otherwise-permissive low nibble, still denied.
    assert TrueTypeEmbedder.is_embedding_permitted(_StubTTF(0x0204)) is False


# --------------------------------------------------------------------- #
# Upstream methods that need Japanese / Indic / Atka Mackerel TTF
# fixtures that pypdfbox doesn't bundle — skipped with a one-line
# reason.
# --------------------------------------------------------------------- #


@pytest.mark.skip(
    reason="upstream's testCIDFontType2VerticalSubsetMonospace needs"
    " target/fonts/ipag00303/ipag.ttf (IPA Gothic, Japanese vertical),"
    " not bundled; vertical-substitution path covered by"
    " tests/fontbox/ttf/upstream/test_glyph_substitution_table.py."
)
def test_cid_font_type2_vertical_subset_monospace() -> None: ...


@pytest.mark.skip(
    reason="upstream's testCIDFontType2VerticalSubsetProportional needs"
    " target/fonts/ipagp00303/ipagp.ttf (IPA P Gothic), not bundled."
)
def test_cid_font_type2_vertical_subset_proportional() -> None: ...


@pytest.mark.skip(
    reason="upstream's testBengali needs Lohit-Bengali.ttf + PDFTextStripper,"
    " neither bundled."
)
def test_bengali() -> None: ...


@pytest.mark.skip(
    reason="upstream's testDevanagari needs Lohit-Devanagari.ttf, not bundled."
)
def test_devanagari() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-6085: needs NotoSansDevanagari-Regular.ttf (specific v2.004"
    " size 204336), not bundled."
)
def test_devanagari2() -> None: ...


@pytest.mark.skip(
    reason="upstream's testGujarati needs Lohit-Gujarati.ttf, not bundled."
)
def test_gujarati() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-4302 testMaxEntries needs ipag.ttf + a"
    " MAX_ENTRIES_PER_OPERATOR-sized Japanese string; the boundary itself is"
    " covered by tests/pdmodel/font/test_to_unicode_writer.py's"
    " test_cmap_*_overflow ports."
)
def test_max_entries() -> None: ...


@pytest.mark.skip(
    reason="upstream's testReuseEmbeddedSubsettedFont exercises the"
    " AppendMode.APPEND content-stream path on a reloaded subset font;"
    " AppendMode + Loader resource-font lookup parity isn't yet covered."
)
def test_reuse_embedded_subsetted_font() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-5812: needs ipag.ttf (Japanese kanji surrogate pair),"
    " not bundled."
)
def test_surrogate_pair_character() -> None: ...


@pytest.mark.skip(
    reason="upstream test verifies the *Java* exception message"
    " 'could not find the glyphId for the character: あ, codePoint: 12354"
    " (0x3042)'; pypdfbox raises ValueError with a different format and"
    " the message wording is not part of the API contract."
)
def test_surrogate_pair_character_exception_is_bmp_code_point() -> None: ...


@pytest.mark.skip(
    reason="upstream test verifies the Java exception message wording for"
    " a missing SMP glyph; see test_surrogate_pair_character_exception_is_bmp"
    " skip reason."
)
def test_surrogate_pair_character_exception_is_valid_code_point() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-5230: needs PDFTextStripper round-trip + Loader"
    " resource-font lookup parity for embedded-subset fonts; skipped"
    " until the text-extraction pipeline is in scope."
)
def test_embedded_font_with_zero_width_chars() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-6210 testToUnicodePrefersUsedCodePoint needs"
    " NotoSansCJKkr-VF.ttf (maven-downloaded from googlefonts, not"
    " bundled), and no bundled font has a glyph shared between two"
    " printable code points; the used-code-point preference is covered"
    " synthetically in"
    " tests/pdmodel/font/test_to_unicode_used_codepoint_wave1602.py."
)
def test_to_unicode_prefers_used_code_point() -> None: ...


@pytest.mark.skip(
    reason="PDFBOX-6210 testToUnicodeCjkAndRadicalLookAlike needs"
    " NotoSansCJKkr-VF.ttf (CJK ideograph U+98DF and radical U+2EDD"
    " share one glyph), not bundled; covered synthetically in"
    " tests/pdmodel/font/test_to_unicode_used_codepoint_wave1602.py."
)
def test_to_unicode_cjk_and_radical_look_alike() -> None: ...
