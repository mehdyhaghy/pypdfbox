# Command-line tools

The `pypdfbox` umbrella command wraps each tool subcommand in a
single dispatcher, mirroring upstream PicoCLI-based PDFBox. It is
implemented on the stdlib `argparse` — no extra runtime
dependencies.

Two ways to invoke:

```
pypdfbox <subcommand> [options...]
python -m pypdfbox.tools.cli <subcommand> [options...]
```

Run `pypdfbox --help` for the full list of subcommands or
`pypdfbox <subcommand> --help` for per-subcommand options.

## info

Print version, page count, encryption status, and every populated
entry of the `/Info` dictionary. `-metadata` adds the XMP packet;
`-output json` switches to machine-readable output.

```
pypdfbox info input.pdf
pypdfbox info input.pdf -metadata -output json
```

## merge

Concatenate inputs in CLI order. Catalog reconciliation covers
`/AcroForm`, `/Names`, `/Dests`, `/Outlines`, `/PageLabels`,
`/Metadata`, and `/StructTreeRoot` via `PDFMergerUtility`.

```
pypdfbox merge -i part-a.pdf part-b.pdf part-c.pdf -o combined.pdf
```

## split

Split a PDF into per-N-page output files. Default chunk size is 1.

```
pypdfbox split -i input.pdf                  # one PDF per page
pypdfbox split -i input.pdf -split 10        # 10 pages per file
pypdfbox split -i input.pdf -startPage 5 -endPage 12 -outputPrefix book
```

When `-startPage` / `-endPage` are supplied without `-split`, the
entire range is emitted as one file (upstream parity).

## decrypt

Strip encryption from a PDF. Owner-password authentication is
required to remove `/Encrypt` cleanly.

```
pypdfbox decrypt -i locked.pdf -o open.pdf -password owner-secret
pypdfbox decrypt -i locked.pdf -keyStore alice.p12 -alias alice -password p12-pin
```

`-keyStore` + `-alias` switch to public-key authentication for
documents protected by `PublicKeyProtectionPolicy`.

## encrypt

Encrypt a PDF document. Pick the algorithm by key length: 40 →
RC4-40 (R2), 128 → RC4-128 / AES-128 (R3 / R4), 256 → AES-256 (R6).

```
pypdfbox encrypt -i plain.pdf -o locked.pdf \
    -ownerPassword owner -userPassword user -keyLength 256 \
    --no-canModify --no-canPrintFaithful
```

The `-can*` / `--no-can*` flags toggle every bit in
`AccessPermission`. `-certFile alice.pem` adds an X.509 recipient
for public-key encryption (repeatable for multiple recipients).

## extracttext

Strip text via `PDFTextStripper`. `--html` / `--md` wrap the output
in `PDFText2HTML` / `PDFText2Markdown` respectively, replacing the
need for separate helper scripts.

```
pypdfbox extracttext -i input.pdf -o output.txt
pypdfbox extracttext -i input.pdf -o output.html --html --sort
pypdfbox extracttext -i input.pdf -o output.md --md
pypdfbox extracttext -i input.pdf --console -startPage 2 -endPage 5
```

`--rotationMagic` engages `FilteredTextStripper` for documents with
rotated/skewed text; `--ignoreBeads` disables article-bead
separation.

## imagetopdf

Build a PDF from one or more images. Pillow opens each input —
PNG, JPEG, TIFF, and GIF are the well-tested formats.

```
pypdfbox imagetopdf -i page1.png page2.png -o out.pdf
pypdfbox imagetopdf -i diagram.tif -o out.pdf -pageSize A4 -resize -margin-pt 36
```

Use `-pageSize auto` to match each image's pixel dimensions
exactly; `-orientation auto` flips to landscape per image when
appropriate.

## texttopdf

Render a UTF-8 text file as a PDF using a Standard 14 font (or an
embedded TrueType via `-ttf`).

```
pypdfbox texttopdf -i notes.txt -o notes.pdf
pypdfbox texttopdf -i notes.txt -o notes.pdf -standardFont Courier -fontSize 11 -landscape
```

`-margins LEFT RIGHT TOP BOTTOM` and `-mediaBox LLX LLY URX URY`
override the default layout.

## Standalone helper modules

Three more tools ship as their own `argparse`-driven modules
(historical parity with upstream's separate JARs); they accept the
same flag spelling and are mounted under `python -m`:

```
python -m pypdfbox.tools.pdf_to_image -i input.pdf -dpi 200 -format png -prefix page
python -m pypdfbox.tools.overlay_pdf -i input.pdf -default stamp.pdf -o stamped.pdf
python -m pypdfbox.tools.extract_images -i input.pdf -prefix img
```

- **pdf_to_image** — render pages to PNG / JPEG / TIFF via
  `PDFRenderer`. Supports `-page N`, `-startPage` / `-endPage`,
  `-color rgb|gray|bitonal`, `-cropbox LLX LLY URX URY`, and
  `-subsampling` for faster low-DPI renders.
- **overlay_pdf** — stamp an overlay onto every page of an input
  PDF. Per-page selection via `-odd`, `-even`, `-first`, `-last`,
  `-useAllPages`, and `-position` (`Foreground` / `Background`).
- **extract_images** — dump every embedded `/XObject Image` to disk.
  `-useDirectJPEG` writes the JPEG bytes unmodified instead of
  re-encoding through Pillow.

## Other umbrella subcommands

Less-commonly-touched commands also live on the umbrella CLI:

- **version** — prints pypdfbox + Python + dependency versions.
- **listbookmarks** — dumps the outline (bookmarks) tree.
- **pdfdebugger** — text dump of the PDF object graph (the lite
  replacement for upstream's Swing PDFDebugger).
- **writedecodedstream** — rewrites a PDF with every stream
  decoded (filters stripped).

## See also

- [API reference](../api/index.md)
- [Text extraction guide](text-extraction.md)
- [Rendering guide](rendering.md)
- [Encryption guide](encryption.md)
- [Documentation index](../index.md)
