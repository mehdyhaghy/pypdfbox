# Digital signing

Pypdfbox ports
[`pypdfbox.pdmodel.interactive.digitalsignature`](../api/pdmodel.md)
on top of [PyCA `cryptography`](https://cryptography.io/). The
signature surface covers PKCS#7 detached signing, PAdES with
RFC 3161 timestamps, public-key encryption recipients, and
document-level timestamps (`/DocTimeStamp`).

## Verify an existing signature

```python
from cryptography import x509
from pathlib import Path
from pypdfbox.pdmodel import PDDocument

pdf_bytes = Path("signed.pdf").read_bytes()
with PDDocument.load(pdf_bytes) as doc:
    sig_fields = doc.get_signature_fields()
    for field in sig_fields:
        signature = field.get_value()
        if signature is None:
            continue
        result = signature.verify(pdf_bytes)
        print(field.get_partial_name(), "valid:", result.is_valid)
        for err in result.errors:
            print(" ", err)
```

`verify` performs the digest check over `/ByteRange`, then extracts
the signer certificate and validates the SignedData signed-attrs
math. Pass `trust_roots=[...]` (a list of
`cryptography.x509.Certificate`) to also walk the issuer chain up to
an anchor:

```python
roots = [x509.load_pem_x509_certificate(Path("root.pem").read_bytes())]
result = signature.verify(pdf_bytes, trust_roots=roots)
```

`SignatureValidationResult.is_valid` is True only when every
available check passed.

## Sign a document with a self-signed cert

```python
import datetime as dt
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.interactive.digitalsignature.pkcs7_signature import Pkcs7Signature

# A real-world key + cert come from a CA-issued PKCS#12 — see
# examples/signature/create_signature.py. Here we assume `cert`, `key`
# already exist (PyCA `cryptography` X.509 + RSAPrivateKey).
signer = Pkcs7Signature(cert, key)

with PDDocument.load("input.pdf") as doc:
    signature = PDSignature()
    signature.set_filter("Adobe.PPKLite")
    signature.set_sub_filter("adbe.pkcs7.detached")
    signature.set_name("Ada Lovelace")
    signature.set_location("London")
    signature.set_reason("I approve this document")
    signature.set_sign_date(dt.datetime.now(dt.timezone.utc))

    doc.add_signature(signature, signer)
    with open("signed.pdf", "wb") as out:
        doc.save_incremental(out)
```

`doc.add_signature` reserves a `/Contents` placeholder; the
incremental save streams the bracketed bytes through `signer.sign()`
and patches the result into the placeholder.

## PAdES with a timestamp

`TimestampedPkcs7Signature` wraps a `Pkcs7Signature` and asks an
RFC 3161 TSA to sign the produced SignerInfo. The token is spliced
into the SignedData as an `id-aa-timeStampToken` unsigned attribute
by default. The base SignedData and the timestamp are
hence inseparable on the wire — `verify` callers see a single blob
that carries both proofs.

```python
import hashlib
from pypdfbox.examples.signature.tsa_client import TSAClient
from pypdfbox.pdmodel.interactive.digitalsignature.timestamped_signature import (
    TimestampedPkcs7Signature,
)

tsa = TSAClient(
    url="https://freetsa.org/tsr",
    username=None,
    password=None,
    digest=hashlib.sha256(),
)
signer = TimestampedPkcs7Signature(Pkcs7Signature(cert, key), tsa)
```

Use `signer` exactly like a plain `Pkcs7Signature` — the
`TimestampedPkcs7Signature.sign` path produces the augmented blob
unchanged. The most recent TSA token is also exposed on
`signer.last_time_stamp_token` for callers that want to log or
audit it.

Set `embed_timestamp=False` if you would rather attach the token via
your own ASN.1 plumbing.

## LTV via /DSS + /VRI

For long-term validation, bundle the validation evidence (certs,
CRLs, OCSPs) into the document-wide `/DSS` store and link them to
the signature via a `/VRI` entry:

```python
from pypdfbox.pdmodel.interactive.digitalsignature.pd_document_security_store import (
    PDDocumentSecurityStore,
)

with PDDocument.load("signed.pdf") as doc:
    dss = PDDocumentSecurityStore.ensure_on(doc)
    info = dss.bundle(
        certs=[ca_der, intermediate_der],
        crls=[crl_der],
        ocsps=[ocsp_der],
        signature=signature,
    )
    with open("ltv.pdf", "wb") as out:
        doc.save_incremental(out)
```

`bundle` appends the byte blobs to the document-wide pools and
writes a `/VRI` entry keyed by the upper-case hex SHA-1 of the
signature's `/Contents` (the upstream-prescribed key form per
PDF 32000-2 §12.8.4.2).

## Seed value constraints

`PDSeedValue` mirrors the `/SV` entry on a signature field. Fill
constraints in the field-author flow; consult them in the signer:

```python
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value import PDSeedValue

sig_field = acro_form.get_field("ApplicantSignature")
sv = PDSeedValue()
sv.set_sub_filter(["adbe.pkcs7.detached"])
sv.set_digest_method(["SHA256"])
sv.set_reasons(["Approval", "Review"])
sv.set_filter_required(True)
sig_field.set_seed_value(sv)
```

When you set `is_filter_required(True)` (etc.) the upstream contract
requires the signer to honour the constraint. Pypdfbox enforces the
flags it can validate at sign time — others surface as warnings.

## Public-key encryption recipients

`PublicKeyRecipient` groups a certificate with an `AccessPermission`
mask. Multiple recipients with the same permissions share an
envelope.

```python
from pypdfbox.pdmodel.encryption import (
    AccessPermission,
    PublicKeyProtectionPolicy,
    PublicKeyRecipient,
)

alice = PublicKeyRecipient()
alice.set_x509(alice_cert)
alice.set_permission(AccessPermission())          # full access

bob = PublicKeyRecipient()
bob.set_x509(bob_cert)
ro = AccessPermission()
ro.set_can_modify(False)
bob.set_permission(ro)                            # read-only

policy = PublicKeyProtectionPolicy()
policy.add_recipient(alice)
policy.add_recipient(bob)
doc.protect(policy)
```

Pypdfbox groups recipients by permission mask before writing the
recipients array, so Alice and Bob land in separate envelopes.

## Document timestamp (`/DocTimeStamp`)

`DocumentTimestampSigner` produces a `SubFilter ETSI.RFC3161`
signature whose `/Contents` is the TSA token directly (no PKCS#7
wrapper). Use it to anchor an LTV chain in time:

```python
from pypdfbox.pdmodel.interactive.digitalsignature.timestamped_signature import (
    DocumentTimestampSigner,
)

doc_ts = DocumentTimestampSigner(tsa)
with PDDocument.load("ltv.pdf") as doc:
    sig = PDSignature()
    sig.set_type("DocTimeStamp")
    sig.set_filter("Adobe.PPKLite")
    sig.set_sub_filter("ETSI.RFC3161")
    doc.add_signature(sig, doc_ts)
    with open("ltv-ts.pdf", "wb") as out:
        doc.save_incremental(out)
```

`PDSignature.is_doc_time_stamp()` is the reciprocal predicate when
reading back.

## See also

- [Examples: `pypdfbox/examples/signature/`](https://github.com/Mehdy-haghy/pypdfbox/tree/main/pypdfbox/examples/signature)
- [API reference: `pypdfbox.pdmodel`](../api/pdmodel.md)
- [Forms guide](forms.md) for `PDSignatureField` usage
- [Documentation index](../index.md)
