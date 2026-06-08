"""Live Apache PDFBox differential fuzz of the crypt-filter DECODE / DISPATCH
path (wave 1517).

The well-formed crypt-filter oracle suite (``test_crypt_filter_oracle``,
``test_crypt_routing_oracle``, ``test_strf_default_oracle``) only exercises
syntactically valid ``/StdCF`` documents where both default filters point at
``/StdCF``. ``EncryptDictFuzzProbe`` (wave 1511) fuzzes the ``/Encrypt``-dict
PARSE + bootstrap leniency. NEITHER exercises the actual string/stream
decryption DISPATCH under malformed / unusual crypt-filter configs — which is
this wave's surface:

* an unknown ``/CFM`` (``/Zz``) on the default crypt filter,
* ``/CFM /None`` (the spec "no cipher" value),
* a ``/Type /Metadata`` stream whose body is cleartext (``<?xpacket``) while
  ``/EncryptMetadata`` is true (PDFBOX-3173 / PDFBOX-2603 heuristic) — and the
  ``/EncryptMetadata false`` variant,
* ``/StmF`` / ``/StrF`` pointing at a filter absent from ``/CF``,
* per-slot ``/Identity`` routing variants.

Strategy: each corpus PDF is hand-built byte-for-byte with the cipher applied
by pypdfbox's *verified-correct* RC4 / AES-128 primitives, so the on-disk bytes
are ground truth independent of pypdfbox's high-level writer. The deterministic
corpus plus a ``manifest.txt`` (one case name per line, in order) is written to
a tmp dir; ``CryptFilterFuzzProbe`` loads each ``<case>.pdf`` with an EMPTY user
password via ``Loader.loadPDF(file, "")`` and reports a stable framed line. Both
sides read the exact same bytes on disk so the decode contract is directly
comparable.

Validation, not blind pinning: the Java line is ground truth. For every case we
assert pypdfbox's decode contract — *opens vs raises*, the recovered page text,
and the recovered metadata — matches Java. These pin the three real bugs fixed
in wave 1517 (see ``CHANGES.md``):

1. a ``/Type /Metadata`` stream whose body is cleartext ``<?xpacket`` was
   RC4/AES-"decrypted" into garbage instead of being left untouched (the
   upstream unencrypted-metadata heuristic),
2. an unknown ``/CFM`` left the bytes as ciphertext instead of RC4-deciphering
   them (PDFBox treats any non-AESV2/AESV3 /CFM as RC4),
3. ``/CFM /None`` was treated as an Identity pass-through instead of RC4.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from pypdfbox.pdmodel.encryption.standard_security_handler import (
    StandardSecurityHandler as _S,
)
from pypdfbox.pdmodel.encryption.standard_security_handler import (
    _aes128_cbc_encrypt,
    _rc4,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_DOCID = b"0123456789abcdef"
_PERMS = -44

_TEXT_MARKER = "CryptFilterFuzz1517"
_META_MARKER = "clearmeta1517"
_XMP = (
    '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    f"<x>{_META_MARKER}</x><?xpacket end=\"w\"?>"
).encode("latin-1")


# --------------------------------------------------------------- key helpers


def _file_key(rev: int, key_len_bytes: int, encrypt_metadata: bool) -> bytes:
    """Owner-derived file key for an empty user/owner password."""
    o = _S._compute_owner_password_r2_r4(b"", b"", rev, key_len_bytes)
    return _S._compute_encryption_key(
        b"", o, _PERMS, _DOCID, rev, key_len_bytes, encrypt_metadata
    )


def _o_u(rev: int, key_len_bytes: int, encrypt_metadata: bool) -> tuple[bytes, bytes]:
    o = _S._compute_owner_password_r2_r4(b"", b"", rev, key_len_bytes)
    u = _S._compute_user_password_r2_r4(
        b"", o, _PERMS, _DOCID, rev, key_len_bytes, encrypt_metadata=encrypt_metadata
    )
    return o, u


def _object_key(file_key: bytes, num: int, gen: int, aes: bool) -> bytes:
    md = hashlib.md5(usedforsecurity=False)
    md.update(file_key)
    md.update(
        bytes([num & 0xFF, (num >> 8) & 0xFF, (num >> 16) & 0xFF, gen & 0xFF, (gen >> 8) & 0xFF])
    )
    if aes:
        md.update(b"sAlT")
    return md.digest()[: min(len(file_key) + 5, 16)]


def _enc_stream(file_key: bytes, num: int, data: bytes, cipher: str) -> bytes:
    if cipher == "identity":
        return data
    if cipher == "rc4":
        return _rc4(_object_key(file_key, num, 0, aes=False), data)
    if cipher == "aesv2":
        return _aes128_cbc_encrypt(_object_key(file_key, num, 0, aes=True), data)
    raise ValueError(cipher)


# --------------------------------------------------------------- PDF builder


def _hx(b: bytes) -> bytes:
    return b"<" + b.hex().encode("ascii") + b">"


def _build_pdf(
    *,
    enc_dict: bytes,
    content_cipher: str,
    file_key: bytes,
    meta_bytes: bytes | None,
    meta_cipher: str,
) -> bytes:
    """Assemble a minimal encrypted PDF.

    ``content_cipher`` / ``meta_cipher`` are one of identity / rc4 / aesv2 and
    drive how object 4 (content) and object 5 (metadata) bodies are enciphered
    on disk. ``meta_bytes`` None omits the /Metadata stream entirely.
    """
    content = f"BT /F1 12 Tf ({_TEXT_MARKER}) Tj ET".encode("latin-1")
    enc_content = _enc_stream(file_key, 4, content, content_cipher)

    objs: dict[int, bytes] = {}
    if meta_bytes is None:
        objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    else:
        objs[1] = b"<< /Type /Catalog /Pages 2 0 R /Metadata 5 0 R >>"
    objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    objs[3] = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 6 0 R >> >> >>"
    )
    objs[4] = (
        b"<< /Length %d >>\nstream\n" % len(enc_content) + enc_content + b"\nendstream"
    )
    objs[6] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objs[7] = enc_dict
    if meta_bytes is not None:
        enc_meta = _enc_stream(file_key, 5, meta_bytes, meta_cipher)
        objs[5] = (
            b"<< /Type /Metadata /Subtype /XML /Length %d >>\nstream\n" % len(enc_meta)
            + enc_meta
            + b"\nendstream"
        )

    order = [1, 2, 3, 4, 5, 6, 7] if meta_bytes is not None else [1, 2, 3, 4, 6, 7]
    out = bytearray(b"%PDF-1.5\n")
    off: dict[int, int] = {}
    for n in order:
        off[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 8\n0000000000 65535 f \n"
    for n in range(1, 8):
        if n in off:
            out += b"%010d 00000 n \n" % off[n]
        else:
            out += b"0000000000 00000 f \n"
    out += (
        b"trailer\n<< /Size 8 /Root 1 0 R /Encrypt 7 0 R /ID [%s %s] >>\n"
        % (_hx(_DOCID), _hx(_DOCID))
    )
    out += b"startxref\n%d\n%%%%EOF" % xref_pos
    return bytes(out)


def _v124_enc_dict(
    *,
    v: int,
    r: int,
    length_bits: int,
    o: bytes,
    u: bytes,
    cf: bytes | None = None,
    stmf: str | None = None,
    strf: str | None = None,
    eff: str | None = None,
    encrypt_metadata: bool | None = None,
) -> bytes:
    parts = [
        b"<< /Filter /Standard",
        b"/V %d" % v,
        b"/R %d" % r,
        b"/Length %d" % length_bits,
        b"/P %d" % _PERMS,
        b"/O %s" % _hx(o),
        b"/U %s" % _hx(u),
    ]
    if cf is not None:
        parts.append(b"/CF %s" % cf)
    if stmf is not None:
        parts.append(b"/StmF /%s" % stmf.encode("ascii"))
    if strf is not None:
        parts.append(b"/StrF /%s" % strf.encode("ascii"))
    if eff is not None:
        parts.append(b"/EFF /%s" % eff.encode("ascii"))
    if encrypt_metadata is not None:
        parts.append(b"/EncryptMetadata %s" % (b"true" if encrypt_metadata else b"false"))
    parts.append(b">>")
    return b" ".join(parts)


def _build_r6_pdf(
    *,
    cfm: str,
    content_cipher: str,
    meta_bytes: bytes | None,
    meta_cipher: str,
) -> bytes:
    """Author an AES-256 (V5/R6) PDF with an empty user password.

    ``content_cipher`` / ``meta_cipher`` are aesv3 / identity. The file key is
    random (r6 wraps it in /OE /UE) so each call produces a fresh but
    self-consistent document.
    """
    handler = _S()
    file_key = os.urandom(32)
    handler.set_encryption_key(file_key)
    handler._encrypt_metadata = True
    o, oe, u, ue, perms = handler._build_r6_dictionary(b"", b"", _PERMS)

    def enc(num: int, data: bytes, cipher: str) -> bytes:
        if cipher == "identity":
            return data
        if cipher == "aesv3":
            return _aes128_cbc_encrypt(file_key, data)
        raise ValueError(cipher)

    content = f"BT /F1 12 Tf ({_TEXT_MARKER}) Tj ET".encode("latin-1")
    enc_content = enc(4, content, content_cipher)

    objs: dict[int, bytes] = {}
    if meta_bytes is None:
        objs[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    else:
        objs[1] = b"<< /Type /Catalog /Pages 2 0 R /Metadata 5 0 R >>"
    objs[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    objs[3] = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
        b"/Contents 4 0 R /Resources << /Font << /F1 6 0 R >> >> >>"
    )
    objs[4] = (
        b"<< /Length %d >>\nstream\n" % len(enc_content) + enc_content + b"\nendstream"
    )
    objs[6] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objs[7] = (
        b"<< /Filter /Standard /V 5 /R 6 /Length 256 /P %d /O %s /U %s "
        b"/OE %s /UE %s /Perms %s /CF << /StdCF << /Type /CryptFilter "
        b"/CFM /%s /Length 32 >> >> /StmF /StdCF /StrF /StdCF >>"
        % (_PERMS, _hx(o), _hx(u), _hx(oe), _hx(ue), _hx(perms), cfm.encode("ascii"))
    )
    if meta_bytes is not None:
        enc_meta = enc(5, meta_bytes, meta_cipher)
        objs[5] = (
            b"<< /Type /Metadata /Subtype /XML /Length %d >>\nstream\n" % len(enc_meta)
            + enc_meta
            + b"\nendstream"
        )

    order = [1, 2, 3, 4, 5, 6, 7] if meta_bytes is not None else [1, 2, 3, 4, 6, 7]
    out = bytearray(b"%PDF-1.7\n")
    off: dict[int, int] = {}
    for n in order:
        off[n] = len(out)
        out += b"%d 0 obj\n" % n + objs[n] + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 8\n0000000000 65535 f \n"
    for n in range(1, 8):
        if n in off:
            out += b"%010d 00000 n \n" % off[n]
        else:
            out += b"0000000000 00000 f \n"
    out += (
        b"trailer\n<< /Size 8 /Root 1 0 R /Encrypt 7 0 R /ID [%s %s] >>\n"
        % (_hx(_DOCID), _hx(_DOCID))
    )
    out += b"startxref\n%d\n%%%%EOF" % xref_pos
    return bytes(out)


# --------------------------------------------------------------- corpus


def _corpus() -> dict[str, bytes]:
    """Return ``{case_name: pdf_bytes}`` for the full dispatch matrix."""
    cases: dict[str, bytes] = {}

    # ---- V1/R2 RC4-40 baseline (no /CF) ----
    fk = _file_key(2, 5, True)
    o, u = _o_u(2, 5, True)
    cases["rc4_40_baseline"] = _build_pdf(
        enc_dict=_v124_enc_dict(v=1, r=2, length_bits=40, o=o, u=u),
        content_cipher="rc4",
        file_key=fk,
        meta_bytes=None,
        meta_cipher="identity",
    )

    # ---- V2/R3 RC4-128 baseline (no /CF) ----
    fk = _file_key(3, 16, True)
    o, u = _o_u(3, 16, True)
    cases["rc4_128_baseline"] = _build_pdf(
        enc_dict=_v124_enc_dict(v=2, r=3, length_bits=128, o=o, u=u),
        content_cipher="rc4",
        file_key=fk,
        meta_bytes=None,
        meta_cipher="identity",
    )

    # ---- V4/R4 family — share key derivation (rev 4, 16 bytes) ----
    fk4 = _file_key(4, 16, True)
    o4, u4 = _o_u(4, 16, True)

    def v4(cf: bytes, stmf: str, strf: str, **kw: object) -> bytes:
        return _v124_enc_dict(
            v=4, r=4, length_bits=128, o=o4, u=u4, cf=cf, stmf=stmf, strf=strf, **kw
        )

    cf_v2 = b"<< /StdCF << /Type /CryptFilter /CFM /V2 /Length 16 >> >>"
    cf_aesv2 = b"<< /StdCF << /Type /CryptFilter /CFM /AESV2 /Length 16 >> >>"
    cf_none = b"<< /StdCF << /Type /CryptFilter /CFM /None /Length 16 >> >>"
    cf_zz = b"<< /StdCF << /Type /CryptFilter /CFM /Zz /Length 16 >> >>"

    cases["v4_cfm_v2"] = _build_pdf(
        enc_dict=v4(cf_v2, "StdCF", "StdCF"),
        content_cipher="rc4",
        file_key=fk4,
        meta_bytes=None,
        meta_cipher="identity",
    )
    cases["v4_cfm_aesv2"] = _build_pdf(
        enc_dict=v4(cf_aesv2, "StdCF", "StdCF"),
        content_cipher="aesv2",
        file_key=fk4,
        meta_bytes=None,
        meta_cipher="identity",
    )
    # /CFM /None — PDFBox treats it as RC4, NOT a pass-through.
    cases["v4_cfm_none_rc4"] = _build_pdf(
        enc_dict=v4(cf_none, "StdCF", "StdCF"),
        content_cipher="rc4",
        file_key=fk4,
        meta_bytes=None,
        meta_cipher="identity",
    )
    # Unknown /CFM — PDFBox treats it as RC4.
    cases["v4_cfm_unknown_rc4"] = _build_pdf(
        enc_dict=v4(cf_zz, "StdCF", "StdCF"),
        content_cipher="rc4",
        file_key=fk4,
        meta_bytes=None,
        meta_cipher="identity",
    )
    # /StmF /Identity (the reserved name) — the content stream stays cleartext
    # but its body is observed via the metadata channel here (a cleartext
    # content stream interacts unpredictably with PDFBox's content tokenizer,
    # which is not the dispatch facet under test). We route the AESV2 default
    # filter for streams but flip /StmF to the reserved /Identity, so the
    # metadata stream (which inherits /StmF) must stay cleartext on both sides.
    cases["v4_stmf_identity_meta_cleartext"] = _build_pdf(
        enc_dict=v4(cf_aesv2, "Identity", "StdCF"),
        content_cipher="identity",
        file_key=fk4,
        meta_bytes=_XMP,
        meta_cipher="identity",
    )
    # /StmF names a filter ABSENT from /CF → PDFBox falls back to RC4.
    cases["v4_stmf_absent_rc4"] = _build_pdf(
        enc_dict=v4(cf_v2, "NoSuch", "NoSuch"),
        content_cipher="rc4",
        file_key=fk4,
        meta_bytes=None,
        meta_cipher="identity",
    )
    # /StmF / /StrF entirely ABSENT on a V4 doc with /CF present → both
    # default to /Identity per PDF 32000-1 §7.6.4.4 Table 20, so the content
    # stream stays cleartext on disk.
    cases["v4_stmf_strf_absent_identity"] = _build_pdf(
        enc_dict=_v124_enc_dict(v=4, r=4, length_bits=128, o=o4, u=u4, cf=cf_aesv2),
        content_cipher="identity",
        file_key=fk4,
        meta_bytes=_XMP,
        meta_cipher="identity",
    )
    # AESV2 default with a /CF /Length that disagrees with /Length — the
    # per-object key length comes from the file key, not /CF/Length, so this
    # round-trips as AES regardless (pins that /CF/Length is not consulted for
    # the per-object key size).
    cf_aesv2_len5 = b"<< /StdCF << /Type /CryptFilter /CFM /AESV2 /Length 5 >> >>"
    cases["v4_aesv2_cf_length_mismatch"] = _build_pdf(
        enc_dict=v4(cf_aesv2_len5, "StdCF", "StdCF"),
        content_cipher="aesv2",
        file_key=fk4,
        meta_bytes=None,
        meta_cipher="identity",
    )
    # Unknown /CFM on a V4 doc that ALSO carries cleartext <?xpacket metadata
    # + /EncryptMetadata true — both heuristics (unknown-CFM → RC4 for the
    # content, xpacket pass-through for the metadata) must fire together.
    cases["v4_unknown_cfm_plus_clear_meta"] = _build_pdf(
        enc_dict=v4(cf_zz, "StdCF", "StdCF", encrypt_metadata=True),
        content_cipher="rc4",
        file_key=fk4,
        meta_bytes=_XMP,
        meta_cipher="identity",
    )

    # ---- AES-256 (V5/R6) family ----
    cases["r6_aesv3_baseline"] = _build_r6_pdf(
        cfm="AESV3",
        content_cipher="aesv3",
        meta_bytes=None,
        meta_cipher="identity",
    )
    cases["r6_aesv3_encrypted_meta"] = _build_r6_pdf(
        cfm="AESV3",
        content_cipher="aesv3",
        meta_bytes=_XMP,
        meta_cipher="aesv3",
    )
    cases["r6_aesv3_cleartext_meta"] = _build_r6_pdf(
        cfm="AESV3",
        content_cipher="aesv3",
        meta_bytes=_XMP,
        meta_cipher="identity",
    )

    # ---- Metadata heuristic cases (V1/R2 RC4-40, content RC4) ----
    fk = _file_key(2, 5, True)
    o, u = _o_u(2, 5, True)
    # cleartext <?xpacket metadata + /EncryptMetadata true → PDFBox leaves it.
    cases["meta_cleartext_encryptmeta_true"] = _build_pdf(
        enc_dict=_v124_enc_dict(
            v=1, r=2, length_bits=40, o=o, u=u, encrypt_metadata=True
        ),
        content_cipher="rc4",
        file_key=fk,
        meta_bytes=_XMP,
        meta_cipher="identity",
    )
    # properly RC4-encrypted metadata + /EncryptMetadata true → both decrypt.
    fk = _file_key(2, 5, True)
    o, u = _o_u(2, 5, True)
    cases["meta_encrypted_encryptmeta_true"] = _build_pdf(
        enc_dict=_v124_enc_dict(
            v=1, r=2, length_bits=40, o=o, u=u, encrypt_metadata=True
        ),
        content_cipher="rc4",
        file_key=fk,
        meta_bytes=_XMP,
        meta_cipher="rc4",
    )
    # cleartext metadata + /EncryptMetadata false → both leave it (separate
    # exemption path; the file key differs because rev>=4 mixes the flag, but
    # for r2 it does not — content still RC4 round-trips).
    fk = _file_key(2, 5, False)
    o, u = _o_u(2, 5, False)
    cases["meta_cleartext_encryptmeta_false"] = _build_pdf(
        enc_dict=_v124_enc_dict(
            v=1, r=2, length_bits=40, o=o, u=u, encrypt_metadata=False
        ),
        content_cipher="rc4",
        file_key=fk,
        meta_bytes=_XMP,
        meta_cipher="identity",
    )

    # ---- AES-128 (V4/R4) with cleartext metadata + EncryptMetadata true.
    # rev>=4 mixes the EncryptMetadata flag into the file key, so derive with
    # encrypt_metadata=True (matching the dict).
    fk = _file_key(4, 16, True)
    o, u = _o_u(4, 16, True)
    cases["meta_cleartext_aesv2_encryptmeta_true"] = _build_pdf(
        enc_dict=_v124_enc_dict(
            v=4,
            r=4,
            length_bits=128,
            o=o,
            u=u,
            cf=cf_aesv2,
            stmf="StdCF",
            strf="StdCF",
            encrypt_metadata=True,
        ),
        content_cipher="aesv2",
        file_key=fk,
        meta_bytes=_XMP,
        meta_cipher="aesv2",
    )

    # ---- extra dispatch coverage (V4 family key fk4 / o4 / u4) ----
    # /EFF /Identity — embedded-file routing differs from /StmF; there is no
    # embedded file, so the doc must still open and recover content via the
    # AESV2 /StmF default (pins /EFF doesn't perturb the stream dispatch).
    cases["v4_eff_identity"] = _build_pdf(
        enc_dict=_v124_enc_dict(
            v=4,
            r=4,
            length_bits=128,
            o=o4,
            u=u4,
            cf=cf_aesv2,
            stmf="StdCF",
            strf="StdCF",
            eff="Identity",
        ),
        content_cipher="aesv2",
        file_key=fk4,
        meta_bytes=None,
        meta_cipher="identity",
    )
    # RC4-128 (V2/R3) cleartext <?xpacket metadata + /EncryptMetadata true —
    # the heuristic must fire on the no-/CF legacy RC4 path too.
    fk = _file_key(3, 16, True)
    o, u = _o_u(3, 16, True)
    cases["rc4_128_clear_meta"] = _build_pdf(
        enc_dict=_v124_enc_dict(
            v=2, r=3, length_bits=128, o=o, u=u, encrypt_metadata=True
        ),
        content_cipher="rc4",
        file_key=fk,
        meta_bytes=_XMP,
        meta_cipher="identity",
    )
    # V4 unknown /CFM with RC4-encrypted metadata + /EncryptMetadata true —
    # unknown CFM ⇒ RC4 for BOTH content and metadata; the metadata bytes are
    # ciphertext (no <?xpacket head) so the pass-through heuristic does NOT
    # fire and the RC4 metadata decrypts.
    cases["v4_unknown_cfm_encrypted_meta"] = _build_pdf(
        enc_dict=v4(cf_zz, "StdCF", "StdCF", encrypt_metadata=True),
        content_cipher="rc4",
        file_key=fk4,
        meta_bytes=_XMP,
        meta_cipher="rc4",
    )
    # V4 AESV2 fully-encrypted metadata round trip + /EncryptMetadata true.
    cases["v4_aesv2_encrypted_meta"] = _build_pdf(
        enc_dict=v4(cf_aesv2, "StdCF", "StdCF", encrypt_metadata=True),
        content_cipher="aesv2",
        file_key=fk4,
        meta_bytes=_XMP,
        meta_cipher="aesv2",
    )

    return cases


# --------------------------------------------------------------- parse Java


def _parse_java(text: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("CASE "):
            continue
        body = line[len("CASE ") :]
        name, rest = body.split(" ", 1)
        fields: dict[str, str] = {}
        # Fields are ``open=… text=… meta=…`` in that fixed order; values may
        # contain spaces. Peel from the RIGHT so a multi-word ``text`` value
        # never swallows the trailing ``meta=…`` segment: split ``meta`` first
        # (last field), then ``text``, then whatever remains is ``open``.
        for key in ("meta", "text"):
            idx = rest.rfind(f" {key}=")
            if idx != -1:
                fields[key] = rest[idx + len(key) + 2 :]
                rest = rest[:idx]
        fields["open"] = rest.replace("open=", "").strip()
        rows[name] = fields
    return rows


# --------------------------------------------------------------- pypdfbox side


def _py_read(pdf: bytes) -> dict[str, str]:
    """Open ``pdf`` with empty password via pypdfbox; mirror the probe fields."""
    import io as _io
    import re

    from pypdfbox import PDDocument
    from pypdfbox.text import PDFTextStripper

    res = {"open": "ok", "text": "NOTEXT", "meta": "NOMETA"}
    try:
        doc = PDDocument.load(_io.BytesIO(pdf))
        doc.decrypt("")
    except Exception as exc:  # noqa: BLE001 — canonicalised below
        res["open"] = "ERR:" + type(exc).__name__
        return res
    try:
        t = PDFTextStripper().get_text(doc)
        for raw in (t or "").split("\n"):
            s = re.sub(r"\s+", " ", raw).strip()
            if s:
                res["text"] = s
                break
    except Exception:  # noqa: BLE001
        res["text"] = "ERR"
    try:
        md = doc.get_document_catalog().get_metadata()
        if md is None:
            res["meta"] = "NOMETA"
        else:
            b = (
                md.to_byte_array()
                if hasattr(md, "to_byte_array")
                else bytes(md.get_cos_object().get_unfiltered_stream())
            )
            s = re.sub(rb"\s+", b" ", bytes(b)).decode("latin-1", "replace").strip()
            res["meta"] = s if s else "NOMETA"
    except Exception:  # noqa: BLE001
        res["meta"] = "ERR"
    return res


# --------------------------------------------------------------- the test


@requires_oracle
def test_crypt_filter_dispatch_matches_pdfbox(tmp_path: Path) -> None:
    corpus = _corpus()
    names = list(corpus)
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    for name, data in corpus.items():
        (corpus_dir / f"{name}.pdf").write_bytes(data)
    (corpus_dir / "manifest.txt").write_text(
        "\n".join(names) + "\n", encoding="utf-8"
    )

    java = _parse_java(run_probe_text("CryptFilterFuzzProbe", str(corpus_dir)))
    assert set(java) == set(names), (set(names) - set(java), set(java) - set(names))

    mismatches: list[str] = []
    for name in names:
        jrow = java[name]
        py = _py_read(corpus[name])

        # Open contract: both open or both raise (we don't require identical
        # exception classes across the Java/Python vocabularies, only the
        # open-vs-raise outcome).
        j_open = jrow["open"] == "ok"
        p_open = py["open"] == "ok"
        if j_open != p_open:
            mismatches.append(
                f"{name}: open java={jrow['open']} py={py['open']}"
            )
            continue
        if not j_open:
            continue

        if jrow.get("text", "NOTEXT") != py["text"]:
            mismatches.append(
                f"{name}: text java={jrow.get('text')!r} py={py['text']!r}"
            )
        if jrow.get("meta", "NOMETA") != py["meta"]:
            mismatches.append(
                f"{name}: meta java={jrow.get('meta')!r} py={py['meta']!r}"
            )

    assert not mismatches, "\n".join(mismatches)


@pytest.mark.parametrize(
    "name",
    [
        "v4_cfm_none_rc4",
        "v4_cfm_unknown_rc4",
        "meta_cleartext_encryptmeta_true",
    ],
)
def test_dispatch_regression_local(name: str) -> None:
    """Pin the three wave-1517 fixes without needing the live oracle.

    These corpus cases were authored so PDFBox recovers the marker; the fix
    makes pypdfbox recover it too. Guards against silent regression on a box
    without Java.
    """
    corpus = _corpus()
    py = _py_read(corpus[name])
    assert py["open"] == "ok"
    if name.startswith("meta_"):
        assert _META_MARKER in py["meta"]
    else:
        assert py["text"] == _TEXT_MARKER
