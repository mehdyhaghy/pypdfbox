# pypdfbox documentation

`pypdfbox` is a Python-native port of
[Apache PDFBox](https://pdfbox.apache.org/) 3.0.x. It exposes the same
class names, package layout, and method semantics PDFBox developers
already know, with Java `camelCase` translated to Python `snake_case`.
For the project overview, status, license, and known limitations, see
the repository [`README.md`](../README.md).

This `docs/` tree is the longer-form user guide. The pages below
break down by audience:

## For users

- [Install guide](install.md) — PyPI install, the `pypdfbox[cjk]`
  extra, source install via `uv`, supported Python versions, the
  platform-support matrix, native-dep build notes, and
  troubleshooting for the common `cryptography` / `skia-python` /
  `imagecodecs` install failures.

- [Support](support.md) — where to ask which kind of question (this
  project's GitHub issue tracker for pypdfbox-specific bugs; the
  upstream Apache PDFBox project for general PDF / PDFBox design
  questions).

- User guides:
  - [Rendering](guides/rendering.md) — `PDFRenderer` usage,
    DPI / scaling, page-image extraction, soft-mask + blend-mode
    notes, structural-parity caveat vs Java AWT.
  - [Text extraction](guides/text-extraction.md) —
    `PDFTextStripper` and `PDFTextStripperByArea`, sorting,
    region masks, ToUnicode handling, the documented bidi
    divergence.
  - [Editing](guides/editing.md) — page-tree manipulation,
    incremental save, xref preservation, no-reflow text editing.
  - [Forms](guides/forms.md) — AcroForm, field types, choice /
    text / checkbox / signature, flattening.
  - [Signatures](guides/signatures.md) — PDSignature, PKCS#7,
    RFC 3161 timestamps, PAdES-LTV `/DSS`+`/VRI` bundling,
    external signing.
  - [Tagged PDF and accessibility](guides/tagged-pdf.md) —
    `PDStructureTreeRoot`, MCID, role map, attribute objects.
  - [Fonts](guides/fonts.md) — Standard 14 substitution, the
    bundled Liberation TTFs, opt-in Noto Sans CJK auto-download,
    Type0 / CID, embedded subsets.
  - [CLI tools](guides/cli.md) — `pypdfbox info|merge|split|
    decrypt|version|texttopdf|overlay|extract`.

## For developers

- [Build guide](build.md) — clone, `uv sync`, the pytest /
  ruff / license-allow-list pre-push hook, coverage refresh
  workflow, provenance protocol.

- [Contributing](../CONTRIBUTING.md) — class-cluster scoping, the
  two-layer test rule (hand-written + ported-upstream),
  `PROVENANCE.md` row format, and the `CHANGES.md` bookkeeping.

- [API reference](api/index.md) — module-by-module surface,
  generated from in-source docstrings. Useful when you want to
  confirm the snake_case spelling of a specific upstream
  method.

## Migration

- [Migrating from Apache PDFBox (Java)](migration-from-pdfbox.md) —
  side-by-side examples, the `camelCase` → `snake_case` cheat
  sheet, behavioural-divergence callouts, the `preflight`-
  shaped hole and what to plug into it.

- [Migrating from other Python PDF libraries](migration-from-python-pdfs.md)
  — `pypdf`, `reportlab`, `pdfminer.six`, `pdfplumber` →
  pypdfbox idiom maps.

## Release information

- [Release notes for the current release](../RELEASE_NOTES_v0.9.0rc1.md)
  — what shipped, known issues at release.
- [`CHANGES.md`](../CHANGES.md) — substantive deviations from
  upstream, organised under "Project-wide deviations" and
  "Active divergences".
- [Issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues) —
  open in-flight gaps that are fixable but not yet closed.
- [`PROVENANCE.md`](../PROVENANCE.md) — one row per ported source
  / test / fixture file, recording the upstream PDFBox version
  and Java path.

## Reading order recommendation

If you are new to pypdfbox and arrived from PDFBox:
[`install.md`](install.md) →
[`migration-from-pdfbox.md`](migration-from-pdfbox.md) →
whichever user guide matches your task.

If you are new to pypdfbox and arrived from another Python PDF
library: [`install.md`](install.md) →
[`migration-from-python-pdfs.md`](migration-from-python-pdfs.md) →
the user guide for your task.

If you intend to contribute: [`build.md`](build.md) →
[`contributing.md`](../CONTRIBUTING.md) (the contribution guide
covers the package layout, the parity rules, the
dependency-ordered implementation, and the test porting
conventions).
