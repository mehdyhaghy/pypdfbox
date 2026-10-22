from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .access_permission import AccessPermission
    from .decryption_material import DecryptionMaterial
    from .invalid_password_exception import InvalidPasswordException
    from .message_digests import MessageDigests
    from .pd_crypt_filter_dictionary import PDCryptFilterDictionary
    from .pd_encryption import PDEncryption
    from .protection_policy import ProtectionPolicy
    from .public_key_decryption_material import PublicKeyDecryptionMaterial
    from .public_key_protection_policy import PublicKeyProtectionPolicy
    from .public_key_recipient import PublicKeyRecipient
    from .public_key_security_handler import PublicKeySecurityHandler
    from .rc4_cipher import RC4Cipher
    from .sasl_prep import SaslPrep
    from .security_handler import SecurityHandler
    from .security_handler_factory import SecurityHandlerFactory
    from .security_provider import (
        SecurityProvider,
        get_security_handler,
        is_registered,
        register_security_handler,
    )
    from .standard_protection_policy import StandardProtectionPolicy
    from .standard_security_handler import (
        StandardDecryptionMaterial,
        StandardSecurityHandler,
    )

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AccessPermission": ".access_permission",
        "DecryptionMaterial": ".decryption_material",
        "InvalidPasswordException": ".invalid_password_exception",
        "MessageDigests": ".message_digests",
        "PDCryptFilterDictionary": ".pd_crypt_filter_dictionary",
        "PDEncryption": ".pd_encryption",
        "ProtectionPolicy": ".protection_policy",
        "PublicKeyDecryptionMaterial": ".public_key_decryption_material",
        "PublicKeyProtectionPolicy": ".public_key_protection_policy",
        "PublicKeyRecipient": ".public_key_recipient",
        "PublicKeySecurityHandler": ".public_key_security_handler",
        "RC4Cipher": ".rc4_cipher",
        "SaslPrep": ".sasl_prep",
        "SecurityHandler": ".security_handler",
        "SecurityHandlerFactory": ".security_handler_factory",
        "SecurityProvider": ".security_provider",
        "get_security_handler": ".security_provider",
        "is_registered": ".security_provider",
        "register_security_handler": ".security_provider",
        "StandardProtectionPolicy": ".standard_protection_policy",
        "StandardDecryptionMaterial": ".standard_security_handler",
        "StandardSecurityHandler": ".standard_security_handler",
    },
)

__all__ = [
    "AccessPermission",
    "DecryptionMaterial",
    "InvalidPasswordException",
    "MessageDigests",
    "PDCryptFilterDictionary",
    "PDEncryption",
    "ProtectionPolicy",
    "PublicKeyDecryptionMaterial",
    "PublicKeyProtectionPolicy",
    "PublicKeyRecipient",
    "PublicKeySecurityHandler",
    "RC4Cipher",
    "SaslPrep",
    "SecurityHandler",
    "SecurityHandlerFactory",
    "SecurityProvider",
    "StandardDecryptionMaterial",
    "StandardProtectionPolicy",
    "StandardSecurityHandler",
    "get_security_handler",
    "is_registered",
    "register_security_handler",
]
