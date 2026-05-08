"""Wave 309 hardening tests for ``pypdfbox writedecodedstream``."""
from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption import AccessPermission, StandardProtectionPolicy
from pypdfbox.tools import cli


def _build_encrypted_pdf(path: Path) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.protect(
            StandardProtectionPolicy(
                owner_password="owner",
                user_password="user",
                permissions=AccessPermission(),
            )
        )
        doc.save(path)
    finally:
        doc.close()
    return path


def test_writedecodedstream_wrong_password_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = _build_encrypted_pdf(tmp_path / "locked.pdf")
    out = tmp_path / "decoded.pdf"

    rc = cli.run_cli(
        [
            "writedecodedstream",
            "-i",
            str(src),
            "-o",
            str(out),
            "-password",
            "wrong",
        ]
    )

    assert rc == 1
    assert "password is incorrect" in capsys.readouterr().out
    assert not out.exists()
