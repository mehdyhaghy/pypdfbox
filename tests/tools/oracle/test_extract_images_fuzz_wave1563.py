"""Differential-fuzz parity for the ``ExtractImages`` CLI tool (wave 1563).

Where :mod:`test_extract_images_oracle` pins the graphics-engine walk on one
fixture and :mod:`test_extract_images_write2file_oracle` pins the
``write2file`` byte/pixel dispatch on a four-image fixture, this module sweeps a
battery of *scenario* PDFs through the real
:class:`pypdfbox.tools.extract_images.ExtractImages` and compares the produced
file set (count + name + suffix + decoded dimensions) against the real
Apache PDFBox 3.0.7 ``ExtractImages`` CLI on the *same PDF bytes*.

The ``ExtractImagesToolFuzzProbe`` Java probe builds each scenario PDF into a
shared workdir and runs the upstream CLI over it, emitting one
``scenario <name> count <n>`` line per scenario followed by ``  file <name>
<wxh>`` lines (files sorted by name, ``-`` dim when ImageIO can't decode). Each
scenario exercises a distinct angle of the tool:

* ``single_rgb`` / ``single_jpeg`` — one image, png vs jpg-passthrough suffix,
* ``multi`` — three distinct images, monotonic ``prefix-N`` numbering,
* ``dedup_same_page`` / ``dedup_cross_page`` — one XObject drawn twice → one
  file, de-dup by COS identity within and across pages,
* ``no_images`` / ``unreferenced`` — zero files (the walk only extracts images
  reached through a ``Do`` operator, never a raw resource-dict entry),
* ``direct_jpeg`` — ``-useDirectJPEG`` still yields one ``.jpg``,
* ``indexed`` — an Indexed-colorspace image exports as ``.png``,
* ``mask`` — an explicit ``/Mask`` forces the ``.png`` path (no jpg passthrough),
* ``stencil`` — a 1-bit image-mask exports as ``.png``,
* ``nested_form`` — an image drawn inside a form XObject is still extracted,
* ``multipage`` — three pages, one distinct image each → three files,
* ``gray`` — a DeviceGray image exports as ``.png``,
* ``mixed`` — jpeg + flate + a cross-page de-dup'd jpeg → two files.

We compare the file **set + suffix + decoded dimensions**, not raw pixel bytes,
so parity holds across PNG-encoder differences between Java2D and Pillow.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from pypdfbox.tools.extract_images import ExtractImages
from tests.oracle.harness import requires_oracle, run_probe_text


def _parse_java(summary: str) -> dict[str, list[tuple[str, str]]]:
    """Parse the probe output into ``{scenario: [(filename, "wxh"), ...]}``."""
    scenarios: dict[str, list[tuple[str, str]]] = {}
    current: str | None = None
    for line in summary.splitlines():
        if line.startswith("scenario "):
            parts = line.split()
            current = parts[1]
            scenarios[current] = []
        elif line.startswith("  file ") and current is not None:
            parts = line.split()
            scenarios[current].append((parts[1], parts[2]))
    return scenarios


def _dim(path: Path) -> str:
    """Decoded ``wxh`` for ``path``, or ``-`` when Pillow can't open it
    (mirrors the probe's ImageIO ``-`` for un-decodable files)."""
    try:
        with Image.open(path) as im:
            return f"{im.width}x{im.height}"
    except Exception:
        return "-"


def _pypdfbox_scenario(pdf: Path, out_dir: Path, direct_jpeg: bool) -> list[tuple[str, str]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = ExtractImages()
    runner.infile = pdf
    runner.prefix = str(out_dir / "img")
    runner.use_direct_jpeg = direct_jpeg
    assert runner.call() == 0
    files = sorted(out_dir.iterdir(), key=lambda p: p.name)
    return [(p.name, _dim(p)) for p in files]


# Scenarios that pass -useDirectJPEG (must match the probe's `directJpeg` flag).
_DIRECT_JPEG = {"direct_jpeg"}


@requires_oracle
def test_extract_images_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    work = tmp_path / "work"
    summary = run_probe_text("ExtractImagesToolFuzzProbe", str(work))
    java = _parse_java(summary)

    assert java, f"probe produced no scenarios:\n{summary}"

    py_root = tmp_path / "py"
    for name, jfiles in java.items():
        pdf = work / f"{name}.pdf"
        assert pdf.is_file(), f"probe did not write fixture {pdf}"
        direct = name in _DIRECT_JPEG
        py_files = _pypdfbox_scenario(pdf, py_root / name, direct)
        assert py_files == jfiles, (
            f"scenario {name!r} divergence:\n"
            f"  java: {jfiles}\n"
            f"  py:   {py_files}"
        )


@requires_oracle
def test_extract_images_fuzz_counts(tmp_path: Path) -> None:
    """Pin the per-scenario file counts explicitly (de-dup, zero-image, and
    nested-form claims) against upstream, independent of suffix/dim details."""
    work = tmp_path / "work"
    summary = run_probe_text("ExtractImagesToolFuzzProbe", str(work))
    java = _parse_java(summary)

    expected_counts = {
        "single_rgb": 1,
        "single_jpeg": 1,
        "multi": 3,
        "dedup_same_page": 1,
        "dedup_cross_page": 1,
        "no_images": 0,
        "unreferenced": 0,
        "direct_jpeg": 1,
        "indexed": 1,
        "mask": 1,
        "stencil": 1,
        "nested_form": 1,
        "multipage": 3,
        "gray": 1,
        "mixed": 2,
    }
    # The probe must emit exactly these scenarios.
    assert set(java.keys()) == set(expected_counts.keys()), sorted(java.keys())

    py_root = tmp_path / "py"
    for name, want in expected_counts.items():
        # Upstream agrees with our pinned expectation.
        assert len(java[name]) == want, f"java {name}: {java[name]}"
        direct = name in _DIRECT_JPEG
        py_files = _pypdfbox_scenario(work / f"{name}.pdf", py_root / name, direct)
        assert len(py_files) == want, f"py {name}: {py_files}"
