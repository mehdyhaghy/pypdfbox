"""Tests for ``pypdfbox writedecodedstream`` and the ``write_decoded`` helper.

The tool reads a PDF, decodes every ``COSStream`` (running the /Filter
chain in reverse), strips the ``/Filter`` and ``/DecodeParms`` entries,
and writes the result back. The test fixture builds a tiny PDF whose
content stream is FlateDecode-encoded, runs the tool, then re-parses
the output and asserts every stream is now plain.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.tools import cli
from pypdfbox.tools.writedecodedstream import (
    calculate_output_filename,
    write_decoded,
)

# A tiny but valid content-stream payload — keeps Flate output a few bytes
# different from the source so we can prove decoding actually ran.
_CONTENT = (
    b"BT /F1 12 Tf 50 700 Td (writedecodedstream round trip) Tj ET\n"
    b"% padding to make the deflate output non-trivial: " + (b"X" * 200)
)


def _build_pdf_with_flate_stream(path: Path) -> Path:
    """Write a PDF whose page-content stream is /FlateDecode-encoded."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        # Encode on the way in so the on-disk body is genuinely Flate'd.
        with stream.create_output_stream(filters=COSName.FLATE_DECODE) as out:
            out.write(_CONTENT)
        page.set_contents(stream)
        doc.save(path)
    finally:
        doc.close()
    return path


# -------------------------------------------------- calculate_output_filename


def test_calculate_output_filename_strips_pdf_suffix() -> None:
    assert calculate_output_filename("foo.pdf") == "foo_unc.pdf"


def test_calculate_output_filename_case_insensitive() -> None:
    assert calculate_output_filename("FOO.PDF") == "FOO_unc.pdf"


def test_calculate_output_filename_no_suffix() -> None:
    assert calculate_output_filename("foo") == "foo_unc.pdf"


def test_calculate_output_filename_path_object(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    expected = str(tmp_path / "doc") + "_unc.pdf"
    assert calculate_output_filename(src) == expected


# ------------------------------------------------------------ write_decoded


def test_write_decoded_strips_filter_entries(tmp_path: Path) -> None:
    src = _build_pdf_with_flate_stream(tmp_path / "in.pdf")

    # Sanity: source genuinely carries a /Filter on at least one stream.
    with PDDocument.load(src) as before:
        had_filter = False
        for cos_obj in before.get_document().get_objects():
            base = cos_obj.get_object()
            if isinstance(base, COSStream) and base.get_filter_list():
                had_filter = True
                break
        assert had_filter, "test fixture must contain a filtered stream"

    out = tmp_path / "out.pdf"
    write_decoded(src, out)

    assert out.is_file()
    with PDDocument.load(out) as after:
        for cos_obj in after.get_document().get_objects():
            base = cos_obj.get_object()
            if isinstance(base, COSStream):
                # The decoder may have run, leaving the stream plain. The
                # writer is allowed to re-encode object streams it owns,
                # so we permit one well-known re-encoding case (the writer
                # may pack into an /ObjStm, but because we forced
                # set_xref_stream(False) and don't pack, none should
                # carry a filter).
                assert base.get_filter_list() == [], (
                    f"stream still carries /Filter after decode: "
                    f"{base.get_filter_list()}"
                )


def test_write_decoded_preserves_content(tmp_path: Path) -> None:
    """The decoded raw bytes must match the original payload."""
    src = _build_pdf_with_flate_stream(tmp_path / "in.pdf")
    out = tmp_path / "out.pdf"
    write_decoded(src, out)

    # Walk the object pool and find the content stream whose raw body now
    # equals _CONTENT — after decoding, the raw body IS the plaintext
    # payload (no filter chain to unwind).
    with PDDocument.load(out) as after:
        found = False
        for cos_obj in after.get_document().get_objects():
            base = cos_obj.get_object()
            if isinstance(base, COSStream) and base.get_raw_data() == _CONTENT:
                found = True
                # And the /Filter entry is gone.
                assert base.get_filter_list() == []
                break
        assert found, "decoded content stream not found in output"


# --------------------------------------------------------------- CLI driver


def test_cli_writes_to_explicit_output(tmp_path: Path) -> None:
    src = _build_pdf_with_flate_stream(tmp_path / "in.pdf")
    out = tmp_path / "decoded.pdf"
    rc = cli.run_cli(
        ["writedecodedstream", "-i", str(src), "-o", str(out)]
    )
    assert rc == 0
    assert out.is_file()


def test_cli_default_output_filename(tmp_path: Path) -> None:
    src = _build_pdf_with_flate_stream(tmp_path / "in.pdf")
    rc = cli.run_cli(["writedecodedstream", "-i", str(src)])
    assert rc == 0
    expected = tmp_path / "in_unc.pdf"
    assert expected.is_file()


def test_cli_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.run_cli(
        ["writedecodedstream", "-i", str(tmp_path / "nope.pdf")]
    )
    assert rc == 4
    assert "not a file" in capsys.readouterr().out


def test_cli_skip_images_flag_accepted(tmp_path: Path) -> None:
    """``-skipImages`` should parse and run; the fixture has no image
    XObjects, so the flag is a pure no-op here."""
    src = _build_pdf_with_flate_stream(tmp_path / "in.pdf")
    out = tmp_path / "decoded.pdf"
    rc = cli.run_cli(
        ["writedecodedstream", "-i", str(src), "-o", str(out), "-skipImages"]
    )
    assert rc == 0
    assert out.is_file()
