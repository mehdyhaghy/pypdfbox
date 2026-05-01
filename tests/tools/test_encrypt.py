"""Tests for ``pypdfbox encrypt`` and the ``encrypt_pdf`` helper.

Round-trips a freshly built PDF through the encrypt CLI and then back
through ``decrypt`` (and ``PDDocument.load`` with a password) to confirm
the output is genuinely encrypted, the supplied permissions land on
``/Encrypt /P``, and ``-keyLength`` plumbs through to the protection
policy.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import AccessPermission
from pypdfbox.tools import cli
from pypdfbox.tools.encrypt import encrypt_pdf


# -------------------------------------------------------------- CLI: basics


def test_encrypt_cli_round_trip_with_decrypt(
    tmp_path: Path, make_pdf
) -> None:
    src = make_pdf("plain.pdf")
    enc = tmp_path / "enc.pdf"
    rc = cli.run_cli(
        [
            "encrypt",
            "-i", str(src),
            "-o", str(enc),
            "-O", "owner",
            "-U", "user",
            "-keyLength", "128",
        ]
    )
    assert rc == 0
    assert enc.is_file()

    # Output must report encrypted.
    with PDDocument.load(enc, password="user") as doc:
        assert doc.is_encrypted() is True
        assert doc.get_number_of_pages() == 1

    # And it must round-trip through decrypt.
    dec = tmp_path / "dec.pdf"
    rc = cli.run_cli(
        ["decrypt", "-i", str(enc), "-o", str(dec), "-password", "owner"]
    )
    assert rc == 0
    with PDDocument.load(dec) as doc:
        assert doc.is_encrypted() is False
        assert doc.get_number_of_pages() == 1


def test_encrypt_cli_owner_password_only(tmp_path: Path, make_pdf) -> None:
    src = make_pdf("oo.pdf")
    enc = tmp_path / "enc.pdf"
    rc = cli.run_cli(
        ["encrypt", "-i", str(src), "-o", str(enc), "-O", "boss",
         "-keyLength", "128"]
    )
    assert rc == 0
    with PDDocument.load(enc, password="boss") as doc:
        assert doc.is_encrypted() is True


def test_encrypt_cli_missing_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.run_cli(["encrypt", "-i", str(tmp_path / "nope.pdf")])
    assert rc == 4
    assert "not a file" in capsys.readouterr().out


def test_encrypt_cli_already_encrypted_is_noop(
    tmp_path: Path, make_pdf, capsys: pytest.CaptureFixture[str]
) -> None:
    src = make_pdf("plain.pdf")
    enc = tmp_path / "enc.pdf"
    rc = cli.run_cli(
        ["encrypt", "-i", str(src), "-o", str(enc), "-U", "u",
         "-keyLength", "128"]
    )
    assert rc == 0
    # Re-encrypting an encrypted file should print the upstream
    # "Document is already encrypted" message and skip the rewrite.
    enc2 = tmp_path / "enc2.pdf"
    rc = cli.run_cli(
        ["encrypt", "-i", str(enc), "-o", str(enc2), "-U", "u",
         "-keyLength", "128"]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "already encrypted" in out
    assert not enc2.exists()


# ----------------------------------------------------- permission flags


def test_encrypt_cli_permission_flags_disabled(
    tmp_path: Path, make_pdf
) -> None:
    src = make_pdf("perm.pdf")
    enc = tmp_path / "enc.pdf"
    rc = cli.run_cli(
        [
            "encrypt", "-i", str(src), "-o", str(enc),
            "-O", "owner", "-U", "user",
            "-keyLength", "128",
            "--no-canPrint",
            "--no-canModify",
            "--no-canExtractContent",
        ]
    )
    assert rc == 0

    # Open with the user password — inspect the /P integer directly so
    # we read the policy as written, not the handler's view of it (which
    # masks bits depending on revision and password type).
    with PDDocument.load(enc, password="user") as doc:
        encryption = doc.get_encryption()
        ap = AccessPermission(encryption.get_p())
        assert ap.can_print() is False
        assert ap.can_modify() is False
        assert ap.can_extract_content() is False
        # Untouched flags stay True (their default).
        assert ap.can_fill_in_form() is True
        assert ap.can_assemble_document() is True


def test_encrypt_cli_default_permissions_all_true(
    tmp_path: Path, make_pdf
) -> None:
    src = make_pdf("allow.pdf")
    enc = tmp_path / "enc.pdf"
    rc = cli.run_cli(
        ["encrypt", "-i", str(src), "-o", str(enc), "-U", "user",
         "-keyLength", "128"]
    )
    assert rc == 0
    with PDDocument.load(enc, password="user") as doc:
        encryption = doc.get_encryption()
        ap = AccessPermission(encryption.get_p())
        assert ap.can_print() is True
        assert ap.can_modify() is True
        assert ap.can_extract_content() is True
        assert ap.can_modify_annotations() is True
        assert ap.can_fill_in_form() is True
        assert ap.can_extract_for_accessibility() is True
        assert ap.can_assemble_document() is True
        assert ap.can_print_degraded() is True


# ------------------------------------------------------ encrypt_pdf API


def test_encrypt_pdf_helper_round_trips(tmp_path: Path, make_pdf) -> None:
    src = make_pdf("api.pdf")
    out = tmp_path / "api-enc.pdf"
    encrypt_pdf(
        src, out,
        owner_password="owner", user_password="user",
        permissions=AccessPermission(),
        key_length=128,
    )
    with PDDocument.load(out, password="user") as doc:
        assert doc.is_encrypted() is True


def test_encrypt_pdf_helper_skips_already_encrypted(
    tmp_path: Path, make_pdf
) -> None:
    src = make_pdf("twice.pdf")
    once = tmp_path / "once.pdf"
    encrypt_pdf(src, once, user_password="u", key_length=128)
    twice = tmp_path / "twice-enc.pdf"
    encrypt_pdf(once, twice, user_password="u", key_length=128)
    # Upstream's "already encrypted" branch is a no-op on the writer side.
    assert not twice.exists()


def test_encrypt_pdf_helper_invalid_key_length_raises(
    tmp_path: Path, make_pdf
) -> None:
    src = make_pdf("bad.pdf")
    out = tmp_path / "bad-enc.pdf"
    with pytest.raises(ValueError):
        encrypt_pdf(src, out, user_password="u", key_length=64)


def test_encrypt_cli_invalid_key_length_returns_four(
    tmp_path: Path, make_pdf, capsys: pytest.CaptureFixture[str]
) -> None:
    src = make_pdf("bad.pdf")
    out = tmp_path / "bad-enc.pdf"
    rc = cli.run_cli(
        ["encrypt", "-i", str(src), "-o", str(out), "-U", "u",
         "-keyLength", "64"]
    )
    assert rc == 4
    assert "Error encrypting" in capsys.readouterr().out


# ------------------------------ upstream parity: print-faithful flag


def test_encrypt_cli_no_can_print_faithful(
    tmp_path: Path, make_pdf
) -> None:
    """`--no-canPrintFaithful` must clear the FAITHFUL_PRINT_BIT (the
    high-quality print bit, 12) — verified by reading /P off the saved
    /Encrypt dictionary. Upstream maps `-canPrintFaithful` directly to
    `AccessPermission.setCanPrintFaithful`."""
    src = make_pdf("faithful.pdf")
    enc = tmp_path / "enc.pdf"
    rc = cli.run_cli(
        [
            "encrypt", "-i", str(src), "-o", str(enc),
            "-U", "user", "-keyLength", "128",
            "--no-canPrintFaithful",
        ]
    )
    assert rc == 0
    with PDDocument.load(enc, password="user") as doc:
        encryption = doc.get_encryption()
        ap = AccessPermission(encryption.get_p())
        # The faithful (high-quality) print bit must be off.
        assert ap.can_print_faithful() is False
        # Other defaults stay on.
        assert ap.can_print() is True
        assert ap.can_modify() is True
