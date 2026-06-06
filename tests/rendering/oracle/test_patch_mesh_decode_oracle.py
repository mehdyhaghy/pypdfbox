"""Live PDFBox differential parity for the **model-layer** patch-mesh
decoder — the bit-stream reader that turns a Type 6 (Coons) / Type 7
(tensor-product) patch-mesh stream into decoded control points and corner
colours, *before* any Bezier / tensor surface evaluation or triangulation.

Companion to ``test_mesh_vertex_decode_oracle.py`` (which pins the Types 4/5
Gouraud vertex decoder). The render-grid oracles
(``test_mesh_shading_oracle.py`` / ``test_patch_mesh_flag_oracle.py``) compare
the painted page; they can mask a parsing bug that interpolates into a
visually similar gradient, and the colour swap / hole guards only catch gross
divergence. This module pins the *exact* decoded patch geometry:

* the reshaped 4x4 control grid (CoonsPatch / TensorPatch
  ``reshapeControlPoints`` — the raw-1D -> grid mapping, incl. the tensor
  interior-point placement), and
* the 4 corner colours per patch, in upstream assignment order.

Two parsing subtleties are load-bearing here and invisible to the render
oracle:

1. **No per-patch byte alignment.** Unlike Types 4/5, which byte-align each
   vertex (PDF 32000-1 §8.7.4.5.5), Types 6/7 pack control points
   contiguously with no padding. The fixtures use a 12-bit coordinate /
   12-bit component / 8-bit flag layout — a free Coons patch is
   8 + 12*(12*2) + 12*(4*3) = 8 + 288 + 144 = 440 bits, but a flag != 0
   continuation patch is 8 + 12*(8*2) + 12*(2*3) = 8 + 192 + 72 = 272 bits;
   neither sub-read lands the cursor on a byte boundary mid-stream, so a
   stray ``align_to_byte`` between control points would desync the whole
   chain.

2. **Edge-flag continuation.** A flag 1/2/3 patch reuses 4 boundary control
   points and 2 corner colours from the previous patch's shared edge
   (``Patch.getFlagNEdge`` / ``getFlagNColor``); the fixtures chain flag-0 ->
   flag-1/2/3 so the carry-over path is exercised and pinned against PDFBox.

The fingerprint comes from ``oracle/probes/PatchMeshDecodeProbe.java`` — a
probe living *in* the ``org.apache.pdfbox.pdmodel.graphics.shading`` package
so it can call package-private ``collectPatches(...)`` and read
``Patch.controlPoints`` / ``Patch.cornerColor``. Coordinates and colours must
match to 1e-3 (both engines use the same
``dstMin + src*(dstMax-dstMin)/srcMax`` dequantisation; the probe formats
``%.6f``).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.shading.coons_patch import CoonsPatch
from pypdfbox.pdmodel.graphics.shading.tensor_patch import TensorPatch
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
_PROBE_FQN = "org.apache.pdfbox.pdmodel.graphics.shading.PatchMeshDecodeProbe"


def _classpath() -> str:
    jars = sorted(str(p) for p in _JARS_DIR.glob("*.jar"))
    return os.pathsep.join([*jars, str(_BUILD)])


def _run_decode_probe(pdf: Path, shading_name: str) -> str:
    """Compile (if stale) and run the packaged PatchMeshDecodeProbe by FQN."""
    src = _PROBES / "PatchMeshDecodeProbe.java"
    cls = (
        _BUILD
        / "org/apache/pdfbox/pdmodel/graphics/shading/PatchMeshDecodeProbe.class"
    )
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
# bit-packed fixture builder (non-byte-aligned control-point widths)
# ---------------------------------------------------------------------------


class _BitWriter:
    """MSB-first bit writer mirroring the reader in pd_mesh_based_shading_type."""

    def __init__(self) -> None:
        self._bits: list[int] = []

    def write(self, value: int, n: int) -> None:
        for i in range(n - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def to_bytes(self) -> bytes:
        # Pad only the FINAL byte (stream-level), never per patch.
        bits = list(self._bits)
        while len(bits) % 8 != 0:
            bits.append(0)
        out = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[i + j]
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


# Non-byte-multiple widths so per-patch byte alignment is load-bearing.
_BC = 12
_BCOMP = 12
_BF = 8

# Four strongly-chromatic per-component-distinct corner colours.
_C0 = (1.0, 0.0, 0.0)
_C1 = (0.0, 1.0, 0.0)
_C2 = (1.0, 1.0, 1.0)
_C3 = (0.0, 0.0, 1.0)
_TOP_C2 = (1.0, 1.0, 0.0)
_TOP_C3 = (1.0, 0.0, 1.0)


def _base_shading(shading_type: int) -> COSStream:
    sh = COSStream()
    sh.set_int(COSName.get_pdf_name("ShadingType"), shading_type)
    sh.set_item(COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB"))
    sh.set_int(COSName.get_pdf_name("BitsPerCoordinate"), _BC)
    sh.set_int(COSName.get_pdf_name("BitsPerComponent"), _BCOMP)
    sh.set_int(COSName.get_pdf_name("BitsPerFlag"), _BF)
    sh.set_item(COSName.get_pdf_name("Decode"), _decode_array())
    return sh


def _write_xy(bw: _BitWriter, x: float, y: float) -> None:
    bw.write(_q(x, 0, 100, _BC), _BC)
    bw.write(_q(y, 0, 100, _BC), _BC)


def _write_col(bw: _BitWriter, rgb: tuple[float, float, float]) -> None:
    for c in rgb:
        bw.write(_q(c, 0, 1, _BCOMP), _BCOMP)


# Curved, non-degenerate boundary so reshape / interior placement is exercised
# (straight edges would collapse calcLevel branches; geometry still pinned).
_BOTTOM = [
    (0, 0), (30, 8), (66, -4), (100, 0),      # p0..p3 bottom L->R
    (96, 18), (104, 34), (100, 50),           # p4..p6 right edge up
    (66, 54), (33, 46),                       # p7..p8 top edge R->L
    (0, 50),                                  # p9 top-left
    (4, 34), (-4, 17),                        # p10..p11 left edge down
]
_TOP_NEW = [
    (96, 68), (104, 84), (100, 100),          # p4..p6 right edge up
    (66, 104), (33, 96),                      # p7..p8 top edge R->L
    (0, 100),                                 # p9 top-left
    (4, 84), (-4, 67),                        # p10..p11 left edge down
]
_BOTTOM_INTERIOR = [(33, 17), (66, 17), (66, 33), (33, 33)]


def _build_type6_free(out: Path) -> Path:
    """Single free (flag 0) Coons patch — 12 points + 4 corners."""
    sh = _base_shading(6)
    bw = _BitWriter()
    bw.write(0, _BF)
    for x, y in _BOTTOM:
        _write_xy(bw, x, y)
    for rgb in (_C0, _C1, _C2, _C3):
        _write_col(bw, rgb)
    sh.set_raw_data(bw.to_bytes())
    return _save(sh, out)


def _build_type6_flag2(out: Path) -> Path:
    """flag-0 patch + flag-2 continuation (shares points[6..9] + colours[2,3])."""
    sh = _base_shading(6)
    bw = _BitWriter()
    bw.write(0, _BF)
    for x, y in _BOTTOM:
        _write_xy(bw, x, y)
    for rgb in (_C0, _C1, _C2, _C3):
        _write_col(bw, rgb)
    bw.write(2, _BF)
    for x, y in _TOP_NEW:
        _write_xy(bw, x, y)
    for rgb in (_TOP_C2, _TOP_C3):
        _write_col(bw, rgb)
    sh.set_raw_data(bw.to_bytes())
    return _save(sh, out)


def _build_type6_flag1(out: Path) -> Path:
    """flag-0 patch + flag-1 continuation (shares points[3..6] + colours[1,2])."""
    sh = _base_shading(6)
    bw = _BitWriter()
    bw.write(0, _BF)
    for x, y in _BOTTOM:
        _write_xy(bw, x, y)
    for rgb in (_C0, _C1, _C2, _C3):
        _write_col(bw, rgb)
    bw.write(1, _BF)
    # Flag 1 reuses previous points[3,4,5,6] as its leading edge; supply 8 new
    # boundary points + 2 new corner colours. Kept within the [0,100] decode
    # range so each point dequantises to a distinct value (no clamp collapse).
    new_boundary = [
        (88, 60), (72, 72), (50, 80),         # p4..p6
        (40, 92), (18, 84),                   # p7..p8
        (8, 96),                              # p9
        (20, 70), (12, 58),                   # p10..p11
    ]
    for x, y in new_boundary:
        _write_xy(bw, x, y)
    for rgb in (_TOP_C2, _TOP_C3):
        _write_col(bw, rgb)
    sh.set_raw_data(bw.to_bytes())
    return _save(sh, out)


def _build_type7_free(out: Path) -> Path:
    """Single free (flag 0) tensor patch — 16 points + 4 corners."""
    sh = _base_shading(7)
    bw = _BitWriter()
    bw.write(0, _BF)
    for x, y in (*_BOTTOM, *_BOTTOM_INTERIOR):
        _write_xy(bw, x, y)
    for rgb in (_C0, _C1, _C2, _C3):
        _write_col(bw, rgb)
    sh.set_raw_data(bw.to_bytes())
    return _save(sh, out)


def _build_type7_flag3(out: Path) -> Path:
    """flag-0 tensor patch + flag-3 continuation (shares points[9..11,0] +
    colours[3,0]); supplies 8 new boundary + 4 interior + 2 colours."""
    sh = _base_shading(7)
    bw = _BitWriter()
    bw.write(0, _BF)
    for x, y in (*_BOTTOM, *_BOTTOM_INTERIOR):
        _write_xy(bw, x, y)
    for rgb in (_C0, _C1, _C2, _C3):
        _write_col(bw, rgb)
    # Flag 3 reuses previous points[9,10,11,0] as its leading edge. The 8 new
    # boundary points + 4 interior points + 2 new corner colours follow. All
    # kept within the [0,100] decode range so points dequantise distinctly.
    bw.write(3, _BF)
    new_boundary = [
        (12, 66), (8, 82), (16, 96),          # p4..p6
        (30, 92), (22, 78),                   # p7..p8
        (40, 100),                            # p9
        (28, 70), (20, 58),                   # p10..p11
    ]
    new_interior = [(12, 70), (24, 72), (30, 86), (18, 88)]
    for x, y in (*new_boundary, *new_interior):
        _write_xy(bw, x, y)
    for rgb in (_TOP_C2, _TOP_C3):
        _write_col(bw, rgb)
    sh.set_raw_data(bw.to_bytes())
    return _save(sh, out)


_BUILDERS = {
    "type6_free_12bit": (_build_type6_free, 12),
    "type6_flag1_12bit": (_build_type6_flag1, 12),
    "type6_flag2_12bit": (_build_type6_flag2, 12),
    "type7_free_12bit": (_build_type7_free, 16),
    "type7_flag3_12bit": (_build_type7_flag3, 16),
}


# ---------------------------------------------------------------------------
# probe-output parsing + pypdfbox decode
# ---------------------------------------------------------------------------


def _parse_dump(text: str) -> list[tuple[list[float], list[float]]]:
    lines = text.strip().splitlines()
    header = lines[0].split()
    assert header[0] == "PATCHES", f"unexpected probe header: {lines[0]}"
    count = int(header[1])
    patches: list[tuple[list[float], list[float]]] = []
    for i in range(count):
        grid = [float(v) for v in lines[1 + 2 * i].split()]
        colors = [float(v) for v in lines[2 + 2 * i].split()]
        patches.append((grid, colors))
    return patches


def _pypdfbox_dump(
    pdf: Path, control_points: int
) -> list[tuple[list[float], list[float]]]:
    with PDDocument.load(pdf) as doc:
        page = doc.get_page(0)
        shading = page.get_resources().get_shading(COSName.get_pdf_name("Sh0"))
        parsed = shading.parse_patches()
    reshape = (
        TensorPatch.reshape_control_points
        if control_points == 16
        else CoonsPatch.reshape_control_points
    )
    out: list[tuple[list[float], list[float]]] = []
    for patch in parsed:
        grid_rows = reshape(patch.points)
        grid: list[float] = []
        for row in grid_rows:
            for x, y in row:
                grid += [float(x), float(y)]
        colors: list[float] = []
        for comps in patch.colors:
            colors += [float(c) for c in comps]
        out.append((grid, colors))
    return out


# ---------------------------------------------------------------------------
# differential tests
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize("label", list(_BUILDERS), ids=list(_BUILDERS))
def test_patch_decode_matches_pdfbox(label: str, tmp_path: Path) -> None:
    builder, control_points = _BUILDERS[label]
    fixture = builder(tmp_path / f"{label}.pdf")
    java = _parse_dump(_run_decode_probe(fixture, "Sh0"))
    py = _pypdfbox_dump(fixture, control_points)

    assert len(py) == len(java), (
        f"{label}: patch count diverges from PDFBox: pypdfbox={len(py)} "
        f"java={len(java)} — a dropped flag continuation or a stray per-patch "
        f"byte alignment desyncs the stream"
    )
    for pi, ((jg, jc), (pg, pc)) in enumerate(zip(java, py, strict=True)):
        assert len(pg) == len(jg) == 32, (
            f"{label} patch {pi}: control-grid field count "
            f"py={len(pg)} java={len(jg)} (expected 32)"
        )
        assert len(pc) == len(jc), (
            f"{label} patch {pi}: colour field count py={len(pc)} java={len(jc)}"
        )
        for fi, (jv, pv) in enumerate(zip(jg, pg, strict=True)):
            assert abs(jv - pv) <= _TOL, (
                f"{label} patch {pi} grid field {fi}: pypdfbox={pv:.6f} "
                f"java={jv:.6f} (|diff|={abs(jv - pv):.6f} > {_TOL}) — decoded "
                f"control point diverges (dequant / reshape / flag carry-over)"
            )
        for fi, (jv, pv) in enumerate(zip(jc, pc, strict=True)):
            assert abs(jv - pv) <= _TOL, (
                f"{label} patch {pi} colour field {fi}: pypdfbox={pv:.6f} "
                f"java={jv:.6f} (|diff|={abs(jv - pv):.6f} > {_TOL}) — decoded "
                f"corner colour diverges (dequant / flag carry-over)"
            )


@requires_oracle
def test_patches_not_byte_aligned_per_patch(tmp_path: Path) -> None:
    """Guard: prove the fixtures exercise the *no per-read / per-patch byte
    alignment* contract (Types 6/7, unlike Types 4/5 which byte-align per
    vertex). A single 12-bit coordinate / 12-bit colour component is not a
    whole number of bytes, so the read cursor walks through bit offsets
    4, 0, 4, 0, ... — never realigning by padding. The decoder must track the
    running bit offset across every read; a stray ``align_to_byte`` between
    reads or between patches would desync the chain (see the negative-control
    below)."""
    assert _BC % 8 != 0, (
        "coordinate width is a whole number of bytes — reshape/decode would "
        "not exercise the sub-byte read cadence"
    )
    assert _BCOMP % 8 != 0, "colour-component width is a whole number of bytes"
    # And confirm PDFBox itself yields 2 patches for the flag-2 fixture.
    fixture = _build_type6_flag2(tmp_path / "guard.pdf")
    java = _parse_dump(_run_decode_probe(fixture, "Sh0"))
    assert len(java) == 2, f"expected PDFBox to decode 2 patches, got {len(java)}"


def test_per_read_alignment_would_desync(tmp_path: Path) -> None:
    """Negative control (no oracle needed): a decoder that byte-aligned after
    each control-point read (the wrong behaviour — that rule is for Types 4/5
    vertices only) produces grossly different geometry on the 12-bit fixture,
    proving the parser path is genuinely sensitive to the alignment contract
    and the oracle above is not vacuously green."""
    from pypdfbox.pdmodel.graphics.shading import pd_mesh_based_shading_type as mod

    fixture = _build_type6_free(tmp_path / "ctrl.pdf")
    correct = _pypdfbox_dump(fixture, 12)

    orig = mod._PatchBitReader.read_bits

    def aligning_read_bits(self: mod._PatchBitReader, n: int) -> int:
        value = orig(self, n)
        self.align_to_byte()  # WRONG for patches — only Types 4/5 do this
        return value

    mod._PatchBitReader.read_bits = aligning_read_bits  # type: ignore[method-assign]
    try:
        with PDDocument.load(fixture) as doc:
            page = doc.get_page(0)
            shading = page.get_resources().get_shading(COSName.get_pdf_name("Sh0"))
            broken_parsed = shading.parse_patches()
    finally:
        mod._PatchBitReader.read_bits = orig  # type: ignore[method-assign]

    # The spurious per-read alignment desyncs the contiguous 12-bit stream:
    # it either drops the patch entirely (EOF mid-patch) or yields grossly
    # different control points. Either outcome proves the parser is sensitive
    # to the no-alignment contract, so the oracle above is not vacuously green.
    if not broken_parsed:
        return
    broken: list[float] = []
    for row in CoonsPatch.reshape_control_points(broken_parsed[0].points):
        for x, y in row:
            broken += [float(x), float(y)]
    correct_grid = correct[0][0]
    assert any(
        abs(a - b) > 1.0 for a, b in zip(correct_grid, broken, strict=False)
    ), "per-read alignment did not change the decode — guard is vacuous"
