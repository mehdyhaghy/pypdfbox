from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

import pytest

from pypdfbox.pdmodel.encryption import AccessPermission
from pypdfbox.tools import encrypt as encrypt_tool


class _ProbeDocument:
    def __init__(self, *, encrypted: bool = False) -> None:
        self.encrypted = encrypted
        self.closed = False

    def __enter__(self) -> _ProbeDocument:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def is_encrypted(self) -> bool:
        return self.encrypted

    def get_signature_dictionaries(self) -> list[object]:
        return []

    def close(self) -> None:
        self.closed = True


def _namespace(**overrides: object) -> argparse.Namespace:
    values = {
        "input": "",
        "output": None,
        "owner_password": None,
        "user_password": None,
        "cert_files": [],
        "key_length": 128,
        "can_assemble_document": True,
        "can_extract_content": True,
        "can_extract_for_accessibility": True,
        "can_fill_in_form": True,
        "can_modify": True,
        "can_modify_annotations": True,
        "can_print": True,
        "can_print_faithful": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_wave630_load_certificates_uses_der_then_pem_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cryptography import x509

    der_path = tmp_path / "one.der"
    pem_path = tmp_path / "two.pem"
    der_path.write_bytes(b"der-bytes")
    pem_path.write_bytes(b"pem-bytes")
    calls: list[tuple[str, bytes]] = []

    def fake_der(data: bytes) -> object:
        calls.append(("der", data))
        if data == b"der-bytes":
            return "der-cert"
        raise ValueError("not der")

    def fake_pem(data: bytes) -> object:
        calls.append(("pem", data))
        return "pem-cert"

    monkeypatch.setattr(x509, "load_der_x509_certificate", fake_der)
    monkeypatch.setattr(x509, "load_pem_x509_certificate", fake_pem)

    assert encrypt_tool._load_certificates([der_path, pem_path]) == [
        "der-cert",
        "pem-cert",
    ]
    assert calls == [
        ("der", b"der-bytes"),
        ("der", b"pem-bytes"),
        ("pem", b"pem-bytes"),
    ]


def test_wave630_run_same_output_replaces_source_and_removes_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = tmp_path / "plain.pdf"
    src.write_bytes(b"original")
    probe = _ProbeDocument()
    calls: list[tuple[Path, Path, str | None, int]] = []

    monkeypatch.setattr(encrypt_tool.PDDocument, "load", lambda path: probe)

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
        calls.append((Path(input_path), Path(output_path), user_password, key_length))
        Path(output_path).write_bytes(b"encrypted")

    monkeypatch.setattr(encrypt_tool, "encrypt_pdf", fake_encrypt_pdf)

    rc = encrypt_tool.run(
        _namespace(input=str(src), output=None, user_password="user", key_length=256)
    )

    assert rc == 0
    assert src.read_bytes() == b"encrypted"
    assert calls == [(src, calls[0][1], "user", 256)]
    assert calls[0][1].parent == tmp_path
    assert not calls[0][1].exists()
    assert list(tmp_path.glob(f".{src.name}.*.tmp")) == []
    assert probe.closed is True


def test_wave630_run_same_output_value_error_preserves_source_and_cleans_temp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "plain.pdf"
    src.write_bytes(b"original")
    tmp_seen: list[Path] = []

    monkeypatch.setattr(encrypt_tool.PDDocument, "load", lambda path: _ProbeDocument())

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
        tmp = Path(output_path)
        tmp_seen.append(tmp)
        tmp.write_bytes(b"partial")
        raise ValueError("bad key length")

    monkeypatch.setattr(encrypt_tool, "encrypt_pdf", fake_encrypt_pdf)

    rc = encrypt_tool.run(_namespace(input=str(src), output=str(src)))

    assert rc == 4
    assert "bad key length" in capsys.readouterr().out
    assert src.read_bytes() == b"original"
    assert tmp_seen and not tmp_seen[0].exists()
    assert list(tmp_path.glob(f".{src.name}.*.tmp")) == []


def test_wave630_run_already_encrypted_skips_encrypt_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "encrypted.pdf"
    src.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(
        encrypt_tool.PDDocument,
        "load",
        lambda path: _ProbeDocument(encrypted=True),
    )

    def fail_encrypt_pdf(*args: object, **kwargs: object) -> None:
        raise AssertionError("encrypt_pdf should not be called")

    monkeypatch.setattr(encrypt_tool, "encrypt_pdf", fail_encrypt_pdf)

    rc = encrypt_tool.run(_namespace(input=str(src), output=str(tmp_path / "out.pdf")))

    assert rc == 0
    assert "already encrypted" in capsys.readouterr().out


def test_wave630_run_non_same_output_notimplemented_returns_four(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    src = tmp_path / "plain.pdf"
    out = tmp_path / "encrypted.pdf"
    src.write_bytes(b"%PDF-1.7\n")

    monkeypatch.setattr(encrypt_tool.PDDocument, "load", lambda path: _ProbeDocument())

    def fake_encrypt_pdf(*args: object, **kwargs: object) -> None:
        raise NotImplementedError("public key encryption")

    monkeypatch.setattr(encrypt_tool, "encrypt_pdf", fake_encrypt_pdf)

    rc = encrypt_tool.run(_namespace(input=str(src), output=str(out)))

    assert rc == 4
    assert "public key encryption" in capsys.readouterr().out
    assert not out.exists()
