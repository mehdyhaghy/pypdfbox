from __future__ import annotations

from pypdfbox.cos import COSName, COSStream


def test_stop_filters_match_short_filter_names_by_long_name() -> None:
    payload = b"short filter alias should still stop before decoding" * 3

    with COSStream() as stream:
        with stream.create_output_stream("Fl") as output:
            output.write(payload)
        raw = stream.to_raw_byte_array()

        assert raw != payload
        assert stream.get_filters_as_strings() == ["Fl"]
        assert stream.create_input_stream(stop_filters="FlateDecode").read() == raw


def test_stop_filters_match_long_filter_names_by_short_name() -> None:
    payload = b"long filter name should stop for short stop alias" * 3

    with COSStream() as stream:
        with stream.create_output_stream(COSName.FLATE_DECODE) as output:  # type: ignore[attr-defined]
            output.write(payload)
        raw = stream.to_raw_byte_array()

        assert raw != payload
        assert stream.create_input_stream(stop_filters=COSName.get_pdf_name("Fl")).read() == raw
