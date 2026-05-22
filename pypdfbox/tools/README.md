# pypdfbox.tools

Port of `org.apache.pdfbox.tools` — the command-line surface that
ships with upstream PDFBox under
`tools/src/main/java/org/apache/pdfbox/tools/`. Two layers live
in this module:

1. The **CLI dispatcher** (`cli.py`) — the `pypdfbox` console
   script's entry point. Mirrors upstream's PicoCLI-based
   `org.apache.pdfbox.tools.PDFBox` dispatcher, but uses the
   stdlib `argparse` so no extra runtime dep is pulled in. Each
   subcommand module registers itself through a
   `build_parser(subparsers)` callable.
2. The **tool classes** — direct ports of the upstream
   `Decrypt`, `Encrypt`, `PDFMerger`, `PDFSplit`, `PDFToImage`,
   `ExtractText`, `ExtractImages`, `ImageToPDF`, `TextToPDF`,
   `OverlayPDF`, `WriteDecodedDoc`, `Version`,
   `DecompressObjectstreams`, `PrintPDF`, `ExportFDF`,
   `ExportXFDF`, `ImportFDF`, `ImportXFDF`, `ExtractXMP`,
   etc. classes plus a `PDFBox` aggregate dispatcher
   (`pdf_box.py`) that holds the picocli subcommand
   registration map.

## CLI subcommands

Run `pypdfbox <command> --help` for the full flag set on any
subcommand. The commands wired into the `pypdfbox` console
dispatcher (`cli.py`):

| Command | Purpose |
|---|---|
| `info` | Print catalog / info-dict metadata for a PDF (title, author, producer, page count, version, encryption status). |
| `merge` | Combine multiple PDFs into one. Page ranges and bookmark preservation. |
| `split` | Split one PDF into N output files by page range or by page-count chunk. |
| `decrypt` | Strip the security handler from an encrypted PDF given owner / user password. |
| `encrypt` | Apply a Standard Security Handler (RC4 40/128, AES 128/256) with permission flags. |
| `decode` | `WriteDecodedDoc` — round-trip a PDF with every stream's filter chain applied, producing an uncompressed copy. |
| `extracttext` | Drive `PDFTextStripper` against a PDF. Page-range, sort-by-position, encoding flags. |
| `imagetopdf` | `fromimage` — wrap one or more images (PNG / JPEG / TIFF / BMP) into a one-image-per-page PDF. |
| `texttopdf` | `fromtext` — render a plain-text file to a PDF with a chosen font and point size. |
| `listbookmarks` | Dump the outline tree to stdout. |
| `pdfdebugger` | Launch the Tk debugger GUI (see `pypdfbox.debugger.README.md`). |
| `writedecodedstream` | Dump a single decoded object stream's bytes to disk. |
| `version` | Print the installed pypdfbox version. |

The aggregate `PDFBox` dispatcher (`pdf_box.py`, the port of
upstream's PicoCLI shell) additionally exposes:

| Aggregate key | Tool class |
|---|---|
| `decrypt` | `Decrypt` |
| `encrypt` | `Encrypt` |
| `decode` | `WriteDecodedDoc` |
| `export:images` | `ExtractImages` |
| `export:xmp` | `ExtractXMP` |
| `export:text` | `ExtractText` |
| `export:fdf` | `ExportFDF` |
| `export:xfdf` | `ExportXFDF` |
| `import:fdf` | `ImportFDF` |
| `import:xfdf` | `ImportXFDF` |
| `overlay` | `OverlayPDF` |
| `print` | `PrintPDF` |
| `render` | `PDFToImage` |
| `merge` | `PDFMerger` |
| `split` | `PDFSplit` |
| `fromimage` | `ImageToPDF` |
| `fromtext` | `TextToPDF` |
| `version` | `Version` |
| `decompress` | `DecompressObjectstreams` |

The two surfaces share the underlying tool classes — `cli.py` is
the lightweight `pypdfbox`-script-facing wiring; `pdf_box.py`
mirrors upstream's `PDFBox.java` exactly for callers porting
direct Java invocations.

## Image format helpers

`pypdfbox/tools/imageio/` ports `org.apache.pdfbox.tools.imageio`
— a thin layer over Pillow that bridges the upstream
`ImageIOUtil` / `JPEGUtil` / `TIFFUtil` / `MetaUtil` shape. The
`PDFToImage` / `ExtractImages` paths route through these so the
flags (`-imageType`, `-resolution`, `-color`, etc.) accept the
same string values upstream accepts.

## Where the tests live

Per-tool tests live under `tests/tools/`, named after the
underlying subcommand (e.g. `test_split.py`,
`test_encrypt.py`, `test_decrypt.py`,
`test_pdf_to_image_wave1345.py`,
`test_texttopdf.py`). The CLI-dispatcher-level argparse wiring is
covered in `tests/tools/test_cli_wave307.py`, and the `pdf_box.py`
aggregate dispatcher in `test_pdf_box_dispatcher_wave1365.py`.

Upstream JUnit ports (where the upstream class has a JUnit test)
live alongside under `tests/tools/upstream/`. Provenance for both
production and test files is tracked in the top-level
`PROVENANCE.md`.
