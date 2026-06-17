"""Live Apache PDFBox parity for ``ExtractImages.write2file`` (wave 1489).

Where :mod:`test_extract_images_oracle` pins the graphics-engine *walk*
(per-image metadata, de-dup, monotonic counter), this module pins the
**file-writing dispatch**: the ``write2file`` extension routing and — crucially —
the JPEG *direct passthrough* byte parity that upstream preserves for
DeviceGray/DeviceRGB DCT images.

The ``ExtractImagesWrite2FileProbe`` Java probe builds a four-image fixture and
runs the *real* ``org.apache.pdfbox.tools.ExtractImages`` CLI over it, then emits
for each produced file:

* ``rawsha`` — sha256 of the on-disk bytes (byte parity for the JPEG
  passthrough path; PNG encoder bytes differ between Java2D and Pillow so PNG
  ``rawsha`` is *not* asserted),
* ``dim`` + ``pixsha`` — width/height and sha256 of the decoded RGB(A) pixel
  bytes (a reproducible digest that survives container-encoder differences).

pypdfbox runs the same extraction (its real :class:`ExtractImages`) over the
identical PDF bytes. The assertions are:

* same set of output filenames (so naming + suffix dispatch + de-dup match),
* the ``.jpg`` file is **byte-identical** (raw DCT stream copied verbatim),
* every file's **decoded-pixel digest** matches upstream's.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PIL import Image

from pypdfbox.tools.extract_images import ExtractImages
from tests.oracle.harness import requires_oracle, run_probe_text


def _parse_java(summary: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for line in summary.splitlines():
        parts = line.split()
        if not parts or parts[0] != "file":
            continue
        name = parts[1]
        fields = {}
        i = 2
        while i + 1 < len(parts):
            fields[parts[i]] = parts[i + 1]
            i += 2
        out[name] = fields
    return out


def _pixel_digest(path: Path) -> tuple[str, str]:
    """Return ``(dim, pixsha)`` for ``path`` matching the probe's encoding:
    RGB row-major bytes, plus an alpha byte per pixel only when the image has
    an alpha channel."""
    with Image.open(path) as im:
        has_alpha = im.mode in ("RGBA", "LA", "PA") or "A" in im.getbands()
        conv = im.convert("RGBA") if has_alpha else im.convert("RGB")
        dim = f"{im.width}x{im.height}"
        digest = hashlib.sha256(conv.tobytes()).hexdigest()
    return dim, digest


@requires_oracle
def test_write2file_matches_pdfbox(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.pdf"
    java_outdir = tmp_path / "java_out"
    java_summary = run_probe_text(
        "ExtractImagesWrite2FileProbe", str(fixture), str(java_outdir)
    )
    java = _parse_java(java_summary)

    # pypdfbox extraction over the SAME fixture bytes.
    py_outdir = tmp_path / "py_out"
    py_outdir.mkdir()
    runner = ExtractImages()
    runner.infile = fixture
    runner.prefix = str(py_outdir / "img")
    assert runner.call() == 0

    py_files = sorted(p.name for p in py_outdir.iterdir())
    assert py_files == sorted(java.keys()), (
        f"filename/dedup divergence: java={sorted(java.keys())} py={py_files}"
    )

    for name, jfields in java.items():
        py_path = py_outdir / name
        # JPEG passthrough → byte-for-byte identical raw DCT stream.
        if name.endswith(".jpg"):
            py_raw = hashlib.sha256(py_path.read_bytes()).hexdigest()
            assert py_raw == jfields["rawsha"], (
                f"{name}: JPEG passthrough not byte-identical "
                f"(java={jfields['rawsha']} py={py_raw})"
            )
        # Every file: decoded-pixel digest parity.
        if "pixsha" in jfields:
            dim, pixsha = _pixel_digest(py_path)
            assert dim == jfields["dim"], f"{name}: dim {dim} != {jfields['dim']}"
            assert pixsha == jfields["pixsha"], (
                f"{name}: decoded-pixel digest divergence "
                f"(java={jfields['pixsha']} py={pixsha})"
            )


@requires_oracle
def test_write2file_dedups_repeated_xobject(tmp_path: Path) -> None:
    """The fixture draws the JPEG XObject on both pages; de-dup means exactly
    three files are produced (jpg + flate png + masked png), not four."""
    fixture = tmp_path / "fixture.pdf"
    java_outdir = tmp_path / "java_out"
    java_summary = run_probe_text(
        "ExtractImagesWrite2FileProbe", str(fixture), str(java_outdir)
    )
    count_line = next(
        ln for ln in java_summary.splitlines() if ln.startswith("count ")
    )
    assert count_line == "count 3", java_summary

    py_outdir = tmp_path / "py_out"
    py_outdir.mkdir()
    runner = ExtractImages()
    runner.infile = fixture
    runner.prefix = str(py_outdir / "img")
    runner.call()
    assert len(list(py_outdir.iterdir())) == 3
