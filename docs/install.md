# Install

This guide covers everything needed to get `pypdfbox` running, on
both binary installs and source builds. For a one-line answer, see
the [project README](../README.md). This page is the full version.

## Python version support

pypdfbox requires **CPython 3.14 or newer**. Older releases are not
supported. The 3.14 minimum was chosen so we can rely on the
free-threaded ("nogil") build for parallel parsing and rendering
work where the user opts in; the regular GIL build is also
supported and is the default.

Other interpreters (PyPy, GraalPy, MicroPython, …) are not tested.
You are welcome to try them, but please flag bugs as
"untested interpreter" when filing.

## Install from PyPI

```sh
pip install pypdfbox
```

That installs the runtime dependencies (all permissively licensed):

- [`cryptography`](https://pypi.org/project/cryptography/) (Apache-2.0
  / BSD) — replaces upstream PDFBox's Java Cryptography Architecture
  and Bouncy Castle. Used by the Standard Security Handlers
  (`pypdfbox.pdmodel.encryption`) and the digital-signature pipeline
  (`pypdfbox.pdmodel.interactive.digitalsignature`).
- [`Pillow`](https://pypi.org/project/Pillow/) (HPND / MIT-CMU) —
  ICC color transforms via `ImageCms` and a handful of raster
  conversions in the renderer.
- [`fontTools`](https://pypi.org/project/fonttools/) (MIT) —
  low-level TTF / CFF / OTF / Type 1 table parsing under
  `pypdfbox.fontbox`. The semantic font logic is ported from
  upstream `org.apache.fontbox.*`; fontTools is the parser layer.
- [`skia-python`](https://pypi.org/project/skia-python/)
  (BSD-3-Clause) — canvas, path drawing, antialiasing, ICC color
  spaces, PNG / JPEG / WebP I/O. Replaces the older `aggdraw`
  binding.
- [`imagecodecs`](https://pypi.org/project/imagecodecs/)
  (BSD-3-Clause) — TIFF, CCITT (RLE / T.4 / T.6), JPEG 2000, plus
  the long tail of raster codecs that the filter pipeline calls
  into.
- [`numpy`](https://pypi.org/project/numpy/) (BSD-3 / 0BSD / MIT /
  Zlib / CC0-1.0, all permissive) — pixel math and CMYK
  conversion in the renderer.

No GPL, LGPL, AGPL, MPL, EPL, CDDL, SSPL, or BUSL dependencies.

JBIG2 decoding (`/JBIG2Decode`) is currently **unsupported**. The
only readily available decoder bundles a GPL-licensed native library,
which the permissive-license policy excludes, so pypdfbox ships no
JBIG2 decoder: the filter is registered for name recognition only and
`JBIG2Decode.decode` raises a clear "unsupported" error. A pure-Python
Apache-2.0 port (of `apache/pdfbox-jbig2`) is planned to restore
support.

A fresh install pulls roughly 90–110 MB of wheels (mostly Skia
binaries and imagecodecs's native blobs). Steady-state disk
footprint after install is around 130 MB.

## Extras

### `pypdfbox[cjk]`

```sh
pip install "pypdfbox[cjk]"
```

This extra is a **consent marker**, not a dependency switch. The
extra itself carries no Python packages — the CJK auto-downloader
uses stdlib only (`urllib`, `zipfile`, `hashlib`). What the marker
signals is: "you accept that pypdfbox may fetch Noto Sans CJK from
the upstream GitHub release on first CJK use, verify the
SHA-256 against a pinned manifest, and cache the font in your
per-user cache directory."

The download is *still* inert until you also set:

```sh
export PYPDFBOX_CJK_AUTODOWNLOAD=1
```

Both gates must be open. This way a user who installed
`pypdfbox[cjk]` for some other reason never accidentally triggers a
network fetch.

Pinned release: `Sans2.004` (2022-01-27). Font license: SIL OFL 1.1.
Cache directory: platform-default per-user cache (override with
`PYPDFBOX_CJK_CACHE_DIR`).

If neither gate is open, PDFs referencing an unembedded CJK font
produce `.notdef` glyphs — same behaviour as upstream Apache PDFBox
under the same conditions.

## Install from source

```sh
git clone https://github.com/mehdyhaghy/pypdfbox.git
cd pypdfbox
uv sync --all-groups
```

`uv` is the package manager we use. Install it from
<https://docs.astral.sh/uv/> if you don't already have it.
`uv sync --all-groups` creates `.venv/` and installs runtime
dependencies plus the `dev` dependency group (pytest, pytest-cov,
ruff, mypy).

To work inside the virtualenv:

```sh
source .venv/bin/activate           # POSIX
.venv\Scripts\Activate.ps1          # Windows PowerShell
```

…or call binaries directly: `.venv/bin/pytest -q --no-cov`.

For the full developer workflow (lint, test, coverage, pre-push
hook), see [`build.md`](build.md).

## Platform support matrix

| OS            | Architecture     | Status   | Notes                                  |
|---------------|------------------|----------|----------------------------------------|
| Linux         | x86_64           | tested   | Wheels published for all native deps.  |
| Linux         | aarch64 / arm64  | tested   | Wheels available; `skia-python` ARM wheels are newer, see troubleshooting. |
| macOS         | x86_64           | tested   | Intel Macs.                            |
| macOS         | arm64            | tested   | M-series Macs. Primary dev platform.   |
| Windows       | x86_64           | tested   | Cross-platform issues called out below. |
| Windows       | ARM64            | untested | Wheels may not exist for all deps.     |

Cross-platform behaviours that the test suite actively guards
against (a non-exhaustive list, drawn from waves 1324–1325 and the
ongoing cross-platform checklist):

- `mmap` constants: pypdfbox feature-detects `mmap.PROT_READ` and
  falls back to `mmap.ACCESS_READ` on Windows.
- File handles + `unlink`: every temp-file path closes the handle
  before unlinking, since Windows raises `PermissionError`
  otherwise.
- `pathlib` flavour: tests that depend on POSIX-only path strings
  are gated with `pytest.mark.skipif(sys.platform == "win32", ...)`.
- libtiff / Pillow byte-padding past EOD: differs between POSIX and
  Windows wheels; pypdfbox does not assert on the post-EOD tail.
- PDF in-place rewrite via the CLI (`decrypt`, `encrypt`): on
  Windows, the CLI closes every helper `PDDocument` before
  overwriting the source path.

If you hit a platform-specific issue we have not already guarded,
please file a GitHub issue with platform + Python version + a
minimal repro.

## Native-dependency notes

### `cryptography`

Modern `cryptography` (≥42, what we require) ships pre-built wheels
for all standard platforms. A source install needs a Rust toolchain.
On macOS, `xcode-select --install` plus `rustup` is enough. On
Linux, `pkg-config`, OpenSSL headers, and a Rust toolchain. On
Windows, the Rust MSVC toolchain.

### `Pillow`

Pre-built wheels exist for every supported platform. Source installs
need libjpeg-turbo, zlib, and (for full feature parity) libtiff,
LittleCMS, and FreeType headers.

### `skia-python`

Pre-built wheels exist for x86_64 macOS / Linux / Windows and arm64
macOS / Linux. The Linux ARM wheel landed relatively recently — if
you are on a very old `pip` (<23), upgrade `pip` first or you may
see "no matching distribution found" for the ARM wheel.

### `imagecodecs`

Pre-built wheels exist for the standard platforms. Source installs
are involved — they bundle a long list of native codec libraries
(libjpeg, libpng, libtiff, libwebp, OpenJPEG, …). Prefer the wheel.

### `numpy`

Universally available. No source-install concerns.

## Troubleshooting

**`cryptography` fails to install on an Apple Silicon Mac.** Update
`pip` first — older `pip` versions failed to match the arm64 wheel
tags. If you actually need a source build, install Rust via
`rustup`, then `xcode-select --install`, then retry.

**`skia-python` "no matching distribution" on Linux ARM.** Upgrade
`pip` (≥23.0). The ARM wheel uses a manylinux tag that older pip
versions do not understand.

**`imagecodecs` install hangs in a source build.** It's almost
certainly trying to compile the bundled native codec list. Use the
wheel: `pip install --only-binary :all: imagecodecs`.

**`PYPDFBOX_CJK_AUTODOWNLOAD=1` set but CJK still renders
`.notdef`.** Two gates: confirm both `pip install "pypdfbox[cjk]"`
*and* the env var are in place. The marker extra is the consent
gate; the env var is the runtime gate.

**Windows: "permission denied" when overwriting a PDF.** Make sure
every `PDDocument` over the source path is closed
(`with PDDocument.load(p) as doc:` or explicit `doc.close()`)
before the rewrite. Java's lock semantics are looser than NTFS's.

**macOS: `libtiff` errors in pure-Python tests.** Pillow's macOS
wheel may use a libtiff that disagrees with imagecodecs on EOD
padding. pypdfbox tests already skip post-EOD assertions; if your
own code hits this, treat past-EOD bytes as undefined.

If the trouble is something else, please open an issue at
<https://github.com/mehdyhaghy/pypdfbox/issues> with the full
traceback, the OS, the Python version, and the output of
`pip freeze | grep -E '(pypdfbox|cryptography|Pillow|skia|imagecodecs|numpy|fontTools)'`.

## Next steps

- [Build guide](build.md) — develop against a source checkout.
- [Migration from Apache PDFBox](migration-from-pdfbox.md) — if you
  arrived from the Java project.
- [Rendering guide](guides/rendering.md) — first user guide if you
  installed pypdfbox to rasterise pages.
