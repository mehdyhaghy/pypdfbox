from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.digitalsignature import pkcs7_signature
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build import (
    PDPropBuild,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_prop_build_data_dict import (
    PDPropBuildDataDict,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value import (
    PDSeedValue,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_certificate import (
    PDSeedValueCertificate,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_mdp import (
    PDSeedValueMDP,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_time_stamp import (
    PDSeedValueTimeStamp,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature_lock import (
    PDSignatureLock,
)
from pypdfbox.pdmodel.interactive.digitalsignature.pkcs7_signature import (
    Pkcs7Signature,
)


def test_seed_value_removal_paths_and_cos_name_filter() -> None:
    seed = PDSeedValue()
    seed.set_filter(COSName.get_pdf_name("Adobe.PPKLite"))
    seed.set_sub_filter(["adbe.pkcs7.detached"])
    seed.set_v(2.0)
    seed.set_reasons(["Approved"])
    seed.set_digest_method(["SHA256"])

    assert seed.get_filter() == "Adobe.PPKLite"
    assert seed.get_sub_filter() == ["adbe.pkcs7.detached"]
    assert seed.get_v() == 2.0
    assert seed.get_reasons() == ["Approved"]
    assert seed.get_digest_method() == ["SHA256"]

    seed.set_sub_filter(None)
    seed.set_v(None)
    seed.set_reasons(None)
    seed.set_digest_method(None)

    assert seed.has_sub_filter() is False
    assert seed.has_v() is False
    assert seed.has_reasons() is False
    assert seed.get_digest_method() == []


def test_seed_value_malformed_reason_array_and_certificate_aliases() -> None:
    seed = PDSeedValue()
    seed.get_cos_object().set_item(
        "Reasons",
        COSArray([COSString("valid"), COSName.get_pdf_name("NotText")]),
    )
    assert seed.get_reasons() is None

    cert = PDSeedValueCertificate()
    seed.set_certificate(cert)

    assert seed.has_certificate() is True
    assert isinstance(seed.get_certificate(), PDSeedValueCertificate)

    seed.set_certificate(None)

    assert seed.has_certificate() is False
    assert seed.get_certificate() is None


def test_seed_value_raw_subdictionary_wrappers_and_digest_validation() -> None:
    seed = PDSeedValue()
    mdp = COSDictionary()
    timestamp = COSDictionary()
    certificate = COSDictionary()

    seed.set_mpd(mdp)
    seed.set_time_stamp(timestamp)
    seed.set_seed_value_certificate(certificate)

    assert isinstance(seed.get_mdp(), PDSeedValueMDP)
    assert isinstance(seed.get_time_stamp(), PDSeedValueTimeStamp)
    assert isinstance(seed.get_seed_value_certificate(), PDSeedValueCertificate)

    with pytest.raises(ValueError, match="isn't allowed"):
        seed.set_digest_method(["MD5"])


def test_signature_lock_removal_predicates_and_summary() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_INCLUDE)
    lock.set_fields(["form.name", "form.date"])
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL)

    assert lock.is_lock_include() is True
    assert lock.is_allow_form_fill() is True
    assert str(lock) == "PDSignatureLock(action=Include, fields=2, p=2 (allow_form_fill))"

    lock.set_fields(None)
    lock.set_p(None)
    lock.set_action(None)

    assert lock.has_fields() is False
    assert lock.has_p() is False
    assert lock.has_action() is False
    assert str(lock) == "PDSignatureLock(<empty>)"


def test_signature_lock_malformed_fields_and_permission_variants() -> None:
    lock = PDSignatureLock()
    lock.get_cos_object().set_item(
        "Fields",
        COSArray([COSString("field"), COSName.get_pdf_name("WrongType")]),
    )
    assert lock.get_fields() is None

    lock.set_action(PDSignatureLock.ACTION_EXCLUDE)
    lock.set_p(PDSignatureLock.P_NO_CHANGES)
    assert lock.is_lock_exclude() is True
    assert lock.is_no_changes() is True

    lock.set_action(PDSignatureLock.ACTION_ALL)
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS)
    assert lock.is_lock_all() is True
    assert lock.is_allow_form_fill_and_annotations() is True


def test_prop_build_app_round_trip_and_removal() -> None:
    prop_build = PDPropBuild()
    app = PDPropBuildDataDict()
    app.set_name("Viewer")

    prop_build.set_pd_prop_build_app(app)

    assert prop_build.get_cos_object().is_direct() is True
    assert prop_build.has_app() is True
    assert prop_build.get_app().get_name() == "Viewer"
    assert str(prop_build) == "PDPropBuild(App)"

    prop_build.set_pd_prop_build_app(None)

    assert prop_build.has_app() is False
    assert prop_build.get_app() is None
    assert str(prop_build) == "PDPropBuild(<empty>)"


def test_pkcs7_signature_default_hash_and_additional_certificate(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    class FakeHashes:
        class SHA256:
            pass

    class FakeSerialization:
        class Encoding:
            DER = object()

    class FakePkcs7:
        class PKCS7Options:
            DetachedSignature = object()
            Binary = object()

        class PKCS7SignatureBuilder:
            def set_data(self, data: bytes) -> FakePkcs7.PKCS7SignatureBuilder:
                calls["data"] = data
                return self

            def add_signer(
                self,
                certificate: object,
                private_key: object,
                hash_algorithm: object,
            ) -> FakePkcs7.PKCS7SignatureBuilder:
                calls["signer"] = (certificate, private_key, hash_algorithm)
                return self

            def add_certificate(
                self,
                certificate: object,
            ) -> FakePkcs7.PKCS7SignatureBuilder:
                calls.setdefault("extra", []).append(certificate)
                return self

            def sign(self, encoding: object, options: list[object]) -> bytes:
                calls["encoding"] = encoding
                calls["options"] = options
                return b"signed"

    monkeypatch.setattr(
        pkcs7_signature,
        "_import_cryptography",
        lambda: (FakeHashes, FakeSerialization, FakePkcs7),
    )

    certificate = object()
    extra_certificate = object()
    signer = Pkcs7Signature(
        certificate,
        object(),
        additional_certificates=[extra_certificate],
    )

    assert signer.certificate is certificate
    assert signer.sign(io.BytesIO(b"content")) == b"signed"
    assert calls["data"] == b"content"
    assert isinstance(calls["signer"][2], FakeHashes.SHA256)
    assert calls["extra"] == [extra_certificate]
