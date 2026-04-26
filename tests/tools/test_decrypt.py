"""Tests for ``pypdfbox decrypt`` and the ``decrypt_pdf`` helper.

The CLI now drives the security cluster end-to-end, so encrypted-input
tests build a real ``/Encrypt`` dictionary via ``PDDocument.protect`` +
``save`` and then decrypt the resulting bytes.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox import Loader
from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.tools import cli
from pypdfbox.tools.decrypt import decrypt_pdf


# ----------------------------------------------------------------- helpers


_CONTENT_PAYLOAD = b"BT /F1 12 Tf 50 700 Td (decrypt-tool round trip) Tj ET"


def _build_encrypted_pdf(
    path: Path,
    *,
    owner_password: str = "owner",
    user_password: str = "user",
) -> Path:
    """Write an encrypted PDF (one page, one content stream) to ``path``."""
    pd = PDDocument()
    try:
        page = PDPage()
        pd.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(_CONTENT_PAYLOAD)
        page.set_contents(stream)
        pd.protect(
            StandardProtectionPolicy(
                owner_password=owner_password,
                user_password=user_password,
                permissions=AccessPermission(),
            )
        )
        pd.save(path)
    finally:
        pd.close()
    return path


# ---------------------------------------------------------- pass-through


def test_decrypt_unencrypted_passthrough(tmp_path: Path, make_pdf) -> None:
    pdf = make_pdf("plain.pdf")
    out = tmp_path / "decrypted.pdf"
    rc = cli.run_cli(["decrypt", "-i", str(pdf), "-o", str(out)])
    assert rc == 0
    assert out.is_file()
    with PDDocument.load(out) as d:
        assert d.get_number_of_pages() == 1
        assert d.is_encrypted() is False


def test_decrypt_in_place_when_no_output(make_pdf) -> None:
    pdf = make_pdf("inplace.pdf")
    rc = cli.run_cli(["decrypt", "-i", str(pdf)])
    assert rc == 0
    with PDDocument.load(pdf) as d:
        assert d.get_number_of_pages() == 1


def test_decrypt_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.run_cli(["decrypt", "-i", str(tmp_path / "nope.pdf")])
    assert rc == 4
    assert "not a file" in capsys.readouterr().out


# ------------------------------------------------- decrypt_pdf API


def test_decrypt_pdf_strips_encrypt_entry(tmp_path: Path) -> None:
    src = _build_encrypted_pdf(tmp_path / "secret.pdf")
    # Sanity: the source IS encrypted on disk.
    encrypted = Loader.load_pdf(src)
    try:
        assert encrypted.is_encrypted() is True
    finally:
        encrypted.close()

    out = tmp_path / "plain.pdf"
    decrypt_pdf(src, out, password="user")

    # Output must load without a password and report unencrypted.
    with PDDocument.load(out) as reloaded:
        assert reloaded.is_encrypted() is False
        assert reloaded.get_number_of_pages() == 1


def test_decrypt_pdf_owner_password(tmp_path: Path) -> None:
    src = _build_encrypted_pdf(
        tmp_path / "owner-locked.pdf",
        owner_password="boss",
        user_password="reader",
    )
    out = tmp_path / "unlocked.pdf"
    decrypt_pdf(src, out, password="boss")
    with PDDocument.load(out) as reloaded:
        assert reloaded.is_encrypted() is False


def test_decrypt_pdf_unencrypted_round_trips(tmp_path: Path, make_pdf) -> None:
    pdf = make_pdf("noenc.pdf")
    out = tmp_path / "noenc-out.pdf"
    decrypt_pdf(pdf, out, password="")
    assert out.is_file()
    with PDDocument.load(out) as reloaded:
        assert reloaded.is_encrypted() is False
        assert reloaded.get_number_of_pages() == 1


# ------------------------------------------------- CLI: encrypted inputs


def test_decrypt_cli_encrypted_with_password(tmp_path: Path) -> None:
    src = _build_encrypted_pdf(tmp_path / "enc.pdf")
    out = tmp_path / "dec.pdf"
    rc = cli.run_cli(
        ["decrypt", "-i", str(src), "-o", str(out), "-password", "user"]
    )
    assert rc == 0
    with PDDocument.load(out) as reloaded:
        assert reloaded.is_encrypted() is False
        assert reloaded.get_number_of_pages() == 1


def test_decrypt_cli_wrong_password_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _build_encrypted_pdf(tmp_path / "enc.pdf")
    out = tmp_path / "dec.pdf"
    rc = cli.run_cli(
        ["decrypt", "-i", str(src), "-o", str(out), "-password", "wrong"]
    )
    assert rc == 1
    assert "password is incorrect" in capsys.readouterr().out
    # Output file should NOT have been created on failure.
    assert not out.exists()


def test_decrypt_cli_in_place_preserves_source_on_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _build_encrypted_pdf(tmp_path / "enc.pdf")
    original = src.read_bytes()
    rc = cli.run_cli(["decrypt", "-i", str(src), "-password", "wrong"])
    assert rc == 1
    assert "password is incorrect" in capsys.readouterr().out
    # Source file untouched after the failed in-place run.
    assert src.read_bytes() == original
