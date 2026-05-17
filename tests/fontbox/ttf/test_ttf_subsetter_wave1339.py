"""Coverage round-out for :class:`TTFSubsetter` — wave 1339.

Targets the few remaining uncovered branches in
``pypdfbox/fontbox/ttf/ttf_subsetter.py``:

* ``_apply_prefix`` empty / already-tagged record edges (line 364).
* ``log2(0)`` short-circuit (line 402).
* ``to_u_int32`` byte-buffer short-of-4 padding (line 418) and
  missing-``low`` ``TypeError`` (line 421).
* ``write_long_date_time`` ``int`` / ``datetime`` / ``timeInMillis`` paths
  (lines 482-493).
* ``write_table_record`` non-4-char tag padding (line 537).
* ``copy_bytes`` non-seekable fallback (lines 572-574) and EOFError
  surface (line 577).
* ``_build_subset_font`` invisible / prefix application (lines 661, 663).
* ``_encoded_table`` ``tag not in tt`` / ``tag not in reader.tables``
  return-None branches (lines 681 / 693).
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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


# ----------------------------------------------------------------------
# _apply_prefix — empty / already-tagged branches (line 364)
# ----------------------------------------------------------------------


class _Rec:
    """Mimic a fontTools NameRecord with a writable ``string``."""

    def __init__(self, name_id: int, text: str) -> None:
        self.nameID = name_id
        self._text = text
        self.string: str | None = None

    def toUnicode(self) -> str:  # noqa: N802 - mirrors fontTools API
        return self._text


class _NameTable:
    def __init__(self, names: list[_Rec]) -> None:
        self.names = names


def test_apply_prefix_skips_record_with_empty_to_unicode() -> None:
    """Upstream's ``buildNameTable`` continues over records whose
    ``toUnicode()`` is empty (line 364) — we must too."""
    rec = _Rec(6, "")  # nameID 6 (PostScript name), empty body
    tt = {"name": _NameTable([rec])}
    TTFSubsetter._apply_prefix(tt, "ABCDEF")  # noqa: SLF001
    assert rec.string is None  # untouched


def test_apply_prefix_skips_already_tagged_record() -> None:
    """A record whose first six chars are uppercase letters followed by
    ``+`` is already-tagged — leave it alone."""
    rec = _Rec(6, "XYZABC+SomeFont")
    tt = {"name": _NameTable([rec])}
    TTFSubsetter._apply_prefix(tt, "ABCDEF")  # noqa: SLF001
    assert rec.string is None


def test_apply_prefix_skips_non_postscript_records() -> None:
    rec = _Rec(4, "FullName")  # nameID 4 — not the PS name
    tt = {"name": _NameTable([rec])}
    TTFSubsetter._apply_prefix(tt, "ABCDEF")  # noqa: SLF001
    assert rec.string is None


def test_apply_prefix_returns_when_no_name_table() -> None:
    """No ``name`` table in the subset -> return immediately."""
    TTFSubsetter._apply_prefix({}, "ABCDEF")  # noqa: SLF001


# ----------------------------------------------------------------------
# log2(0) / negative (line 402)
# ----------------------------------------------------------------------


def test_log2_returns_zero_for_zero_input() -> None:
    assert TTFSubsetter.log2(0) == 0


def test_log2_returns_zero_for_negative_input() -> None:
    assert TTFSubsetter.log2(-3) == 0


def test_log2_returns_floor_log_two_for_positive() -> None:
    # Sanity for the happy path.
    assert TTFSubsetter.log2(1) == 0
    assert TTFSubsetter.log2(8) == 3
    assert TTFSubsetter.log2(9) == 3


# ----------------------------------------------------------------------
# to_u_int32 — padding + TypeError (lines 418, 421)
# ----------------------------------------------------------------------


def test_to_u_int32_pads_short_buffer() -> None:
    """Buffer shorter than 4 bytes is right-padded with zeros (line 418)."""
    # ``b"\x01"`` becomes ``b"\x01\x00\x00\x00"`` -> big-endian 0x01000000.
    assert TTFSubsetter.to_u_int32(b"\x01") == 0x01000000


def test_to_u_int32_raises_type_error_without_low() -> None:
    with pytest.raises(TypeError):
        TTFSubsetter.to_u_int32(123)


def test_to_u_int32_packs_two_uint16_values() -> None:
    assert TTFSubsetter.to_u_int32(0xAABB, 0xCCDD) == 0xAABBCCDD


# ----------------------------------------------------------------------
# write_long_date_time — int / datetime / timeInMillis (lines 482-493)
# ----------------------------------------------------------------------


def test_write_long_date_time_accepts_int_seconds() -> None:
    out = io.BytesIO()
    TTFSubsetter.write_long_date_time(out, 0)
    assert out.getvalue() == b"\x00" * 8


def test_write_long_date_time_accepts_aware_datetime() -> None:
    out = io.BytesIO()
    TTFSubsetter.write_long_date_time(out, datetime(1904, 1, 1, tzinfo=UTC))
    assert out.getvalue() == b"\x00" * 8


def test_write_long_date_time_accepts_naive_datetime() -> None:
    out = io.BytesIO()
    # Naive datetime treated as UTC per the docstring.
    TTFSubsetter.write_long_date_time(out, datetime(1904, 1, 1))
    assert out.getvalue() == b"\x00" * 8


def test_write_long_date_time_accepts_java_calendar_shim() -> None:
    """An object with a ``timeInMillis`` attribute (Java Calendar-shim
    duck-typing) must work — the implementation re-bases from the Java
    epoch (1970-01-01) into the TrueType epoch (1904-01-01)."""
    out = io.BytesIO()
    cal = SimpleNamespace(timeInMillis=0)  # 1970-01-01 UTC in Java millis
    TTFSubsetter.write_long_date_time(out, cal)
    # Seconds from 1904-01-01 to 1970-01-01 = 2_082_844_800.
    decoded = int.from_bytes(out.getvalue(), "big", signed=True)
    assert decoded == 2_082_844_800


def test_write_long_date_time_rejects_unrecognised_value() -> None:
    out = io.BytesIO()
    with pytest.raises(TypeError):
        TTFSubsetter.write_long_date_time(out, object())


# ----------------------------------------------------------------------
# write_table_record — tag padding (line 537)
# ----------------------------------------------------------------------


def test_write_table_header_pads_short_tag() -> None:
    """A tag shorter than 4 bytes is right-padded with spaces (line 537)."""
    sub = TTFSubsetter.__new__(TTFSubsetter)
    out = io.BytesIO()
    sub.write_table_header(out, "abc", 0, b"hello")
    # The first 4 bytes of the output should be the padded tag.
    assert out.getvalue()[:4] == b"abc "


def test_write_table_header_pads_long_tag() -> None:
    """Tags longer than 4 bytes are truncated to the first 4 bytes."""
    sub = TTFSubsetter.__new__(TTFSubsetter)
    out = io.BytesIO()
    sub.write_table_header(out, "abcdef", 0, b"x")
    assert out.getvalue()[:4] == b"abcd"


# ----------------------------------------------------------------------
# copy_bytes — non-seekable fallback + EOF (lines 572-574, 577)
# ----------------------------------------------------------------------


class _NonSeekableSrc:
    """A stream-like object that raises ``OSError`` on ``seek``."""

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)

    def seek(self, *_args: Any, **_kwargs: Any) -> int:
        raise OSError("not seekable")

    def read(self, n: int) -> bytes:
        return self._buf.read(n)


def test_copy_bytes_falls_back_to_read_when_seek_fails() -> None:
    """Non-seekable src -> ``read(nskip)`` consumes the skip-band."""
    src = _NonSeekableSrc(b"ABCDEFGHIJ")
    dst = io.BytesIO()
    new_offset = TTFSubsetter.copy_bytes(src, dst, new_offset=3, last_offset=0, count=4)
    assert dst.getvalue() == b"DEFG"
    assert new_offset == 7


class _NoSeekSrc:
    """A stream-like object whose ``seek`` attribute is missing entirely.

    Calling ``self.seek`` from inside ``copy_bytes`` raises
    ``AttributeError`` — the helper catches it and falls back to
    ``read``-and-discard.
    """

    def __init__(self, data: bytes) -> None:
        self._buf = io.BytesIO(data)

    def read(self, n: int) -> bytes:
        return self._buf.read(n)


def test_copy_bytes_falls_back_when_seek_raises_attribute_error() -> None:
    """No ``seek`` attribute -> AttributeError swallowed, read-and-discard
    consumes the skip-band (lines 572-574)."""
    src = _NoSeekSrc(b"abcdefghij")
    dst = io.BytesIO()
    TTFSubsetter.copy_bytes(src, dst, new_offset=2, last_offset=0, count=3)
    assert dst.getvalue() == b"cde"


def test_copy_bytes_raises_eof_on_short_read() -> None:
    """Source has fewer bytes than requested -> EOFError (line 577)."""
    src = io.BytesIO(b"abc")
    dst = io.BytesIO()
    with pytest.raises(EOFError):
        TTFSubsetter.copy_bytes(src, dst, new_offset=0, last_offset=0, count=999)


# ----------------------------------------------------------------------
# _build_subset_font — invisible / prefix (lines 661, 663)
# ----------------------------------------------------------------------


def test_build_subset_font_applies_prefix_and_invisible(
    liberation_sans: TrueTypeFont,
) -> None:
    """Round-trip a tiny subset with a six-letter prefix AND an invisible
    codepoint — both branches at the tail of ``_build_subset_font``
    (lines 661, 663) must run."""
    sub = TTFSubsetter(liberation_sans)
    sub.set_prefix("ABCDEF")
    sub.add(ord("A"))
    sub.force_invisible(ord("A"))  # registers in _invisible_unicodes
    tt = sub._build_subset_font()  # noqa: SLF001
    # The PostScript name should now be tagged.
    name_table = tt["name"]
    for record in name_table.names:
        if record.nameID == 6 and record.toUnicode():
            assert record.toUnicode().startswith("ABCDEF+")
            break
    else:
        pytest.fail("nameID-6 record not found after subsetting")


# ----------------------------------------------------------------------
# _encoded_table — tag not in tt / tag not in reader (lines 681, 693)
# ----------------------------------------------------------------------


def test_encoded_table_returns_none_for_keep_tables_miss(
    liberation_sans: TrueTypeFont,
) -> None:
    """``keep_tables`` allow-list excludes the requested tag -> early
    return None at the top of ``_encoded_table`` (the gate above 681)."""
    sub = TTFSubsetter(liberation_sans, tables=["head"])
    sub.add(ord("A"))
    assert sub._encoded_table("name") is None  # noqa: SLF001


def test_encoded_table_returns_none_for_table_not_in_subset(
    liberation_sans: TrueTypeFont,
) -> None:
    """If the subset font lacks the requested tag at all (e.g. ``DSIG``
    which the subset options always drop), the body branch at line 681
    returns ``None``."""
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    # ``DSIG`` is in ``options.drop_tables``; the resulting subset has no
    # DSIG table, so ``_encoded_table('DSIG')`` should return None.
    assert sub._encoded_table("DSIG") is None  # noqa: SLF001


def test_encoded_table_returns_none_when_reader_lacks_tag(
    liberation_sans: TrueTypeFont, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Edge: ``tag in tt`` but the save/reload reader doesn't expose it —
    coerce the branch by intercepting ``_encoded_table`` mid-way to
    replace the reader's ``tables`` map (covers line 693)."""
    import fontTools.ttLib as ttLib

    original_init = ttLib.TTFont.__init__
    call_count = {"n": 0}

    def _patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        # The first call is the source-font load; the second is the
        # post-save reload — that's the one we want to mutate AFTER the
        # full init completes so save/load itself works.
        call_count["n"] += 1

    monkeypatch.setattr(ttLib.TTFont, "__init__", _patched_init)
    # Also patch the ``reader.tables`` attribute lookup. The implementation
    # checks ``tag not in reader.tables`` — make ``tables`` empty for the
    # *second* TTFont (the reloaded subset).
    original_getattr = ttLib.TTFont.__getattribute__

    def _patched_get(self: Any, name: str) -> Any:
        result = original_getattr(self, name)
        if name == "reader" and call_count["n"] >= 2:
            # Wrap once with an empty-tables shim.
            class _Shim:
                tables: dict[str, Any] = {}

                def __getitem__(self, _key: str) -> bytes:  # pragma: no cover
                    return b""

            return _Shim()
        return result

    monkeypatch.setattr(ttLib.TTFont, "__getattribute__", _patched_get)
    sub = TTFSubsetter(liberation_sans)
    sub.add(ord("A"))
    assert sub._encoded_table("name") is None  # noqa: SLF001
