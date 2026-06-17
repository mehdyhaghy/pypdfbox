"""Live Apache PDFBox differential parity for crypt-filter ROUTING — the
per-string-vs-per-stream dispatch of ``/StmF`` / ``/StrF`` and the
``/Identity`` pass-through (PDF 32000-1 §7.6.5).

Companion to ``test_crypt_filter_oracle.py`` (wave 1427), which pinned the
*introspection* surface (``/StmF`` / ``/StrF`` / ``/CF`` / ``/CFM`` read
parity) for documents where both default filters point at ``/StdCF``, plus
the ``/Identity`` short-circuit at the read-side routing-table level
(``_populate_routing_table`` unit tests). This module narrows in on the facet
wave 1427 did **not** touch: a *mixed-routing* document where ``/StmF`` and
``/StrF`` point at **different** crypt filters, so each object type must be
enciphered or left cleartext according to its own slot:

* ``/StmF /StdCF`` + ``/StrF /Identity`` — streams enciphered, strings
  cleartext on the wire.
* ``/StmF /Identity`` + ``/StrF /StdCF`` — streams cleartext, strings
  enciphered.

Neither library's *high-level* 3.0.7 API can author a mixed document
(``StandardProtectionPolicy`` always installs a single ``/StdCF`` for both
slots, and PDFBox's writer re-stamps both at save time even if the live
``/Encrypt`` dict is patched after ``protect()`` — verified). So pypdfbox
authors the mixed document by overriding the one write-side seam that wires
the routing names (``StandardSecurityHandler._install_std_crypt_filter``),
exercising the genuine per-object cipher-dispatch pipeline end-to-end, and
Apache PDFBox reads the result back. The differential asserts:

* the ``/Identity``-routed object type is **not** enciphered on the wire
  (stream bodies stay FlateDecode-inflatable; the string stays plaintext —
  pypdfbox writes an Identity-routed string in hex literal form, so the
  marker's hex appears verbatim on disk),
* the ``/StdCF``-routed object type **is** enciphered on the wire,
* Apache PDFBox recovers the SAME decrypted string bytes and the SAME page
  text pypdfbox does — proving the routing is interoperable in both
  read directions for both combos.

This pins the routing bugs fixed in wave 1439 (see ``CHANGES.md``): the read
walk decrypted strings through the raw single-algorithm cipher instead of the
per-slot ``decrypt_string`` override (so ``/StrF /Identity`` was ignored and
``/StrF /StdCF`` under ``/StmF /Identity`` derived the per-object key with the
wrong AES salt). Without the fix, PDFBox-authored cleartext routing and
pypdfbox's own mixed output were mutually unreadable.
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

# Probe markers — kept identical to oracle/probes/CryptRoutingProbe.java so the
# decrypted-string byte-equality assertion is meaningful across the boundary.
_STRING_MARKER = b"CryptRoutingStringMarker1439"
_STRING_KEY = COSName.get_pdf_name("CryptRoutingStr")


# --------------------------------------------------------------- helpers


def _fixture_present() -> None:
    if not _FIXTURE.is_file():
        pytest.skip(f"fixture missing: {_FIXTURE}")


def _author_mixed(
    out: Path, stmf: str, strf: str, key_length: int, prefer_aes: bool
) -> None:
    """Encrypt the fixture so ``/StmF`` and ``/StrF`` route independently.

    The high-level API installs a single ``/StdCF`` for both slots, so we
    override the one write-side seam that wires the routing names
    (``_install_std_crypt_filter``) for the duration of the save. The full
    per-object cipher-dispatch pipeline (``encrypt_string`` / ``encrypt_stream``
    → routing table → ``_dispatch_encrypt``) still runs — only the slot→filter
    assignment is steered. A probe string is stamped into the catalog so the
    ``/StrF`` routing is observable independently of the page content streams
    (``/StmF``).
    """

    def install(encryption: object, cfm: str, length_bytes: int) -> None:
        std = PDCryptFilterDictionary()
        std.set_cfm(cfm)
        std.set_length(length_bytes)
        encryption.set_std_crypt_filter_dictionary(std)  # type: ignore[attr-defined]
        encryption.set_stm_f(stmf)  # type: ignore[attr-defined]
        encryption.set_str_f(strf)  # type: ignore[attr-defined]

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


def _count_inflatable_streams(path: Path) -> int:
    """Number of ``stream … endstream`` bodies on disk that zlib-inflate.

    A FlateDecode body left cleartext (``/StmF /Identity``) inflates; an
    AES-enciphered body (``/StmF /StdCF``) does not. The fixture's page
    content streams are all FlateDecode, so this is a robust on-the-wire
    signal for whether the stream slot was routed to Identity.
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

    pypdfbox writes an ``/Identity``-routed string in hex literal form
    (``visit_from_string`` forces hex on the enciphered branch and Identity is
    a no-op cipher), so a cleartext Identity string shows up as the marker's
    uppercase hex. An enciphered string shows neither the ASCII nor the hex.
    """
    data = path.read_bytes()
    hex_upper = _STRING_MARKER.hex().upper().encode("ascii")
    hex_lower = _STRING_MARKER.hex().encode("ascii")
    return _STRING_MARKER in data or hex_upper in data or hex_lower in data


def _java_inspect(path: Path, password: str) -> dict[str, str]:
    raw = run_probe_text("CryptRoutingProbe", "inspect", str(path), password)
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


# (id, stmf, strf, key_length, prefer_aes, stream_is_identity)
_COMBOS = [
    ("aes128_stmf_identity", "Identity", "StdCF", 128, True, True),
    ("aes128_strf_identity", "StdCF", "Identity", 128, True, False),
    ("aes256_stmf_identity", "Identity", "StdCF", 256, False, True),
    ("aes256_strf_identity", "StdCF", "Identity", 256, False, False),
]


# --------------------------------- pypdfbox authors mixed → PDFBox reads


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "stmf", "strf", "key_length", "prefer_aes", "stream_is_identity"),
    _COMBOS,
    ids=[c[0] for c in _COMBOS],
)
def test_pypdfbox_mixed_routing_pdfbox_reads(
    algo_id: str,
    stmf: str,
    strf: str,
    key_length: int,
    prefer_aes: bool,
    stream_is_identity: bool,
    tmp_path: Path,
) -> None:
    """pypdfbox encrypts with ``/StmF`` ≠ ``/StrF`` (one /StdCF, one /Identity);
    the Identity-routed object type stays cleartext on the wire, the
    /StdCF-routed type is enciphered, and Apache PDFBox reads the result back
    recovering the SAME string bytes + page text pypdfbox does."""
    _fixture_present()
    enc = tmp_path / f"py_mixed_{algo_id}.pdf"
    _author_mixed(enc, stmf, strf, key_length, prefer_aes)

    # --- on-the-wire routing: the Identity slot leaves its objects cleartext.
    inflatable = _count_inflatable_streams(enc)
    string_cleartext = _string_marker_cleartext_on_wire(enc)
    if stream_is_identity:
        # /StmF /Identity → stream bodies stay FlateDecode-inflatable.
        # /StrF /StdCF    → the catalog string is enciphered (not on wire).
        assert inflatable > 0, f"{algo_id}: Identity-routed streams not cleartext"
        assert not string_cleartext, f"{algo_id}: StdCF string leaked cleartext"
    else:
        # /StmF /StdCF    → every stream body is enciphered (none inflate).
        # /StrF /Identity → the catalog string stays cleartext (hex literal).
        assert inflatable == 0, f"{algo_id}: StdCF streams not enciphered"
        assert string_cleartext, f"{algo_id}: Identity string not cleartext"

    # --- PDFBox reads the mixed-routing file (the interop direction).
    java = _java_inspect(enc, _USER_PW)
    assert java["STMF"] == stmf, f"{algo_id}: PDFBox saw /StmF {java['STMF']}"
    assert java["STRF"] == strf, f"{algo_id}: PDFBox saw /StrF {java['STRF']}"
    assert java["STRING_VALUE"] == _STRING_MARKER.hex()
    assert java["PAGES"] == "2"

    # --- pypdfbox reads its own mixed-routing file; both recover identically.
    py_marker, py_text = _py_read(enc, _USER_PW)
    assert py_marker == _STRING_MARKER, f"{algo_id}: pypdfbox lost the string"
    assert py_text.strip() == java["TEXT"].strip(), (
        f"{algo_id}: recovered text diverges between pypdfbox and PDFBox"
    )


# --------------- PDFBox-authored plain StdCF → pypdfbox reads (sanity floor)


@requires_oracle
@pytest.mark.parametrize(
    ("algo_id", "key_length", "prefer_aes"),
    [("aes128", 128, True), ("aes256", 256, False)],
    ids=["aes128", "aes256"],
)
def test_pdfbox_authored_routing_pypdfbox_reads(
    algo_id: str, key_length: int, prefer_aes: bool, tmp_path: Path
) -> None:
    """Apache PDFBox encrypts (its high-level writer always points both /StmF
    and /StrF at /StdCF — it re-stamps the slots at save time even if patched
    post-protect, verified). pypdfbox reads the result and recovers the same
    string + text the PDFBox reader does, confirming the StdCF→StdCF routing
    direction is symmetric. (PDFBox 3.0.7 cannot author a MIXED file through
    its public API; the mixed direction is exercised by the pypdfbox→PDFBox
    test above, which PDFBox proves it can consume.)"""
    _fixture_present()
    enc = tmp_path / f"java_plain_{algo_id}.pdf"
    # CryptRoutingProbe stamps the probe string then encrypts; the post-protect
    # /StmF /StrF override is a no-op for PDFBox's writer, so the file ends up
    # plain StdCF/StdCF — a clean interop floor for the pypdfbox reader.
    run_probe_text(
        "CryptRoutingProbe",
        "encrypt-mixed",
        str(_FIXTURE),
        str(enc),
        _OWNER_PW,
        _USER_PW,
        str(key_length),
        "true" if prefer_aes else "false",
        "StdCF",
        "Identity",
    )

    java = _java_inspect(enc, _USER_PW)
    py_marker, py_text = _py_read(enc, _USER_PW)
    assert py_marker == _STRING_MARKER
    assert py_marker.hex() == java["STRING_VALUE"]
    assert py_text.strip() == java["TEXT"].strip()


# ------------------------------------ /EFF embedded-file routing resolution


def test_eff_routes_independently_of_stmf() -> None:
    """An ``/EFF`` slot pointed at a distinct crypt filter resolves to that
    filter's /CFM, independent of /StmF. When /EFF is absent it inherits
    /StmF (PDF 32000-1 §7.6.5). Pins the embedded-file routing resolution
    that the per-object ``is_embedded_file`` cipher dispatch keys off; the
    writer does not yet flag embedded-file streams, so this stays a read-side
    routing-table assertion (the differential surface above covers /StmF and
    /StrF, which the writer DOES drive end-to-end)."""
    from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

    enc = PDEncryption()
    enc.set_v(4)
    enc.set_revision(4)
    std = PDCryptFilterDictionary()
    std.set_cfm("AESV2")
    std.set_length(16)
    enc.set_std_crypt_filter_dictionary(std)
    enc.set_stm_f("StdCF")
    enc.set_str_f("StdCF")
    enc.set_eff("Identity")  # embedded files explicitly NOT enciphered

    handler = StandardSecurityHandler(enc)
    handler._populate_routing_table(enc)  # noqa: SLF001 — read-side surface

    assert handler.get_stream_cfm() == "AESV2"
    assert handler.get_string_cfm() == "AESV2"
    assert handler.get_embedded_file_cfm() == "Identity"
