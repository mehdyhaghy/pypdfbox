"""Hand-written tests for the Wave 1304 :class:`TrueTypeCollection`
writer-adjacent surface.

Builds a multi-font ``.ttc`` collection on the fly via fontTools (no
new fixture committed) and exercises:

* :meth:`TrueTypeCollection.get_num_fonts` — shorter alias of
  :meth:`get_number_of_fonts`.
* :meth:`TrueTypeCollection.get_font_at_index` — per-index lookup
  returning a fully-formed :class:`TrueTypeFont`.
* :meth:`TrueTypeCollection.process_all_fonts` — callback variant over
  every font in the collection.

The wave 1304 task asked for a real ``.ttc`` round-trip when one is
available; no ``.ttc`` files ship in-tree, so the fixture is synthesised
in-test (same library-first pattern as the existing
``test_ttc_cluster_wave1279.py``).
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_collection import TrueTypeCollection
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def two_font_ttc_bytes() -> bytes:
    """Build a two-font TTC by re-packing the existing TTF fixture twice
    through fontTools. Two fonts is enough to verify index-based lookup
    and ``process_all_fonts`` iteration."""
    pytest.importorskip("fontTools")
    from fontTools.ttLib import TTCollection, TTFont

    font_a = TTFont(os.fspath(_FIXTURE_TTF))
    font_b = TTFont(os.fspath(_FIXTURE_TTF))
    coll = TTCollection()
    coll.fonts.append(font_a)
    coll.fonts.append(font_b)
    sink = io.BytesIO()
    coll.save(sink)
    return sink.getvalue()


class TestTrueTypeCollectionWave1304:
    def test_get_num_fonts_matches_get_number_of_fonts(
        self, two_font_ttc_bytes: bytes
    ) -> None:
        with TrueTypeCollection(two_font_ttc_bytes) as ttc:
            assert ttc.get_num_fonts() == 2
            assert ttc.get_num_fonts() == ttc.get_number_of_fonts()

    def test_get_font_at_index_returns_distinct_fonts(
        self, two_font_ttc_bytes: bytes
    ) -> None:
        with TrueTypeCollection(two_font_ttc_bytes) as ttc:
            font0 = ttc.get_font_at_index(0)
            font1 = ttc.get_font_at_index(1)
            try:
                assert isinstance(font0, TrueTypeFont)
                assert isinstance(font1, TrueTypeFont)
                # Both refer to the same source font, so PS name matches.
                assert font0.get_name() == font1.get_name() == "LiberationSans"
                # …but they're separate TTFont wrappers.
                assert font0 is not font1
            finally:
                font0.close()
                font1.close()

    def test_get_font_at_index_out_of_range(
        self, two_font_ttc_bytes: bytes
    ) -> None:
        with (
            TrueTypeCollection(two_font_ttc_bytes) as ttc,
            pytest.raises(IndexError),
        ):
            ttc.get_font_at_index(99)

    def test_process_all_fonts_visits_every_index(
        self, two_font_ttc_bytes: bytes
    ) -> None:
        seen: list[str] = []

        def _cb(font: TrueTypeFont) -> None:
            name = font.get_name()
            if name is not None:
                seen.append(name)

        with TrueTypeCollection(two_font_ttc_bytes) as ttc:
            ttc.process_all_fonts(_cb)
        assert seen == ["LiberationSans", "LiberationSans"]

    def test_get_font_by_name_returns_matching_font(
        self, two_font_ttc_bytes: bytes
    ) -> None:
        with TrueTypeCollection(two_font_ttc_bytes) as ttc:
            font = ttc.get_font_by_name("LiberationSans")
            assert font is not None
            try:
                assert font.get_name() == "LiberationSans"
            finally:
                font.close()

    def test_collection_round_trip_via_get_font_at_index_save(
        self, two_font_ttc_bytes: bytes, tmp_path: Path
    ) -> None:
        """Pulling a font out of a TTC and saving it back as a standalone
        TTF is the workflow ``TTFParser`` / ``TrueTypeCollection`` users
        care about for embedding. This exercises that end-to-end."""
        out_path = tmp_path / "extracted.ttf"
        with TrueTypeCollection(two_font_ttc_bytes) as ttc:
            font = ttc.get_font_at_index(0)
            try:
                font.save(out_path)
            finally:
                font.close()

        assert out_path.is_file()
        assert out_path.stat().st_size > 0

        # Re-parse the extracted standalone TTF.
        from pypdfbox.fontbox.ttf.ttf_parser import TTFParser

        reparsed = TTFParser.parse_font(out_path)
        try:
            assert reparsed.get_name() == "LiberationSans"
            assert reparsed.has_table("name")
            assert reparsed.has_table("head")
        finally:
            reparsed.close()


# ---------------------------------------------------------------------
# A note on real .ttc fixtures: the project does not ship any (none in
# upstream's redistributable set), so this file synthesises one in-test
# via fontTools.  When a real .ttc is added under tests/fixtures/ a
# future wave can replace the synthesised fixture above; the public-API
# assertions on TrueTypeCollection do not depend on which file we feed
# them.
# ---------------------------------------------------------------------
