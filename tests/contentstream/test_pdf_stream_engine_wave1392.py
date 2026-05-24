"""Wave 1392 coverage round-out for
:mod:`pypdfbox.contentstream.pdf_stream_engine`.

Closes the residual gaps in 0.9.0rc1 after wave 1390 / 1391:

* :meth:`PDFStreamEngine.show_form` ``cos has no get_length`` branch
  (branch 622->629 — defensive fall-through when the form's COS object
  lacks the attribute entirely).
* :meth:`PDFStreamEngine._decode_codes_via_font` tuple-form
  ``read_code(string, offset)`` happy-path (lines 1117-1132).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
from pypdfbox.pdmodel import PDPage

# ---------- show_form: COS without get_length ----------


def test_show_form_skips_get_length_check_when_attribute_absent() -> None:
    """Branch 622->629 — when ``cos.get_length`` is not exposed at all
    (legacy / minimal test doubles), the helper must NOT abort; it falls
    straight through to :meth:`process_stream` so the form body is
    parsed."""
    dispatched: list[str] = []

    class _FakeCosNoLength:
        """Looks like a COSStream but doesn't carry ``get_length``."""

    class _FakeForm:
        def __init__(self, cos: object) -> None:
            self._cos = cos

        def get_cos_object(self) -> object:
            return self._cos

    class _RecordingEngine(PDFStreamEngine):
        def process_stream(self, _content_stream: Any) -> None:
            dispatched.append("process_stream")

    engine = _RecordingEngine()
    engine._current_page = PDPage()  # noqa: SLF001
    form = _FakeForm(_FakeCosNoLength())
    engine.show_form(form)  # type: ignore[arg-type]
    assert dispatched == ["process_stream"]


def test_show_form_skips_when_get_length_raises_typeerror() -> None:
    """Branch 625-626 — when ``cos.get_length()`` raises ``TypeError``
    (e.g. method requires args), the helper coerces to length=0 and
    early-returns."""

    class _BadCos:
        def get_length(self) -> int:
            raise TypeError("bad get_length")

    class _FakeForm:
        def get_cos_object(self) -> object:
            return _BadCos()

    class _Engine(PDFStreamEngine):
        def process_stream(self, _content_stream: Any) -> None:
            raise AssertionError("process_stream must NOT run; length <= 0")

    engine = _Engine()
    engine._current_page = PDPage()  # noqa: SLF001
    engine.show_form(_FakeForm())  # type: ignore[arg-type]


# ---------- _decode_codes_via_font tuple-form happy path ----------


def test_decode_codes_via_font_tuple_form_happy_path() -> None:
    """Lines 1119-1127 — a font whose ``read_code(string, offset)``
    returns a ``(code, consumed)`` tuple drives the loop correctly."""

    class _TupleFont:
        def read_code(self, string: bytes, offset: int) -> tuple[int, int]:
            # 1-byte single-byte font.
            return string[offset], 1

    codes = PDFStreamEngine._decode_codes_via_font(b"AB", _TupleFont())  # noqa: SLF001
    assert codes == [0x41, 0x42]


def test_decode_codes_via_font_tuple_form_zero_consumed_breaks() -> None:
    """Branch 1124-1125 — the tuple-form ``consumed <= 0`` defensive
    break."""

    class _LoopFont:
        def read_code(self, string: bytes, offset: int) -> tuple[int, int]:
            return string[offset], 0  # zero progress.

    codes = PDFStreamEngine._decode_codes_via_font(b"AB", _LoopFont())  # noqa: SLF001
    assert codes == []


def test_decode_codes_via_font_returns_none_breaks() -> None:
    """Lines 1119-1120 — ``read_code`` returning ``None`` (e.g. EOF
    sentinel) breaks the loop cleanly."""

    class _NoneFont:
        def read_code(self, _s: bytes, _o: int) -> None:
            return None

    codes = PDFStreamEngine._decode_codes_via_font(b"AB", _NoneFont())  # noqa: SLF001
    assert codes == []


def test_decode_codes_via_font_two_arg_returns_int_treated_as_single_byte() -> None:
    """Lines 1128-1132 — when ``read_code(string, offset)`` returns a
    raw ``int`` (not a tuple), the helper treats it as a single-byte
    code and advances by 1."""

    class _IntFont:
        def read_code(self, string: bytes, offset: int) -> int:
            return string[offset]

    codes = PDFStreamEngine._decode_codes_via_font(b"XYZ", _IntFont())  # noqa: SLF001
    assert codes == [ord("X"), ord("Y"), ord("Z")]


def test_decode_codes_via_font_two_arg_raises_oserror_breaks() -> None:
    """Lines 1117-1118 — when the tuple-form ``read_code(string, offset)``
    raises one of (OSError, EOFError, ValueError), the loop breaks."""

    class _BadFont:
        def read_code(self, _s: bytes, _o: int) -> tuple[int, int]:
            raise OSError("bad bytes in stream")

    codes = PDFStreamEngine._decode_codes_via_font(b"AB", _BadFont())  # noqa: SLF001
    assert codes == []
