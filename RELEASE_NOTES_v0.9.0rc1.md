# pypdfbox 0.9.0rc1 — Release Notes

**Release candidate of pypdfbox — a Python-native port of Apache
PDFBox 3.0.x.** This RC is approaching the 1.0 cut.

---

## What it is

`pypdfbox` is a direct port of
[Apache PDFBox](https://pdfbox.apache.org/) to pure Python. No
JVM, no JPype, no Java subprocess — the COS object model, parser,
writer, content-stream engine, font subsystem, renderer, tagged-
PDF accessibility model, digital signature pipeline, XMP metadata
schema, debugger GUI, and CLI tools are all reimplemented in
Python while preserving PDFBox's package layout, class names,
inheritance hierarchies, and method semantics. A developer
already familiar with PDFBox should recognise pypdfbox at roughly
85-90% conceptual familiarity. The one consistent translation is
naming: Java `camelCase` becomes Python `snake_case`. Everything
else — `COSDictionary`, `PDDocument`, `PDFParser`, `PDFRenderer`,
`PDStructureTreeRoot`, lazy COS loading, incremental save with
xref preservation, object streams, ToUnicode mapping, Type0/CID
font handling — is the same shape upstream PDFBox developers
already know.

---

## Status

- **Phase 3 closeout.** The port covers the full in-scope upstream
  surface (parser, writer, pdmodel, content streams, text
  extraction, fontbox, rendering, xmpbox, signature, debugger,
  tools, examples, benchmark). What remains before the 1.0 cut is
  consolidation work — divergence audits, follow-ups in
  `DEFERRED.md`, and polish — not new feature porting.
- **Tests**: **44,400 passing** (full pytest with coverage,
  wave 1390 canonical recipe — 4 deselects, 138 documented skips,
  0 deterministic failures).
- **Line coverage**: **99.273% global**
  (124,369 / 125,280 statements; 2,093 excluded; 911 missing —
  follow-up coverage-augmentation waves planned).
- **Method parity**: 99.8% (8,752 / 8,766 mapped against upstream
  3.0 HEAD; 1,110 / 1,110 classes matched, 0 Java-only; remaining
  0.2% is debugger inner-helper surface that doesn't translate
  one-to-one from Swing to Tk).
- **Active divergences**: 5 — see
  [`CHANGES.md` → Active divergences](CHANGES.md#active-divergences-vs-upstream).

---

## Major features shipped since the previous RC

- **Port complete across every upstream module** except the
  intentionally-out-of-scope ones (`preflight`, which PDFBox 4.0
  removes). COS, parser, writer, pdmodel, contentstream, text,
  fontbox, rendering, xmpbox, multipdf, signature, printing,
  debugger, tools, examples, benchmark are all in.
- **CJK auto-downloader.** Opt-in (`pip install pypdfbox[cjk]`
  plus `PYPDFBOX_CJK_AUTODOWNLOAD=1`) loader fetches Noto Sans CJK
  (pinned to release `Sans2.004`, SIL OFL 1.1) from the upstream
  GitHub releases on first use, verifies SHA-256, and caches per
  user. Default behaviour is unchanged — `.notdef` glyphs without
  the opt-in, exactly as upstream falls back when the host system
  lacks a CJK font.
- **Liberation last-resort substitution.** Every Standard 14 font
  reference without an embedded program substitutes through the
  bundled Liberation Sans / Serif / Mono families (regular, bold,
  italic, bold-italic) plus DejaVuSans for symbolic glyph
  coverage (Symbol ~84%, ZapfDingbats ~100%). All permissive
  licences.
- **PAdES-LTV signing.** End-to-end PAdES-LTV signing through
  `PDDocument.add_signature` + `save_incremental` —
  `Pkcs7Signature` (PyCA `cryptography.PKCS7SignatureBuilder`
  wrapper for `adbe.pkcs7.detached`), `ExternalSigningSupport` /
  `SigningSupport` external-signing seam, `TSAClient` (RFC 3161),
  `TimestampedPkcs7Signature`, `DocumentTimestampSigner`
  (`/Type /DocTimeStamp` + `/SubFilter ETSI.RFC3161`), and the
  `/DSS` + `/VRI` revocation-info bundling under
  `pdmodel.interactive.digitalsignature`.
- **Rich-text `/RV` round-trip** for variable-text AcroForm
  fields. Type-checked XML/HTML serialisation of the rich-value
  representation matches PDFBox's read/write shape.
- **GSUB lookup Types 1-8.** Full OpenType GSUB lookup-table
  family: single-substitution (1), multiple-substitution (2),
  alternate-substitution (3), ligature-substitution (4),
  contextual (5, all three formats), chained contextual (6, all
  three formats), extension-substitution (7), and reverse-chained
  contextual single-substitution (8). The flat
  `MapBackedGsubData` projection skips the context-aware Types 5
  and 6 (they need a shaping engine), but the data classes are
  present and validated.
- **Coons / tensor patch rendering.** Shading Type 6 (Coons) and
  Type 7 (tensor-product) patch meshes render through a Pillow-
  backed tessellator. Earlier RCs raised on these types; the
  renderer now matches the upstream shape.

---

## Active divergences

Recorded in `CHANGES.md` under "Active divergences vs upstream":

- **ICU bidi reordering not ported.** Text extraction uses
  `unicodedata.bidirectional` for RTL detection. Pure-LTR and
  pure-RTL runs reorder; mixed-LTR+RTL paragraph reordering
  differs from ICU's full bidi algorithm. ICU is a hard runtime
  dependency we do not take on (permissive-license-only policy).
- **`SimpleDateFormat` locale-sensitive parsing not ported.**
  `pypdfbox.xmpbox.date_converter.parse_simple_date` handles
  every digit-start shape; alpha-start patterns (locale
  month/weekday strings like `"Friday, January 11, 2115"`) fall
  through. Production callers exercise digit-start only.
- **`split_on_space` / `tokenize_on_space` Python regex
  semantics.** Trailing-empty / zero-width-lookaround behaviour
  differs from `String.split` / `Pattern.split`. Documented in
  `pypdfbox.util.string_util`.
- **Renderer pixel-exact parity is not portable.** Pillow plus a
  Skia-backed `_aggdraw_compat` rasteriser can't be byte-equal
  to Java AWT. Parity is enforced structurally (page count,
  MediaBox, Rotation, Contents shape, Resources keys, save-
  reload round-trip), anchored to the bundled reference PDFs.
- **Skia anti-aliasing vs Java2D AA.** Low-resolution raster
  edge pixels may differ from upstream. Same root cause as the
  preceding bullet.

The active list is the live picture — see
[`CHANGES.md`](CHANGES.md) for the canonical version. Closed
divergences from earlier RCs (e.g. the Symbol / ZapfDingbats
fallback gap, the `/IC` markup-annotation accessor asymmetry, the
GSUB Type 5-8 gap) are recorded in `HISTORY.md`.

---

## Installation

This is a **pre-release**, so pip needs `--pre`:

```sh
pip install --pre pypdfbox==0.9.0rc1
```

Or pin the exact version:

```sh
pip install pypdfbox==0.9.0rc1
```

Python 3.14+ is required. Runtime dependencies (all permissive —
Apache 2.0 / BSD / MIT / HPND):

- `cryptography>=42`
- `Pillow>=12.2.0`
- `fontTools>=4`
- `aggdraw>=1.3`
- `jbig2-parser`
- `skia-python`
- `imagecodecs`
- `numpy`

The `pypdfbox[cjk]` extra is the opt-in consent gate for the CJK
font auto-downloader; it carries no Python deps of its own.

---

## Migration from upstream PDFBox

The only mechanical rule is **Java `camelCase` becomes Python
`snake_case`.** Class names, package paths, inheritance, and
behaviour are preserved verbatim.

| PDFBox (Java) | pypdfbox (Python) |
|---|---|
| `org.apache.pdfbox.cos.COSDictionary` | `pypdfbox.cos.COSDictionary` |
| `org.apache.pdfbox.pdmodel.PDDocument` | `pypdfbox.pdmodel.PDDocument` |
| `org.apache.fontbox.ttf.TrueTypeFont` | `pypdfbox.fontbox.ttf.TrueTypeFont` |
| `doc.saveIncremental(out)` | `doc.save_incremental(out)` |
| `catalog.getDocumentCatalog()` | `catalog.get_document_catalog()` |
| `Loader.loadPDF(file)` | `Loader.load_pdf(file)` (or `PDDocument.load(file)`) |

Inheritance hierarchies are intact
(`BaseParser → COSParser → PDFParser`), so subclass-based Java
extensions translate directly. The `ICOSVisitor` protocol exposes
`visit_from_object` from the start (a PDFBox 4.0 alignment).

A typical port of a PDFBox snippet:

```java
// Java / PDFBox
try (PDDocument doc = Loader.loadPDF(new File("in.pdf"))) {
    PDDocumentInformation info = doc.getDocumentInformation();
    info.setTitle("Annual Report 2025");
    doc.save("out.pdf");
}
```

```python
# Python / pypdfbox
from pypdfbox import PDDocument

with PDDocument.load("in.pdf") as doc:
    info = doc.get_document_information()
    info.set_title("Annual Report 2025")
    doc.save("out.pdf")
```

Migration is a mechanical sed-style sweep. Full guide:
[`docs/migration.md`](docs/migration.md) (if present), with
the active divergences list as the canonical exception register.

---

## Known issues / DEFERRED items

Open follow-ups (fixable, not yet done) live in
[`DEFERRED.md`](DEFERRED.md). The substantive open items between
this RC and 1.0:

- **ICC v4 chunked profile parsing.** v2 profiles round-trip; v4
  chunked is partially supported.
- **ICC color-conversion math.** ICC profiles parse, but full
  colorimetric ICC-to-device transforms are not yet implemented;
  rendering falls back to device-RGB approximations.
- **PDF/A conformance from the writer.** The writer can produce
  structurally valid tagged PDFs, but does not guarantee a
  clean PDF/A-1/2/3/4 conformance report without external
  remediation. Validator choice is left to downstream users; per
  the permissive-licence-only rule, no specific validator is
  bundled.

None of these block the 1.0 cut on their own. They are tracked
for transparency.

---

## Upgrade notes

No public API breakage between earlier RC builds and `0.9.0rc1`.
Two minor surface changes worth noting if you were tracking the
wave history:

- **camelCase Java-name aliases have been removed** from `cos.*`,
  `xmpbox.type.*`, `fontbox.*`, and `pdmodel.font.*`. Callers
  that explicitly invoked `cosArray.addAll(...)` or
  `cosString.getString()` should switch to the snake_case form
  (`cos_array.add_all(...)`, `cos_string.get_string()`). The
  aliases were marked deprecated in earlier RCs; final removal
  landed in waves 1380 / 1381.
- **`set_no_subset_tables` / `get_no_subset_tables` API pair**
  added to `pypdfbox.fontbox.ttf.ttf_subsetter.TTFSubsetter`
  and to the `PDTrueTypeFontEmbedder` / `PDCIDFontType2Embedder`
  font-embedding surfaces. Existing callers see no change
  (defaults preserve the descriptor metadata tables every PDF
  reader consults via `/FontFile2`).

---

## Acknowledgements

`pypdfbox` exists because of work by:

- **The Apache PDFBox project** — the source code we ported under
  Apache 2.0. See [`NOTICE`](NOTICE) and
  [`PROVENANCE.md`](PROVENANCE.md) for per-file attribution.
- **Liberation Fonts** (Red Hat) — bundled Sans / Serif / Mono
  families substituting for the Standard 14.
- **DejaVu Fonts** — bundled `DejaVuSans` for extended Unicode
  and symbolic glyph coverage.
- **fontTools** — TTF / CFF / OTF / Type 1 table parsing and
  font subsetting.
- **Pillow** (and `aggdraw` / `skia-python`) — rasterisation
  canvas backing `PDFRenderer`.
- **cryptography** — primitives for `StandardSecurityHandler`,
  public-key handler, PKCS#7 signature read / write, RFC 3161
  TSA client.

Full licence texts ship under `LICENSE` and in
`pypdfbox/resources/ttf/`.

---

## Reporting issues

File bugs, parity gaps, and questions at the GitHub issue
tracker:

**<https://github.com/mehdyhaghy/pypdfbox/issues>**

When reporting a parity issue, include:

1. The minimal PDF that reproduces the problem (or the exact
   PDFBox Java snippet whose output you expect to match).
2. The Java PDFBox version you're comparing against.
3. The pypdfbox version
   (`python -c "import pypdfbox; print(pypdfbox.__version__)"`).

---

## What to expect before 0.9.0 final

This RC exists to surface integration issues against real-world
PDF corpora. Between `0.9.0rc1` and `0.9.0` final we expect to:

- Close the ICC color-math gap so rendered raster output matches
  PDFBox at pixel parity on color-managed inputs (where the
  underlying rasteriser difference allows).
- Tighten writer output so a clean PDF/A round-trip is achievable
  on the common conformance levels without external remediation.
- Drive method parity from 99.8% toward 100% on the remaining
  debugger inner-helper surface.

No public API breakage is planned between this RC and `0.9.0`.
