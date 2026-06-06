from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature import (
    compute_byte_range,
    compute_signed_digest,
    extract_pkcs7_message_digest,
    get_last_relevant_signature,
    get_mdp_permission,
)
from pypdfbox.pdmodel.pd_document import PDDocument

_DOC_MDP = COSName.get_pdf_name("DocMDP")
_P = COSName.get_pdf_name("P")
_PERMS = COSName.get_pdf_name("Perms")
_REFERENCE = COSName.get_pdf_name("Reference")
_TRANSFORM_METHOD = COSName.get_pdf_name("TransformMethod")
_TRANSFORM_PARAMS = COSName.get_pdf_name("TransformParams")


def _doc_with_perms(perms: COSDictionary) -> PDDocument:
    doc = PDDocument()
    doc.get_document_catalog().set_perms(perms)
    return doc


def _doc_mdp_perms(
    *,
    method: object | None = COSName.get_pdf_name("DocMDP"),
    params: object | None = None,
) -> COSDictionary:
    perms = COSDictionary()
    sig_dict = COSDictionary()
    ref = COSDictionary()
    if method is not None:
        ref.set_item(_TRANSFORM_METHOD, method)
    if params is not None:
        ref.set_item(_TRANSFORM_PARAMS, params)
    refs = COSArray()
    refs.add(ref)
    sig_dict.set_item(_REFERENCE, refs)
    perms.set_item(_DOC_MDP, sig_dict)
    return perms


def _make_perms_with_doc_mdp(value: object) -> COSDictionary:
    perms = COSDictionary()
    perms.set_item(_DOC_MDP, value)
    return perms


def _make_perms_with_reference(value: object) -> COSDictionary:
    perms = COSDictionary()
    sig_dict = COSDictionary()
    sig_dict.set_item(_REFERENCE, value)
    perms.set_item(_DOC_MDP, sig_dict)
    return perms


def _array_with(value: object) -> COSArray:
    array = COSArray()
    array.add(value)
    return array


def _params_with_p(value: object) -> COSDictionary:
    params = COSDictionary()
    params.set_item(_P, value)
    return params


@pytest.mark.parametrize(
    "perms",
    [
        pytest.param(
            COSDictionary(),
            id="missing-doc-mdp",
        ),
        pytest.param(
            (lambda: _make_perms_with_doc_mdp(COSName.get_pdf_name("NotADict")))(),
            id="doc-mdp-not-dictionary",
        ),
        pytest.param(
            (lambda: _make_perms_with_reference(COSName.get_pdf_name("NotArray")))(),
            id="reference-not-array",
        ),
        pytest.param(
            (lambda: _make_perms_with_reference(
                _array_with(COSName.get_pdf_name("NotDict"))
            ))(),
            id="reference-entry-not-dictionary",
        ),
        pytest.param(
            _doc_mdp_perms(method=COSString("DocMDP")),
            id="method-not-name",
        ),
        pytest.param(
            _doc_mdp_perms(params=COSName.get_pdf_name("NotParamsDict")),
            id="params-not-dictionary",
        ),
        pytest.param(
            _doc_mdp_perms(params=_params_with_p(COSString("2"))),
            id="p-not-integer",
        ),
    ],
)
def test_get_mdp_permission_returns_zero_for_malformed_structures(
    perms: COSDictionary,
) -> None:
    doc = _doc_with_perms(perms)
    try:
        assert get_mdp_permission(doc) == 0
    finally:
        doc.close()


def test_get_mdp_permission_uses_first_doc_mdp_reference() -> None:
    perms = COSDictionary()
    sig_dict = COSDictionary()
    refs = COSArray()

    wrong = COSDictionary()
    wrong.set_item(_TRANSFORM_METHOD, COSName.get_pdf_name("FieldMDP"))
    refs.add(wrong)

    params = COSDictionary()
    params.set_item(_P, COSInteger.get(3))
    correct = COSDictionary()
    correct.set_item(_TRANSFORM_METHOD, COSName.get_pdf_name("DocMDP"))
    correct.set_item(_TRANSFORM_PARAMS, params)
    refs.add(correct)

    sig_dict.set_item(_REFERENCE, refs)
    perms.set_item(_DOC_MDP, sig_dict)

    doc = _doc_with_perms(perms)
    try:
        assert get_mdp_permission(doc) == 3
    finally:
        doc.close()


def test_get_last_relevant_signature_accepts_missing_type() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
    from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
        PDSignatureField,
    )

    doc = PDDocument()
    acro = PDAcroForm(doc)
    doc.get_document_catalog().set_acro_form(acro)
    field = PDSignatureField(acro)
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])
    sig.set_type(None)
    field.set_value(sig)
    acro.set_fields([field])

    try:
        chosen = get_last_relevant_signature(doc)
        assert chosen is not None
        assert chosen.get_cos_object() is sig.get_cos_object()
    finally:
        doc.close()


def test_compute_byte_range_accepts_bytearray() -> None:
    document = bytearray(b"abc<placeholder>xyz")

    # `<` at 3, `>` at 15; delimiters excluded (PDFBox COSWriter convention):
    # range1 ends before `<` (len1=3), range2 starts after `>` (start2=16).
    assert compute_byte_range(document, 3, 15) == [0, 3, 16, 3]


def test_compute_signed_digest_accepts_bytearray_and_named_algorithm() -> None:
    import hashlib

    document = bytearray(b"HEADxxxxTAIL")
    byte_range = [0, 4, 8, 4]

    assert compute_signed_digest(document, byte_range, algorithm="sha512") == (
        hashlib.sha512(b"HEADTAIL").digest()
    )


def test_compute_signed_digest_rejects_unknown_algorithm_after_validation() -> None:
    with pytest.raises(ValueError, match="unsupported hash type"):
        compute_signed_digest(b"HEADxxxxTAIL", [0, 4, 8, 4], algorithm="nope")


def test_extract_pkcs7_message_digest_returns_none_when_oid_is_at_eof() -> None:
    oid_der = bytes.fromhex("06092A864886F70D010904")

    assert extract_pkcs7_message_digest(oid_der) is None


def test_extract_pkcs7_message_digest_returns_none_when_set_tag_missing() -> None:
    oid_der = bytes.fromhex("06092A864886F70D010904")

    assert extract_pkcs7_message_digest(oid_der + b"\x30\x03abc") is None


def test_extract_pkcs7_message_digest_returns_none_when_octet_tag_missing() -> None:
    oid_der = bytes.fromhex("06092A864886F70D010904")
    set_with_integer = b"\x31\x03\x02\x01\x01"

    assert extract_pkcs7_message_digest(oid_der + set_with_integer) is None


def test_extract_pkcs7_message_digest_returns_none_when_octet_overruns_set() -> None:
    oid_der = bytes.fromhex("06092A864886F70D010904")
    set_with_truncated_octet = b"\x31\x04\x04\x04ab"

    assert extract_pkcs7_message_digest(oid_der + set_with_truncated_octet) is None


def test_catalog_perms_key_is_same_name_used_by_catalog_setter() -> None:
    doc = PDDocument()
    perms = COSDictionary()

    doc.get_document_catalog().set_perms(perms)

    try:
        catalog_dict = doc.get_document_catalog().get_cos_object()
        assert catalog_dict.get_dictionary_object(_PERMS) is perms
    finally:
        doc.close()
