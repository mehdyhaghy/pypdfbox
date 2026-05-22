# Encryption

Pypdfbox ports the standard (password-based) and public-key
security handlers under
[`pypdfbox.pdmodel.encryption`](../api/pdmodel.md). Algorithms
covered: RC4-40 (R2), RC4-128 (R3), AES-128 (R4), AES-256-r5 (R5,
legacy), and AES-256-r6 (R6 / PDF 2.0).

## Decrypt an encrypted PDF

`PDDocument.load` accepts a `password` keyword (or positional second
argument). When the password authenticates the document is
transparently decrypted on read:

```python
from pypdfbox.pdmodel import PDDocument

with PDDocument.load("locked.pdf", "secret") as doc:
    print(doc.get_number_of_pages())
```

To check encryption state without decrypting, load with no password
and inspect `doc.is_encrypted()`. The document's contents stay
encrypted until you supply a working password via `doc.decrypt(...)`.

To strip encryption permanently, decrypt, mark the document as no
longer needing encryption, and save:

```python
with PDDocument.load("locked.pdf", "secret") as doc:
    doc.set_all_security_to_be_removed(True)
    doc.save("unlocked.pdf")
```

This requires the owner password — the user password authenticates
for reading but lacks the right to strip encryption.

## Encrypt with a password

`StandardProtectionPolicy` bundles owner + user passwords and an
`AccessPermission` bitmask. The key-length argument on
`set_encryption_key_length` picks the algorithm:

| Key length | Algorithm | Revision |
|---|---|---|
| 40 | RC4 | R2 |
| 128 | RC4 | R3 |
| 128 | AES | R4 (when `set_preferred_aes(True)`) |
| 256 | AES-256 | R6 (PDF 2.0) |

```python
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import AccessPermission, StandardProtectionPolicy

perms = AccessPermission()
perms.set_can_print(True)
perms.set_can_modify(False)
perms.set_can_extract_content(False)
perms.set_can_modify_annotations(False)

policy = StandardProtectionPolicy(
    owner_password="owner-secret",
    user_password="user-secret",
    permissions=perms,
)
policy.set_encryption_key_length(256)        # AES-256 (R6)

with PDDocument.load("plain.pdf") as doc:
    doc.protect(policy)
    doc.save("locked.pdf")
```

The same flow with `set_encryption_key_length(128)` produces an R3
(RC4-128) document; call `policy.set_preferred_aes(True)` to upgrade
to R4 (AES-128).

## /EncryptMetadata = false

By default the standard handler encrypts every stream — including
the catalog's `/Metadata` XMP packet. PDF 32000-1 §7.6.3.2 allows
producers to leave metadata cleartext so search engines and library
catalogs can index it without the password. Wave 1367 closed a bug
where this flag was advertised in the encryption dictionary but the
metadata stream itself stayed encrypted; both ends now agree.

```python
policy.set_encrypt_metadata(False)
```

The standard handler now skips metadata streams during encryption
and writes `/EncryptMetadata false` into the on-the-wire encryption
dictionary so reader-side key derivation stays consistent.

## Public-key encryption with cert recipients

For non-password protection (recipients identified by X.509
certificate), use `PublicKeyProtectionPolicy`. Wave 1374 added
recipient grouping: when two recipients share the same permission
mask they share an envelope, matching upstream PDFBox.

```python
from pathlib import Path
from cryptography import x509
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.encryption import (
    AccessPermission,
    PublicKeyProtectionPolicy,
    PublicKeyRecipient,
)

alice_cert = x509.load_pem_x509_certificate(Path("alice.pem").read_bytes())
bob_cert = x509.load_pem_x509_certificate(Path("bob.pem").read_bytes())
carol_cert = x509.load_pem_x509_certificate(Path("carol.pem").read_bytes())

full = AccessPermission()
read_only = AccessPermission()
read_only.set_read_only()

alice = PublicKeyRecipient()
alice.set_x509(alice_cert)
alice.set_permission(full)

bob = PublicKeyRecipient()
bob.set_x509(bob_cert)
bob.set_permission(read_only)

carol = PublicKeyRecipient()
carol.set_x509(carol_cert)
carol.set_permission(read_only)

policy = PublicKeyProtectionPolicy()
policy.add_recipient(alice)
policy.add_recipient(bob)
policy.add_recipient(carol)

with PDDocument.load("plain.pdf") as doc:
    doc.protect(policy)
    doc.save("locked-pubkey.pdf")
```

Alice lands in her own envelope; Bob and Carol share an envelope
because they have identical permissions.

To open a public-key encrypted document, load the document with the
matching private key and certificate (typically from a PKCS#12
keystore) — see `pypdfbox decrypt --keyStore ...` in
[the CLI guide](cli.md).

## See also

- [API reference: `pypdfbox.pdmodel`](../api/pdmodel.md)
- [Signing guide](signing.md) for digital signatures vs encryption
- [CLI guide](cli.md) for the `pypdfbox encrypt` / `pypdfbox decrypt` tools
- [Documentation index](../index.md)
