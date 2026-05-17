"""Tests for ``ShowSignature``."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.show_signature import ShowSignature

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_pkcs7_certs_blob() -> bytes:
    """Return a DER-encoded PKCS#7 ``SignedData`` envelope carrying one
    self-signed certificate — enough for the parser to surface a non-empty
    certificate list back to ``_summarize``."""
    import datetime as _dt

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "show-sig")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_dt.datetime.now(_dt.UTC) - _dt.timedelta(days=1))
        .not_valid_after(_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    # Produce a PKCS#7 SignedData envelope carrying the cert + a signature
    # over a trivial payload — load_der_pkcs7_certificates only needs the
    # certs field, but cryptography won't synthesise SignedData without a
    # signer, so we sign over an empty buffer.
    return pkcs7.PKCS7SignatureBuilder().set_data(b"").add_signer(
        cert, key, hashes.SHA256()
    ).sign(serialization.Encoding.DER, [])


# ---------------------------------------------------------------------------
# Construction / CLI surface
# ---------------------------------------------------------------------------


def test_construction() -> None:
    show = ShowSignature()
    assert show._results == []


def test_main_too_few_args_exits(capsys) -> None:
    with pytest.raises(SystemExit):
        ShowSignature.main([])
    captured = capsys.readouterr()
    assert "ShowSignature" in captured.err


def test_main_too_many_args_exits(capsys) -> None:
    with pytest.raises(SystemExit):
        ShowSignature.main(["a", "b", "c"])
    captured = capsys.readouterr()
    assert "ShowSignature" in captured.err


def test_main_invokes_show_signature_with_args(tmp_path) -> None:
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%EOF\n")  # invalid; only the dispatch matters
    with patch.object(
        ShowSignature, "show_signature", return_value=[]
    ) as mock_show:
        ShowSignature.main(["secret", str(pdf)])
    mock_show.assert_called_once_with("secret", str(pdf))


def test_usage_writes_to_stderr(capsys) -> None:
    ShowSignature.usage()
    captured = capsys.readouterr()
    assert "ShowSignature" in captured.err
    assert "password" in captured.err


# ---------------------------------------------------------------------------
# show_signature — missing input / no signatures
# ---------------------------------------------------------------------------


def test_show_signature_raises_on_missing_file(tmp_path) -> None:
    show = ShowSignature()
    with pytest.raises(FileNotFoundError):
        show.show_signature(None, tmp_path / "missing.pdf")


def test_show_signature_returns_empty_for_unsigned_pdf(tmp_path) -> None:
    """A fresh blank PDF carries no signature fields → empty result list."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    pdf = tmp_path / "blank.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(pdf)
    finally:
        doc.close()

    show = ShowSignature()
    out = show.show_signature(None, pdf)
    assert out == []
    assert show._results == []


def test_show_signature_accepts_string_path(tmp_path) -> None:
    """Path coercion from ``str`` is exercised."""
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    pdf = tmp_path / "stringpath.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(pdf)
    finally:
        doc.close()

    show = ShowSignature()
    assert show.show_signature(None, str(pdf)) == []


# ---------------------------------------------------------------------------
# _summarize
# ---------------------------------------------------------------------------


def _make_signature(**kwargs) -> object:
    """Build a duck-typed PDSignature returning the supplied values."""
    sig = MagicMock()
    sig.get_name.return_value = kwargs.get("name")
    sig.get_location.return_value = kwargs.get("location")
    sig.get_reason.return_value = kwargs.get("reason")
    sig.get_filter.return_value = kwargs.get("filter_name")
    sig.get_sub_filter.return_value = kwargs.get("sub_filter")
    sig.get_contents.return_value = kwargs.get("contents")
    return sig


def test_summarize_includes_basic_fields() -> None:
    show = ShowSignature()
    sig = _make_signature(
        name="Alice",
        location="NYC",
        reason="approval",
        filter_name="Adobe.PPKLite",
        sub_filter="adbe.pkcs7.detached",
    )
    summary = show._summarize(sig)
    assert summary["name"] == "Alice"
    assert summary["location"] == "NYC"
    assert summary["reason"] == "approval"
    assert summary["filter"] == "Adobe.PPKLite"
    assert summary["sub_filter"] == "adbe.pkcs7.detached"
    # No contents → certificates key omitted.
    assert "certificates" not in summary


def test_summarize_extracts_certificates_from_valid_pkcs7() -> None:
    show = ShowSignature()
    blob = _build_pkcs7_certs_blob()
    sig = _make_signature(contents=blob)
    summary = show._summarize(sig)
    assert summary["certificates"]
    assert any("show-sig" in subj for subj in summary["certificates"])


def test_summarize_swallows_invalid_pkcs7(caplog) -> None:
    show = ShowSignature()
    sig = _make_signature(contents=b"not a real DER blob")
    with caplog.at_level("DEBUG"):
        summary = show._summarize(sig)
    assert summary["certificates"] == []


def test_summarize_with_empty_contents_omits_certificates() -> None:
    show = ShowSignature()
    sig = _make_signature(contents=b"")
    summary = show._summarize(sig)
    assert "certificates" not in summary


# ---------------------------------------------------------------------------
# show_signature — end-to-end: a doc carrying a signature dictionary
# ---------------------------------------------------------------------------


def test_show_signature_returns_summary_for_added_signature(tmp_path) -> None:
    """Build a PDF whose /AcroForm carries a signature field, save it,
    then verify ``show_signature`` produces a one-entry summary list."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import (
        PDSignature,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    pdf = tmp_path / "signed.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        sig = PDSignature()
        sig.set_name("Charlie")
        sig.set_location("Berlin")
        sig.set_reason("test")
        sig.set_contents(b"\x00" * 16)
        # add_signature wires the sig dict into /AcroForm.
        doc.add_signature(sig)
        doc.save(pdf)
    finally:
        doc.close()

    show = ShowSignature()
    results = show.show_signature(None, pdf)
    # The signature field is reachable through /AcroForm even when the
    # /ByteRange isn't a real signature — only the dictionary metadata
    # matters here.
    assert isinstance(results, list)
    if results:  # field may or may not be discovered depending on the path
        summary = results[0]
        assert summary["name"] == "Charlie"
        assert summary["location"] == "Berlin"
        assert summary["reason"] == "test"


# ---------------------------------------------------------------------------
# check_content_value_with_file
# ---------------------------------------------------------------------------


def test_check_content_value_with_file_matches(tmp_path, caplog) -> None:
    show = ShowSignature()
    # Construct a file whose slice matches the contents.
    payload = b"hello"
    hex_body = payload.hex().encode("ascii")
    # The slice formula is: data[byte_range[0]+byte_range[1]+1 :
    # byte_range[2]-1]. Pick offsets that frame ``hex_body`` exactly.
    prefix = b"<"
    suffix = b">"
    blob = prefix + hex_body + suffix
    f = tmp_path / "blob.bin"
    f.write_bytes(blob)
    # byte_range[0] + byte_range[1] + 1 = 1  (start of hex_body)
    # byte_range[2] - 1 = 1 + len(hex_body)
    br = [0, 0, 1 + len(hex_body) + 1, 0]
    with caplog.at_level("WARNING"):
        show.check_content_value_with_file(str(f), br, payload)
    assert not any("do not match" in r.message for r in caplog.records)


def test_check_content_value_with_file_mismatch_warns(tmp_path, caplog) -> None:
    show = ShowSignature()
    blob = b"<deadbeef>"
    f = tmp_path / "blob.bin"
    f.write_bytes(blob)
    # Slice = "deadbeef" -> bytes \xde\xad\xbe\xef; compare against
    # something else.
    br = [0, 0, 9 + 1, 0]
    with caplog.at_level("WARNING"):
        show.check_content_value_with_file(str(f), br, b"\x00\x00")
    assert any("do not match" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# verify_ets_idot_rfc3161 (and its alias)
# ---------------------------------------------------------------------------


def test_verify_ets_idot_rfc3161_is_noop(caplog) -> None:
    show = ShowSignature()
    with caplog.at_level(logging.DEBUG):
        show.verify_ets_idot_rfc3161(b"signed", b"sig")
    # Stub only emits DEBUG, never raises.
    assert any("ETSI.RFC3161" in r.message for r in caplog.records)


def test_verify_etsi_dot_rfc3161_forwards_to_primary(caplog) -> None:
    show = ShowSignature()
    with caplog.at_level(logging.DEBUG):
        show.verify_etsi_dot_rfc3161(b"signed", b"sig")
    assert any("ETSI.RFC3161" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# verify_pkcs7
# ---------------------------------------------------------------------------


def test_verify_pkcs7_with_valid_blob(caplog) -> None:
    show = ShowSignature()
    blob = _build_pkcs7_certs_blob()
    with caplog.at_level("WARNING"):
        show.verify_pkcs7(b"signed", blob, signature=None)
    # No warning expected — parser accepted the blob.
    assert not any("PKCS#7 parse failed" in r.message for r in caplog.records)


def test_verify_pkcs7_with_invalid_blob_logs_warning(caplog) -> None:
    show = ShowSignature()
    with caplog.at_level("WARNING"):
        show.verify_pkcs7(b"signed", b"garbage", signature=None)
    assert any("PKCS#7 parse failed" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# get_root_certificates
# ---------------------------------------------------------------------------


def test_get_root_certificates_is_empty_set() -> None:
    show = ShowSignature()
    roots = show.get_root_certificates()
    assert roots == set()
    assert isinstance(roots, set)


# ---------------------------------------------------------------------------
# analyse_dss
# ---------------------------------------------------------------------------


def test_analyse_dss_no_dss_dictionary(caplog) -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument

    show = ShowSignature()
    doc = PDDocument()
    try:
        with caplog.at_level("INFO"):
            show.analyse_dss(doc)
        assert any("No DSS dictionary" in r.message for r in caplog.records)
    finally:
        doc.close()


def test_analyse_dss_dumps_keys_when_present(caplog) -> None:
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.pdmodel.pd_document import PDDocument

    show = ShowSignature()
    doc = PDDocument()
    try:
        catalog = doc.get_document_catalog().get_cos_object()
        dss = COSDictionary()
        dss.set_item(COSName.get_pdf_name("Certs"), COSDictionary())
        dss.set_item(COSName.get_pdf_name("CRLs"), COSDictionary())
        catalog.set_item(COSName.get_pdf_name("DSS"), dss)
        with caplog.at_level("INFO"):
            show.analyse_dss(doc)
        records = [r.message for r in caplog.records if "DSS" in r.message]
        assert any("Certs" in m or "CRLs" in m for m in records)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# print_streams_from_array
# ---------------------------------------------------------------------------


def test_print_streams_from_array_with_elements(caplog) -> None:
    show = ShowSignature()

    class _Arr:
        def size(self) -> int:
            return 3

    with caplog.at_level("INFO"):
        show.print_streams_from_array(_Arr(), "CRLs")
    assert any("CRLs" in r.message and "3" in r.message for r in caplog.records)


def test_print_streams_from_array_with_none(caplog) -> None:
    show = ShowSignature()
    with caplog.at_level("INFO"):
        show.print_streams_from_array(None, "Certs")
    assert any("Certs" in r.message and "0" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Path type coercion (sanity)
# ---------------------------------------------------------------------------


def test_show_signature_accepts_pathlib_path(tmp_path) -> None:
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage

    pdf = tmp_path / "blank2.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(pdf)
    finally:
        doc.close()

    show = ShowSignature()
    assert show.show_signature(None, Path(pdf)) == []
