from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .cos_filter_input_stream import COSFilterInputStream
    from .pd_document_security_store import (
        PDDocumentSecurityStore,
        PDValidationInformation,
    )
    from .pd_prop_build import PDPropBuild
    from .pd_prop_build_data_dict import PDPropBuildDataDict
    from .pd_seed_value import PDSeedValue
    from .pd_seed_value_certificate import PDSeedValueCertificate
    from .pd_seed_value_mdp import PDSeedValueMDP
    from .pd_seed_value_time_stamp import PDSeedValueTimeStamp
    from .pd_signature import PDSignature
    from .pd_signature_lock import PDSignatureLock
    from .pkcs7_signature import Pkcs7Signature
    from .sig_utils import (
        check_certificate_usage,
        check_responder_certificate_usage,
        check_time_stamp_certificate_usage,
        compute_byte_range,
        compute_signed_digest,
        extract_pkcs7_message_digest,
        get_last_relevant_signature,
        get_mdp_permission,
        set_mdp_permission,
        strip_signature_padding,
    )
    from .signature_interface import SignatureInterface
    from .signature_options import (
        DEFAULT_SIGNATURE_SIZE,
        SignatureOptions,
    )
    from .signature_validation_result import SignatureValidationResult
    from .signing_support import SigningSupport
    from .timestamped_signature import (
        DocumentTimestampSigner,
        TimestampedPkcs7Signature,
    )

__getattr__, __dir__ = _attach(
    __name__,
    {
        "COSFilterInputStream": ".cos_filter_input_stream",
        "PDDocumentSecurityStore": ".pd_document_security_store",
        "PDValidationInformation": ".pd_document_security_store",
        "PDPropBuild": ".pd_prop_build",
        "PDPropBuildDataDict": ".pd_prop_build_data_dict",
        "PDSeedValue": ".pd_seed_value",
        "PDSeedValueCertificate": ".pd_seed_value_certificate",
        "PDSeedValueMDP": ".pd_seed_value_mdp",
        "PDSeedValueTimeStamp": ".pd_seed_value_time_stamp",
        "PDSignature": ".pd_signature",
        "PDSignatureLock": ".pd_signature_lock",
        "Pkcs7Signature": ".pkcs7_signature",
        "check_certificate_usage": ".sig_utils",
        "check_responder_certificate_usage": ".sig_utils",
        "check_time_stamp_certificate_usage": ".sig_utils",
        "compute_byte_range": ".sig_utils",
        "compute_signed_digest": ".sig_utils",
        "extract_pkcs7_message_digest": ".sig_utils",
        "get_last_relevant_signature": ".sig_utils",
        "get_mdp_permission": ".sig_utils",
        "set_mdp_permission": ".sig_utils",
        "strip_signature_padding": ".sig_utils",
        "SignatureInterface": ".signature_interface",
        "DEFAULT_SIGNATURE_SIZE": ".signature_options",
        "SignatureOptions": ".signature_options",
        "SignatureValidationResult": ".signature_validation_result",
        "SigningSupport": ".signing_support",
        "DocumentTimestampSigner": ".timestamped_signature",
        "TimestampedPkcs7Signature": ".timestamped_signature",
    },
)

__all__ = [
    "COSFilterInputStream",
    "DEFAULT_SIGNATURE_SIZE",
    "DocumentTimestampSigner",
    "PDDocumentSecurityStore",
    "PDPropBuild",
    "PDPropBuildDataDict",
    "PDSeedValue",
    "PDSeedValueCertificate",
    "PDSeedValueMDP",
    "PDSeedValueTimeStamp",
    "PDSignature",
    "PDSignatureLock",
    "PDValidationInformation",
    "Pkcs7Signature",
    "SignatureInterface",
    "SignatureOptions",
    "SignatureValidationResult",
    "SigningSupport",
    "TimestampedPkcs7Signature",
    "check_certificate_usage",
    "check_responder_certificate_usage",
    "check_time_stamp_certificate_usage",
    "compute_byte_range",
    "compute_signed_digest",
    "extract_pkcs7_message_digest",
    "get_last_relevant_signature",
    "get_mdp_permission",
    "set_mdp_permission",
    "strip_signature_padding",
]
