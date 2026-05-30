"""Live Apache PDFBox parity for the API-level encrypt-on-save path.

This is the API twin of the ``Encrypt`` CLI oracle: instead of driving the
``encrypt`` subcommand we exercise the public ``PDDocument.protect(
StandardProtectionPolicy)`` + ``save()`` surface directly, the way a library
consumer would. The produced file must:

* pass ``qpdf --check`` *with the user password* (rc 0 clean / 3 warnings) and
  be rejected (rc 2) with a wrong password — proving /U / /O actually gate
  access rather than the file merely carrying a no-op /Encrypt; and
* be openable by Apache PDFBox 3.0.7 with both the user and the owner
  password, round-trip to identical decrypted text, and carry the /Encrypt
  dictionary structure the spec requires for each key-length family:
    - RC4-128 → /V 2 /R 3 /Length 128, /U + /O present, no crypt filters;
    - AES-256 → /V 5 /R 6 /Length 256, /U + /O + /UE + /OE present, with
      /StmF = /StrF = StdCF and the StdCF /CFM = AESV3.

Permission bits PDFBox reconstructs from the decrypted /P must match the
``AccessPermission`` pypdfbox encoded (the owner password unlocks everything
upstream, so the restricted-permission assertion uses the user-password view).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_OWNER_PASSWORD = "0wn3r-pass"
_USER_PASSWORD = "us3r-pass"

_CONTENT = b"BT /F1 12 Tf 50 700 Td (Protect save parity sample) Tj ET"
_EXPECTED_TEXT = "Protect save parity sample"


def _protect_and_save(
    path: Path,
    key_length: int,
    *,
    can_print: bool = True,
    can_modify: bool = True,
    can_extract: bool = True,
) -> Path:
    """Build a one-page PDF, ``protect()`` it, and ``save()`` to ``path``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        stream = COSStream()
        with stream.create_raw_output_stream() as out:
            out.write(_CONTENT)
        page.set_contents(stream)

        ap = AccessPermission()
        ap.set_can_print(can_print)
        ap.set_can_modify(can_modify)
        ap.set_can_extract_content(can_extract)

        policy = StandardProtectionPolicy(
            owner_password=_OWNER_PASSWORD,
            user_password=_USER_PASSWORD,
            permissions=ap,
        )
        policy.set_encryption_key_length(key_length)
        doc.protect(policy)
        doc.save(path)
    finally:
        doc.close()
    return path


def _qpdf_check(path: Path, password: str) -> subprocess.CompletedProcess[str]:
    qpdf = shutil.which("qpdf")
    if qpdf is None:  # pragma: no cover - environment dependent
        pytest.skip("qpdf not installed")
    return subprocess.run(
        [qpdf, "--check", f"--password={password}", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


@requires_oracle
@pytest.mark.parametrize(
    (
        "key_length",
        "exp_version",
        "exp_revision",
        "exp_has_ue",
        "exp_stm_f",
        "exp_cfm",
    ),
    [
        (128, 2, 3, False, None, None),
        (256, 5, 6, True, "StdCF", "AESV3"),
    ],
    ids=["rc4-128", "aes-256"],
)
def test_protect_save_roundtrips_through_pdfbox(
    tmp_path: Path,
    key_length: int,
    exp_version: int,
    exp_revision: int,
    exp_has_ue: bool,
    exp_stm_f: str | None,
    exp_cfm: str | None,
) -> None:
    out = _protect_and_save(tmp_path / "protected.pdf", key_length)

    # qpdf accepts with the correct password, rejects a wrong one.
    good = _qpdf_check(out, _USER_PASSWORD)
    assert good.returncode in (0, 3), (
        f"qpdf --check rejected a correctly-encrypted file:\n"
        f"{good.stdout}\n{good.stderr}"
    )
    bad = _qpdf_check(out, "definitely-wrong-password")
    assert bad.returncode == 2, (
        "qpdf accepted a wrong password — encryption is not gating access:\n"
        f"{bad.stdout}\n{bad.stderr}"
    )

    # PDFBox opens with both passwords and round-trips to identical content.
    for password in (_USER_PASSWORD, _OWNER_PASSWORD):
        probe = json.loads(run_probe_text("ProtectSaveProbe", str(out), password))
        assert probe.get("opened") is True, (
            f"PDFBox failed to open protect()+save() file with {password!r}: {probe}"
        )
        assert probe["isEncrypted"] is True
        assert probe["pages"] == 1
        assert _EXPECTED_TEXT in probe["text"], (
            f"decrypted text divergence: {probe['text']!r}"
        )
        # /Encrypt dict structure per key-length family.
        assert probe["version"] == exp_version
        assert probe["revision"] == exp_revision
        assert probe["length"] == key_length
        assert probe["hasU"] is True
        assert probe["hasO"] is True
        assert probe["hasUE"] is exp_has_ue
        assert probe["hasOE"] is exp_has_ue
        assert probe["stmF"] == exp_stm_f
        assert probe["strF"] == exp_stm_f
        assert probe["cfm"] == exp_cfm
        # Default policy grants all three permissions.
        assert probe["canPrint"] is True
        assert probe["canModify"] is True
        assert probe["canExtract"] is True


@requires_oracle
def test_protect_save_restricted_permissions_match(tmp_path: Path) -> None:
    """A restricted AccessPermission round-trips through /P to PDFBox."""
    out = _protect_and_save(
        tmp_path / "restricted.pdf",
        128,
        can_print=False,
        can_modify=False,
        can_extract=False,
    )

    # Owner password unlocks everything upstream; assert the user-password view,
    # which reflects the encoded /P bits.
    probe = json.loads(
        run_probe_text("ProtectSaveProbe", str(out), _USER_PASSWORD)
    )
    assert probe.get("opened") is True, probe
    assert probe["canPrint"] is False
    assert probe["canModify"] is False
    assert probe["canExtract"] is False
    assert _EXPECTED_TEXT in probe["text"]
