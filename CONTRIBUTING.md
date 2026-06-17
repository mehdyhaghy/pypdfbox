# Contributing to pypdfbox

Thanks for your interest in pypdfbox. This document covers the
practical rules contributors should know before opening a pull
request. Everything below is binding on PR review — code that
violates the parity / licence / testing rules will be asked to
change.

## What this project is

`pypdfbox` is an Apache 2.0-licensed, Python-native port of
[Apache PDFBox](https://pdfbox.apache.org/) 3.0.x. The product is
*API compatibility itself* — a developer who already knows PDFBox
should recognise the surface here at roughly 85-90% conceptual
familiarity. We don't invent abstractions, we don't rename
concepts, and we don't collapse inheritance hierarchies. We
translate.

The only mechanical translation is naming: Java `camelCase`
becomes Python `snake_case`. Everything else — package paths
(`org.apache.pdfbox.cos` → `pypdfbox.cos`), class names
(`COSDictionary`, `PDDocument`, `PDFParser`, `PDFRenderer`,
`PDStructureTreeRoot`), inheritance chains
(`BaseParser → COSParser → PDFParser`), and lazy / force-parse
semantics — is preserved verbatim.

## Code style

- **Mirror PDFBox package layout.** New code goes into the module
  whose Java namespace it maps from. Don't flatten.
- **Preserve class names exactly.** `COSStream` stays
  `COSStream`. No Pythonic renames.
- **`camelCase` → `snake_case` and nothing else.**
  `saveIncremental()` becomes `save_incremental()`, not
  `save_inc()` or `save()` with a flag.
- **No camelCase aliases.** Don't ship `saveIncremental` alongside
  `save_incremental` for source-port convenience, and don't add
  `# noqa: N802` aliases. snake_case only.
- **Behaviour over style.** Lazy COS loading, incremental save
  with byte-range preservation, xref reconstruction, object stream
  generation, marked-content extraction — these must match upstream
  even when a more "Pythonic" rewrite would be shorter.
- **No per-file licence headers.** Attribution lives in
  `PROVENANCE.md` (see below). Source files stay clean.
- **Library-first for generic concerns.** Compression, encryption,
  signing, logging, image decoding, font parsing, and XML are
  delegated to existing permissive libraries (`cryptography`,
  `Pillow`, `fontTools`, stdlib `logging`, `xml.etree`). Don't
  reimplement crypto / compression primitives.
- **New dependencies require explicit approval.** Don't add to
  `pyproject.toml` without proposing the dep first and waiting for
  a maintainer ack.

## Local development setup

The project uses [`uv`](https://docs.astral.sh/uv/) as the package
manager.

```sh
git clone https://github.com/mehdyhaghy/pypdfbox.git
cd pypdfbox
uv sync --all-groups
```

Run the full test suite (fast pass, no coverage):

```sh
.venv/bin/pytest -q --no-cov
```

Refresh `coverage.json`:

```sh
.venv/bin/pytest -q
```

Run the linter:

```sh
uv run ruff check --fix
uv run ruff check
```

The first command auto-fixes the cheap rules (import ordering,
whitespace, simple rewrites); the second confirms a clean tree.

## Pre-push hook

A local `.git/hooks/pre-push` gates every push to GitHub. It is
not versioned (per-clone), and runs two checks in order:

1. `uv run ruff check` — same lint pass you'd run manually.
2. `uv run --with pip-licenses pip-licenses` against a permissive
   allow-list — Apache 2.0 / MIT / BSD / ISC / PSF / HPND / MPL-2.0.

The full recipe lives in `docs/build.md`. Recreate the hook from
that recipe on a fresh clone:

```sh
chmod +x .git/hooks/pre-push
```

Don't bypass the hook with `--no-verify`. If lint or licensing
fails, fix the underlying issue.

## PROVENANCE.md

Every file ported from upstream PDFBox source needs a row in
`PROVENANCE.md`. This is how the project satisfies Apache 2.0
§4(b) ("notices stating that You changed the files") in one
centralised place, instead of per-file licence headers.

Format (rows are tab-separated):

```
pypdfbox/<py path>    PDFBox <version>    <upstream Java path>
```

Example:

```
pypdfbox/cos/cos_dictionary.py    PDFBox 3.0.5    pdfbox/src/main/java/org/apache/pdfbox/cos/COSDictionary.java
```

Same rule applies to test ports: when you translate a JUnit test
under `pdfbox/src/test/java/...` to `tests/<module>/upstream/...`,
add a row. Binary fixtures copied from
`pdfbox/src/test/resources/` get rows too — keep filenames
upstream-identical so future re-syncs are diffable.

## CHANGES.md

**`CHANGES.md`** records *active behavioural divergences from
upstream PDFBox*. Add an entry whenever the port deliberately
deviates from upstream behaviour (not just translates). Format:

```
- pypdfbox/<path>: <one-line description of deviation>
  upstream: PDFBox <version> <java path>
  reason: <why we deviate>
```

Read the "Active divergences vs upstream" section before making
cross-cutting changes — that's the live list of things you must
not silently re-resolve.

Open items that are *fixable but not yet done* are tracked on the
[GitHub issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues).
Open an issue when a port lands partial functionality with a
follow-up, and close it when the follow-up lands.

Routine `camelCase → snake_case` translations are not changelog
material. Only record substantive behavioural deltas.

## License agreement

By submitting a contribution, you agree it is released under the
project licence: **Apache License, Version 2.0**.

Dependency policy is **permissive-only**:

- **Allowed:** Apache 2.0, MIT, BSD (2/3 clause), ISC, PSF, HPND,
  MPL 2.0.
- **Forbidden:** GPL, LGPL, AGPL, MPL (1.x), EPL, CDDL, SSPL,
  BUSL.

The pre-push hook hard-fails if a forbidden licence appears in
the resolved dependency tree. The rule applies to wrapped /
recommended external CLI tools as well — pypdfbox stays
validator-agnostic for PDF/A and PDF/UA precisely so we don't
have to recommend any copyleft validator.

Per-file licence headers are not used; the project-level
`LICENSE` + `NOTICE` + `PROVENANCE.md` cover the obligations.

## Testing requirements

Every new class needs tests in the same change. Two layers, when
upstream has a JUnit equivalent:

1. **Hand-written tests** in `tests/<module>/test_<class>.py`
   covering the API as it's actually used in pypdfbox.
2. **Ported upstream tests** in
   `tests/<module>/upstream/test_<class>.py`, translated from
   `pdfbox/src/test/java/org/apache/pdfbox/<module>/<Class>Test.java`.

Translation conventions:

| Java / JUnit | Python / pytest |
|---|---|
| `@Test public void testFoo()` | `def test_foo()` |
| `assertEquals(expected, actual)` | `assert actual == expected` |
| `assertTrue(x)` / `assertFalse(x)` | `assert x` / `assert not x` |
| `assertNull(x)` / `assertNotNull(x)` | `assert x is None` / `assert x is not None` |
| `assertThrows(X.class, () -> ...)` | `with pytest.raises(X): ...` |
| `@BeforeEach setUp()` | pytest fixture |

If a JUnit case targets Java-specific plumbing (`PrintStream`
formatting, locale-sensitive number formatting that doesn't apply
to Python, reflection assertions), skip the case with a one-line
comment explaining why instead of forcing a translation.

The full pytest suite must stay green:

```sh
.venv/bin/pytest -q --no-cov
```

Tests that were skipped for legitimate reasons (network-dependent
render compare, un-bundled JIRA fixtures, etc.) document the
reason in a `pytest.skip(...)` call inline. Don't introduce new
silent skips.

## Cross-platform expectations

The supported platforms are Ubuntu, macOS, and Windows. Most of
the developer machines are macOS or Linux. Before pushing, scan
your diff for the following platform-specific patterns:

- `mmap.PROT_*` constants are POSIX-only — feature-detect.
- `os.unlink` on an open file raises on Windows — close handles
  first.
- `tempfile.NamedTemporaryFile(delete=True)` can't be re-opened
  by name on Windows.
- `pathlib.Path` flavour is fixed at interpreter import; you
  can't monkey-patch `sys.platform` to swap `PosixPath` /
  `WindowsPath` at runtime.
- Tk widget mapping after `update_idletasks` is synchronous on
  POSIX, async on Windows.
- `os.sep` for substring assertions on path strings.
- `pytest.parametrize` with long `bytes` values needs explicit
  `ids=[...]` (Windows test-ID env var caps at 32,767 chars).

A five-minute diff review for these patterns heads off
Windows-specific test failures that are otherwise only caught
after pushing.

## Submitting a pull request

1. Branch from `main`.
2. Make the change.
3. Run `uv run ruff check --fix && uv run ruff check`.
4. Run `.venv/bin/pytest -q --no-cov`.
5. Update `PROVENANCE.md` (per ported file) and `CHANGES.md` (if
   you introduce a behavioural divergence). If your change closes
   an open item on the issue tracker, reference it in the PR.
6. Push and open a PR against `main` on GitHub:
   <https://github.com/mehdyhaghy/pypdfbox>.

Keep PRs focused. A class cluster (e.g. "port `COSName` +
`COSString` + `COSArray` + their tests") is the right granularity.
Don't try to port a whole module in one PR.

## Where to ask

- Bugs / parity gaps / feature requests:
  <https://github.com/mehdyhaghy/pypdfbox/issues>.
- Design-level PDF / PDFBox questions: upstream
  [PDFBox project](https://pdfbox.apache.org/) — mailing lists
  and the Stack Overflow `pdfbox` tag are usually a faster route
  for concept-level questions, since pypdfbox's surface is close
  enough that PDFBox answers translate directly.

Thanks for porting. The upstream PDFBox maintainers did the hard
design work; we just translate.
