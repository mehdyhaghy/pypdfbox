<p align="center">
  <img src="https://raw.githubusercontent.com/mehdyhaghy/pypdfbox/main/docs/assets/pypdfbox-logo.png"
       alt="pypdfbox" width="128" height="128">
</p>

# pypdfbox

[![PyPI](https://img.shields.io/pypi/v/pypdfbox)](https://pypi.org/project/pypdfbox/)
[![Downloads](https://img.shields.io/pypi/dm/pypdfbox)](https://pypistats.org/packages/pypdfbox)
[![License](https://img.shields.io/pypi/l/pypdfbox)](https://github.com/mehdyhaghy/pypdfbox/blob/main/LICENSE)

A pure-Python PDF library and command-line toolbox: split, merge,
extract text and images, render pages, fill forms, sign and verify,
encrypt and decrypt, create tagged/accessible PDFs. No JVM, no
external binaries, Apache-2.0 throughout.

It is a Python-native port of [Apache PDFBox](https://pdfbox.apache.org/)
3.0.x — same class names, same object model, same behaviour, with Java
`camelCase` mapped to `snake_case`. PDFBox answers usually translate
directly. This is a community port, not an official Apache release.

- **One library for the whole job** — parse, edit, render, sign,
  extract, create. Not four partial ones.
- **Permissive end to end, enforced.** Every runtime dependency is
  Apache/MIT/BSD-family. Copyleft is blocked by two automated gates: a
  dependency allow-list, and a scan that reads the bytes of compiled
  wheels to catch statically linked copyleft that package metadata
  hides. Safe to embed in closed-source products.
- **No environment friction.** `pip install pypdfbox` — pure Python
  plus wheels. Same behaviour in a container, a CI runner, or a sandbox.

## Install

```sh
pip install pypdfbox
```

Command line only? Install it as an isolated tool instead:

```sh
uv tool install pypdfbox    # or: pipx install pypdfbox
```

Requires CPython 3.14+. Wheels cover macOS (x86_64 + arm64),
Linux/glibc (x86_64 + aarch64), and Windows (x86_64).

## Quick start

```python
from pypdfbox import PDDocument
from pypdfbox.text import PDFTextStripper

with PDDocument.load("input.pdf") as doc:
    print(f"{doc.get_number_of_pages()} pages")
    text = PDFTextStripper().get_text(doc)

    doc.get_document_information().set_title("Annual Report")
    doc.save("output.pdf")
```

## Command line

Installing the package puts a `pypdfbox` command on your `PATH`. Use
`pypdfbox <command> --help` for all options.

| Command | Does |
|---|---|
| `pypdfbox split -i in.pdf` | one file per page (`-split N` for N-page chunks) |
| `pypdfbox merge -i a.pdf b.pdf -o out.pdf` | concatenate, carrying bookmarks, forms and links |
| `pypdfbox extracttext -i in.pdf` | text to `in.txt` (`-console`, `-html`, `-md`, `-sort`) |
| `pypdfbox info in.pdf` | pages, version, encryption, metadata (`-output json`) |
| `pypdfbox encrypt -i in.pdf -o out.pdf -O pass` | password-protect (`-can*` flags tune permissions) |
| `pypdfbox decrypt -i in.pdf -o out.pdf -password pass` | remove protection |
| `pypdfbox imagetopdf -i a.png b.png -o out.pdf` | one page per image |
| `pypdfbox texttopdf -i notes.txt -o out.pdf` | plain text in, paginated PDF out |
| `python -m pypdfbox.tools.pdf_to_image -i in.pdf -dpi 150` | pages to images |
| `python -m pypdfbox.tools.extract_images -i in.pdf` | pull out embedded images |

Also: `listbookmarks`, `pdfdebugger` (interactive structure viewer),
`writedecodedstream`, `version`. Full reference:
[CLI guide](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/guides/cli.md).

## Documentation

- [Compatibility matrix](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/compatibility.md)
  — what's supported, and the PDFBox → pypdfbox API mapping
- [Known limitations](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/limitations.md)
  — divergences and gaps worth knowing before you adopt
- [Migration guide](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/migration.md)
  — from Java PDFBox, `pypdf`, `pdfminer.six` or `reportlab`
- [Guides](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/guides/)
  — text extraction, merging, rendering, forms, encryption, signing,
  tagged PDF, embedded files
- [Install notes](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/install.md)
  · [Changes](https://github.com/mehdyhaghy/pypdfbox/blob/main/CHANGES.md)
  · [Examples](https://github.com/mehdyhaghy/pypdfbox/tree/main/pypdfbox/examples/)

## Support

File bugs and feature requests on the
[issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues). For a
bug, please attach a minimal PDF that reproduces it.

Because the API mirrors Apache PDFBox, general "how do I do X with
PDFBox" answers usually translate directly. pypdfbox is a community
port — please don't file pypdfbox bugs with the Apache project.

## Contributing

PRs welcome.

```sh
git clone https://github.com/mehdyhaghy/pypdfbox.git
cd pypdfbox
uv sync --all-groups
.venv/bin/pytest -q --no-cov
```

Changes must match upstream PDFBox naming and behaviour. See
[CONTRIBUTING.md](https://github.com/mehdyhaghy/pypdfbox/blob/main/CONTRIBUTING.md)
and the [developer workflow](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/build.md).

## License

Apache License 2.0, same as upstream PDFBox — see
[LICENSE](https://github.com/mehdyhaghy/pypdfbox/blob/main/LICENSE) and
[NOTICE](https://github.com/mehdyhaghy/pypdfbox/blob/main/NOTICE). All
runtime dependencies are permissively licensed.

Ported files are tracked in
[PROVENANCE.md](https://github.com/mehdyhaghy/pypdfbox/blob/main/PROVENANCE.md),
which satisfies Apache 2.0 §4(b) in one place; source files carry no
per-file headers. Behavioural deviations are in
[CHANGES.md](https://github.com/mehdyhaghy/pypdfbox/blob/main/CHANGES.md).

**Export control:** this software contains cryptographic functionality
(PDF encryption and signatures, via PyCA `cryptography`). Your country
may restrict import, possession, use, or re-export — check local law.
[Details](https://github.com/mehdyhaghy/pypdfbox/blob/main/docs/export-control.md).

## Upstream

pypdfbox is a port of [Apache PDFBox](https://pdfbox.apache.org/),
maintained by the Apache Software Foundation. The COS model, parser
architecture, content-stream operators, accessibility model, font
subsystem, signature pipeline, and rendering design it mirrors are the
cumulative work of the PDFBox maintainers and contributors.

This is a community port. It is not endorsed by, affiliated with, or
released by the Apache Software Foundation. Bugs in pypdfbox are bugs
in pypdfbox, not in Apache PDFBox.
