"""Tests for ``pypdfbox decrypt``.

Cluster #1 only handles the not-encrypted case; an encrypted-input test
is included as ``xfail`` to guard the upgrade once the security cluster
lands. Generating an encrypted document requires the security cluster
itself, so we stub it via a manual ``/Encrypt`` entry on the trailer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.tools import cli


def test_decrypt_unencrypted_passthrough(tmp_path: Path, make_pdf) -> None:
    pdf = make_pdf("plain.pdf")
    out = tmp_path / "decrypted.pdf"
    rc = cli.run_cli(["decrypt", "-i", str(pdf), "-o", str(out)])
    assert rc == 0
    assert out.is_file()
    with PDDocument.load(out) as d:
        assert d.get_number_of_pages() == 1


def test_decrypt_in_place_when_no_output(make_pdf) -> None:
    pdf = make_pdf("inplace.pdf")
    rc = cli.run_cli(["decrypt", "-i", str(pdf)])
    assert rc == 0
    # File still loads.
    with PDDocument.load(pdf) as d:
        assert d.get_number_of_pages() == 1


def test_decrypt_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.run_cli(["decrypt", "-i", str(tmp_path / "nope.pdf")])
    assert rc == 4
    assert "not a file" in capsys.readouterr().out


def test_decrypt_encrypted_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cluster #1 cannot strip real encryption — must exit 1, not crash."""
    src = tmp_path / "fake_encrypted.pdf"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Count 0 /Kids [] >>\nendobj\n",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(data))
        data.extend(obj)
    startxref = len(data)
    data.extend(b"xref\n0 3\n")
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = (
        b"trailer\n"
        b"<< /Size 3 /Root 1 0 R /Encrypt << /V 1 /R 2 /Length 40 >> >>\n"
        b"startxref\n"
        + str(startxref).encode("ascii")
        + b"\n%%EOF\n"
    )
    data.extend(trailer)
    src.write_bytes(bytes(data))

    rc = cli.run_cli(["decrypt", "-i", str(src)])
    assert rc == 1
    assert "security cluster" in capsys.readouterr().out
