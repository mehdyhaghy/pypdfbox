"""Operand-run / simple-array shortcuts of the splitter's fast resource scan.

The shortcuts skip name-free operand runs and flat ``TJ``-style arrays in one
regex match; they must never change what ``_fast_scan_resource_names``
returns, so every case is checked against the exact ``PDFStreamParser`` scan
(or, for rejected streams, that the fast path still bails out).
"""

import random
import time

import pytest

from pypdfbox.cos import COSName
from pypdfbox.multipdf import Splitter
from pypdfbox.multipdf.splitter import _fast_scan_resource_names


def _fast_as_str(data: bytes) -> dict[str, frozenset[str]] | None:
    fast = _fast_scan_resource_names(data)
    if fast is None:
        return None
    return {
        c: frozenset(COSName.get_pdf_name(raw).get_name() for raw in names)
        for c, names in fast.items()
    }


_ACCEPTED = [
    b"BT 1 0 0 1 72 720 Tm [(abc) -120 <4142> (d\\)e)] TJ /F1 9 Tf ET",
    b"[(a\\(b) 3] TJ /F1 1 Tf",  # escaped "(" -> token-by-token path
    b"1 2 d0 /F1 1 Tf",  # d0 folding is left to the main loop
    b"[1 2] 0 d /F2 1 Tf",
    b"5 w true /F1 1 Tf /F3 2 Tf",  # true is an operand, so F1 is not a name op
    b"[[1 2] 3] /F1 1 Tf /F4 2 Tf",  # nested array -> token path
    b"0.5 g ' /F5 1 Tf (x) \" /Im1 Do",
    b"%c 1 2\n3 re f* /GS0 gs",
    b"[<41> ( ) 1.5 -.5 +2] TJ\r\n/P0 scn",
    b"(x) Tj [] TJ /Sh0 sh",
]

_REJECTED = [
    b"1 1 Iq /F1 1 Tf",  # keyword starting with I
    b"1 2 BI /W 1 ID \x00 EI",
    b"[1 2 12Tf] /F1 Tf",
    b"1 2 3 >> /F1 1 Tf",
    b"[" + b" " * 50000 + b"{",
]


@pytest.mark.parametrize("data", _ACCEPTED, ids=range(len(_ACCEPTED)))
def test_shortcut_streams_match_exact_parser(data: bytes) -> None:
    fast = _fast_as_str(data)
    assert fast is not None
    assert fast == Splitter._exact_scan_resource_names(data)


@pytest.mark.parametrize("data", _REJECTED, ids=range(len(_REJECTED)))
def test_shortcut_streams_outside_subset_still_rejected(data: bytes) -> None:
    assert _fast_scan_resource_names(data) is None


def test_long_unsupported_runs_do_not_backtrack() -> None:
    data = b"1 " * 20000 + b"[" + b"(a) " * 20000 + b"{"
    start = time.perf_counter()
    assert _fast_scan_resource_names(data) is None
    assert time.perf_counter() - start < 5


def test_shortcut_fuzz_agrees_with_exact_parser() -> None:
    vocab = [
        b"1", b"-2", b".5", b"5.", b"(a)", b"(a\\)b)", b"(a\\(b)", b"<41>",
        b"[", b"]", b"[(a) -1 <42>]", b"TJ", b"Tj", b"Tf", b"Do", b"d", b"d0",
        b"0", b"true", b"null", b"'", b"\"", b"/F1", b"/Im0", b"%c\n", b"BT",
        b"ET", b"I", b"<<", b">>", b"(", b")", b"re", b"f*", b"12Tf",
    ]
    rng = random.Random(1631)
    accepted = 0
    for _ in range(4000):
        data = b"".join(
            rng.choice(vocab) + rng.choice([b" ", b"\n", b"", b"\r\n"])
            for _ in range(rng.randint(1, 25))
        )
        fast = _fast_as_str(data)
        if fast is None:
            continue
        accepted += 1
        assert fast == Splitter._exact_scan_resource_names(data), data
    assert accepted > 100
