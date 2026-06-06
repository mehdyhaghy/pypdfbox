"""Live PDFBox differential parity for the **model-layer** mesh-shading
decoder — the bit-stream reader that turns a Type 4 / 5 free-form / lattice
Gouraud mesh stream into decoded ``(x, y)`` vertices and per-vertex colours,
*before* any rasterisation.

The render-grid oracles (``test_mesh_shading_oracle.py`` etc.) compare the
painted page; they can mask a parsing bug that happens to interpolate into a
visually similar gradient, and — crucially — every fixture they build uses
``BitsPerCoordinate = BitsPerComponent = BitsPerFlag = 8``, so each vertex's
data already lands on a byte boundary. That hides the **per-vertex byte
alignment** mandated by PDF 32000-1 §8.7.4.5.5:

    "Each set of vertex data shall occupy a whole number of bytes. If the
    total number of bits required is not divisible by 8, the last data byte
    for each vertex is padded at the end with extra bits, which shall be
    ignored."

Apache PDFBox implements this in ``PDTriangleBasedShadingType.readVertex``
(``getBitOffset()`` → ``readBits(8 - bitOffset)``). pypdfbox originally omitted
it; with a 12-bit coordinate / 12-bit component / 8-bit flag layout (vertex =
8 + 12 + 12 + 36 = 68 bits, **not** a multiple of 8) every vertex after the
first was read from the wrong bit offset, corrupting the whole mesh.

This module pins the exact decoded geometry against PDFBox via
``oracle/probes/MeshVertexDumpProbe.java`` — a probe living *in* the
``org.apache.pdfbox.pdmodel.graphics.shading`` package so it can call the
package-private ``collectTriangles(...)`` and read ``ShadedTriangle.corner`` /
``.color``. Coordinates and colours must match to 1e-4 (both engines use the
same ``dstMin + src*(dstMax-dstMin)/srcMax`` dequantisation).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import oracle_available

_PAGE = 100.0
_TOL = 1e-3  # %.6f probe output vs Python float; coord range 0..100

requires_oracle = pytest.mark.skipif(
    not oracle_available(),
    reason="live PDFBox oracle unavailable — run oracle/download_jars.sh",
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ORACLE = _REPO_ROOT / "oracle"
_JARS_DIR = _ORACLE / "jars"
_PROBES = _ORACLE / "probes"
_BUILD = _ORACLE / "build"
_PROBE_FQN = "org.apache.pdfbox.pdmodel.graphics.shading.MeshVertexDumpProbe"


def _classpath() -> str:
    jars = sorted(str(p) for p in _JARS_DIR.glob("*.jar"))
    return os.pathsep.join([*jars, str(_BUILD)])


def _run_dump_probe(pdf: Path, shading_name: str) -> str:
    """Compile (if stale) and run the packaged MeshVertexDumpProbe.

    The shared harness keys the compiled class on the bare probe name; this
    probe is *package-scoped* (so it can reach package-private upstream API),
    so it has a dedicated runner that invokes it by fully-qualified name.
    """
    src = _PROBES / "MeshVertexDumpProbe.java"
    cls = _BUILD / "org/apache/pdfbox/pdmodel/graphics/shading/MeshVertexDumpProbe.class"
    if not cls.is_file() or cls.stat().st_mtime < src.stat().st_mtime:
        _BUILD.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["javac", "-cp", _classpath(), "-d", str(_BUILD), str(src)],
            check=True,
            capture_output=True,
        )
    result = subprocess.run(
        ["java", "-cp", _classpath(), _PROBE_FQN, str(pdf), shading_name],
        check=True,
        capture_output=True,
    )
    return result.stdout.decode("utf-8")


# ---------------------------------------------------------------------------
# bit-packed fixture builder (non-byte-aligned vertex widths)
# ---------------------------------------------------------------------------


class _BitWriter:
    """MSB-first bit writer mirroring the reader in pd_mesh_based_shading_type."""

    def __init__(self) -> None:
        self._bits: list[int] = []

    def write(self, value: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def align(self) -> None:
        while len(self._bits) % 8 != 0:
            self._bits.append(0)

    def to_bytes(self) -> bytes:
        self.align()
        out = bytearray()
        for i in range(0, len(self._bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | self._bits[i + j]
            out.append(byte)
        return bytes(out)


def _q(value: float, lo: float, hi: float, bits: int) -> int:
    src_max = (1 << bits) - 1
    if hi == lo:
        return 0
    raw = round((value - lo) / (hi - lo) * src_max)
    return max(0, min(src_max, raw))


def _decode_array() -> COSArray:
    arr = COSArray()
    for v in (0.0, 100.0, 0.0, 100.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        arr.add(COSFloat(v))
    return arr


def _save(shading: COSStream, out: Path) -> Path:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE, _PAGE))
    doc.add_page(page)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("Shading"), COSName.get_pdf_name("Sh0"), shading
    )
    contents = COSStream()
    contents.set_raw_data(b"/Sh0 sh\n")
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    doc.save(str(out))
    doc.close()
    return out


# Vertex layout that is deliberately NOT a multiple of 8 bits, so per-vertex
# byte alignment is load-bearing:
#   type4: flag(8) + x(12) + y(12) + r(12) + g(12) + b(12) = 68 bits
#   type5: x(12) + y(12) + r(12) + g(12) + b(12)           = 60 bits
_BC = 12
_BCOMP = 12
_BF = 8

_CORNERS = [
    (0.0, 0.0, 1.0, 0.0, 0.0),  # red
    (100.0, 0.0, 0.0, 1.0, 0.0),  # green
    (0.0, 100.0, 0.0, 0.0, 1.0),  # blue
    (100.0, 100.0, 1.0, 1.0, 1.0),  # white
]


def _base_shading(shading_type: int) -> COSStream:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), shading_type)
    sh.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), _BC)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), _BCOMP)
    sh.set_item(COSName.get_pdf_name("Decode"), _decode_array())
    return sh


def _build_type4_unaligned(out: Path) -> Path:
    sh = _base_shading(4)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), _BF)
    bw = _BitWriter()

    def vtx(flag: int, x: float, y: float, r: float, g: float, b: float) -> None:
        bw.write(flag, _BF)
        bw.write(_q(x, 0, 100, _BC), _BC)
        bw.write(_q(y, 0, 100, _BC), _BC)
        bw.write(_q(r, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(g, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(b, 0, 1, _BCOMP), _BCOMP)
        bw.align()  # per-vertex byte padding (spec)

    # Triangle 1 (flag 0): red, green, blue.
    vtx(0, *_CORNERS[0])
    vtx(0, *_CORNERS[1])
    vtx(0, *_CORNERS[2])
    # Triangle 2 (flag 0): green, blue, white.
    vtx(0, *_CORNERS[1])
    vtx(0, *_CORNERS[2])
    vtx(0, *_CORNERS[3])
    sh.set_raw_data(bw.to_bytes())
    return _save(sh, out)


def _build_type5_unaligned(out: Path) -> Path:
    sh = _base_shading(5)
    sh.set_int(COSName.get_pdf_name("VerticesPerRow"), 2)
    bw = _BitWriter()

    def vtx(x: float, y: float, r: float, g: float, b: float) -> None:
        bw.write(_q(x, 0, 100, _BC), _BC)
        bw.write(_q(y, 0, 100, _BC), _BC)
        bw.write(_q(r, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(g, 0, 1, _BCOMP), _BCOMP)
        bw.write(_q(b, 0, 1, _BCOMP), _BCOMP)
        bw.align()  # per-vertex byte padding (spec)

    for x, y, r, g, b in _CORNERS:
        vtx(x, y, r, g, b)
    sh.set_raw_data(bw.to_bytes())
    return _save(sh, out)


_BUILDERS = {
    "type4_freeform_12bit": _build_type4_unaligned,
    "type5_lattice_12bit": _build_type5_unaligned,
}


# ---------------------------------------------------------------------------
# probe-output parsing + pypdfbox decode
# ---------------------------------------------------------------------------


def _parse_dump(text: str) -> list[list[float]]:
    lines = text.strip().splitlines()
    header = lines[0].split()
    assert header[0] == "TRIANGLES", f"unexpected probe header: {lines[0]}"
    count = int(header[1])
    rows = [[float(v) for v in ln.split()] for ln in lines[1 : 1 + count]]
    assert len(rows) == count
    return rows


def _pypdfbox_dump(pdf: Path) -> list[list[float]]:
    with PDDocument.load(pdf) as doc:
        page = doc.get_page(0)
        shading = page.get_resources().get_shading(COSName.get_pdf_name("Sh0"))
        triangles = shading.collect_triangles()
    rows: list[list[float]] = []
    for pts, cols in triangles:
        row: list[float] = []
        for x, y in pts:
            row += [float(x), float(y)]
        for comps in cols:
            row += [float(c) for c in comps]
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_mesh_vertex_decode_matches_pdfbox(label: str, tmp_path: Path) -> None:
    fixture = _BUILDERS[label](tmp_path / f"{label}.pdf")
    java_rows = _parse_dump(_run_dump_probe(fixture, "Sh0"))
    py_rows = _pypdfbox_dump(fixture)

    assert len(py_rows) == len(java_rows), (
        f"{label}: triangle count diverges from PDFBox: "
        f"pypdfbox={len(py_rows)} java={len(java_rows)} — a wrong per-vertex "
        f"byte alignment collapses the mesh into fewer / corrupt triangles"
    )
    for ti, (jr, pr) in enumerate(zip(java_rows, py_rows, strict=True)):
        assert len(pr) == len(jr), (
            f"{label} tri {ti}: field count diverges {len(pr)} vs {len(jr)}"
        )
        for fi, (jv, pv) in enumerate(zip(jr, pr, strict=True)):
            assert abs(jv - pv) <= _TOL, (
                f"{label} tri {ti} field {fi}: pypdfbox={pv:.6f} "
                f"java={jv:.6f} (|diff|={abs(jv - pv):.6f} > {_TOL}) — "
                f"decoded vertex coord/colour diverges (dequant or bit "
                f"alignment)"
            )


@requires_oracle
def test_unaligned_layout_actually_needs_alignment(tmp_path: Path) -> None:
    """Guard: prove the fixture's vertex width is genuinely non-byte-aligned,
    so this oracle exercises the per-vertex padding path. The type-4 vertex is
    flag(8)+x(12)+y(12)+3*comp(12) = 68 bits; 68 % 8 != 0 confirms a decoder
    without alignment would desync after the first vertex."""
    vertex_bits = _BF + 2 * _BC + 3 * _BCOMP
    assert vertex_bits % 8 != 0, (
        f"fixture vertex width {vertex_bits} is byte-aligned — the test would "
        f"not exercise the padding path"
    )
    # And confirm PDFBox itself yields the full 2-triangle mesh (not a
    # truncated / corrupt parse) so the parity comparison is meaningful.
    fixture = _build_type4_unaligned(tmp_path / "guard.pdf")
    java_rows = _parse_dump(_run_dump_probe(fixture, "Sh0"))
    assert len(java_rows) == 2, (
        f"expected PDFBox to decode 2 triangles, got {len(java_rows)}"
    )
