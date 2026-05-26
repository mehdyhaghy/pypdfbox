"""Robustness (wave 1405): malformed CFF data must raise ``OSError``, not leak
fontTools' ``AssertionError``.

``CFFParser`` delegates the CFF binary parse to fontTools (library-first), which
validates with bare ``assert`` statements (e.g. ``assert offSize <= 4``) and can
raise struct/index/key errors on malformed data. A raw ``AssertionError`` would
surprise callers catching ``OSError`` — and ``python -O`` strips ``assert``
entirely, removing the validation. CFF is embedded in PDFs (Type1C /
CIDFontType0C via ``/FontFile3``), so this is reachable from untrusted input.
The parser now adapts fontTools' failure modes to ``OSError`` (mirroring
upstream ``CFFParser``, which throws ``IOException``). Found by the wave-1405
fuzz harness.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser


def test_malformed_cff_raises_oserror_not_assertionerror() -> None:
    # These bytes trip fontTools' ``assert offSize <= 4`` deep in decompile.
    with pytest.raises(OSError) as exc:
        CFFParser().parse(b"\x01\x00\x04\x02not a real cff font blah blah")
    assert not isinstance(exc.value, AssertionError)


def test_empty_cff_raises_oserror() -> None:
    with pytest.raises(OSError):
        CFFParser().parse(b"")


def test_truncated_cff_header_raises_oserror() -> None:
    with pytest.raises(OSError):
        CFFParser().parse(b"\x01\x00")
