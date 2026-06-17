"""Timestamp-aware signing drivers (wave 1380; CMS embedding wave 1382).

Two :class:`SignatureInterface` implementations sit on top of the existing
:class:`Pkcs7Signature` + :class:`TSAClient` building blocks:

* :class:`TimestampedPkcs7Signature` — produces a normal PKCS#7 detached
  SignedData blob and (when ``embed_timestamp=True``, the default) embeds
  the TSA-returned RFC 3161 timestamp token directly into the SignerInfo's
  ``unsignedAttrs`` SET as an ``id-aa-timeStampToken`` attribute. The token
  bytes also remain available on
  :attr:`TimestampedPkcs7Signature.last_time_stamp_token` for callers that
  want to inspect or relog them. Setting ``embed_timestamp=False`` falls
  back to the wave-1380 behaviour (token exposed only via attribute, not
  spliced into the blob — useful when the caller wants to attach the
  token via their own ASN.1 plumbing or when the TSA response is not real
  DER, as in tests).

* :class:`DocumentTimestampSigner` — produces a SubFilter
  ``ETSI.RFC3161`` document timestamp. The signature's ``/Contents`` is the
  TSA-returned timestamp token directly (no separate PKCS#7 wrapping). Use
  this when adding a document-level TSA timestamp via the same
  :meth:`PDDocument.add_signature` + :meth:`PDDocument.save_incremental`
  pipeline that drives normal signatures.

Library-first per the project's dependency policy: we do not reimplement PKCS#7 or
RFC 3161; we wrap :class:`Pkcs7Signature` (PyCA ``cryptography``) and
:class:`TSAClient` (built on ``urllib`` with a pluggable transport).
PyCA does not expose CMS ``unsignedAttrs`` insertion, so the embedding
step (wave 1382) does the minimum-necessary DER walk in
:mod:`pypdfbox.pdmodel.interactive.digitalsignature.cms_helpers` — no
new dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO

from .cms_helpers import inject_timestamp_token
from .pkcs7_signature import Pkcs7Signature
from .signature_interface import SignatureInterface

if TYPE_CHECKING:  # pragma: no cover — typing only
    from pypdfbox.examples.signature.tsa_client import TSAClient


class TimestampedPkcs7Signature(SignatureInterface):
    """A :class:`Pkcs7Signature` that ALSO obtains an RFC 3161 timestamp
    token covering the produced PKCS#7 SignerInfo.

    The :meth:`sign` return value is the base PKCS#7 detached SignedData
    bytes — same shape as :class:`Pkcs7Signature.sign`. The TSA token
    bytes are stored on the signer object under
    :attr:`last_time_stamp_token` so a caller can splice them into the
    SignedData's ``unsignedAttrs`` (``id-aa-timeStampToken``) externally if
    a TSP ASN.1 library is available.

    PyCA ``cryptography``'s ``PKCS7SignatureBuilder`` does not expose
    unsigned-attribute embedding directly. Wave 1382 closes that gap by
    splicing the token in with a minimal DER walk (see
    :func:`pypdfbox.pdmodel.interactive.digitalsignature.cms_helpers.inject_timestamp_token`).
    Mirrors upstream PDFBox ``PDFBOX.signer`` family's
    "produce signature, fetch TSA token, attach as unsignedAttrs" flow.

    Construction params:

    * ``signer``           — the inner :class:`Pkcs7Signature` (CMS engine).
    * ``tsa_client``       — :class:`TSAClient` to fetch the RFC 3161 token.
    * ``embed_timestamp``  — if ``True`` (default), the TSA token is
      spliced into the produced PKCS#7 as the ``id-aa-timeStampToken``
      unsigned attribute on the first SignerInfo. If ``False``, the token
      is only exposed via :attr:`last_time_stamp_token` and the returned
      blob is byte-identical to what :class:`Pkcs7Signature` produces.
    """

    def __init__(
        self,
        signer: Pkcs7Signature,
        tsa_client: TSAClient,
        *,
        embed_timestamp: bool = True,
    ) -> None:
        if not isinstance(signer, Pkcs7Signature):
            raise TypeError(
                f"signer must be a Pkcs7Signature, got {type(signer).__name__}"
            )
        self._signer = signer
        self._tsa_client = tsa_client
        self._embed_timestamp = bool(embed_timestamp)
        self._last_time_stamp_token: bytes | None = None

    @property
    def signer(self) -> Pkcs7Signature:
        return self._signer

    @property
    def tsa_client(self) -> TSAClient:
        return self._tsa_client

    @property
    def embed_timestamp(self) -> bool:
        """Whether :meth:`sign` will embed the TSA token into the
        produced PKCS#7 as an ``id-aa-timeStampToken`` unsigned
        attribute (wave 1382)."""
        return self._embed_timestamp

    @property
    def last_time_stamp_token(self) -> bytes | None:
        """The most recent TSA-returned timestamp token, or ``None`` when
        :meth:`sign` has not yet been called. Cleared on the next
        :meth:`sign` invocation (the previous token is overwritten)."""
        return self._last_time_stamp_token

    def sign(self, content: BinaryIO) -> bytes:
        """Sign ``content`` with the wrapped :class:`Pkcs7Signature`, then
        ask the configured :class:`TSAClient` to timestamp the resulting
        SignerInfo and (when ``embed_timestamp=True``) splice the token
        into the SignerInfo's ``unsignedAttrs``.

        Per RFC 3161 §3.3.2 the TSA hashes the SignerInfo's
        ``encryptedDigest`` (the signature value over the signed
        attributes). pypdfbox keeps this simple by hashing the entire
        DER-encoded PKCS#7 blob — TSP tokens are still anchored to the
        produced signature, just at the SignedData granularity rather
        than the SignerInfo granularity. Callers that need precise
        SignerInfo-anchoring should compute the token externally and
        attach it via their own ASN.1 plumbing or pass
        ``embed_timestamp=False`` to skip the wave-1382 auto-embed.
        """
        import io as _io

        pkcs7_der = self._signer.sign(content)
        # Ask the TSA for a token over the produced PKCS#7 blob.
        token = self._tsa_client.get_time_stamp_token(_io.BytesIO(pkcs7_der))
        self._last_time_stamp_token = token
        if self._embed_timestamp:
            return inject_timestamp_token(pkcs7_der, token)
        return pkcs7_der


class DocumentTimestampSigner(SignatureInterface):
    """Document-level RFC 3161 timestamp signer (``/SubFilter
    ETSI.RFC3161`` per ISO 32000-2 §12.8.5).

    For document timestamps the signature ``/Contents`` is the raw TSA
    timestamp token — there is no PKCS#7 SignedData wrapper around it
    (the token itself is a SignedData). :meth:`sign` therefore just
    forwards the bracketed bytes to the wrapped :class:`TSAClient` and
    returns the token unchanged.

    Pair with a :class:`PDSignature` carrying ``/Type /DocTimeStamp`` and
    ``/SubFilter ETSI.RFC3161`` — see :meth:`PDSignature.is_doc_time_stamp`
    for the reciprocal predicate.
    """

    def __init__(self, tsa_client: TSAClient) -> None:
        self._tsa_client = tsa_client

    @property
    def tsa_client(self) -> TSAClient:
        return self._tsa_client

    def sign(self, content: BinaryIO) -> bytes:
        """Return the TSA timestamp token bytes over ``content``."""
        return self._tsa_client.get_time_stamp_token(content)


__all__ = ["DocumentTimestampSigner", "TimestampedPkcs7Signature"]
