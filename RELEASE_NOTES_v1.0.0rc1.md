# pypdfbox 1.0.0rc1 — Release Notes

**First release candidate for the 1.0 cut of pypdfbox — a
Python-native port of Apache PDFBox 3.0.x.**

---

## What it is

`pypdfbox` is a direct port of
[Apache PDFBox](https://pdfbox.apache.org/) to pure Python. No
JVM, no JPype, no Java subprocess — the COS object model, parser,
writer, content-stream engine, text extractor, font subsystem
(fontbox), renderer, tagged-PDF accessibility model, digital
signature pipeline (PAdES-LTV), XMP metadata schema (xmpbox),
JBIG2 decoder, debugger GUI, and CLI tools are all reimplemented
in Python while preserving PDFBox's package layout, class names,
inheritance hierarchies, and method semantics. A developer
already familiar with PDFBox should recognise pypdfbox at roughly
85–90% conceptual familiarity. The one consistent translation is
naming: Java `camelCase` becomes Python `snake_case`. Everything
else — `COSDictionary`, `PDDocument`, `PDFParser`, `PDFRenderer`,
`PDStructureTreeRoot`, lazy COS loading, incremental save with
xref preservation, object streams, ToUnicode mapping, Type0/CID
font handling — is the same shape upstream PDFBox developers
already know.

---

## Status

- **Release candidate for 1.0.** The port covers the full
  in-scope upstream surface. The consolidation phase that
  followed the 0.9.0 pre-release is complete: the deferred-item
  backlog is drained and the differential fuzz/parity campaign
  has run through wave 1598.
- **Method parity: 100%** — 1,015 / 1,015 upstream classes
  matched, 8,408 / 8,408 mapped Java methods present, 0
  Java-only classes (measured against upstream 3.0 HEAD).
- **Tests**: **56,839 passing** (hand-written + ported upstream
  suites; 137 documented skips, 0 deterministic failures). A
  separate live-differential oracle suite (~790 test files
  driving the real PDFBox 3.0.7 jar) backs the parity claims and
  remains in the repository's archive.
- **Line coverage**: **99.21%** (133,905 statements).
- **Behavioural parity method**: every surface was
  differentially fuzzed against a live Java PDFBox 3.0.7 oracle —
  malformed inputs, edge encodings, float corners, exception
  shapes — with divergences either fixed or pinned and
  documented. The final ten waves alone (1589–1598) closed 40+
  oracle-confirmed divergences, down to Java-bytecode-level
  details like `Math.round` half-up rounding, `String.trim()`
  vs `str.strip()`, and `int`→`char` narrowing casts.

---

## Changed since 0.9.0 (TestPyPI pre-release)

- **Python floor lowered to 3.12** (0.9.0rc1 required 3.14).
  Classifiers cover 3.12 / 3.13 / 3.14.
- **Rendering import errors are actionable.** When `skia-python`
  can't find the system GL / fontconfig libraries (minimal Docker
  images), the ImportError now names the exact packages to
  install per distro instead of a bare `libEGL.so.1` failure.
- **Platform support matrix verified empirically** (Docker +
  bare-metal CI runs) and documented in `docs/install.md`:
  Linux glibc x86_64/arm64, macOS arm64, Windows x64 supported;
  macOS Intel supported via source-built `cryptography` (needs a
  Rust toolchain); Alpine/musl and Windows ARM64/x86 out of
  scope with recorded reasons.
- **Wave 1598 parity fixes (12)**, including: SASLprep
  (AES-256/R6 password canonicalisation) now mirrors upstream's
  astral-codepoint narrowing; `PDFTextStripper` duplicate-glyph
  suppression is page-global with upstream's tolerance formula
  and `/ActualText` bypass; `PDAnnotationSquareCircle` /
  `PDAnnotationRubberStamp` restored to the upstream
  `PDAnnotationMarkup` hierarchy; Type 1 (function-based)
  shadings honour `/Background` and out-of-domain semantics;
  TrueType `name`-table decoding is byte-aligned with upstream
  (storage offsets, charset dispatch, malformed-record
  handling).
- **Release pipeline hardened**: tag-triggered trusted
  publishing now rehearses on TestPyPI and then publishes to
  production PyPI.

---

## Active divergences

The canonical, always-current list lives in
[`CHANGES.md` → Active divergences](CHANGES.md). The headline
entries, all deliberate:

- **ICU bidi reordering not ported.** Pure-LTR and pure-RTL runs
  reorder correctly; mixed-direction paragraph reordering
  differs from ICU's full bidi algorithm (ICU is not a
  permissively-licensed dependency we take on).
- **`SimpleDateFormat` locale-sensitive parsing not ported.**
  Digit-start date shapes all parse; alpha-start locale strings
  (`"Friday, January 11, 2115"`) fall through.
- **Renderer pixel-exact parity is not portable.** Skia + Pillow
  cannot be byte-equal to Java AWT; parity is enforced
  structurally and pixel-wise within tolerance (MAD gates)
  against the live oracle. Anti-aliased edge pixels may differ.
- **Python regex semantics** in `split_on_space` /
  `tokenize_on_space` (trailing-empty / zero-width lookaround)
  differ from Java `String.split`.
- **Bounded leniency contracts** — a small set of
  malformed-input edges where pypdfbox is deliberately more
  lenient than upstream (each pinned by tests on both sides and
  recorded in `CHANGES.md`).

---

## Installation

This is a **pre-release**, so pip needs `--pre`:

```sh
pip install --pre pypdfbox
# or pin exactly:
pip install pypdfbox==1.0.0rc1
```

Python **3.12+** is required. Runtime dependencies (all
permissive — Apache-2.0 / BSD / MIT / HPND):

- `cryptography>=42`
- `Pillow>=12.2.0`
- `fontTools>=4`
- `skia-python>=144`
- `imagecodecs>=2026`
- `numpy>=2`

`/JBIG2Decode` is supported natively — the JBIG2 decoder is an
Apache-2.0 in-tree port (no GPL decoder dependency).

Rendering on minimal Linux images needs the system GL/fontconfig
libraries; the Alpine/musl and macOS-Intel caveats are in
[`docs/install.md`](docs/install.md). The `pypdfbox[cjk]` extra
is the opt-in consent gate for the CJK font auto-downloader
(Noto Sans CJK, SIL OFL 1.1, SHA-256-verified); it carries no
Python deps of its own.

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
| `doc.getDocumentCatalog()` | `doc.get_document_catalog()` |
| `Loader.loadPDF(file)` | `Loader.load_pdf(file)` (or `PDDocument.load(file)`) |

Inheritance hierarchies are intact
(`BaseParser → COSParser → PDFParser`), so subclass-based Java
extensions translate directly. See
[`docs/migration.md`](docs/migration.md) for the full guide.

---

## Licensing

Apache License 2.0, matching upstream PDFBox. `LICENSE` and
`NOTICE` ship in the wheel; per-file porting attribution is
recorded in `PROVENANCE.md` (Apache 2.0 §4(b)), which also ships
in both the wheel and the sdist. All runtime dependencies are
permissively licensed; the dependency tree is gated by both a
metadata license check and a native-artifact copyleft byte-scan.

---

## Feedback

This RC is the last stop before 1.0.0. Bug reports — especially
"PDFBox does X, pypdfbox does Y" divergence reports with a
sample PDF — are exactly what this phase is for:
<https://github.com/mehdyhaghy/pypdfbox/issues>
