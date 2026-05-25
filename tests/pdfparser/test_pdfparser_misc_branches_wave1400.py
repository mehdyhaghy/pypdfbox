"""Branch coverage for misc :mod:`pypdfbox.pdfparser` files — wave 1400.

Closes residual partial branches in:

* ``pdf_xref_stream_parser.py``: ``close()`` when ``_src is None``
  (154 → 156).
* ``linearization_hint_table.py``: ``align_to_byte`` when already
  byte-aligned (207 → 202).
* ``pdf_stream_parser.py``: ``Operator.get_operator`` cache-miss
  inner-recheck branch (88 → 91) and ``_skip_linebreak`` with CR not
  followed by LF (517 → 519).
"""

from __future__ import annotations

from pypdfbox.cos import COSDocument, COSInteger, COSName, COSStream
from pypdfbox.pdfparser.linearization_hint_table import _BitReader
from pypdfbox.pdfparser.pdf_stream_parser import Operator, PDFStreamParser
from pypdfbox.pdfparser.pdf_xref_stream_parser import PDFXrefStreamParser

# ----------------------------------------------------------------------
# PDFXrefStreamParser.close() with _src already None
# ----------------------------------------------------------------------


def _make_xref_stream() -> COSStream:
    from pypdfbox.cos import COSArray

    s = COSStream()
    w = COSArray()
    w.add(COSInteger.get(1))
    w.add(COSInteger.get(2))
    w.add(COSInteger.get(1))
    s.set_item(COSName.W, w)
    s.set_item(COSName.SIZE, COSInteger.get(2))
    # Give the stream a minimal body so create_view doesn't raise.
    out = s.create_raw_output_stream()
    try:
        out.write(b"\x00" * 8)  # 2 rows of (1+2+1)=4 bytes each
    finally:
        out.close()
    return s


def test_pdf_xref_stream_parser_close_when_src_already_none() -> None:
    """Calling ``close()`` twice must not raise when the second call
    finds ``_src`` already cleared.

    Closes branch (154 → 156)."""
    s = _make_xref_stream()
    doc = COSDocument()
    parser = PDFXrefStreamParser(s, doc)
    # First close runs through the _src.close() branch.
    parser.close()
    # Force _src to None so the second close exercises the (154 → 156)
    # branch where the close is skipped.
    parser._src = None  # noqa: SLF001
    parser.close()
    assert parser._document is None  # noqa: SLF001
    doc.close()


# ----------------------------------------------------------------------
# _BitReader.align_to_byte — already aligned no-op
# ----------------------------------------------------------------------


def test_bit_reader_align_to_byte_noop_when_aligned() -> None:
    """When the bit cursor is already on a byte boundary, ``align_to_byte``
    must not advance the cursor.

    Closes branch (207 → 202)."""
    reader = _BitReader(b"\xff\xff")
    # Read exactly 16 bits → cursor lands on a byte boundary (16).
    reader.read(8)
    reader.read(8)
    pos_before = reader._bit_pos  # noqa: SLF001
    assert pos_before % 8 == 0
    reader.align_to_byte()
    assert reader._bit_pos == pos_before  # noqa: SLF001 - unchanged


def test_bit_reader_align_to_byte_advances_when_misaligned() -> None:
    """Positive control: a partial-byte read leaves the cursor mid-byte;
    align_to_byte rounds it up."""
    reader = _BitReader(b"\xff\xff")
    reader.read(3)
    assert reader._bit_pos == 3  # noqa: SLF001
    reader.align_to_byte()
    assert reader._bit_pos == 8  # noqa: SLF001


# ----------------------------------------------------------------------
# Operator.get_operator — concurrent cache repopulation branch
# ----------------------------------------------------------------------


def test_operator_get_operator_double_check_cache_hit() -> None:
    """The double-checked locking idiom: when two threads race to create
    the same operator, one wins the lock and populates the cache; the
    other enters the locked block and finds ``cached is not None``.

    We force the race deterministically by pre-populating the cache
    *inside* the with-block on the second thread's behalf — calling
    ``get_operator`` from a thread that already holds the lock would
    deadlock, so we simulate the scenario by manually pre-seeding the
    operators dict between the outer-cache check and the inner one.

    Closes branch (88 → 91)."""
    op_name = "WAVE_1400_TEST_OP"
    Operator._operators.pop(op_name, None)  # noqa: SLF001
    # The contended-cache-hit branch happens when one thread populates
    # the cache while another is waiting on the lock. We simulate this
    # by populating the cache in the main thread *before* invoking
    # get_operator — but only after the outer check has run.
    #
    # That's not directly possible without monkeypatching, so we use a
    # subclass of dict that pre-seeds the cache on the second get().
    real_dict = Operator._operators  # noqa: SLF001

    class _RaceDict(dict):
        """Dict that emulates a contended cache hit: the second
        ``get(name)`` call (the one inside the with-lock block) returns
        a pre-seeded entry, even though the first (outside the lock)
        returned None."""

        def __init__(self, source: dict, race_name: str) -> None:
            super().__init__(source)
            self._race_name = race_name
            self._calls = 0
            self._sentinel = Operator(race_name)

        def get(self, key: object, default: object = None) -> object:
            if key == self._race_name:
                self._calls += 1
                # First call (outside lock) returns None — natural miss.
                # Second call (inside lock) returns the sentinel,
                # mimicking the racing thread having populated.
                if self._calls >= 2:
                    return self._sentinel
                return None
            return super().get(key, default)

    race = _RaceDict(real_dict, op_name)
    try:
        Operator._operators = race  # noqa: SLF001
        result = Operator.get_operator(op_name)
        # The inner-lock cache hit produced the sentinel — that's the
        # closed branch.
        assert result is race._sentinel
    finally:
        Operator._operators = real_dict  # noqa: SLF001
        Operator._operators.pop(op_name, None)  # noqa: SLF001


def test_operator_get_operator_inline_image_bypasses_cache() -> None:
    """``BI`` / ``ID`` bypass the cache (each instance carries distinct
    inline-image payloads). Positive control for the early-return
    branch in get_operator."""
    op1 = Operator.get_operator("BI")
    op2 = Operator.get_operator("BI")
    assert op1 is not op2


# ----------------------------------------------------------------------
# PDFStreamParser._skip_linebreak — lone CR (no LF follows)
# ----------------------------------------------------------------------


def test_pdf_stream_parser_skip_linebreak_lone_cr() -> None:
    """A CR not followed by LF (some legacy encoders emit just CR) —
    ``_skip_linebreak`` must consume the CR and return True without
    also consuming the following non-LF byte.

    Closes branch (517 → 519)."""
    parser = PDFStreamParser.from_bytes(b"\rX")  # lone CR followed by 'X'
    consumed = parser._skip_linebreak()  # noqa: SLF001
    assert consumed is True
    # The lone CR was consumed; the next byte should be 'X'.
    assert parser.peek_byte() == ord("X")


def test_pdf_stream_parser_skip_linebreak_lf_only() -> None:
    """LF alone consumed."""
    parser = PDFStreamParser.from_bytes(b"\nrest")
    consumed = parser._skip_linebreak()  # noqa: SLF001
    assert consumed is True
    assert parser.peek_byte() == ord("r")


def test_pdf_stream_parser_skip_linebreak_crlf() -> None:
    """CRLF consumed as a unit."""
    parser = PDFStreamParser.from_bytes(b"\r\ntail")
    consumed = parser._skip_linebreak()  # noqa: SLF001
    assert consumed is True
    assert parser.peek_byte() == ord("t")


def test_pdf_stream_parser_skip_linebreak_no_eol_returns_false() -> None:
    """When the cursor isn't on an EOL byte, the helper returns False
    and doesn't move the cursor."""
    parser = PDFStreamParser.from_bytes(b"abc")
    assert parser._skip_linebreak() is False  # noqa: SLF001
    assert parser.peek_byte() == ord("a")
