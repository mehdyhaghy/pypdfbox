"""Live Apache PDFBox differential parity for the ``/StrF`` defaults-to-
``/Identity`` rule (PDF 32000-1 §7.6.4.4 Table 20).

A V=4 / V=5 ``/Encrypt`` dictionary that declares ``/StmF /StdCF`` but omits
``/StrF`` must leave strings *cleartext on the wire* — the absent slot
defaults to ``/Identity`` (no cipher), only stream bodies route through
``/StdCF``. Companion to ``test_crypt_routing_oracle.py`` (wave 1439, the
explicit mixed-routing case where both ``/StmF`` and ``/StrF`` are present
but point at different filters); this module pins the *absent-slot* facet
the wave 1439 differential did not exercise.

Why it matters for interop: PDFBox's ``PDEncryption.getStringFilterName``
returns the spec-default ``/Identity`` when ``/StrF`` is absent, so PDFBox
treats those strings as plaintext on read. If pypdfbox's write side encrypts
them anyway (legacy single-algorithm fallback for an unrouted slot), PDFBox
can no longer recover them — exactly the bug this wave fixes. The
``StandardSecurityHandler._populate_routing_table`` now substitutes the
``Identity`` CFM for an absent ``/StmF`` or ``/StrF`` so per-object cipher
dispatch leaves the slot as cleartext pass-through instead of falling back
to the V<4 single-algorithm path.

PDFBox 3.0.7's high-level writer always re-stamps both ``/StmF`` and
``/StrF`` at save time (verified — see the wave 1439 note in
``test_crypt_routing_oracle.py``), so the absent-/StrF file is authored by
pypdfbox; Apache PDFBox proves it can READ the result and recover the same
string + page text pypdfbox does.
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path

import pytest

from pypdfbox import PDDocument
from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel.encryption import standard_security_handler as _ssh_mod
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_crypt_filter_dictionary import (
    PDCryptFilterDictionary,
)
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.standard_protection_policy import (
    StandardProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler,
)
from pypdfbox.text import PDFTextStripper
from tests.oracle.harness import requires_oracle, run_probe_text

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "pdfwriter" / "unencrypted.pdf"

_OWNER_PW = "ownerpw"
_USER_PW = "userpw"

# Probe marker — kept identical to oracle/probes/StrFDefaultProbe.java so the
# decrypted-string byte-equality assertion is meaningful across the boundary.
_STRING_MARKER = b"StrFDefaultMarker1451"
_STRING_KEY = COSName.get_pdf_name("StrFDefaultMarker")


# --------------------------------------------------------------- helpers


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _author_strf_absent(
    out: Path, key_length: int, prefer_aes: bool
) -> None:
    """Encrypt the fixture so ``/StmF /StdCF`` is set but ``/StrF`` is absent.

    The high-level API installs ``/StmF`` and ``/StrF`` both pointing at
    ``/StdCF``; we override the one write-side seam that wires them
    (``_install_std_crypt_filter``) for the duration of the save so only
    ``/StmF`` is written. The full per-object cipher-dispatch pipeline
    (``encrypt_string`` / ``encrypt_stream`` → routing table →
    ``_dispatch_encrypt``) still runs — the routing-table substitution of
    ``Identity`` for an absent ``/StrF`` is exactly what this differential
    pins. A probe string is stamped into the catalog so the ``/StrF``
    default's *cleartext-on-wire* outcome is observable independently of the
    page content streams (which route through ``/StmF``).
    """

    def install(encryption: PDEncryption, cfm: str, length_bytes: int) -> None:
        std = PDCryptFilterDictionary()
        std.set_cfm(cfm)
        std.set_length(length_bytes)
        encryption.set_std_crypt_filter_dictionary(std)
        encryption.set_stm_f("StdCF")
        # Omit /StrF entirely — spec default is Identity (cleartext strings).
        encryption.clear_str_f()

    original = StandardSecurityHandler._install_std_crypt_filter
    _ssh_mod.StandardSecurityHandler._install_std_crypt_filter = staticmethod(install)
    try:
        with PDDocument.load(str(_FIXTURE)) as pd:
            pd.get_document_catalog().get_cos_object().set_item(
                _STRING_KEY, COSString(_STRING_MARKER)
            )
            policy = StandardProtectionPolicy(
                owner_password=_OWNER_PW,
                user_password=_USER_PW,
                permissions=AccessPermission(),
            )
            policy.set_encryption_key_length(key_length)
            policy.set_prefer_aes(prefer_aes)
            pd.protect(policy)
            pd.save(str(out))
    finally:
        _ssh_mod.StandardSecurityHandler._install_std_crypt_filter = staticmethod(
            original
        )


def _strf_on_disk(path: Path) -> str | None:
    """Return the ``/StrF`` value written into ``/Encrypt`` on disk, or None
    when the slot is absent. The on-the-wire absence is the spec signal
    PDFBox keys off when applying the Identity default."""
    data = path.read_bytes()
    match = re.search(rb"/StrF\s+/(\w+)", data)
    return match.group(1).decode() if match else None


def _count_inflatable_streams(path: Path) -> int:
    """Number of ``stream … endstream`` bodies on disk that zlib-inflate.

    A FlateDecode body routed through ``/StmF /StdCF`` (AES) does NOT inflate
    on the wire; this serves as a positive on-the-wire confirmation that the
    stream slot really is enciphered (paired with the cleartext string check
    below so the test asserts BOTH ends of the mixed default).
    """
    data = path.read_bytes()
    ok = 0
    for match in re.finditer(rb"stream\r?\n", data):
        start = match.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        body = data[start:end].rstrip(b"\r\n")
        try:
            zlib.decompress(body)
        except zlib.error:
            continue
        ok += 1
    return ok


def _string_marker_cleartext_on_wire(path: Path) -> bool:
    """True when the probe string's bytes appear cleartext on disk.

    pypdfbox writes an ``Identity``-routed string in hex literal form
    (``visit_from_string`` forces hex on the enciphered branch and Identity
    is a no-op cipher), so a cleartext Identity string shows up as the
    marker's uppercase hex. An enciphered string shows neither the ASCII nor
    the hex.
    """
    data = path.read_bytes()
    hex_upper = _STRING_MARKER.hex().upper().encode("ascii")
    hex_lower = _STRING_MARKER.hex().encode("ascii")
    return _STRING_MARKER in data or hex_upper in data or hex_lower in data


def _java_inspect(path: Path, password: str) -> dict[str, str]:
    raw = run_probe_text("StrFDefaultProbe", "inspect", str(path), password)
    fields: dict[str, str] = {}
    text_lines: list[str] = []
    in_text = False
    for line in raw.split("\n"):
        if in_text:
            text_lines.append(line)
            continue
        if line.startswith("TEXT:"):
            in_text = True
            text_lines.append(line[len("TEXT:") :])
            continue
        key, _, value = line.partition(":")
        fields[key] = value
    fields["TEXT"] = "\n".join(text_lines)
    return fields


def _py_read(path: Path, password: str) -> tuple[bytes | None, str]:
    with PDDocument.load(str(path), password=password) as doc:
        marker = doc.get_document_catalog().get_cos_object().get_dictionary_object(
            _STRING_KEY
        )
        marker_bytes = marker.get_bytes() if marker is not None else None
        text = PDFTextStripper().get_text(doc)
    return marker_bytes, text


# (id, key_length, prefer_aes)
_COMBOS = [
    ("aes128", 128, True),
    ("aes256", 256, False),
]


# ---------------------- pypdfbox authors /StrF-absent → PDFBox reads


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _COMBOS,
    ids=[c[0] for c in _COMBOS],
)
def test_pypdfbox_strf_absent_pdfbox_reads(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """pypdfbox writes ``/StmF /StdCF`` with NO ``/StrF`` (spec default is
    Identity); the catalog string stays cleartext on the wire while stream
    bodies are enciphered, and Apache PDFBox reads the result back recovering
    the SAME string bytes + page text pypdfbox does."""
    _fixture_present()
    enc = tmp_path / f"py_strf_absent_{algo_id}.pdf"
    _author_strf_absent(enc, key_length, prefer_aes)

    # --- on-the-wire: /StrF absent + cleartext string + enciphered streams.
    assert _strf_on_disk(enc) is None, (
        f"{algo_id}: /StrF leaked into /Encrypt — absent-slot test invalid"
    )
    assert _string_marker_cleartext_on_wire(enc), (
        f"{algo_id}: Identity-defaulted string was enciphered on the wire"
    )
    assert _count_inflatable_streams(enc) == 0, (
        f"{algo_id}: stream body slipped through cleartext (/StmF /StdCF)"
    )

    # --- PDFBox reads it: /StrF coerces to Identity, /StmF stays /StdCF,
    #     the cleartext marker round-trips byte-for-byte.
    java = _java_inspect(enc, _USER_PW)
    assert java["STMF"] == "StdCF", f"{algo_id}: PDFBox saw /StmF {java['STMF']}"
    assert java["STRF"] == "Identity", (
        f"{algo_id}: PDFBox did not coerce absent /StrF to Identity "
        f"(got {java['STRF']})"
    )
    assert java["STRING_VALUE"] == _STRING_MARKER.hex(), (
        f"{algo_id}: PDFBox could not recover the cleartext marker"
    )
    assert java["PAGES"] == "2"

    # --- pypdfbox reads its own file; both libraries recover identically.
    py_marker, py_text = _py_read(enc, _USER_PW)
    assert py_marker == _STRING_MARKER, f"{algo_id}: pypdfbox lost the string"
    assert py_text.strip() == java["TEXT"].strip(), (
        f"{algo_id}: recovered page text diverges between pypdfbox and PDFBox"
    )


# ---------------- /StmF absent + /StrF /StdCF — the symmetric default


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    _COMBOS,
    ids=[c[0] for c in _COMBOS],
)
def test_pypdfbox_stmf_absent_pdfbox_reads(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """Symmetric default: ``/StmF`` absent (defaults to Identity) +
    ``/StrF /StdCF`` — stream bodies stay cleartext, the catalog string is
    enciphered. Same spec rule, opposite slot."""
    _fixture_present()

    def install(encryption: PDEncryption, cfm: str, length_bytes: int) -> None:
        std = PDCryptFilterDictionary()
        std.set_cfm(cfm)
        std.set_length(length_bytes)
        encryption.set_std_crypt_filter_dictionary(std)
        encryption.clear_stm_f()
        encryption.set_str_f("StdCF")

    enc = tmp_path / f"py_stmf_absent_{algo_id}.pdf"
    original = StandardSecurityHandler._install_std_crypt_filter
    _ssh_mod.StandardSecurityHandler._install_std_crypt_filter = staticmethod(install)
    try:
        with PDDocument.load(str(_FIXTURE)) as pd:
            pd.get_document_catalog().get_cos_object().set_item(
                _STRING_KEY, COSString(_STRING_MARKER)
            )
            policy = StandardProtectionPolicy(
                owner_password=_OWNER_PW,
                user_password=_USER_PW,
                permissions=AccessPermission(),
            )
            policy.set_encryption_key_length(key_length)
            policy.set_prefer_aes(prefer_aes)
            pd.protect(policy)
            pd.save(str(enc))
    finally:
        _ssh_mod.StandardSecurityHandler._install_std_crypt_filter = staticmethod(
            original
        )

    # --- on-the-wire: /StmF absent + enciphered string + inflatable streams.
    data = enc.read_bytes()
    assert re.search(rb"/StmF\s+/(\w+)", data) is None, (
        f"{algo_id}: /StmF leaked into /Encrypt — absent-slot test invalid"
    )
    assert not _string_marker_cleartext_on_wire(enc), (
        f"{algo_id}: /StrF /StdCF string slipped through cleartext"
    )
    assert _count_inflatable_streams(enc) > 0, (
        f"{algo_id}: Identity-defaulted streams were enciphered"
    )

    # --- PDFBox reads it: /StmF -> Identity, /StrF -> StdCF, string recovers.
    java = _java_inspect(enc, _USER_PW)
    assert java["STMF"] == "Identity", (
        f"{algo_id}: PDFBox did not coerce absent /StmF to Identity "
        f"(got {java['STMF']})"
    )
    assert java["STRF"] == "StdCF", f"{algo_id}: PDFBox saw /StrF {java['STRF']}"
    assert java["STRING_VALUE"] == _STRING_MARKER.hex()

    # --- pypdfbox reads its own file; both libraries recover identically.
    py_marker, py_text = _py_read(enc, _USER_PW)
    assert py_marker == _STRING_MARKER, f"{algo_id}: pypdfbox lost the string"
    assert py_text.strip() == java["TEXT"].strip()


# ----------------- read-side routing-table unit pin (no oracle required)


def test_absent_strf_resolves_to_identity_cfm() -> None:
    """When ``/Encrypt`` declares ``/V 4`` with ``/StmF /StdCF`` but omits
    ``/StrF``, the read-side routing table must resolve the string slot to
    the Identity CFM so per-object cipher dispatch leaves strings cleartext
    instead of falling back to the legacy single-algorithm path. Pins the
    fix in ``_populate_routing_table``."""
    enc = PDEncryption()
    enc.set_v(4)
    enc.set_revision(4)
    std = PDCryptFilterDictionary()
    std.set_cfm("AESV2")
    std.set_length(16)
    enc.set_std_crypt_filter_dictionary(std)
    enc.set_stm_f("StdCF")
    # /StrF absent — spec default is Identity.

    handler = StandardSecurityHandler(enc)
    handler._populate_routing_table(enc)  # noqa: SLF001 — read-side surface

    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "Identity"
    # /EFF absent + /StmF /StdCF → embedded files inherit /StmF (AESV2),
    # not the Identity substitution applied to /StrF.
    assert handler.get_embedded_file_cfm() == "AESV2"


def test_absent_stmf_resolves_to_identity_cfm() -> None:
    """Symmetric default: ``/StmF`` absent → stream slot resolves to
    ``Identity``; ``/EFF`` (which inherits ``/StmF``) follows."""
    enc = PDEncryption()
    enc.set_v(4)
    enc.set_revision(4)
    std = PDCryptFilterDictionary()
    std.set_cfm("AESV2")
    std.set_length(16)
    enc.set_std_crypt_filter_dictionary(std)
    enc.set_str_f("StdCF")
    # /StmF absent — spec default is Identity. /EFF inherits /StmF.

    handler = StandardSecurityHandler(enc)
    handler._populate_routing_table(enc)  # noqa: SLF001 — read-side surface

    assert handler.get_stream_cfm() == "Identity"
    assert handler.get_string_cfm() == "AESV2"
    assert handler.get_embedded_file_cfm() == "Identity"
