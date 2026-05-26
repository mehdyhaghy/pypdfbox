from __future__ import annotations


class DecryptionMaterial:
    """This class represents data required to decrypt PDF documents.

    Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.encryption.DecryptionMaterial``.

    This can be a password for standard security
    (``StandardDecryptionMaterial``) or an X.509 certificate with a private
    key for public-key security (``PublicKeyDecryptionMaterial``). Upstream
    declares no members of its own — it is an empty abstract base shared by
    the two concrete subclasses.
    """


__all__ = ["DecryptionMaterial"]
