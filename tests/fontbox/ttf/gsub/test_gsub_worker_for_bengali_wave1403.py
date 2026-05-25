"""Wave 1403 — branch round-out for :class:`GsubWorkerForBengali`.

Closes the partial arc ``[170,178]`` — the ``init_feature is not None``
False branch in :meth:`get_before_half_glyph_ids`: the ``init`` feature
is reported as supported but adapts to ``None``, so the augmentation loop
is skipped and only the static before-half glyph ids are returned.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.cmap_lookup import CmapLookup
from pypdfbox.fontbox.ttf.gsub import GsubData, GsubWorkerForBengali


class _FakeCmap(CmapLookup):
    def __init__(self, mapping: dict[int, int]) -> None:
        self._mapping = mapping

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._mapping.get(code_point_at, 0)

    def get_char_codes(self, gid: int) -> list[int] | None:
        return [cp for cp, g in self._mapping.items() if g == gid] or None


def _bengali_cmap() -> _FakeCmap:
    return _FakeCmap(
        {
            ord("ি"): 101,
            ord("ে"): 102,
            ord("ৈ"): 103,
        }
    )


def test_init_feature_supported_but_adapts_to_none() -> None:
    """``init`` reported as supported but its payload is ``None`` →
    ``_adapt_feature`` returns ``None`` and the augmentation loop is
    skipped (``init_feature is not None`` False arc, [170,178]).

    Only the three statically-known before-half glyph ids survive.
    """
    gd = GsubData(
        language="BENGALI",
        feature_list={"init": None},  # type: ignore[dict-item]
    )
    worker = GsubWorkerForBengali(_bengali_cmap(), gd)
    assert sorted(worker._before_half_glyph_ids) == [101, 102, 103]
