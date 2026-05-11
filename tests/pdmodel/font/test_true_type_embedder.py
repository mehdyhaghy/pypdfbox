"""Tests for :mod:`pypdfbox.pdmodel.font.true_type_embedder`.

The upstream class is abstract — we exercise the static helpers (the
permission probes and the tag generator) that are pure functions of
their inputs.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.pdmodel.font.true_type_embedder import TrueTypeEmbedder


class _FakeOS2:
    def __init__(self, fs_type: int) -> None:
        self.fsType = fs_type  # noqa: N815 - mirror fontTools attribute name


class _FakeTTF:
    """Stand-in for fontTools' TTFont with the OS/2 attribute we care about."""

    def __init__(self, os2: _FakeOS2 | None) -> None:
        self._os2 = os2

    def __getitem__(self, key: str) -> Any:
        if key == "OS/2" and self._os2 is not None:
            return self._os2
        raise KeyError(key)


def test_embedding_permitted_default_when_no_os2() -> None:
    assert TrueTypeEmbedder.is_embedding_permitted(_FakeTTF(None)) is True


def test_embedding_blocked_for_restricted_license() -> None:
    # fsType masked == 0x0002 -> RESTRICTED_LICENSE_EMBEDDING.
    ttf = _FakeTTF(_FakeOS2(0x0002))
    assert TrueTypeEmbedder.is_embedding_permitted(ttf) is False


def test_embedding_blocked_for_bitmap_only() -> None:
    ttf = _FakeTTF(_FakeOS2(0x0200))
    assert TrueTypeEmbedder.is_embedding_permitted(ttf) is False


def test_embedding_permitted_for_installable() -> None:
    # fsType 0 -> installable embedding.
    ttf = _FakeTTF(_FakeOS2(0x0000))
    assert TrueTypeEmbedder.is_embedding_permitted(ttf) is True


def test_subsetting_blocked_for_no_subsetting_flag() -> None:
    ttf = _FakeTTF(_FakeOS2(0x0100))
    assert TrueTypeEmbedder.is_subsetting_permitted(ttf) is False


def test_subsetting_permitted_by_default() -> None:
    assert TrueTypeEmbedder.is_subsetting_permitted(_FakeTTF(None)) is True


def test_get_tag_is_deterministic() -> None:
    mapping_1 = {1: 1, 2: 2, 3: 3}
    mapping_2 = {3: 3, 2: 2, 1: 1}  # different insertion order
    tag_1 = TrueTypeEmbedder.get_tag(mapping_1)
    tag_2 = TrueTypeEmbedder.get_tag(mapping_2)
    assert tag_1 == tag_2


def test_get_tag_format() -> None:
    tag = TrueTypeEmbedder.get_tag({1: 1, 2: 2, 3: 3})
    # 6 uppercase letters, then '+'.
    assert len(tag) == 7
    assert tag[-1] == "+"
    assert tag[:-1].isalpha() and tag[:-1].isupper()


def test_get_tag_empty_mapping_pads_to_six_letters() -> None:
    tag = TrueTypeEmbedder.get_tag({})
    assert len(tag) == 7
    assert tag[-1] == "+"


def test_get_tag_uses_base25_alphabet() -> None:
    # Base25 -> "BCDEFGHIJKLMNOPQRSTUVWXYZ" (no 'A' in the alphabet body
    # but 'A' is used as left-pad).
    tag = TrueTypeEmbedder.get_tag({1: 1})
    body = tag[:-1]
    for ch in body:
        assert ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
