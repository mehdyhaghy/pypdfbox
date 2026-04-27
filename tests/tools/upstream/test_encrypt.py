"""
Ported upstream tests for ``org.apache.pdfbox.tools.Encrypt``.

Upstream PDFBox 3.0 ships **no** ``EncryptTest.java`` — the ``encrypt``
CLI is exercised only indirectly through end-to-end CLI smoke checks
(``PDFBoxHeadlessTest``) and through the underlying
``StandardSecurityHandler`` / ``StandardProtectionPolicy`` unit tests
that already live under ``pypdfbox.tests.pdmodel.encryption``.

This file therefore contains a single intent-level smoke test that
mirrors the upstream ``Encrypt#call`` happy path: load a plain PDF,
apply standard protection with an owner+user password, save, and
confirm the saved file requires a password to open. Behavioural
coverage of the per-flag permission plumbing lives in the hand-written
``tests/tools/test_encrypt.py``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import PDInvalidPasswordException
from pypdfbox.tools import cli


def test_encrypt_saved_pdf_requires_password(
    tmp_path: Path, make_pdf
) -> None:
    """Mirrors the upstream ``Encrypt#call`` happy-path contract:
    after encryption the saved file is opened only with the right password.
    """
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

    # Loading with the wrong password fails ...
    with pytest.raises(PDInvalidPasswordException):
        PDDocument.load(enc, password="bogus").close()

    # ... and succeeds with the user password.
    with PDDocument.load(enc, password="user") as doc:
        assert doc.is_encrypted() is True
