# Export control

This distribution includes cryptographic software. The country in
which you currently reside may have restrictions on the import,
possession, use, and/or re-export to another country of encryption
software. BEFORE using any encryption software, please check your
country's laws, regulations and policies concerning the import,
possession, or use, and re-export of encryption software, to see if
this is permitted. See <https://www.wassenaar.org/> for more
information.

Upstream [Apache PDFBox](https://pdfbox.apache.org/) is classified by
the U.S. Government Department of Commerce, Bureau of Industry and
Security (BIS) as Export Commodity Control Number (ECCN) 5D002.C.1
and is distributed under the License Exception ENC Technology
Software Unrestricted (TSU) exception (BIS Export Administration
Regulations, Section 740.13) — that classification and filing apply
to the Apache Software Foundation's releases. pypdfbox is a
community port providing the same cryptographic surfaces; it
performs its cryptography through the PyCA
[`cryptography`](https://pypi.org/project/cryptography/) library
(Apache-2.0 / BSD), which handles export-compliance for its own
distribution.

The cryptographic surfaces in pypdfbox are:

- PDF Standard Security Handlers (r2–r6: RC4 40/128, AES-128/256
  CBC) and the public-key security handler, implemented in
  `pypdfbox.pdmodel.encryption` on top of `cryptography`.
- Digital signature read + write (PKCS#7 / CAdES / PAdES, RFC 3161
  timestamps, PAdES-LTV `/DSS`+`/VRI` revocation-info bundling),
  implemented in `pypdfbox.pdmodel.interactive.digitalsignature` on
  top of `cryptography`'s PKCS#7 builders.

Upstream PDFBox uses the Java Cryptography Architecture (JCA) and
Bouncy Castle for the same surfaces; pypdfbox uses PyCA
`cryptography`. The functionality is equivalent.
