"""Robustness (wave 1404): an unknown/corrupted ``/Filter`` name in stream
data must fail with an I/O-level error, not leak the filter registry's
``KeyError`` to the caller.

Found by the malformed-input fuzz harness: mutating a valid PDF so a stream's
``/Filter`` became e.g. ``/Fla4eDecode`` made ``Loader.load_pdf`` raise a bare
``KeyError`` instead of the parser's graceful error type. ``COSStream``'s
decode path now mirrors upstream ``FilterFactory.getFilter`` (which throws
``IOException("Invalid filter: ...")``) by re-raising as ``OSError``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream


def test_unknown_filter_raises_oserror_not_keyerror() -> None:
    with COSStream() as s:
        with s.create_raw_output_stream() as out:
            out.write(b"some raw bytes")
        # Name an unregistered filter directly on the dict.
        s.set_item(COSName.FILTER, COSName.get_pdf_name("Fla4eDecode"))
        with pytest.raises(OSError) as exc:
            s.create_input_stream()
    # Must be the graceful I/O error, and must NOT be a bare KeyError.
    assert not isinstance(exc.value, KeyError)
    assert "Invalid filter" in str(exc.value)
    assert "Fla4eDecode" in str(exc.value)


def test_unknown_filter_in_chain_raises_oserror() -> None:
    """An unknown filter anywhere in a multi-filter chain still fails
    gracefully (here the first entry is valid, the second is bogus)."""
    from pypdfbox.cos import COSArray

    with COSStream() as s:
        with s.create_raw_output_stream() as out:
            out.write(b"abc")
        chain = COSArray()
        chain.add(COSName.FLATE_DECODE)
        chain.add(COSName.get_pdf_name("NlateDecode"))
        s.set_item(COSName.FILTER, chain)
        with pytest.raises(OSError):
            s.create_input_stream()
