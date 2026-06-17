"""Differential ``/DCTDecode`` (JPEG / DCT) fuzz vs Apache PDFBox 3.0.7 (wave 1528).

A DCT-specific complement to the generic wave-1505 ``FilterFuzzProbe`` decode
fuzz. PDFBox's ``DCTFilter.decode`` does NOT pass the JPEG bytes through -- it
runs them through ImageIO and writes the decompressed interleaved raster
(8x8 RGB -> 192 bytes, 8x8 grayscale -> 64 bytes, 8x8 CMYK -> 256 bytes).
pypdfbox's ``DCTDecode`` mirrors that contract via imagecodecs (libjpeg-turbo)
with a Pillow fallback. Because both engines wrap libjpeg-turbo, the aligned
cases match byte-for-byte (the ``sha`` projection is identical, not merely the
length), so this wave pins the projection EXACT for them.

The crafted corpus covers the fuzz surface for this filter:

* structural edges -- empty, SOI-only, garbage, junk prefix before SOI,
  double SOI, trailing garbage after EOI;
* truncated scan data at several fractions for baseline RGB, grayscale and
  progressive JPEG (PDFBox throws once the scan is cut deep enough; a tail
  trim that still completes the scan decodes cleanly);
* colour variants -- grayscale (L), RGB, CMYK, CMYK with its Adobe APP14
  segment stripped, and progressive RGB;
* ``/DecodeParms ColorTransform`` 0 / 1 -- upstream's DCTFilter relies on the
  JPEG markers for the colour transform and ignores this entry for the actual
  decode, so 0 and 1 produce the identical raster; pypdfbox matches;
* a corrupt SOF0 marker and a zero-dimension SOF (both throw on both sides).

One genuine divergence is pinned BOTH sides as a library gap (see
``_DIVERGENT_CORPUS`` below): a forged maximum-width SOF (declared width
0xFFFF on an 8x8 scan). libjpeg-turbo as exposed by imagecodecs tolerates the
exhausted scan by padding the raster out to the declared dimensions and
returns success, whereas Java ImageIO (PDFBox) -- and, independently, Pillow --
reject the premature end-of-data and throw. There is no clean invariant that
separates this forged-oversize case from a genuinely valid, highly compressible
large image (a solid-colour 2000x2000 JPEG has the same decoded/encoded size
ratio), so forcing parity would mean either a heuristic that falsely rejects
valid images or routing every decode through Pillow -- which itself diverges
from PDFBox in the opposite direction on a barely-truncated tail (it rejects a
99%-truncated stream that PDFBox accepts). The divergence is therefore pinned,
not fixed: see CHANGES.md "Wave 1528".

The Java side is ``oracle/probes/DctDecodeFuzzProbe.java``; ``_py_dump``
reproduces the same fingerprint on the pypdfbox side.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import tempfile

import pytest
from PIL import Image

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.filter import FilterFactory
from tests.oracle.harness import requires_oracle, run_probe_text

_Case = tuple[str, bytes]


# ---------------------------------------------------------------------------
# JPEG builders (deterministic; solid-fill images keep the corpus tiny)
# ---------------------------------------------------------------------------
def _jpeg(mode: str, size: tuple[int, int], fill, **save_kw: object) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, fill).save(buf, "JPEG", **save_kw)
    return buf.getvalue()


def _set_sof_dims(data: bytes, height: int, width: int) -> bytes:
    """Overwrite the SOF0 height/width fields, forging the declared geometry.

    SOF0 layout: ``FF C0`` marker, 2-byte segment length, 1-byte precision,
    2-byte height, 2-byte width. Returns the data unchanged if no SOF0 marker
    is present.
    """
    out = bytearray(data)
    i = out.find(b"\xff\xc0")
    if i < 0:
        return bytes(out)
    out[i + 5] = (height >> 8) & 0xFF
    out[i + 6] = height & 0xFF
    out[i + 7] = (width >> 8) & 0xFF
    out[i + 8] = width & 0xFF
    return bytes(out)


def _strip_app14(data: bytes) -> bytes:
    """Remove the Adobe APP14 (``FF EE``) segment if present."""
    out = bytearray(data)
    i = out.find(b"\xff\xee")
    if i < 0:
        return bytes(out)
    seg_len = (out[i + 2] << 8) | out[i + 3]
    del out[i : i + 2 + seg_len]
    return bytes(out)


_RGB = _jpeg("RGB", (8, 8), (120, 30, 200))
_GRAY = _jpeg("L", (16, 16), 120)
_CMYK = _jpeg("CMYK", (8, 8), (10, 20, 30, 40))
_PROG = _jpeg("RGB", (16, 16), (10, 200, 50), progressive=True)
_CORRUPT_SOF = (lambda d: d[: d.find(b"\xff\xc0") + 1] + b"\x01" + d[d.find(b"\xff\xc0") + 2 :])(
    _RGB
)


def _build_aligned_corpus() -> list[_Case]:
    out: list[_Case] = []

    def add(name: str, body: bytes) -> None:
        out.append((name, body))

    # -- structural / empty edges ----------------------------------------
    add("empty", b"")
    add("soi_only", b"\xff\xd8")
    add("garbage", b"\xde\xad\xbe\xef" * 8)
    add("junk_prefix", b"GARBAGE" + _RGB)
    add("double_soi", b"\xff\xd8" + _RGB)
    add("trailing_garbage", _PROG + b"\x00" * 50)

    # -- colour variants (valid) -----------------------------------------
    add("rgb", _RGB)
    add("gray", _GRAY)
    add("cmyk", _CMYK)
    add("cmyk_no_app14", _strip_app14(_CMYK))
    add("progressive", _PROG)

    # -- baseline RGB truncated scan -------------------------------------
    for frac in (1, 30, 60, 90, 99):
        add(f"rgb_trunc{frac}", _RGB[: max(1, len(_RGB) * frac // 100)])
    add("rgb_no_eoi", _RGB[:-2])  # drop the EOI marker; scan still complete

    # -- grayscale / progressive truncated -------------------------------
    for frac in (40, 80):
        add(f"gray_trunc{frac}", _GRAY[: max(1, len(_GRAY) * frac // 100)])
    for frac in (30, 60, 90):
        add(f"prog_trunc{frac}", _PROG[: max(1, len(_PROG) * frac // 100)])

    # -- SOF dimension corruption that BOTH sides reject -----------------
    add("sof_zero_dims", _set_sof_dims(_RGB, 0, 0))
    add("sof_zero_height", _set_sof_dims(_RGB, 0, 8))
    add("corrupt_sof0_marker", _CORRUPT_SOF)

    return out


# Modest-oversize SOF that BOTH sides tolerate: PDFBox and pypdfbox each pad
# the raster out to the (forged) declared geometry and succeed with the SAME
# byte length, but the *padding pixel content* differs between Java ImageIO and
# libjpeg-turbo-via-imagecodecs, so the sha differs. These are pinned on the
# OUTCOME + LENGTH only (a milder form of the oversize library gap below).
_OVERSIZE_TOLERATED: list[_Case] = [
    ("sof_height_plus_one", _set_sof_dims(_RGB, 9, 8)),
    ("sof_width_x16", _set_sof_dims(_RGB, 8, 128)),
]
_OVERSIZE_TOLERATED_IDS = [c[0] for c in _OVERSIZE_TOLERATED]


_ALIGNED = _build_aligned_corpus()
_ALIGNED_IDS = [c[0] for c in _ALIGNED]


# Forged-oversize SOF: the one genuine library-gap divergence (see module
# docstring + CHANGES.md "Wave 1528"). Java/PDFBox throws (ok=false);
# pypdfbox via imagecodecs/libjpeg-turbo pads and returns ok=true.
_DIVERGENT: list[_Case] = [
    ("sof_width_0xffff", _set_sof_dims(_RGB, 8, 0xFFFF)),
    ("sof_60000x60000", _set_sof_dims(_RGB, 60000, 60000)),
]
_DIVERGENT_IDS = [c[0] for c in _DIVERGENT]


# ---------------------------------------------------------------------------
# projection helpers (mirror DctDecodeFuzzProbe exactly)
# ---------------------------------------------------------------------------
def _sha_prefix(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def _build_stream_dict() -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Filter"), COSName.get_pdf_name("DCTDecode"))
    return d


def _py_dump(encoded: bytes) -> str:
    try:
        flt = FilterFactory.get("DCTDecode")
        out = io.BytesIO()
        flt.decode(io.BytesIO(encoded), out, _build_stream_dict(), 0)
        decoded = out.getvalue()
    except Exception:
        return "ok=false\n"
    return f"ok=true\nlen={len(decoded)}\nsha={_sha_prefix(decoded)}\n"


def _java_dump(encoded: bytes) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".bin")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(encoded)
        return run_probe_text("DctDecodeFuzzProbe", tmp)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Differential parity: aligned corpus produces the identical projection.
# Pinned EXACT (ok + len + sha) -- both engines wrap libjpeg-turbo, so the
# decoded raster is byte-identical on success.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(("name", "encoded"), _ALIGNED, ids=_ALIGNED_IDS)
def test_dct_decode_fuzz_parity(name: str, encoded: bytes) -> None:
    java = _java_dump(encoded)
    py = _py_dump(encoded)
    assert py == java, (
        f"DCTDecode divergence on {name!r}:\n java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Modest forged-oversize SOF both sides tolerate: same decoded LENGTH, but the
# padding content (hence sha) is engine-dependent, so only ok + len is pinned.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(
    ("name", "encoded"), _OVERSIZE_TOLERATED, ids=_OVERSIZE_TOLERATED_IDS
)
def test_dct_decode_oversize_tolerated_len_parity(name: str, encoded: bytes) -> None:
    java = _java_dump(encoded)
    py = _py_dump(encoded)
    java_head = "\n".join(java.splitlines()[:2]) + "\n"
    py_head = "\n".join(py.splitlines()[:2]) + "\n"
    assert py_head == java_head, (
        f"DCTDecode ok/len divergence on {name!r}:\n java={java!r}\n  py={py!r}"
    )


# ---------------------------------------------------------------------------
# Pinned divergence: forged-oversize SOF. PDFBox throws; pypdfbox's
# imagecodecs path pads to the declared dimensions and succeeds. Pinned both
# sides as a library gap rather than fixed (see module docstring). The py
# raster size/sha are libjpeg-version dependent, so only the OUTCOME shape is
# asserted (java rejects, py accepts) -- not the exact py len/sha.
# ---------------------------------------------------------------------------
@requires_oracle
@pytest.mark.parametrize(("name", "encoded"), _DIVERGENT, ids=_DIVERGENT_IDS)
def test_dct_decode_oversize_sof_divergence(name: str, encoded: bytes) -> None:
    java = _java_dump(encoded)
    py = _py_dump(encoded)
    assert java == "ok=false\n", f"expected PDFBox to reject {name!r}, got {java!r}"
    assert py.startswith("ok=true\n"), (
        f"expected pypdfbox to (leniently) accept {name!r}, got {py!r}"
    )


# ---------------------------------------------------------------------------
# Sanity: crafted "valid" streams really decode to the expected raster sizes,
# so a corpus-build regression cannot turn every case into a vacuous
# ok=true|len=0 (or every case into ok=false).
# ---------------------------------------------------------------------------
def test_crafted_valid_streams_decode_expected_sizes() -> None:
    expected = {
        "rgb": 8 * 8 * 3,
        "gray": 16 * 16 * 1,
        "cmyk": 8 * 8 * 4,
        "progressive": 16 * 16 * 3,
        "cmyk_no_app14": 8 * 8 * 4,
    }
    body_by_name = {c[0]: c[1] for c in _ALIGNED}
    for name, size in expected.items():
        out = io.BytesIO()
        FilterFactory.get("DCTDecode").decode(
            io.BytesIO(body_by_name[name]), out, _build_stream_dict(), 0
        )
        assert len(out.getvalue()) == size, name
