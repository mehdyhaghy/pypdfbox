from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSignature,
    check_certificate_usage,
    check_responder_certificate_usage,
    get_last_relevant_signature,
    get_mdp_permission,
    set_mdp_permission,
)
from pypdfbox.pdmodel.pd_document import PDDocument


# ---------------------------------------------------------- cert factory


def _make_cert(
    *,
    key_usage: dict | None = None,
    key_usage_critical: bool = True,
    extended_key_usage: list[str] | None = None,
):
    """Build a self-signed leaf cert with the requested KU / EKU bits.

    Returns a ``cryptography`` ``Certificate`` object — only the extension
    bits matter for SigUtils, so this stays compact.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID, ObjectIdentifier

    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(now)
        .not_valid_after(now + dt.timedelta(days=1))
    )

    if key_usage is not None:
        ku_kwargs = {
            "digital_signature": False,
            "content_commitment": False,
            "key_encipherment": False,
            "data_encipherment": False,
            "key_agreement": False,
            "key_cert_sign": False,
            "crl_sign": False,
            "encipher_only": False,
            "decipher_only": False,
        }
        ku_kwargs.update(key_usage)
        builder = builder.add_extension(
            x509.KeyUsage(**ku_kwargs), critical=key_usage_critical
        )

    if extended_key_usage is not None:
        usages = [ObjectIdentifier(o) for o in extended_key_usage]
        builder = builder.add_extension(
            x509.ExtendedKeyUsage(usages), critical=False
        )

    return builder.sign(private_key, hashes.SHA256())


# ---------------------------------------------------------- check_certificate_usage


def test_check_certificate_usage_clean_cert_returns_no_warnings():
    cert = _make_cert(
        key_usage={"digital_signature": True},
        extended_key_usage=["1.3.6.1.5.5.7.3.4"],  # emailProtection
    )
    assert check_certificate_usage(cert) == []


def test_check_certificate_usage_warns_on_missing_key_usage():
    cert = _make_cert()  # no KU at all
    warnings = check_certificate_usage(cert)
    assert any("KeyUsage" in w for w in warnings)


def test_check_certificate_usage_warns_when_key_usage_not_critical():
    cert = _make_cert(
        key_usage={"digital_signature": True},
        key_usage_critical=False,
    )
    warnings = check_certificate_usage(cert)
    assert any("not marked critical" in w for w in warnings)


def test_check_certificate_usage_warns_when_signing_bits_clear():
    cert = _make_cert(key_usage={"key_encipherment": True})
    warnings = check_certificate_usage(cert)
    assert any("digitalSignature" in w for w in warnings)


def test_check_certificate_usage_accepts_non_repudiation():
    """``content_commitment`` is the v3 name for nonRepudiation."""
    cert = _make_cert(
        key_usage={"content_commitment": True},
        extended_key_usage=["1.2.840.113583.1.1.5"],  # Adobe Authentic Docs
    )
    assert check_certificate_usage(cert) == []


def test_check_certificate_usage_warns_on_bad_extended_key_usage():
    cert = _make_cert(
        key_usage={"digital_signature": True},
        extended_key_usage=["1.3.6.1.5.5.7.3.1"],  # serverAuth
    )
    warnings = check_certificate_usage(cert)
    assert any("ExtendedKeyUsage" in w for w in warnings)


def test_check_certificate_usage_no_eku_is_ok():
    """ExtendedKeyUsage is optional; absence shouldn't warn."""
    cert = _make_cert(key_usage={"digital_signature": True})
    warnings = check_certificate_usage(cert)
    assert not any("ExtendedKeyUsage" in w for w in warnings)


# -------------------------------------------------- check_responder_certificate_usage


def test_responder_cert_with_ocsp_signing_passes():
    cert = _make_cert(extended_key_usage=["1.3.6.1.5.5.7.3.9"])
    assert check_responder_certificate_usage(cert) == []


def test_responder_cert_without_eku_warns():
    cert = _make_cert()
    warnings = check_responder_certificate_usage(cert)
    assert any("ExtendedKeyUsage" in w for w in warnings)


def test_responder_cert_without_ocsp_signing_warns():
    cert = _make_cert(extended_key_usage=["1.3.6.1.5.5.7.3.4"])
    warnings = check_responder_certificate_usage(cert)
    assert any("OCSPSigning" in w for w in warnings)


# --------------------------------------------------------------- MDP API


def test_get_mdp_permission_returns_zero_for_fresh_doc():
    doc = PDDocument()
    assert get_mdp_permission(doc) == 0


def test_set_mdp_permission_round_trips():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 2)
    assert get_mdp_permission(doc) == 2


def test_set_mdp_permission_round_trips_p1():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 1)
    assert get_mdp_permission(doc) == 1


def test_set_mdp_permission_round_trips_p3():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 3)
    assert get_mdp_permission(doc) == 3


def test_set_mdp_permission_rejects_invalid_value():
    doc = PDDocument()
    sig = PDSignature()
    with pytest.raises(ValueError, match="1, 2 or 3"):
        set_mdp_permission(doc, sig, 4)
    with pytest.raises(ValueError, match="1, 2 or 3"):
        set_mdp_permission(doc, sig, 0)


def test_set_mdp_permission_rejects_double_install():
    doc = PDDocument()
    sig1 = PDSignature()
    sig2 = PDSignature()
    set_mdp_permission(doc, sig1, 2)
    with pytest.raises(ValueError, match="already present"):
        set_mdp_permission(doc, sig2, 1)


def test_get_mdp_permission_ignores_unknown_transform_method():
    """A SigRef with TransformMethod=FieldMDP must not be reported."""
    doc = PDDocument()
    catalog = doc.get_document_catalog()
    perms = COSDictionary()
    sig_dict = COSDictionary()
    ref = COSDictionary()
    ref.set_item(
        COSName.get_pdf_name("TransformMethod"),
        COSName.get_pdf_name("FieldMDP"),
    )
    params = COSDictionary()
    params.set_item(COSName.get_pdf_name("P"), COSInteger.get(2))
    ref.set_item(COSName.get_pdf_name("TransformParams"), params)
    refs = COSArray()
    refs.add(ref)
    sig_dict.set_item(COSName.get_pdf_name("Reference"), refs)
    perms.set_item(COSName.get_pdf_name("DocMDP"), sig_dict)
    catalog.set_perms(perms)
    assert get_mdp_permission(doc) == 0


def test_get_mdp_permission_clamps_out_of_range_p_to_zero():
    doc = PDDocument()
    sig = PDSignature()
    set_mdp_permission(doc, sig, 2)
    # Mutate /P to an invalid value behind SigUtils' back.
    sig_dict = sig.get_cos_object()
    refs = sig_dict.get_dictionary_object(COSName.get_pdf_name("Reference"))
    ref = refs.get_object(0)
    params = ref.get_dictionary_object(COSName.get_pdf_name("TransformParams"))
    params.set_item(COSName.get_pdf_name("P"), COSInteger.get(99))
    assert get_mdp_permission(doc) == 0


# --------------------------------------------------------- get_last_relevant_signature


def _attach_signature(doc: PDDocument, byte_range: list[int] | None) -> PDSignature:
    """Attach a PDSignature value to a synthetic PDSignatureField on ``doc``."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    catalog = doc.get_document_catalog()
    acro = catalog.get_acro_form()
    if acro is None:
        acro = PDAcroForm(doc)
        catalog.set_acro_form(acro)
    field = PDSignatureField(acro)
    sig = PDSignature()
    if byte_range is not None:
        sig.set_byte_range(byte_range)
    field.set_value(sig)
    fields = acro.get_fields()
    fields.append(field)
    acro.set_fields(fields)
    return sig


def test_get_last_relevant_signature_none_when_no_signatures():
    doc = PDDocument()
    assert get_last_relevant_signature(doc) is None


def test_get_last_relevant_signature_picks_latest_byte_range():
    doc = PDDocument()
    early = _attach_signature(doc, [0, 100, 200, 50])  # ends at 250
    late = _attach_signature(doc, [0, 500, 600, 400])  # ends at 1000
    _attach_signature(doc, [0, 200, 300, 100])  # ends at 400
    chosen = get_last_relevant_signature(doc)
    assert chosen is not None
    # Wrappers are recreated per ``get_signature_dictionaries`` call, so
    # compare the underlying COS dictionary identity instead.
    assert chosen.get_cos_object() is late.get_cos_object()
    assert chosen.get_cos_object() is not early.get_cos_object()


def test_get_last_relevant_signature_falls_back_to_last_when_no_byte_range():
    doc = PDDocument()
    _attach_signature(doc, None)
    last = _attach_signature(doc, None)
    chosen = get_last_relevant_signature(doc)
    assert chosen is not None
    assert chosen.get_cos_object() is last.get_cos_object()
