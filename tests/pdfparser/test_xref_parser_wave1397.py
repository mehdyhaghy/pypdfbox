"""Wave 1397 — close residual XrefParser façade-body coverage.

Wave 1396 added the 10 façade delegators to :class:`pypdfbox.pdfparser.
xref_parser.XrefParser`, plus parity tests that verified the surface is
present and that 5 of the 10 delegators preserve upstream short-circuit
behaviour through real :class:`COSParser` instances. The remaining 5
delegators (``parse_trailer``, ``parse_xref_obj_stream``,
``check_x_ref_offset``, ``calculate_x_ref_fixed_offset``,
``parse_xref_table``) need full-stack PDFs to exercise the real
implementation, which makes their facade-body lines uncovered after a
canonical coverage run.

This wave uses a tiny stub :class:`COSParser` that records each call
and returns a sentinel, exercising the façade's return-statement body
without paying the cost of constructing a full PDF for each. The stub
mirrors the upstream contract: each forwarding method is invoked once
with the exact argument tuple the façade received, and the façade's
return value is what the stub returned (so the ``return self._parser.X``
line is fully exercised).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSObjectKey
from pypdfbox.pdfparser import XrefParser


class _RecordingParser:
    """Minimal ``COSParser`` stub: records each call + returns a sentinel.

    The façade only touches its bound parser through the public-helper
    method names — it never touches private attributes — so a plain
    object with the right methods satisfies the contract.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        # Sentinels by method so each test can assert the façade returned
        # the value that came back from the stub (i.e. exercised the
        # ``return self._parser.X(...)`` body).
        self._returns: dict[str, Any] = {
            "parse_trailer": True,
            "parse_xref_obj_stream": 42,
            "check_x_ref_offset": 7,
            "calculate_x_ref_fixed_offset": 11,
            "parse_xref_table": True,
        }

    def parse_trailer(self) -> bool:
        self.calls.append(("parse_trailer", ()))
        return self._returns["parse_trailer"]

    def parse_xref_obj_stream(
        self, obj_byte_offset: int, is_standalone: bool
    ) -> int:
        self.calls.append(
            ("parse_xref_obj_stream", (obj_byte_offset, is_standalone))
        )
        return self._returns["parse_xref_obj_stream"]

    def check_x_ref_offset(self, start_x_ref_offset: int) -> int:
        self.calls.append(("check_x_ref_offset", (start_x_ref_offset,)))
        return self._returns["check_x_ref_offset"]

    def calculate_x_ref_fixed_offset(self, object_offset: int) -> int:
        self.calls.append(("calculate_x_ref_fixed_offset", (object_offset,)))
        return self._returns["calculate_x_ref_fixed_offset"]

    def parse_xref_table(self, start_byte_offset: int) -> bool:
        self.calls.append(("parse_xref_table", (start_byte_offset,)))
        return self._returns["parse_xref_table"]


def test_wave1397_parse_trailer_delegates_and_returns_sentinel() -> None:
    """``parse_trailer`` body forwards to the bound parser and returns its
    value verbatim (closes residual line 125)."""
    stub = _RecordingParser()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    assert xref.parse_trailer() is True
    assert stub.calls == [("parse_trailer", ())]


def test_wave1397_parse_xref_obj_stream_delegates_with_args() -> None:
    """``parse_xref_obj_stream(offset, standalone)`` forwards both args
    through and returns the stub's int verbatim (closes residual line 132)."""
    stub = _RecordingParser()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    assert xref.parse_xref_obj_stream(1234, True) == 42
    assert stub.calls == [("parse_xref_obj_stream", (1234, True))]


def test_wave1397_check_x_ref_offset_delegates_with_offset() -> None:
    """``check_x_ref_offset(offset)`` forwards the offset and returns the
    stub's int verbatim (closes residual line 137)."""
    stub = _RecordingParser()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    assert xref.check_x_ref_offset(99) == 7
    assert stub.calls == [("check_x_ref_offset", (99,))]


def test_wave1397_calculate_x_ref_fixed_offset_delegates_with_offset() -> None:
    """``calculate_x_ref_fixed_offset(offset)`` forwards the offset and
    returns the stub's int verbatim (closes residual line 142)."""
    stub = _RecordingParser()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    assert xref.calculate_x_ref_fixed_offset(555) == 11
    assert stub.calls == [("calculate_x_ref_fixed_offset", (555,))]


def test_wave1397_parse_xref_table_delegates_with_offset() -> None:
    """``parse_xref_table(offset)`` forwards the byte offset and returns
    the stub's bool verbatim (closes residual line 180)."""
    stub = _RecordingParser()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    assert xref.parse_xref_table(2048) is True
    assert stub.calls == [("parse_xref_table", (2048,))]


def test_wave1397_all_five_residual_facades_exercised_in_one_pass() -> None:
    """End-to-end: call all five residual façade methods on a single
    XrefParser, verify each forwarded once with the right args, and that
    the façade returned the stub's value for each. This is the consolidated
    smoke test for the five residual lines collectively."""
    stub = _RecordingParser()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    assert xref.parse_trailer() is True
    assert xref.parse_xref_obj_stream(10, False) == 42
    assert xref.check_x_ref_offset(20) == 7
    assert xref.calculate_x_ref_fixed_offset(30) == 11
    assert xref.parse_xref_table(40) is True
    assert stub.calls == [
        ("parse_trailer", ()),
        ("parse_xref_obj_stream", (10, False)),
        ("check_x_ref_offset", (20,)),
        ("calculate_x_ref_fixed_offset", (30,)),
        ("parse_xref_table", (40,)),
    ]


def test_wave1397_facade_does_not_invoke_other_helpers() -> None:
    """Sanity: each façade method touches exactly one underlying COSParser
    method. The stub's ``calls`` log must show no extra invocations."""
    stub = _RecordingParser()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    xref.parse_trailer()
    # Only one call; nothing else has been triggered.
    assert len(stub.calls) == 1
    assert stub.calls[0][0] == "parse_trailer"


def test_wave1397_facade_accepts_cos_object_key_args_for_find_object_key() -> None:
    """``find_object_key`` already had coverage via the wave-1396 short-circuit
    test; this confirms the COSObjectKey + dict-shaped argument forwarding
    keeps working alongside the new stub-based residual closures."""

    class _FindOnlyStub:
        def __init__(self) -> None:
            self.received: tuple[Any, ...] | None = None

        def find_object_key(
            self,
            object_key: COSObjectKey,
            offset: int,
            xref_offset: dict[COSObjectKey, int],
        ) -> COSObjectKey | None:
            self.received = (object_key, offset, xref_offset)
            return object_key

    stub = _FindOnlyStub()
    xref = XrefParser(stub)  # type: ignore[arg-type]
    key = COSObjectKey(7, 0)
    table: dict[COSObjectKey, int] = {key: 100}
    assert xref.find_object_key(key, 100, table) is key
    assert stub.received == (key, 100, table)
