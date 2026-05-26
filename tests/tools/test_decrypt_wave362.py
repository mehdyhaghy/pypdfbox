"""Wave 362 coverage for ``pypdfbox decrypt`` branches."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from pypdfbox import Loader
from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption import InvalidPasswordException
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.tools import cli, decrypt


def _build_encrypted_pdf(
    path: Path,
    *,
    owner_password: str = "owner",
    user_password: str = "user",
) -> Path:
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(b"BT /F1 12 Tf 50 700 Td (wave362 decrypt) Tj ET")
        page.set_contents(stream)
        doc.protect(
            StandardProtectionPolicy(
                owner_password=owner_password,
                user_password=user_password,
                permissions=AccessPermission(),
            )
        )
        doc.save(path)
    finally:
        doc.close()
    return path


def _self_signed_cert() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wave362")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return key, cert


def _write_pkcs12(
    path: Path,
    *,
    alias: bytes = b"wave362",
    password: str = "secret",
) -> Path:
    key, cert = _self_signed_cert()
    data = pkcs12.serialize_key_and_certificates(
        name=alias,
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(
            password.encode("utf-8")
        ),
    )
    path.write_bytes(data)
    return path


def test_wave362_load_pkcs12_keystore_matching_alias(tmp_path: Path) -> None:
    store = _write_pkcs12(tmp_path / "good.p12", alias=b"signing", password="pw")

    material = decrypt._load_pkcs12_keystore(store, "signing", "pw")

    assert material.get_certificate() is not None
    assert material.get_private_key() is not None
    assert material.get_password() == b"pw"


def test_wave362_load_pkcs12_keystore_rejects_missing_key_entry(
    tmp_path: Path,
) -> None:
    _, cert = _self_signed_cert()
    store = tmp_path / "cert-only.p12"
    store.write_bytes(
        pkcs12.serialize_key_and_certificates(
            name=None,
            key=None,
            cert=None,
            cas=[cert],
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    with pytest.raises(OSError, match="no private-key certificate entry"):
        decrypt._load_pkcs12_keystore(store, None, "")


def test_wave362_load_pkcs12_keystore_rejects_alias_mismatch(
    tmp_path: Path,
) -> None:
    store = _write_pkcs12(tmp_path / "good.p12", alias=b"expected", password="pw")

    with pytest.raises(OSError, match="matching alias"):
        decrypt._load_pkcs12_keystore(store, "other", "pw")


def test_wave362_valid_keystore_path_returns_not_implemented(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    src = tmp_path / "exists.pdf"
    src.write_bytes(b"%PDF-1.4\n%%EOF\n")
    store = _write_pkcs12(tmp_path / "good.p12", alias=b"signing", password="pw")

    rc = cli.run_cli(
        [
            "decrypt",
            "-i",
            str(src),
            "-keyStore",
            str(store),
            "-alias",
            "signing",
            "-password",
            "pw",
        ]
    )

    assert rc == 4
    assert "public-key keystore decryption is not yet wired" in capsys.readouterr().out


def test_wave362_in_place_decrypt_success_replaces_source(tmp_path: Path) -> None:
    src = _build_encrypted_pdf(tmp_path / "encrypted.pdf")

    rc = cli.run_cli(["decrypt", "-i", str(src), "-password", "owner"])

    assert rc == 0
    with PDDocument.load(src) as reloaded:
        assert reloaded.is_encrypted() is False
        assert reloaded.get_number_of_pages() == 1


def test_wave362_in_place_helper_io_error_removes_temp(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = _build_encrypted_pdf(tmp_path / "encrypted.pdf")
    original = src.read_bytes()

    def fail_decrypt_pdf(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(decrypt, "decrypt_pdf", fail_decrypt_pdf)

    rc = cli.run_cli(["decrypt", "-i", str(src), "-password", "owner"])

    assert rc == 4
    assert "disk full" in capsys.readouterr().out
    assert src.read_bytes() == original
    assert list(tmp_path.glob(".encrypted.pdf.*.tmp")) == []


def test_wave362_non_in_place_helper_password_error_after_probe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = _build_encrypted_pdf(tmp_path / "encrypted.pdf")
    out = tmp_path / "out.pdf"

    def fail_decrypt_pdf(*_args: object, **_kwargs: object) -> None:
        raise InvalidPasswordException("late password failure")

    monkeypatch.setattr(decrypt, "decrypt_pdf", fail_decrypt_pdf)

    rc = cli.run_cli(["decrypt", "-i", str(src), "-o", str(out), "-password", "owner"])

    assert rc == 1
    assert "late password failure" in capsys.readouterr().out
    assert not out.exists()


def test_wave362_non_in_place_helper_io_error_after_probe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    src = _build_encrypted_pdf(tmp_path / "encrypted.pdf")
    out = tmp_path / "out.pdf"

    def fail_decrypt_pdf(*_args: object, **_kwargs: object) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(decrypt, "decrypt_pdf", fail_decrypt_pdf)

    rc = cli.run_cli(["decrypt", "-i", str(src), "-o", str(out), "-password", "owner"])

    assert rc == 4
    assert "permission denied" in capsys.readouterr().out
    assert not out.exists()


def test_wave362_in_place_decrypt_removes_encrypt_entry(tmp_path: Path) -> None:
    src = _build_encrypted_pdf(tmp_path / "encrypted.pdf")

    # Close the probe document before running the in-place decrypt. On
    # Windows, an open PDDocument keeps a handle on the underlying file
    # and the decrypt tool cannot atomically overwrite it (rc=4 instead
    # of 0). POSIX platforms tolerate the unclosed handle, but the
    # explicit close pattern is portable.
    probe = Loader.load_pdf(src)
    try:
        assert probe.is_encrypted() is True
    finally:
        probe.close()
    assert cli.run_cli(["decrypt", "-i", str(src), "-password", "owner"]) == 0

    reloaded = Loader.load_pdf(src)
    try:
        assert reloaded.is_encrypted() is False
    finally:
        reloaded.close()
