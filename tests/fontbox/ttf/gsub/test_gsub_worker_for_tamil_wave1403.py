"""Wave 1403 — branch round-out for :class:`GsubWorkerForTamil`.

Closes the partial arc ``[121,108]`` — the ``matra_glyph in
before_reph`` False branch in :meth:`adjust_reph_position`: a RA+VIRAMA
cluster whose index+3 trailing glyph is NOT a before-reph glyph, so only
the basic 3-glyph reorder runs and the loop continues.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForTamil


class _FakeCmap(CmapLookup):
    """Minimal :class:`CmapLookup` backed by an explicit code-point map."""

    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._mapping.get(code_point_at, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return [cp for cp, g in self._mapping.items() if g == gid] or None


def _tamil_cmap() -> _FakeCmap:
    return _FakeCmap(
        {
            ord("ர"): 400,  # Tamil RA (reph[0])
            ord("்"): 401,  # Tamil VIRAMA (reph[1])
            ord("ஸ"): 402,  # SA (before-reph[0])
            ord("િ"): 403,  # before-half
        }
    )


def test_adjust_reph_position_reph_with_non_matra_tail() -> None:
    """A RA+VIRAMA cluster whose index+3 glyph is NOT a before-reph
    glyph takes the ``matra_glyph in before_reph`` False arc ([121,108]).

    Input ``[RA=400, VIRAMA=401, CONS=50, X=60]`` — index 0 matches the
    reph cluster; the trailing glyph (60) is not a before-reph glyph, so
    only the basic reorder happens and no matra drag occurs.
    """
    gd = GsubData(language="TAMIL", feature_list={})
    worker = GsubWorkerForTamil(_tamil_cmap(), gd)
    out = worker.adjust_reph_position([400, 401, 50, 60])
    assert out == [50, 400, 401, 60]
