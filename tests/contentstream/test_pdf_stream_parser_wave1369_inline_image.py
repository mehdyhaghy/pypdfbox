"""Wave 1369 — PDFStreamParser inline-image entry/exit + operator interning.

Targets:

- Operator-name interning: identical operator names from independent
  parse runs return the **same** :class:`Operator` instance (via the
  singleton pool). Inline-image operators (``BI`` / ``ID``) bypass the
  pool because they carry per-occurrence payloads.
- Inline-image entry/exit bookkeeping — ``is_in_inline_image`` /
  ``get_inline_image_depth`` / ``get_inline_offset`` track the parser's
  state through the BI/ID/EI segment so PDFBOX-6038-style nested ``BI``
  diagnostics can pinpoint the opening offset.
- Image-data byte boundary: ``EI`` inside the payload (no following
  separator → looks like binary) does NOT terminate the segment.
- Short-name (single-letter) inline-image keys (W instead of Width, H
  instead of Height) round-trip from the parser into PDInlineImage.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import PDFParseError
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser


def _parse(data: bytes) -> list[object]:
    return list(PDFStreamParser(RandomAccessReadBuffer(data)).tokens())


# ---------- operator name interning ----------


def test_operator_get_operator_returns_same_instance_for_same_name() -> None:
    """The singleton pool ensures that every parse of ``q`` returns the
    same :class:`Operator` instance — saves allocation and enables
    cheap ``is``-comparisons."""
    a = Operator.get_operator("q")
    b = Operator.get_operator("q")
    assert a is b


def test_operator_pool_intern_persists_across_parser_runs() -> None:
    """Two independent parse runs of the same operator share an
    instance. We capture the first run's ``Tj`` operator and assert
    identity against the second run's."""
    toks_a = _parse(b"(x) Tj")
    toks_b = _parse(b"(y) Tj")
    op_a = next(t for t in toks_a if isinstance(t, Operator))
    op_b = next(t for t in toks_b if isinstance(t, Operator))
    assert op_a is op_b


def test_inline_image_operators_bypass_the_pool() -> None:
    """``BI`` and ``ID`` carry per-occurrence payloads — every call to
    ``get_operator`` returns a *fresh* instance so caching can't alias
    image_data / image_parameters across unrelated parses."""
    a = Operator.get_operator("BI")
    b = Operator.get_operator("BI")
    assert a is not b
    c = Operator.get_operator("ID")
    d = Operator.get_operator("ID")
    assert c is not d


def test_is_inline_image_operator_name_classifies_correctly() -> None:
    assert Operator.is_inline_image_operator_name("BI") is True
    assert Operator.is_inline_image_operator_name("ID") is True
    # ``EI`` is not on the pool-bypass list — it's a regular operator
    # consumed inside the BI/ID parse loop.
    assert Operator.is_inline_image_operator_name("EI") is False
    assert Operator.is_inline_image_operator_name("Tj") is False


def test_is_inline_image_instance_predicate() -> None:
    assert Operator.get_operator("BI").is_inline_image() is True
    assert Operator.get_operator("ID").is_inline_image() is True
    assert Operator.get_operator("Tj").is_inline_image() is False


# ---------- has_image_data / has_image_parameters predicates ----------


def test_has_image_data_default_false_then_true_after_set() -> None:
    op = Operator.get_operator("ID")
    assert op.has_image_data() is False
    op.set_image_data(b"\x01\x02")
    assert op.has_image_data() is True


def test_has_image_parameters_default_false_then_true_after_set() -> None:
    from pypdfbox.cos import COSDictionary

    op = Operator.get_operator("BI")
    assert op.has_image_parameters() is False
    op.set_image_parameters(COSDictionary())
    assert op.has_image_parameters() is True


# ---------- inline-image depth tracking ----------


def test_parser_inline_image_depth_zero_outside_segment() -> None:
    """No inline image yet → depth 0, not inside segment."""
    parser = PDFStreamParser(RandomAccessReadBuffer(b"q Q"))
    assert parser.is_in_inline_image() is False
    assert parser.get_inline_image_depth() == 0
    assert parser.get_inline_offset() == 0


def test_parser_inline_image_depth_resets_after_normal_segment() -> None:
    """After a BI/ID/EI segment completes the depth returns to 0."""
    parser = PDFStreamParser(RandomAccessReadBuffer(b"BI /W 1 ID\nABCEI Q"))
    list(parser.tokens())
    assert parser.get_inline_image_depth() == 0
    assert parser.is_in_inline_image() is False


def test_parser_records_inline_offset_after_segment() -> None:
    """The ``inline_offset`` field captures the source position where
    the most recent ``BI`` opened. Useful for PDFBOX-6038 diagnostics
    after a nested-BI failure points back at the *first* BI."""
    raw = b"q\nBI /W 1 ID\nABCEI Q"
    parser = PDFStreamParser(RandomAccessReadBuffer(raw))
    list(parser.tokens())
    # ``BI`` lives at offset 2 (after "q\n"); inline_offset captures the
    # parser cursor position *after* the BI keyword was consumed.
    assert parser.get_inline_offset() > 0


def test_nested_bi_raises_with_offset_diagnostic() -> None:
    """PDFBOX-6038 — a nested ``BI`` inside an unterminated outer
    inline-image dictionary raises with an offset / depth diagnostic."""
    with pytest.raises(PDFParseError) as excinfo:
        _parse(b"BI/IB/IB BI/ BI")
    msg = str(excinfo.value)
    assert "Nested 'BI'" in msg
    assert "offset" in msg
    assert "depth" in msg


# ---------- image-data byte boundary (EI vs literal EI in data) ----------


def test_image_data_does_not_terminate_on_literal_ei_inside_payload() -> None:
    """An ``EI`` byte pair embedded inside the binary payload (no
    following whitespace + non-binary trailer) is part of the data, not
    the terminator. Mirrors upstream's ``hasNoFollowingBinData`` /
    ``hasNextSpaceOrReturn`` heuristic."""
    toks = _parse(b"BI /W 1 ID\n12EI5EI Q")
    assert isinstance(toks[0], Operator) and toks[0].name == "BI"
    assert toks[0].image_data == b"12EI5"


def test_image_data_terminator_with_whitespace_then_operator() -> None:
    """The minimal valid terminator is ``EI`` followed by whitespace
    *and* a non-binary trailing token (Q / EMC / S / number)."""
    toks = _parse(b"BI /W 1 ID\nABCEI Q")
    assert toks[0].image_data == b"ABC"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_image_data_terminator_with_null_byte_separator() -> None:
    """Upstream accepts the NUL byte as an EI separator candidate via the
    ``hasNoFollowingBinData`` whitespace classification."""
    toks = _parse(b"BI /W 1 ID\n12345EI \x00Q")
    assert toks[0].image_data == b"12345"
    assert isinstance(toks[1], Operator) and toks[1].name == "Q"


def test_image_data_at_end_of_stream_terminates_segment() -> None:
    """``EI`` at the very end of the stream (no trailing whitespace)
    still terminates — caught via the parser's EOF guard rather than
    ``hasNextSpaceOrReturn``."""
    toks = _parse(b"BI /W 1 ID\n12345EI")
    assert len(toks) == 1
    assert toks[0].name == "BI"
    assert toks[0].image_data == b"12345"


# ---------- short-name keys (W / H / BPC / CS / F / D) ----------


def test_inline_image_short_keys_captured_in_parameter_dict() -> None:
    """Short single-letter inline-image keys (W, H, BPC, CS) are
    captured verbatim in the parameter dictionary — the long names
    (Width, Height, BitsPerComponent, ColorSpace) are *not* synthesised
    by the parser; PDInlineImage handles the fall-through at lookup."""
    toks = _parse(b"BI /W 2 /H 3 /BPC 8 /CS /G ID\nABCDEFEI Q")
    bi = toks[0]
    params = bi.get_image_parameters()
    assert params is not None
    assert params.get_item(COSName.get_pdf_name("W")).int_value() == 2
    assert params.get_item(COSName.get_pdf_name("H")).int_value() == 3
    assert params.get_item(COSName.get_pdf_name("BPC")).int_value() == 8
    assert params.get_item(COSName.get_pdf_name("CS")) == COSName.get_pdf_name("G")
    # Long-form keys are *not* present — the parser doesn't synthesise them.
    assert not params.contains_key(COSName.get_pdf_name("Width"))
    assert not params.contains_key(COSName.get_pdf_name("Height"))


def test_inline_image_short_keys_round_trip_through_pdinlineimage() -> None:
    """End-to-end short→long fall-through: PDInlineImage's ``get_width``
    / ``get_height`` / ``get_bits_per_component`` resolve the short key
    via the two-key lookup helper."""
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    toks = _parse(b"BI /W 4 /H 5 /BPC 8 /CS /G ID\n" + b"\x00" * 20 + b"\nEI Q")
    bi = toks[0]
    img = PDInlineImage(bi.get_image_parameters(), bi.get_image_data(), None)
    assert img.get_width() == 4
    assert img.get_height() == 5
    assert img.get_bits_per_component() == 8


def test_inline_image_long_keys_still_work_when_short_absent() -> None:
    """Backward-compat: long-form keys (Width / Height / etc.) round
    through the same accessors even when the abbreviated form is
    missing."""
    from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage

    toks = _parse(
        b"BI /Width 7 /Height 8 /BitsPerComponent 8 /ColorSpace /DeviceGray "
        b"ID\n" + b"\x00" * 60 + b"\nEI Q"
    )
    bi = toks[0]
    img = PDInlineImage(bi.get_image_parameters(), bi.get_image_data(), None)
    assert img.get_width() == 7
    assert img.get_height() == 8


# ---------- operator repr / to_string ----------


def test_operator_repr_matches_upstream_to_string_form() -> None:
    """Upstream ``Operator.toString()`` is ``"PDFOperator{<name>}"`` —
    callers that rely on the format (e.g. pretty-printers, log lines)
    get the same output from ``repr`` / ``to_string`` / ``str``."""
    op = Operator.get_operator("Tj")
    assert repr(op) == "PDFOperator{Tj}"
    assert str(op) == "PDFOperator{Tj}"
    assert op.to_string() == "PDFOperator{Tj}"


def test_operator_starting_with_slash_rejected() -> None:
    """Upstream rejects operator names starting with ``/`` (those are
    name-object operands, not operators)."""
    with pytest.raises(ValueError, match="Operators are not allowed"):
        Operator("/Tj")


def test_operator_len_matches_name_length() -> None:
    """``__len__`` matches ``len(name)`` — convenient parity with
    upstream ``op.getName().length()`` idiom."""
    assert len(Operator.get_operator("Tj")) == 2
    assert len(Operator.get_operator("BDC")) == 3
    assert len(Operator.get_operator("'")) == 1


# ---------- wave 1517: ID operator stops at exactly two chars ----------


def test_id_followed_by_binary_byte_no_separator() -> None:
    """PDFBOX-1751: ``ID`` immediately followed by a non-whitespace binary
    byte (no separator) must tokenize as the ``ID`` operator, with that
    byte beginning the raw image payload. Before the fix the binary byte
    was folded into a bogus ``ID<byte>`` keyword and the inline-image
    segment was lost (image_data stayed ``None``)."""
    tokens = _parse(b"BI /W 1 /H 1 ID\x10\x11EI Q\n")
    bi = next(t for t in tokens if isinstance(t, Operator) and t.get_name() == "BI")
    assert bi.get_image_data() == b"\x10\x11"


def test_id_followed_by_high_byte_no_separator() -> None:
    tokens = _parse(b"BI /W 1 /H 1 ID\xff\x02EI Q\n")
    bi = next(t for t in tokens if isinstance(t, Operator) and t.get_name() == "BI")
    assert bi.get_image_data() == b"\xff\x02"


def test_id_followed_by_letter_no_separator() -> None:
    """``IDX...`` tokenizes as ``ID`` plus payload starting with ``X`` —
    ``readOperator`` stops the moment the buffer reads exactly ``ID``."""
    tokens = _parse(b"BI /W 1 /H 1 IDX\x02EI Q\n")
    bi = next(t for t in tokens if isinstance(t, Operator) and t.get_name() == "BI")
    assert bi.get_image_data() == b"X\x02"
