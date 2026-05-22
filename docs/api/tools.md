# pypdfbox.tools — command-line interface

`pypdfbox.tools` mirrors the upstream `org.apache.pdfbox.tools` package: a
small dispatcher (`pypdfbox.tools.cli:main`) and one module per subcommand.
Installing pypdfbox via `pip install pypdfbox` registers the `pypdfbox`
console script (declared in `pyproject.toml`).

```bash
pypdfbox <subcommand> [options]
pypdfbox --help
pypdfbox <subcommand> --help
```

## Public surface

| Symbol | Purpose |
| --- | --- |
| `main` | The CLI entry point. Reads `sys.argv`, dispatches to the right subcommand, returns an exit code. |
| `run_cli(argv)` | Same as `main` but takes an explicit `argv` list — useful in tests. |

The subcommand registry is internal; the user-facing names are:

| Subcommand | Description |
| --- | --- |
| `info` | Print PDF metadata: version, page count, `/Info` fields, optional XMP. |
| `merge` | Concatenate input PDFs into one output. Forwards to `pypdfbox.multipdf.PDFMergerUtility`. |
| `split` | Split a PDF into per-page or per-N-page files. Forwards to `pypdfbox.multipdf.Splitter`. |
| `decrypt` | Strip Standard-handler encryption (requires the user/owner password). |
| `encrypt` | Apply Standard-handler encryption (`-O ownerpwd -U userpwd -keyLength 128|256`). |
| `extracttext` | Extract Unicode text via `pypdfbox.text.PDFTextStripper`. |
| `imagetopdf` | Pack one or more images into a one-image-per-page PDF. |
| `texttopdf` | Typeset a plain-text file onto a new PDF (Standard 14 font, default Helvetica 10pt). |
| `listbookmarks` | Print the outline / bookmark hierarchy. |
| `pdfdebugger` | Launch the Tkinter `PDFDebugger` UI (port of the upstream Swing debugger). |
| `writedecodedstream` | Rewrite a PDF with every stream decoded (Flate / LZW / ASCII85 / ASCIIHex / RunLength / CCITTFax pipelines applied). |
| `version` | Print pypdfbox + Python + key dependency versions. |
| `decode` | Decode a single filtered stream from a PDF (`--obj 12 --gen 0`). |
| `render` | Render a page to an image (PNG / JPEG / TIFF / BMP). Forwards to `pypdfbox.rendering.PDFRenderer`. |
| `overlay` | Overlay one PDF on top of another (`--bg base.pdf --overlay stamp.pdf`). Forwards to `pypdfbox.multipdf.Overlay`. |
| `print` | Print a PDF (`pypdfbox.printing.PDFPrintable`). |

The `export:*` / `import:*` subcommands handle structured-data exchange:

| Subcommand | Description |
| --- | --- |
| `export:fdf` | Export AcroForm field values to an FDF file. |
| `export:xfdf` | Export AcroForm field values to an XFDF file. |
| `export:xmp` | Export the document's XMP metadata packet. |
| `export:images` | Extract every image X-object (JPEG / lossless already shipped; image-decoding cluster gates remaining formats). |
| `import:fdf` | Apply an FDF file's field values to an AcroForm. |
| `import:xfdf` | Apply an XFDF file's field values to an AcroForm. |
| `import:xmp` | Replace the document's XMP metadata packet. |

## Typical usage

```bash
# Inspect
pypdfbox info input.pdf

# Combine
pypdfbox merge a.pdf b.pdf c.pdf -o combined.pdf

# Split into per-page files
pypdfbox split input.pdf --split 1 -o pages/

# Extract text
pypdfbox extracttext input.pdf -o text.txt --sort

# Encrypt
pypdfbox encrypt input.pdf -O ownerpwd -U userpwd --keylength 256 -o enc.pdf

# Render a page
pypdfbox render input.pdf --page 1 --dpi 300 -o page1.png
```

## Programmatic invocation

```python
from pypdfbox.tools import run_cli

exit_code = run_cli(["info", "input.pdf"])
```

## Exit codes

`main` returns:

- `0` on success,
- `1` on argument parse errors,
- `2` on I/O failures (missing file, permission denied),
- `3` on PDF-level errors (`PDFParseError`, invalid password),
- `4` on internal errors (uncaught exception — bug report worthy).

## PDFBox divergence

- Subcommand names match upstream (e.g. `extracttext`, not
  `extract-text`).
- The Java `PDFBox` launcher (with sub-classloader dispatch) collapses
  into one `argparse`-based dispatcher.
- Logging uses Python `logging` with the level controlled by `--quiet`
  (warnings only) / `--verbose` (info+) flags.

## See also

- [pdmodel.md](pdmodel.md), [text.md](text.md), [rendering.md](rendering.md),
  [multipdf.md](multipdf.md) — the subsystems each subcommand wraps.
- [guides/cli-cookbook.md](../guides/cli-cookbook.md) — recipe-style CLI
  usage.
