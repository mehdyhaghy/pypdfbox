"""Tests for ``pypdfbox decrypt``.

Cluster #1 only handles the not-encrypted case; an encrypted-input test
is included as ``xfail`` to guard the upgrade once the security cluster
lands. Generating an encrypted document requires the security cluster
itself, so we stub it via a manual ``/Encrypt`` entry on the trailer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName
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
    doc = PDDocument()
    # Stamp /Encrypt on the trailer so PDDocument.is_encrypted() returns
    # True. The dict body is intentionally minimal — we exercise the CLI
    # branch, not the security stack.
    enc = COSDictionary()
    enc.set_int(COSName.get_pdf_name("V"), 1)
    enc.set_int(COSName.get_pdf_name("R"), 2)
    enc.set_int(COSName.get_pdf_name("Length"), 40)
    trailer = doc.get_document().get_trailer()
    assert trailer is not None
    trailer.set_item(COSName.ENCRYPT, enc)  # type: ignore[attr-defined]
    doc.save(src)
    doc.close()

    rc = cli.run_cli(["decrypt", "-i", str(src)])
    assert rc == 1
    assert "security cluster" in capsys.readouterr().out
