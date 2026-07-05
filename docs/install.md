# Install

This guide covers everything needed to get `pypdfbox` running, on
both binary installs and source builds. For a one-line answer, see
the [project README](../README.md). This page is the full version.

## Python version support

pypdfbox requires **CPython 3.12 or newer** (tested on 3.12, 3.13,
and 3.14). Older releases are not supported. On 3.14 the free-threaded
("nogil") build is additionally available for parallel parsing and
rendering work where the user opts in; the regular GIL build is the
default on every supported version.

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

JBIG2 decoding (`/JBIG2Decode`) is supported by a **first-party
pure-Python decoder** in `pypdfbox/jbig2/`, ported from the Apache-2.0
`apache/pdfbox-jbig2` project (the decoder upstream PDFBox uses). It
adds no dependency and no native code — the GPL `jbig2-parser` it
replaced was removed under the permissive-license policy. The port is
differential-tested bit-exact against the bundled Java JBIG2 plugin.

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

| OS                  | Architecture    | Status        | Notes                                  |
|---------------------|-----------------|---------------|----------------------------------------|
| Linux (glibc)       | x86_64          | supported     | Wheels published for all native deps.  |
| Linux (glibc)       | aarch64 / arm64 | supported     | Wheels published for all native deps.  |
| Linux (musl/Alpine) | x86_64 / arm64  | not supported | `pip install pypdfbox` **fails** — `skia-python` and `imagecodecs` (hard deps) publish no musllinux wheels. Use a glibc image; see the Alpine note below. |
| macOS               | arm64           | supported     | M-series Macs. Primary dev platform.   |
| macOS               | x86_64          | supported (source build) | Intel Macs. `cryptography` publishes no macOS x86_64 wheel, so pip compiles it from source — a Rust toolchain is required (see the `cryptography` note below). |
| Windows             | x86_64          | supported     | Cross-platform issues called out below. |
| Windows             | ARM64           | not supported | `cryptography` does not publish `win_arm64` wheels (dropped upstream in 46.0.4); out of scope. |
| Windows             | x86 (32-bit)    | not supported | `cryptography` removed 32-bit Windows support in 49.0; out of scope. |

**Alpine / musl note.** Installing pypdfbox on Alpine currently
**fails**: `skia-python` and `imagecodecs` are required dependencies and
neither ships a musllinux wheel, so pip cannot resolve the dependency
set (it errors with *"No matching distribution found for imagecodecs"*).
The core's other native deps (`cryptography`, `Pillow`, `numpy`,
`fontTools`) *do* publish musllinux wheels, so a future optional-extras
split could enable a rendering-free core install — but as shipped, use a
**glibc base image** such as `python:3.12-slim` instead of
`python:3.12-alpine`. This is also the wider Python-ecosystem
recommendation for native-heavy dependency stacks.

**Minimal images and rendering — required system libraries.** The
renderer (`skia-python`) loads system OpenGL/EGL and fontconfig
libraries at import time. Minimal base images (`-slim`, distroless)
omit them, so `import pypdfbox.rendering` fails with
`ImportError: libEGL.so.1: cannot open shared object file` until they
are installed. On Debian / `python:3.12-slim`:

```sh
apt-get update && apt-get install -y libegl1 libgl1 libgles2 libfontconfig1
```

The non-rendering core (parsing, writing, text extraction, encryption)
needs none of these and runs on a bare `slim` image. Note the GL/font
libraries are **not** present in any stock `python:3.12` image —
neither `-slim` *nor* the full Debian image — so the `apt-get` step
above is required for rendering regardless of which you start from.
This is the same `libGL`/`libEGL` system requirement that
`opencv-python`, PyQt, and other native graphics wheels have; per
manylinux policy these driver-coupled libraries are deliberately not
vendored into wheels.

Cross-platform behaviours that the test suite actively guards
against (a non-exhaustive list):

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
for all standard platforms **except Intel (x86_64) macOS** — upstream
dropped that wheel target, so on an Intel Mac pip falls back to a
source build. A source install needs a Rust toolchain. On macOS,
`xcode-select --install` plus `rustup` is enough. On Linux,
`pkg-config`, OpenSSL headers, and a Rust toolchain. On Windows, the
Rust MSVC toolchain.

### `Pillow`

Pre-built wheels exist for every supported platform. Source installs
need libjpeg-turbo, zlib, and (for full feature parity) libtiff,
LittleCMS, and FreeType headers.

### `skia-python`

Pre-built wheels exist for x86_64 macOS / Linux / Windows and arm64
macOS / Linux. The Linux ARM wheel landed relatively recently — if
you are on a very old `pip` (<23), upgrade `pip` first or you may
see "no matching distribution found" for the ARM wheel. **No
musllinux wheels** are published, so rendering is unavailable on
Alpine — use a glibc base image (see the platform matrix above).

### `imagecodecs`

Pre-built wheels exist for the standard platforms (macOS, glibc
Linux, Windows). **No musllinux wheels** are published, so the
JPEG/JPEG2000 filter path is unavailable on Alpine. Source installs
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
