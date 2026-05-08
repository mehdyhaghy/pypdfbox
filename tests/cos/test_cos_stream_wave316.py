from __future__ import annotations

from pypdfbox.cos import COSName, COSStream


def test_wave316_unfiltered_output_clears_stale_filters() -> None:
    with COSStream() as stream:
        with stream.create_output_stream(COSName.FLATE_DECODE) as output:  # type: ignore[attr-defined]
            output.write(b"compressed first")

        with stream.create_output_stream() as output:
            output.write(b"plain replacement")

        assert stream.get_filters() is None
        assert stream.to_raw_byte_array() == b"plain replacement"
        assert stream.to_byte_array() == b"plain replacement"
