"""Round-out tests for :class:`TTFSubsetter` parity with PDFBox 3.0.

Covers:

* The newly-exposed ``should_copy_name_record`` helper (matches
  upstream's private ``shouldCopyNameRecord`` filter at
  ``TTFSubsetter.java`` line 301).
* The fixed ``_apply_prefix`` divergence — upstream only tags nameID 6
  (PostScript name); the wrapper used to also tag nameID 4 (full name).
"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_bytes() -> bytes:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return FIXTURE.read_bytes()


@pytest.fixture
def liberation_sans(liberation_bytes: bytes) -> TrueTypeFont:
    return TrueTypeFont.from_bytes(liberation_bytes)


def _load_fonttools(buf: bytes):
    import fontTools.ttLib as ttLib  # type: ignore[import-untyped]  # noqa: PLC0415

    return ttLib.TTFont(io.BytesIO(buf))


# ---------- should_copy_name_record (parity with shouldCopyNameRecord) ----


def _name_record(
    *,
    platform_id: int = 3,
    enc_id: int = 1,
    lang_id: int = 0x0409,
    name_id: int = 6,
) -> SimpleNamespace:
    return SimpleNamespace(
        platformID=platform_id,
        platEncID=enc_id,
        langID=lang_id,
        nameID=name_id,
    )


def test_should_copy_name_record_keeps_windows_unicode_en_us_low_id() -> None:
    """The canonical keep-record: Windows / Unicode-BMP / EN-US / id 0..6."""
    for nid in range(7):
        assert TTFSubsetter.should_copy_name_record(_name_record(name_id=nid))


def test_should_copy_name_record_drops_records_with_id_seven_or_higher() -> None:
    assert not TTFSubsetter.should_copy_name_record(_name_record(name_id=7))
    assert not TTFSubsetter.should_copy_name_record(_name_record(name_id=16))


def test_should_copy_name_record_drops_non_windows_platform() -> None:
    assert not TTFSubsetter.should_copy_name_record(_name_record(platform_id=1))


def test_should_copy_name_record_drops_non_unicode_bmp_encoding() -> None:
    assert not TTFSubsetter.should_copy_name_record(_name_record(enc_id=10))


def test_should_copy_name_record_drops_non_english_us_language() -> None:
    assert not TTFSubsetter.should_copy_name_record(_name_record(lang_id=0x040C))


def test_should_copy_name_record_handles_attribute_less_input() -> None:
    """Defensive: missing attributes mean the record can't be classified
    and so must be dropped (rather than raising)."""
    assert not TTFSubsetter.should_copy_name_record(object())


# ---------- prefix tags only nameID 6 (parity with buildNameTable) --------


def test_apply_prefix_tags_postscript_name_only(liberation_sans: TrueTypeFont) -> None:
    """Upstream ``buildNameTable`` (line 359) prepends the subset tag
    only to nameID 6 (PostScript name). Other records — full name (4),
    family (1), subfamily (2) — must remain un-tagged."""
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    sub.set_prefix("ABCDEF")
    out = sub.to_bytes()
    tt = _load_fonttools(out)
    name_table = tt["name"]

    ps_name = name_table.getDebugName(6) or ""
    full_name = name_table.getDebugName(4) or ""
    family_name = name_table.getDebugName(1) or ""

    assert ps_name.startswith("ABCDEF+"), ps_name
    # Full name and family must NOT carry the subset tag — that's a
    # divergence from upstream that the previous wrapper had.
    assert not full_name.startswith("ABCDEF+"), full_name
    assert not family_name.startswith("ABCDEF+"), family_name


def test_apply_prefix_idempotent_on_postscript_name(
    liberation_sans: TrueTypeFont,
) -> None:
    """Two passes with the same prefix mustn't double-tag nameID 6."""
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    sub.set_prefix("ABCDEF")
    first = TrueTypeFont.from_bytes(sub.to_bytes())

    sub2 = TTFSubsetter(first)
    sub2.add(ord("A"))
    sub2.set_prefix("ABCDEF")
    tt = _load_fonttools(sub2.to_bytes())
    ps_name = tt["name"].getDebugName(6) or ""
    assert ps_name.count("ABCDEF+") == 1
