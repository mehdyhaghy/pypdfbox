"""Wave 1403 branch-closure test for
:meth:`PDType3CharProc._first_metric_operator`.

* ``288->296`` — the inner token-scanning ``while i < n`` loop exits via
  its *condition* (end of data) rather than via the ``break`` on a
  delimiter. This happens when the final token runs to the very end of
  the content stream with no trailing whitespace or delimiter byte.
"""

from __future__ import annotations

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font


def _proc(body: bytes) -> PDType3CharProc:
    glyph = COSStream()
    glyph.set_raw_data(body)
    return PDType3CharProc(PDType3Font(), glyph)


def test_first_metric_operator_token_runs_to_end_of_stream() -> None:
    """A d0 operator at the very end of the stream (no trailing newline
    or delimiter) makes the token scanner reach EOF via the loop
    condition (``288->296``)."""
    # Note: NO trailing whitespace after "d0".
    proc = _proc(b"500 0 d0")
    operator, operands = proc._first_metric_operator()
    assert operator == b"d0"
    assert operands == [b"500", b"0"]
