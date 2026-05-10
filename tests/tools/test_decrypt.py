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


def test_decrypt_unencrypted_returns_one(
    tmp_path: Path, make_pdf, capsys: pytest.CaptureFixture[str]
) -> None:
    """Upstream Decrypt#call returns 1 with "Error: Document is not encrypted."
    when the input has no /Encrypt entry. Mirror that exit code + message."""
    pdf = make_pdf("plain.pdf")
    out = tmp_path / "decrypted.pdf"
    rc = cli.run_cli(["decrypt", "-i", str(pdf), "-o", str(out)])
    assert rc == 1
    assert "not encrypted" in capsys.readouterr().out
    # The output file must NOT have been written.
    assert not out.exists()


def test_decrypt_in_place_when_no_output_unencrypted_returns_one(
    make_pdf, capsys: pytest.CaptureFixture[str]
) -> None:
    """Upstream returns 1 even for in-place runs when input is unencrypted."""
    pdf = make_pdf("inplace.pdf")
    original_bytes = pdf.read_bytes()
    rc = cli.run_cli(["decrypt", "-i", str(pdf)])
    assert rc == 1
    assert "not encrypted" in capsys.readouterr().out
    # Source file must remain untouched.
    assert pdf.read_bytes() == original_bytes


def test_decrypt_pdf_helper_unencrypted_passthrough(
    tmp_path: Path, make_pdf
) -> None:
    """The library helper still passes through unencrypted inputs; only the
    CLI gates them off (matches upstream API surface — Decrypt#call is the
    error gate, Loader.loadPDF is the helper)."""
    pdf = make_pdf("plain.pdf")
    out = tmp_path / "decrypted.pdf"
    decrypt_pdf(pdf, out, password="")
    assert out.is_file()
    with PDDocument.load(out) as d:
        assert d.get_number_of_pages() == 1
        assert d.is_encrypted() is False


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
    """Owner password is required to strip /Encrypt — matches upstream
    Decrypt#call's owner-permission gate."""
    src = _build_encrypted_pdf(tmp_path / "enc.pdf")
    out = tmp_path / "dec.pdf"
    rc = cli.run_cli(
        ["decrypt", "-i", str(src), "-o", str(out), "-password", "owner"]
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


# ----------------------------------------- upstream parity: owner gate


def test_decrypt_cli_user_password_only_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Upstream prints "Error: You are only allowed to decrypt a document
    with the owner password." and returns 1 when the supplied password
    unlocks the document but only with user-level permissions (i.e. the
    AccessPermission is not is_owner_permission())."""
    src = _build_encrypted_pdf(
        tmp_path / "owner-locked.pdf",
        owner_password="boss",
        user_password="reader",
    )
    out = tmp_path / "dec.pdf"
    # Build with restrictive permissions so opening as user is non-owner.
    pd = PDDocument()
    try:
        from pypdfbox.cos import COSStream
        from pypdfbox.pdmodel import PDPage

        page = PDPage()
        pd.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as o:
            o.write(b"BT ET")
        page.set_contents(stream)
        ap = AccessPermission()
        ap.set_can_print(False)
        ap.set_can_modify(False)
        pd.protect(
            StandardProtectionPolicy(
                owner_password="boss",
                user_password="reader",
                permissions=ap,
            )
        )
        pd.save(src)
    finally:
        pd.close()

    rc = cli.run_cli(
        ["decrypt", "-i", str(src), "-o", str(out), "-password", "reader"]
    )
    assert rc == 1
    captured = capsys.readouterr().out
    assert "owner password" in captured
    # Output file must NOT have been written when owner gate fails.
    assert not out.exists()


def test_decrypt_cli_owner_password_succeeds_when_restricted(
    tmp_path: Path,
) -> None:
    """Owner password must succeed even when user permissions are restricted.
    This is the inverse of the user-password test above — owner credentials
    grant full access regardless of the /P bits."""
    src = tmp_path / "owner-locked.pdf"
    pd = PDDocument()
    try:
        from pypdfbox.cos import COSStream
        from pypdfbox.pdmodel import PDPage

        page = PDPage()
        pd.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as o:
            o.write(b"BT ET")
        page.set_contents(stream)
        ap = AccessPermission()
        ap.set_can_print(False)
        pd.protect(
            StandardProtectionPolicy(
                owner_password="boss",
                user_password="reader",
                permissions=ap,
            )
        )
        pd.save(src)
    finally:
        pd.close()

    out = tmp_path / "dec.pdf"
    rc = cli.run_cli(
        ["decrypt", "-i", str(src), "-o", str(out), "-password", "boss"]
    )
    assert rc == 0
    with PDDocument.load(out) as reloaded:
        assert reloaded.is_encrypted() is False


# ----------------------------------------- upstream parity: keyStore flag


def test_decrypt_cli_keystore_flag_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `-keyStore` and `-alias` flags must parse and surface a
    parity-shaped error when the file isn't a valid PKCS#12 keystore. This
    locks the CLI surface even though end-to-end public-key decryption is
    not yet wired into PDDocument.decrypt."""
    bogus = tmp_path / "fake.p12"
    bogus.write_bytes(b"not-a-real-pkcs12-blob")
    rc = cli.run_cli(
        [
            "decrypt", "-i", str(bogus), "-keyStore", str(bogus),
            "-alias", "myalias", "-password", "kspw",
            "-o", str(tmp_path / "out.pdf"),
        ]
    )
    # The input file existence check happens before keystore loading;
    # bogus exists, so we proceed to keystore load and fail with exit 4
    # in upstream's error format.
    assert rc == 4
    out = capsys.readouterr().out
    assert "Error decrypting document" in out


def test_decrypt_cli_keystore_help_lists_alias() -> None:
    """`-keyStore` and `-alias` must appear in the parser help (CLI surface
    parity check)."""
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    from pypdfbox.tools.decrypt import build_parser

    build_parser(sub)
    decrypt_parser = sub.choices["decrypt"]
    flags = {action.option_strings[0] for action in decrypt_parser._actions
             if action.option_strings}
    assert "-keyStore" in flags
    assert "-alias" in flags


# ----------------------------------------- upstream parity: error format


def test_decrypt_cli_io_error_uses_upstream_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed encrypted-looking input should surface as
    `Error decrypting document [<class>]: <msg>` (upstream format)."""
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4\n%%EOF garbage")
    rc = cli.run_cli(["decrypt", "-i", str(bad)])
    assert rc == 4
    out = capsys.readouterr().out
    assert "Error decrypting document" in out
