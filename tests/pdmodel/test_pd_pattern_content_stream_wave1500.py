from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
from pypdfbox.pdmodel.pd_abstract_content_stream import PDAbstractContentStream
from pypdfbox.pdmodel.pd_pattern_content_stream import PDPatternContentStream
from pypdfbox.pdmodel.pd_resources import PDResources

_FLATE: COSName = COSName.FLATE_DECODE  # type: ignore[attr-defined]


def _new_pattern() -> PDTilingPattern:
    """A fresh stream-backed tiling pattern (ctor seeds an empty
    /Resources, exactly as upstream does)."""
    return PDTilingPattern()


# ------------------------------------------------------------------
# constructor / target wiring
# ------------------------------------------------------------------


def test_constructor_binds_existing_pattern_resources() -> None:
    pattern = _new_pattern()
    seeded = pattern.get_resources()
    assert seeded is not None
    cs = PDPatternContentStream(pattern)
    # Writer binds against the pattern's already-present /Resources dict
    # rather than creating a fresh one. ``get_resources`` returns a fresh
    # wrapper each call, so compare by the underlying COS dictionary.
    assert (
        cs.get_resources().get_cos_object()
        is seeded.get_cos_object()
    )
    assert pattern.get_resources() is not None


def test_constructor_creates_resources_when_absent() -> None:
    # Build a pattern from an explicit stream with NO /Resources so the
    # writer's "create one and push it back" branch fires.
    pattern = PDTilingPattern(COSStream())
    assert pattern.get_resources() is None
    cs = PDPatternContentStream(pattern)
    res = cs.get_resources()
    assert isinstance(res, PDResources)
    # The freshly-minted /Resources is pushed back onto the pattern.
    assert pattern.has_resources()


def test_target_stream_is_the_pattern_cos_stream() -> None:
    pattern = _new_pattern()
    cs = PDPatternContentStream(pattern)
    assert cs._target_stream is pattern.get_cos_object()


def test_fraction_digits_pinned_to_abstract_base() -> None:
    pattern = _new_pattern()
    cs = PDPatternContentStream(pattern)
    # Upstream extends PDAbstractContentStream → 4 fractional digits,
    # not the page writer's 5.
    assert (
        cs._max_fraction_digits
        == PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS
    )


def test_document_is_none_and_state_initialised() -> None:
    pattern = _new_pattern()
    cs = PDPatternContentStream(pattern)
    assert cs._document is None
    assert cs._closed is False
    assert cs._compress is False
    assert cs._reset_context is False
    assert cs._in_text_mode is False
    assert isinstance(cs._buffer, bytearray)
    assert cs._pattern is pattern


# ------------------------------------------------------------------
# constructor type guards
# ------------------------------------------------------------------


def test_constructor_rejects_non_pattern() -> None:
    with pytest.raises(TypeError, match="requires a PDTilingPattern"):
        PDPatternContentStream(object())  # type: ignore[arg-type]


def test_constructor_rejects_dictionary_backed_pattern() -> None:
    from pypdfbox.cos import COSDictionary

    # A tiling pattern backed by a bare COSDictionary (not a COSStream) has
    # no body to write a tile cell into — upstream requires a stream.
    pattern = PDTilingPattern(COSDictionary())
    with pytest.raises(TypeError, match="stream-backed"):
        PDPatternContentStream(pattern)


# ------------------------------------------------------------------
# operator buffering + close flush
# ------------------------------------------------------------------


def test_operators_flush_into_pattern_stream_on_close() -> None:
    pattern = _new_pattern()
    with PDPatternContentStream(pattern) as cs:
        cs.move_to(10, 20)
        cs.line_to(30, 40)
        cs.stroke()
    assert pattern.get_cos_object().get_raw_data() == b"10 20 m\n30 40 l\nS\n"


def test_close_is_idempotent() -> None:
    pattern = _new_pattern()
    cs = PDPatternContentStream(pattern)
    cs.move_to(1, 2)
    cs.close()
    first = pattern.get_cos_object().get_raw_data()
    # A second close must not append or re-flush.
    cs.close()
    assert pattern.get_cos_object().get_raw_data() == first


def test_close_compresses_when_compress_flag_set() -> None:
    pattern = _new_pattern()
    cs = PDPatternContentStream(pattern)
    cs._compress = True
    cs.move_to(1, 2)
    cs.stroke()
    cs.close()
    stream = pattern.get_cos_object()
    # /Filter records the FlateDecode and the decoded body round-trips.
    assert stream.get_cos_object().get_item(COSName.FILTER) == _FLATE  # type: ignore[attr-defined]
    with stream.create_input_stream() as inp:
        assert inp.read() == b"1 2 m\nS\n"


def test_fraction_digits_limit_applies_to_operands() -> None:
    pattern = _new_pattern()
    with PDPatternContentStream(pattern) as cs:
        # 0.123456 → 4 fractional digits → 0.1235 (round-half-up).
        cs.move_to(0.123456, 1.0)
    assert pattern.get_cos_object().get_raw_data() == b"0.1235 1 m\n"
