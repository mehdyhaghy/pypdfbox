# pypdfbox documentation

`pypdfbox` is a pure-Python PDF library and command-line toolbox:
read, write, and edit PDFs — split, merge, extract text and images,
render pages, fill forms, sign, encrypt — with no JVM and no external
binaries. It is a Python-native port of
[Apache PDFBox](https://pdfbox.apache.org/) 3.0.x, so the classes and
behavior match the PDFBox API you may already know, with Java
`camelCase` translated to Python `snake_case`.

New here? Start with the repository [`README.md`](../README.md) — it
has the install one-liner, the ten most common command-line
operations, and a Python quick start.

## Getting started

- [Install guide](install.md) — `pip install pypdfbox`, supported
  Python versions and platforms, the optional `pypdfbox[cjk]` extra,
  source installs, and troubleshooting for the common
  `cryptography` / `skia-python` / `imagecodecs` install failures.

- [Command-line tools](guides/cli.md) — the `pypdfbox` command:
  `split`, `merge`, `extracttext`, `info`, `encrypt`, `decrypt`,
  `imagetopdf`, `texttopdf`, `listbookmarks`, `pdfdebugger`, and
  friends, with all options.

## Guides by task

- [Text extraction](guides/text-extraction.md) —
  `PDFTextStripper` and `PDFTextStripperByArea`, positional
  sorting, region masks, ToUnicode handling, and the documented
  bidi divergence.
- [Merging and splitting](guides/merging-splitting.md) —
  `PDFMergerUtility` and `Splitter`, what carries over (forms,
  bookmarks, links), and page-range extraction.
- [Rendering](guides/rendering.md) — `PDFRenderer` usage,
  DPI / scaling, page-image extraction, soft-mask + blend-mode
  notes.
- [Forms](guides/forms.md) — AcroForm, field types (text,
  checkbox, choice, signature), filling and flattening.
- [Encryption](guides/encryption.md) — password protection,
  permissions, AES/RC4 handlers, opening encrypted documents.
- [Digital signatures](guides/signing.md) — PDSignature, PKCS#7,
  RFC 3161 timestamps, PAdES-LTV `/DSS`+`/VRI` bundling, external
  signing.
- [Tagged PDF and accessibility](guides/tagged-pdf.md) —
  `PDStructureTreeRoot`, MCID, role map, attribute objects.
- [Embedded files and attachments](guides/embedded-files.md) —
  the `/Names` embedded-file tree, attaching and extracting files.

## Coming from another library

- [Migration guide](migration.md) — side-by-side examples for
  developers arriving from Apache PDFBox (Java) — including the
  `camelCase` → `snake_case` cheat sheet — and idiom maps from
  `pypdf`, `reportlab`, `pdfminer.six`, and `pdfplumber`.

## Help and support

- [Support](support.md) — where to ask which kind of question:
  the [issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues)
  for pypdfbox bugs; upstream PDFBox resources for general PDF /
  API design questions (answers usually translate directly).
- [`README.md` → Known limitations](../README.md#known-limitations-and-problems)
  — the stable-state divergences (Symbol glyph coverage, bidi,
  pixel-exact rendering, PDF/A validation scope).

## Reference

- [API reference](api/index.md) — module-by-module surface,
  generated from in-source docstrings. Useful to confirm the
  snake_case spelling of a specific upstream method.
- [Changelog index](changelog.md) — release notes and the log of
  deliberate behavioral deviations from upstream
  ([`CHANGES.md`](../CHANGES.md)).
- [Export control](export-control.md) — cryptographic functionality
  notice (encryption + signing surfaces, upstream ECCN
  classification, PyCA `cryptography`).

## For contributors

- [Build guide](build.md) — clone, `uv sync`, running the tests,
  lint and the pre-push checks.
- [Contributing](../CONTRIBUTING.md) — contribution rules: match
  upstream PDFBox naming and behavior, the two-layer test rule,
  and the [`PROVENANCE.md`](../PROVENANCE.md) /
  [`CHANGES.md`](../CHANGES.md) bookkeeping.
