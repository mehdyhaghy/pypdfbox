"""Live Apache PDFBox cross-library PUBLIC-KEY (certificate) encryption interop.

The strongest parity check for the ``/Adobe.PubSec`` security handler: encrypt a
real PDF with one library and decrypt it with the other, asserting the recovered
content (page count + extracted text) matches the plaintext original. A shared
X.509 cert + RSA key (generated in-test via ``cryptography``) bridges the two
sides — the certificate's DER feeds PDFBox's ``PublicKeyRecipient`` on the
encrypt side and a PKCS#12 keystore feeds PDFBox's
``PublicKeyDecryptionMaterial(keyStore, alias, password)`` on the decrypt side.

Two Java probes drive the oracle:

* ``PubKeyEncryptProbe`` — load a plaintext PDF, build a
  ``PublicKeyProtectionPolicy`` with one ``PublicKeyRecipient`` (the shared cert
  + default all-allowed ``AccessPermission``), select the algorithm via
  ``(keyLengthBits, preferAES)``, and save the encrypted result.
* ``PubKeyDecryptProbe`` — open a public-key-encrypted PDF through
  ``Loader.loadPDF(File, keystorePassword, keystoreInputStream, alias)`` (PDFBox
  reads the InputStream as a PKCS#12 KeyStore) and print ``PAGES:<n>`` then the
  ``PDFTextStripper`` text. A keystore whose cert matches no recipient makes
  ``loadPDF`` throw → non-zero exit → the wrong-key rejection assertion.

Interop results (both AES variants; RC4 public-key variants are not produced by
this lite port — it is AES-only on the write side):

| direction          | AES-128 | AES-256 | note                                    |
|--------------------|---------|---------|-----------------------------------------|
| pypdfbox → Java    | PASS    | PASS    | full content recovery                   |
| Java → pypdfbox    | SKIP    | SKIP    | PDFBox/Acrobat wrap the recipient seed  |
|                    |         |         | in an RC2-CBC CMS envelope; the         |
|                    |         |         | cryptography PKCS#7 backend decrypts    |
|                    |         |         | AES-CBC envelopes only (RC2 is not      |
|                    |         |         | exposed by OpenSSL, and hand-rolling it |
|                    |         |         | is out of scope) — genuinely            |
|                    |         |         | unsupported, not a bug.                 |

Three real interop bugs in pypdfbox's public-key handler were found and FIXED
to make pypdfbox → Java work (see CHANGES.md, wave 1418):

1. Read path only looked for ``/Recipients`` at the ``/Encrypt`` top level; for
   the crypt-filter-based V>=4 handler PDFBox/Acrobat put it inside
   ``/CF /DefaultCryptFilter`` — pypdfbox now falls back there.
2. Write path emitted ``/Recipients`` at the top level (PDFBox derived the wrong
   file key on read → empty text); it now lives in the default crypt filter, and
   the whole ``/CF`` subtree is written DIRECT so a reader doesn't dereference an
   indirect object mid-``prepareForDecryption`` (NullPointerException).
3. Write path wrote the crypt filter ``/Length`` in BYTES (16/32); PDFBox writes
   and reads it in BITS (128/256) and truncated the file key to 16 *bits* →
   garbage streams. Now written in bits to match upstream.
"""

from __future__ import annotations

import datetime
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from pypdfbox import PDDocument
from pypdfbox.cos import COSArray, COSDictionary, COSObjectKey, COSStream, COSString
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.public_key_decryption_material import (
    PublicKeyDecryptionMaterial,
)
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from pypdfbox.pdmodel.encryption.public_key_security_handler import (
    PublicKeySecurityHandler,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe, run_probe_text

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import (
        RSAPrivateKey,
    )

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_ALIAS = "interop-alias"
_P12_PASSWORD = "p12pass"

# (id, key_length_bits) — preferAES is implied true; the lite write path is
# AES-only, and PDFBox maps 128→AES-128 (V4) / 256→AES-256 (V5) with preferAES.
_ALGORITHMS = [
    ("aes_128", 128),
    ("aes_256", 256),
]


# ----------------------------------------------------------------- cert/key setup


def _make_self_signed_rsa(
    common_name: str = "pypdfbox-pubkey-interop",
) -> tuple[x509.Certificate, RSAPrivateKey]:
    """Return ``(cert, private_key)`` — a fresh 2048-bit self-signed RSA cert.

    Shared between the Java and Python sides: the DER cert is handed to PDFBox's
    ``PublicKeyRecipient`` and a PKCS#12 of (key, cert) feeds PDFBox's
    ``PublicKeyDecryptionMaterial``; the same objects drive pypdfbox's
    ``PublicKeyProtectionPolicy`` / ``PublicKeyDecryptionMaterial``.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime(2020, 1, 1))
        .not_valid_after(datetime.datetime(2040, 1, 1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _write_cert_der(cert: x509.Certificate, path: Path) -> Path:
    path.write_bytes(cert.public_bytes(serialization.Encoding.DER))
    return path


def _write_pkcs12(
    cert: x509.Certificate, key: RSAPrivateKey, path: Path
) -> Path:
    blob = pkcs12.serialize_key_and_certificates(
        _ALIAS.encode("utf-8"),
        key,
        cert,
        None,
        serialization.BestAvailableEncryption(_P12_PASSWORD.encode("utf-8")),
    )
    path.write_bytes(blob)
    return path


# ----------------------------------------------------------------- pypdfbox side


def _py_encrypt(
    src: Path, out: Path, cert: x509.Certificate, key_length: int
) -> None:
    """Public-key-encrypt ``src`` to ``out`` for ``cert`` via pypdfbox."""
    doc = PDDocument.load(str(src))
    try:
        policy = PublicKeyProtectionPolicy()
        policy.add_recipient(
            PublicKeyRecipient(certificate=cert, permissions=AccessPermission())
        )
        policy.set_encryption_key_length(key_length)
        doc.protect(policy)
        doc.save(str(out))
    finally:
        doc.close()


def _py_pubkey_decrypt_text(
    path: Path, cert: x509.Certificate, key: RSAPrivateKey
) -> tuple[int, str]:
    """Open a public-key-encrypted ``path`` with pypdfbox + the matching key
    and return ``(page_count, extracted_text)``.

    There is no integrated ``PDDocument.load`` public-key path (the load-time
    decrypt pipeline is password-only); this helper performs the equivalent
    wiring the password path does: run ``prepare_for_decryption`` against the
    ``/Encrypt`` dictionary, attach the handler to every non-ObjStm-member
    ``COSStream`` so bodies decrypt lazily, then run the per-object string/array
    decrypt. Mirrors ``PDDocument.decrypt`` for the standard handler.
    """
    doc = PDDocument.load(str(path))
    try:
        cos_doc = doc.get_document()
        enc_dict = cos_doc.get_encryption_dictionary()
        assert enc_dict is not None
        encryption = PDEncryption(enc_dict)
        material = PublicKeyDecryptionMaterial(certificate=cert, private_key=key)
        handler = PublicKeySecurityHandler()
        handler.prepare_for_decryption(encryption, b"", material)

        objstm_members = {
            obj_key
            for obj_key, off in cos_doc.get_xref_table().items()
            if off is not None and off < 0
        }

        def _obj_key(obj: object) -> COSObjectKey:
            return COSObjectKey(
                obj.get_object_number(),  # type: ignore[attr-defined]
                obj.get_generation_number(),  # type: ignore[attr-defined]
            )

        for cos_obj in cos_doc.get_objects():
            if _obj_key(cos_obj) in objstm_members:
                continue
            actual = cos_obj.get_object()
            if isinstance(actual, COSStream):
                actual.set_security_handler(
                    handler,
                    cos_obj.get_object_number(),
                    cos_obj.get_generation_number(),
                )

        decrypt_dict = handler._decrypt_dictionary  # noqa: SLF001
        for cos_obj in cos_doc.get_objects():
            if _obj_key(cos_obj) in objstm_members:
                continue
            actual = cos_obj.get_object()
            if actual is enc_dict:
                continue
            if isinstance(actual, COSStream):
                decrypt_dict(
                    actual,
                    cos_obj.get_object_number(),
                    cos_obj.get_generation_number(),
                )
            elif isinstance(actual, (COSDictionary, COSArray, COSString)):
                handler.decrypt(
                    actual,
                    cos_obj.get_object_number(),
                    cos_obj.get_generation_number(),
                )

        return doc.get_number_of_pages(), PDFTextStripper().get_text(doc)
    finally:
        doc.close()


# ----------------------------------------------------------------- Java side


def _java_pubkey_encrypt(
    src: Path, out: Path, cert_der: Path, key_length: int
) -> None:
    run_probe(
        "PubKeyEncryptProbe",
        str(src),
        str(out),
        str(cert_der),
        str(key_length),
        "true",
    )


def _java_pubkey_decrypt(path: Path, p12: Path) -> tuple[int, str]:
    raw = run_probe_text(
        "PubKeyDecryptProbe", str(path), str(p12), _P12_PASSWORD, _ALIAS
    )
    first, _, rest = raw.partition("\n")
    assert first.startswith("PAGES:"), f"probe framing broke: {first!r}"
    return int(first[len("PAGES:") :]), rest


def _java_pubkey_decrypt_fails(path: Path, p12: Path) -> bool:
    try:
        run_probe("PubKeyDecryptProbe", str(path), str(p12), _P12_PASSWORD, _ALIAS)
    except subprocess.CalledProcessError:
        return True
    return False


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


# ----------------------------------------------------- pypdfbox encrypts → Java


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length"), _ALGORITHMS, ids=[a[0] for a in _ALGORITHMS]
)
def test_pypdfbox_pubkey_encrypts_java_decrypts(
    algo_id: str, key_length: int, tmp_path: Path
) -> None:
    """pypdfbox public-key-encrypts; Apache PDFBox opens it with the matching
    PKCS#12 private key and recovers the same content as the plaintext baseline.

    Guards the three interop fixes in wave 1418 (recipients in the crypt filter,
    direct /CF subtree, crypt filter /Length in bits)."""
    _fixture_present()
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    cert, key = _make_self_signed_rsa()
    p12 = _write_pkcs12(cert, key, tmp_path / "ks.p12")

    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, cert, key_length)
    # The ciphertext must not contain the plaintext verbatim.
    assert base_text[:40].encode("latin-1", "ignore") not in enc.read_bytes()

    pages, text = _java_pubkey_decrypt(enc, p12)
    assert pages == 2
    assert text == base_text


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length"), _ALGORITHMS, ids=[a[0] for a in _ALGORITHMS]
)
def test_java_rejects_wrong_key_on_pypdfbox_pubkey_file(
    algo_id: str, key_length: int, tmp_path: Path
) -> None:
    """A pypdfbox public-key file opened by Apache PDFBox with a keystore whose
    certificate matches no recipient is rejected (non-zero exit)."""
    _fixture_present()
    cert, key = _make_self_signed_rsa()
    wrong_cert, wrong_key = _make_self_signed_rsa("wrong-recipient")
    wrong_p12 = _write_pkcs12(wrong_cert, wrong_key, tmp_path / "wrong.p12")

    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, cert, key_length)

    assert _java_pubkey_decrypt_fails(enc, wrong_p12)


# ----------------------------------------------------- pypdfbox self round-trip


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length"), _ALGORITHMS, ids=[a[0] for a in _ALGORITHMS]
)
def test_pypdfbox_pubkey_self_roundtrip(
    algo_id: str, key_length: int, tmp_path: Path
) -> None:
    """pypdfbox public-key-encrypts AND decrypts its own file, recovering the
    same content the Java text-extract baseline reports. Pins the read + write
    halves of the public-key handler against each other (and against PDFBox's
    notion of the plaintext)."""
    _fixture_present()
    base_text = run_probe_text("TextExtractProbe", str(_FIXTURE))

    cert, key = _make_self_signed_rsa()
    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, cert, key_length)

    pages, text = _py_pubkey_decrypt_text(enc, cert, key)
    assert pages == 2
    assert text == base_text


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length"), _ALGORITHMS, ids=[a[0] for a in _ALGORITHMS]
)
def test_pypdfbox_rejects_wrong_key_on_pypdfbox_pubkey_file(
    algo_id: str, key_length: int, tmp_path: Path
) -> None:
    """pypdfbox rejects a wrong private key on its own public-key file with a
    ValueError (matched-no-recipient) — NOT the unsupported-algorithm error,
    which is reserved for the RC2 case."""
    _fixture_present()
    cert, _key = _make_self_signed_rsa()
    _wrong_cert, wrong_key = _make_self_signed_rsa("wrong-recipient")

    enc = tmp_path / f"py_{algo_id}.pdf"
    _py_encrypt(_FIXTURE, enc, cert, key_length)

    doc = PDDocument.load(str(enc))
    try:
        encryption = PDEncryption(doc.get_document().get_encryption_dictionary())
        handler = PublicKeySecurityHandler()
        material = PublicKeyDecryptionMaterial(
            certificate=cert, private_key=wrong_key
        )
        with pytest.raises(ValueError, match="matched none"):
            handler.prepare_for_decryption(encryption, b"", material)
    finally:
        doc.close()


# ----------------------------------------------- Java encrypts → pypdfbox (RC2)


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length"), _ALGORITHMS, ids=[a[0] for a in _ALGORITHMS]
)
def test_java_pubkey_encrypts_pypdfbox_decrypts_rc2_unsupported(
    algo_id: str, key_length: int, tmp_path: Path
) -> None:
    """Document the Java → pypdfbox limitation as an explicit contract.

    Apache PDFBox / Acrobat wrap the recipient seed in an **RC2-CBC** CMS
    envelope. The ``cryptography`` PKCS#7 backend decrypts AES-128/256-CBC
    envelopes only — RC2 is not exposed by OpenSSL and hand-rolling it is out of
    scope (no hand-rolled crypto; permissive-library rule). So a
    PDFBox-produced public-key file is not decryptable here regardless of the
    private key. pypdfbox surfaces this as a *distinct* ``UnsupportedAlgorithm``
    (not "wrong key"), which this test pins. If a future ``cryptography`` gains
    RC2 content-decryption support, flip this to a content-recovery assertion.
    """
    _fixture_present()
    cert, key = _make_self_signed_rsa()
    cert_der = _write_cert_der(cert, tmp_path / "cert.der")

    enc = tmp_path / f"java_{algo_id}.pdf"
    _java_pubkey_encrypt(_FIXTURE, enc, cert_der, key_length)

    # Confirm PDFBox really produced an RC2-CBC recipient envelope (OID
    # 1.2.840.113549.3.2) — proves the skip reason is accurate and not masking
    # a different failure.
    doc = PDDocument.load(str(enc))
    try:
        encryption = PDEncryption(doc.get_document().get_encryption_dictionary())
        default_cf = encryption.get_default_crypt_filter_dictionary()
        assert default_cf is not None
        recipients = default_cf.get_recipients()
        assert recipients is not None and recipients.size() >= 1
        blob = recipients.get(0).get_bytes()
        rc2_cbc_oid_der = bytes.fromhex("2a864886f70d0302")
        assert rc2_cbc_oid_der in blob, "expected an RC2-CBC CMS envelope"

        handler = PublicKeySecurityHandler()
        material = PublicKeyDecryptionMaterial(certificate=cert, private_key=key)
        with pytest.raises(UnsupportedAlgorithm, match="RC2"):
            handler.prepare_for_decryption(encryption, b"", material)
    finally:
        doc.close()
