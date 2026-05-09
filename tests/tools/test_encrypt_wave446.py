"""Wave 446 coverage for ``pypdfbox.tools.encrypt`` edge branches."""
from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

import pytest

from pypdfbox.pdmodel.encryption import (
    AccessPermission,
    PublicKeyProtectionPolicy,
    StandardProtectionPolicy,
)
from pypdfbox.tools import cli
from pypdfbox.tools import encrypt as encrypt_tool


def _namespace(**overrides: object) -> argparse.Namespace:
    values = {
        "can_assemble_document": False,
        "can_extract_content": False,
        "can_extract_for_accessibility": False,
        "can_fill_in_form": False,
        "can_modify": False,
        "can_modify_annotations": False,
        "can_print": False,
        "can_print_faithful": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_build_access_permission_maps_every_cli_flag() -> None:
    ap = encrypt_tool._build_access_permission(
        _namespace(
            can_assemble_document=True,
            can_extract_for_accessibility=True,
            can_modify_annotations=True,
            can_print_faithful=True,
        )
    )

    assert ap.can_assemble_document() is True
    assert ap.can_extract_for_accessibility() is True
    assert ap.can_modify_annotations() is True
    assert ap.can_print_faithful() is True
    assert ap.can_extract_content() is False
    assert ap.can_fill_in_form() is False
    assert ap.can_modify() is False
    assert ap.can_print() is False


class _FakeDocument:
    def __init__(self, *, encrypted: bool = False, signatures: bool = False) -> None:
        self.encrypted = encrypted
        self.signatures = signatures
        self.protected_with: object | None = None
        self.saved_to: Path | None = None
        self.closed = False

    def __enter__(self) -> _FakeDocument:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def is_encrypted(self) -> bool:
        return self.encrypted

    def get_signature_dictionaries(self) -> list[object]:
        return [object()] if self.signatures else []

    def protect(self, policy: object) -> None:
        self.protected_with = policy

    def save(self, output_path: str | Path) -> None:
        self.saved_to = Path(output_path)

    def close(self) -> None:
        self.closed = True


def test_encrypt_pdf_uses_public_key_policy_for_cert_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _FakeDocument()
    certs = [object(), object()]

    monkeypatch.setattr(encrypt_tool.PDDocument, "load", lambda path: document)
    monkeypatch.setattr(encrypt_tool, "_load_certificates", lambda paths: certs)

    permissions = AccessPermission()
    out = tmp_path / "cert-encrypted.pdf"

    encrypt_tool.encrypt_pdf(
        tmp_path / "plain.pdf",
        out,
        permissions=permissions,
        cert_files=["one.cer", "two.cer"],
        key_length=128,
    )

    assert isinstance(document.protected_with, PublicKeyProtectionPolicy)
    assert document.protected_with.get_encryption_key_length() == 128
    recipients = document.protected_with.get_recipients()
    assert [recipient.get_x509() for recipient in recipients] == certs
    assert [recipient.get_permission() for recipient in recipients] == [
        permissions,
        permissions,
    ]
    assert document.saved_to == out
    assert document.closed is True


def test_encrypt_pdf_closes_document_when_standard_policy_save_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = _FakeDocument()

    def fail_save(output_path: str | Path) -> None:
        raise OSError("disk full")

    document.save = fail_save  # type: ignore[method-assign]
    monkeypatch.setattr(encrypt_tool.PDDocument, "load", lambda path: document)

    with pytest.raises(OSError, match="disk full"):
        encrypt_tool.encrypt_pdf(tmp_path / "plain.pdf", tmp_path / "out.pdf")

    assert isinstance(document.protected_with, StandardProtectionPolicy)
    assert document.closed is True


def test_run_warns_for_signed_document_and_continues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "signed.pdf"
    out = tmp_path / "encrypted.pdf"
    src.write_bytes(b"%PDF-1.7\n")
    probe = _FakeDocument(signatures=True)

    monkeypatch.setattr(encrypt_tool.PDDocument, "load", lambda path: probe)

    calls: list[tuple[Path, Path]] = []

    def fake_encrypt_pdf(
        input_path: str | Path,
        output_path: str | Path,
        *,
        owner_password: str | None = None,
        user_password: str | None = None,
        permissions: AccessPermission | None = None,
        cert_files: Iterable[str | Path] = (),
        key_length: int = encrypt_tool.DEFAULT_KEY_LENGTH,
    ) -> None:
        calls.append((Path(input_path), Path(output_path)))

    monkeypatch.setattr(encrypt_tool, "encrypt_pdf", fake_encrypt_pdf)

    rc = encrypt_tool.run(
        argparse.Namespace(
            input=str(src),
            output=str(out),
            owner_password=None,
            user_password="user",
            cert_files=[],
            key_length=128,
            **vars(_namespace()),
        )
    )

    assert rc == 0
    assert calls == [(src, out)]
    assert "contains signatures" in capsys.readouterr().out


def test_run_returns_four_when_probe_load_raises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "broken.pdf"
    src.write_bytes(b"%PDF-1.7\n")

    def fail_load(path: Path) -> _FakeDocument:
        raise OSError("cannot parse")

    monkeypatch.setattr(encrypt_tool.PDDocument, "load", fail_load)

    rc = encrypt_tool.run(
        argparse.Namespace(
            input=str(src),
            output=None,
            owner_password=None,
            user_password=None,
            cert_files=[],
            key_length=128,
            **vars(_namespace()),
        )
    )

    assert rc == 4
    assert "cannot parse" in capsys.readouterr().out


def test_cli_no_permission_flag_can_be_reenabled(tmp_path: Path, make_pdf) -> None:
    src = make_pdf("reenabled.pdf")
    enc = tmp_path / "enc.pdf"

    rc = cli.run_cli(
        [
            "encrypt",
            "-i",
            str(src),
            "-o",
            str(enc),
            "-U",
            "user",
            "-keyLength",
            "128",
            "--no-canPrint",
            "-canPrint",
        ]
    )

    assert rc == 0
