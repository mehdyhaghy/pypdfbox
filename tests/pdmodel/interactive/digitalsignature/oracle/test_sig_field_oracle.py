"""Live Apache PDFBox differential parity for signature-field metadata.

Direction: **pypdfbox-writes → Java-reads**. pypdfbox builds an AcroForm with
a ``/FT /Sig`` :class:`PDSignatureField` carrying:

* a ``/Lock`` :class:`PDSignatureLock` (``/Action /Include`` + ``/Fields``),
* an ``/SV`` :class:`PDSeedValue` (``/SubFilter`` ``adbe.pkcs7.detached``,
  ``/DigestMethod`` ``SHA256``, a ``/Reasons`` text-string list, and the
  ``/Ff`` required-flag bits for SubFilter / Reason / DigestMethod),
* a widget rectangle, and
* a visible signature appearance (``/AP /N`` form XObject).

``SigFieldProbe`` then loads the PDF with Apache PDFBox 3.0.7 and reports the
field type, the ``/Lock`` action + fields, the ``/SV`` subfilter / digest /
reasons / required-flag bits, whether the widget has an ``/AP /N``, and (when
signed) the ``/V`` subfilter. We assert PDFBox reads back exactly what
pypdfbox's typed accessors hold.

Upstream-bug note: PDFBox 3.0.7's ``PDSeedValue.getReasons()`` calls
``COSArray.toCOSNameStringList()`` and throws ``ClassCastException`` on the
``COSString`` entries its own ``setReasons()`` writes (``/Reasons`` is an
array of *text strings* per PDF 32000-1 Table 234, not names). The probe
therefore reads ``/Reasons`` straight off the COS array as strings — the
spec-correct interpretation pypdfbox implements. See CHANGES.md.

No key/cert material is committed; the signed variant uses an in-test
self-signed cert built with ``cryptography``.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel import PDDocument, PDPage, PDResources
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.annotation import (
    PDAppearanceDictionary,
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSeedValue,
    PDSignature,
    PDSignatureLock,
    Pkcs7Signature,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from tests.oracle.harness import requires_oracle, run_probe_text

_LOCK_FIELDS = ["foo"]
_REASONS = ["I approve", "I reviewed"]


# --------------------------------------------------------------- helpers


def _parse_probe_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _make_self_signed_cert(
    cn: str = "pypdfbox-sigfield-signer",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-sigfield-oracle"),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
        ]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _build_sig_field_pdf(out: Path, *, visible: bool = True) -> None:
    """Build a 1-page PDF with one unsigned signature field carrying /Lock,
    /SV, a widget rectangle, and (when ``visible``) an /AP /N appearance."""
    doc = PDDocument()
    try:
        page = PDPage()
        # Give the page an explicit (empty) /Resources so qpdf --check does
        # not emit a "Resources is missing; repairing" warning unrelated to
        # the signature-field surface under test.
        page.set_resources(PDResources())
        doc.add_page(page)
        form = PDAcroForm(doc)
        doc.get_document_catalog().set_acro_form(form)

        sig = PDSignatureField(form)
        sig.set_partial_name("Signature1")

        widget = sig.get_widgets()[0]
        widget.set_rectangle(PDRectangle(50, 600, 250, 700))

        lock = PDSignatureLock()
        lock.set_action(PDSignatureLock.ACTION_INCLUDE)
        lock.set_fields(_LOCK_FIELDS)
        sig.set_lock(lock)

        sv = PDSeedValue()
        sv.set_sub_filter([PDSeedValue.SUBFILTER_ADBE_PKCS7_DETACHED])
        sv.set_digest_method([PDSeedValue.DIGEST_SHA256])
        sv.set_reasons(_REASONS)
        sv.set_sub_filter_required(True)
        sv.set_reason_required(True)
        sv.set_digest_method_required(True)
        sig.set_seed_value(sv)

        if visible:
            ap_stream = PDAppearanceStream(doc)
            ap_stream.set_bbox(PDRectangle(0, 0, 200, 100))
            ap_stream.get_cos_object().set_data(
                b"q 0 0 1 rg 10 10 180 80 re f Q\n"
            )
            ap = PDAppearanceDictionary()
            ap.set_normal_appearance(ap_stream)
            widget.set_appearance(ap)

        form.set_fields([sig])
        page.get_annotations().append(widget.get_cos_object())
        doc.save(out)
    finally:
        doc.close()


def _sign_sig_field_pdf(src: Path, out: Path) -> None:
    """Reload ``src``, sign its signature field, incrementally save to ``out``."""
    cert, key = _make_self_signed_cert()
    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_name("pypdfbox sigfield signer")
        sig.set_reason(_REASONS[0])
        doc.add_signature(sig, Pkcs7Signature(cert, key))
        doc.save_incremental(out)


# --------------------------------------------------------- the parity tests


@requires_oracle
def test_field_type_is_sig(tmp_path: Path) -> None:
    """PDFBox classifies the field as ``/FT /Sig`` — same as pypdfbox's
    :meth:`PDSignatureField.get_field_type`."""
    out = tmp_path / "sigfield.pdf"
    _build_sig_field_pdf(out)

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        assert isinstance(field, PDSignatureField)
        py_ft = field.get_field_type()

    java = _parse_probe_kv(run_probe_text("SigFieldProbe", str(out)))
    assert java["field.present"] == "true"
    assert java["field.ft"] == "Sig"
    assert py_ft == java["field.ft"]


@requires_oracle
def test_lock_action_and_fields_match(tmp_path: Path) -> None:
    """The ``/Lock`` ``/Action`` enum (``Include``) and ``/Fields`` list read
    back identically in PDFBox and pypdfbox — the high-value lock case."""
    out = tmp_path / "sigfield.pdf"
    _build_sig_field_pdf(out)

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        lock = field.get_lock()
        assert lock is not None
        py_action = lock.get_action()
        py_fields = lock.get_fields()

    java = _parse_probe_kv(run_probe_text("SigFieldProbe", str(out)))
    assert java["lock.present"] == "true"
    assert java["lock.action"] == "Include"
    assert py_action == java["lock.action"]
    assert py_action == PDSignatureLock.ACTION_INCLUDE
    assert java["lock.fields"] == "foo"
    assert py_fields == _LOCK_FIELDS
    assert ",".join(py_fields) == java["lock.fields"]


@requires_oracle
def test_seed_value_subfilter_digest_reasons_match(tmp_path: Path) -> None:
    """The ``/SV`` ``/SubFilter`` / ``/DigestMethod`` / ``/Reasons`` accessors
    return exactly the values PDFBox reads from the same dictionary — the
    high-value seed-value case."""
    out = tmp_path / "sigfield.pdf"
    _build_sig_field_pdf(out)

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        sv = field.get_seed_value()
        assert sv is not None
        py_subfilter = sv.get_sub_filter()
        py_digest = sv.get_digest_method()
        py_reasons = sv.get_reasons()

    java = _parse_probe_kv(run_probe_text("SigFieldProbe", str(out)))
    assert java["sv.present"] == "true"

    assert java["sv.subfilter"] == "adbe.pkcs7.detached"
    assert py_subfilter == [PDSeedValue.SUBFILTER_ADBE_PKCS7_DETACHED]
    assert ",".join(py_subfilter) == java["sv.subfilter"]

    assert java["sv.digestmethod"] == "SHA256"
    assert py_digest == [PDSeedValue.DIGEST_SHA256]
    assert ",".join(py_digest) == java["sv.digestmethod"]

    assert java["sv.reasons"] == "I approve|I reviewed"
    assert py_reasons == _REASONS
    assert "|".join(py_reasons) == java["sv.reasons"]


@requires_oracle
def test_seed_value_required_flags_match(tmp_path: Path) -> None:
    """The ``/SV`` ``/Ff`` required-flag bits pypdfbox decodes (SubFilter /
    Reason / DigestMethod set, Filter clear) agree bit-for-bit with the
    integer PDFBox reads."""
    out = tmp_path / "sigfield.pdf"
    _build_sig_field_pdf(out)

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        sv = field.get_seed_value()
        assert sv is not None
        py_subfilter_req = sv.is_sub_filter_required()
        py_reason_req = sv.is_reason_required()
        py_digest_req = sv.is_digest_method_required()
        py_filter_req = sv.is_filter_required()

    java = _parse_probe_kv(run_probe_text("SigFieldProbe", str(out)))
    assert java["sv.subfilterReq"] == "true"
    assert java["sv.reasonReq"] == "true"
    assert java["sv.digestReq"] == "true"
    assert java["sv.filterReq"] == "false"

    assert py_subfilter_req is True
    assert py_reason_req is True
    assert py_digest_req is True
    assert py_filter_req is False

    assert str(py_subfilter_req).lower() == java["sv.subfilterReq"]
    assert str(py_reason_req).lower() == java["sv.reasonReq"]
    assert str(py_digest_req).lower() == java["sv.digestReq"]
    assert str(py_filter_req).lower() == java["sv.filterReq"]

    # The composite /Ff integer: bit2 (SubFilter) + bit4 (Reason) + bit7
    # (DigestMethod) = 2 + 8 + 64 = 74.
    expected_ff = (
        PDSeedValue.FLAG_SUBFILTER
        | PDSeedValue.FLAG_REASON
        | PDSeedValue.FLAG_DIGEST_METHOD
    )
    assert expected_ff == 74
    assert java["sv.ff"] == str(expected_ff)


@requires_oracle
def test_visible_widget_has_normal_appearance(tmp_path: Path) -> None:
    """A visibly-signed field's widget carries an ``/AP /N`` form XObject —
    PDFBox and pypdfbox agree the appearance structure is present."""
    out = tmp_path / "sigfield.pdf"
    _build_sig_field_pdf(out, visible=True)

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        widget = field.get_widgets()[0]
        ap = widget.get_appearance()
        py_has_apn = ap is not None and ap.get_normal_appearance() is not None
        assert field.has_visible_widget() is True

    java = _parse_probe_kv(run_probe_text("SigFieldProbe", str(out)))
    assert java["widget.hasAPN"] == "true"
    assert py_has_apn is True


@requires_oracle
def test_invisible_field_has_no_appearance(tmp_path: Path) -> None:
    """When no ``/AP`` is written, PDFBox reports the widget has no normal
    appearance — matching pypdfbox."""
    out = tmp_path / "sigfield_invisible.pdf"
    _build_sig_field_pdf(out, visible=False)

    with PDDocument.load(out) as doc:
        field = doc.get_document_catalog().get_acro_form().get_fields()[0]
        widget = field.get_widgets()[0]
        ap = widget.get_appearance()
        py_has_apn = ap is not None and ap.get_normal_appearance() is not None

    java = _parse_probe_kv(run_probe_text("SigFieldProbe", str(out)))
    assert java["widget.hasAPN"] == "false"
    assert py_has_apn is False


@requires_oracle
def test_signed_field_subfilter_matches(tmp_path: Path) -> None:
    """After signing the field, PDFBox reads the same ``/V`` ``/SubFilter`` as
    pypdfbox's :meth:`PDSignatureField.get_signature` reports."""
    unsigned = tmp_path / "sigfield.pdf"
    _build_sig_field_pdf(unsigned, visible=False)
    signed = tmp_path / "sigfield_signed.pdf"
    _sign_sig_field_pdf(unsigned, signed)

    with PDDocument.load(signed) as doc:
        sig_fields = doc.get_document_catalog().get_acro_form().get_fields()
        py_sub = None
        for field in sig_fields:
            if isinstance(field, PDSignatureField):
                signature = field.get_signature()
                if signature is not None:
                    py_sub = signature.get_sub_filter()
                    break

    java = _parse_probe_kv(run_probe_text("SigFieldProbe", str(signed)))
    assert java["sig.present"] == "true"
    assert java["sig.subfilter"] == "adbe.pkcs7.detached"
    assert py_sub == java["sig.subfilter"]
