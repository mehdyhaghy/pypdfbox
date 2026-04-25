# pypdfbox

**Apache 2.0**-licensed, Python-native port of Apache PDFBox-compatible APIs.

> Status: **pre-alpha / Phase 1 in progress.** APIs are not stable.

## What this is

A Python library targeting broad functional parity with Apache PDFBox, including:

- COS object model
- Parsing and malformed-PDF recovery
- Content-stream editing without reflow
- Incremental writing
- Tagged PDF accessibility manipulation
- Forms and annotations
- Font handling, rendering, PDF/A preflight
- Signatures / encryption
- Tools / CLI

This is **not** a Java wrapper. It is a Python-native port of Apache PDFBox, built under the same Apache 2.0 license as the upstream project, with PDFBox API names preserved so existing PDFBox developers can transfer ~85–90% of their mental model directly.

## Compatibility goals

- Package layout mirrors `org.apache.pdfbox.*` → `pypdfbox.*`.
- Class names preserved: `COSDictionary`, `PDDocument`, `PDFParser`, `PDStructureTreeRoot`, `PDFRenderer`, …
- Method names: Java camelCase → Python snake_case; semantics unchanged.
- Inheritance hierarchies preserved.
- Behavioral compatibility (lazy loading, incremental save, xref preservation, object streams) takes priority over Pythonic simplification.

See [`pypdfbox_full_prd_v_1.md`](pypdfbox_full_prd_v_1.md) for the full PRD and [`CLAUDE.md`](CLAUDE.md) for AI-assistant rules.

## Acknowledgements / prior art

pypdfbox is a port of [Apache PDFBox](https://pdfbox.apache.org/) — see [`NOTICE`](NOTICE) for full attribution.
The upstream PDFBox project, maintained by the Apache Software Foundation, established the COS model, parser architecture, content-stream operators, accessibility model, font subsystem, and rendering pipeline that this project deliberately mirrors. We thank the PDFBox maintainers for decades of work on the canonical PDF toolkit.

## Licensing

- **Source: Apache License 2.0** (matches upstream PDFBox; see [`LICENSE`](LICENSE)).
- Required attribution lives in [`NOTICE`](NOTICE) — downstream redistributors must propagate it.
- Dependency policy: **Apache-2.0 / MIT / BSD only**. GPL/LGPL/AGPL/MPL/EPL/CDDL/SSPL/BUSL are forbidden and CI hard-fails on any.
- **No per-file license headers.** Ported files are tracked in [`PROVENANCE.md`](PROVENANCE.md) (file → upstream PDFBox version + Java path), which satisfies Apache 2.0 §4(b) in one centralized place.
- Substantive deviations from upstream behavior are recorded in [`CHANGES.md`](CHANGES.md).

## Implementation status

Phase 1 (read/write core): `io` → `cos` → `pdfparser` → `pdfwriter`.

| Module | Status |
|---|---|
| `io` | ✅ complete (read/write ABCs, BytesIO/file/mmap/view adapters, ScratchFile, MemoryUsageSetting, IOUtils) |
| `cos` | ✅ complete (visitor + leaf primitives + containers + COSObject/Key + COSStream + COSDocument) |
| `pdfparser` | not started |
| `pdfwriter` | not started |

## Development

**Requires Python 3.14+** (chosen so we can use the official no-GIL free-threaded build for parallel parsing/rendering work later).

Package management is [`uv`](https://docs.astral.sh/uv/).

```sh
uv sync               # creates .venv and installs pypdfbox + dev deps (pinned via uv.lock)
uv run pytest         # run the test suite
uv run ruff check .   # lint
uv run mypy pypdfbox  # type-check
```

To add a runtime or dev dependency:

```sh
uv add <pkg>                  # runtime
uv add --group dev <pkg>      # dev
```


## Contributing

PRs require:
- For ported files: an entry in `PROVENANCE.md` (file path, upstream PDFBox version, upstream Java path)
- Parity / oracle tests (PRD §12) — no class is complete without them
- Class-cluster scoped changes (PRD §11) — do not port whole modules in one change
- For ported files whose behavior deviates from upstream: a one-line entry in `CHANGES.md`
