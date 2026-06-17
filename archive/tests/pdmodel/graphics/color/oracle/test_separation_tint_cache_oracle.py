"""Live PDFBox differential parity for two under-pinned aspects of
``PDSeparation.toRGB`` (PDSeparation.java line 137): out-of-``[0, 1]`` tint
handling and the quantised ``toRGBMap`` cache key.

The Java side is ``oracle/probes/SeparationTintCacheProbe.java``. The alternate
colour space is **DeviceRGB**, so the tint-transform output flows straight
through ``DeviceRGB.toRGB`` (identity, no CMM) — every emitted RGB is
deterministic float arithmetic identical on both sides. This is therefore an
EXACT-match probe with no documented-divergence tier.

Two empirically pinned findings (verified against the live jar)
---------------------------------------------------------------
**No input-domain clamp.** ``PDSeparation.toRGB`` forwards the raw tint to
``tintTransform.eval``. PDFBox 3.0.7's Type-2 exponential function evaluates
``C0 + t**N * (C1 - C0)`` on the *raw* ``t`` — it does NOT clip ``t`` to the
function ``/Domain`` first. So a tint of ``-0.5`` yields ``(-0.5)**2 = 0.25``
(not the domain-clamped ``0.0``), and ``1.5`` yields ``1.5**2 = 2.25``
(post-clamped to 1.0 only by the final ``round(component*255)`` ceiling, not by
a domain clamp). pypdfbox mirrors this exactly — :meth:`PDSeparation.to_rgb`
forwards the raw tint and its Type-2 function applies no input-domain clamp.

**Quantised cache key.** ``toRGB`` caches results in a ``Map<Integer,float[]>``
keyed on ``(int)(value[0] * 255)`` (truncate toward zero). Two tints that land
on the SAME truncated key return whichever was computed first; two tints on
DIFFERENT keys each compute fresh. The probe drives a fixed call ORDER on one
shared space so the cache-population sequence is reproducible: ``0.75`` (key
191) computes fresh, then ``0.7505`` (also key 191) is a cache hit returning the
``0.75`` RGB; ``0.5`` (key 127) and ``0.5039`` (key 128) are distinct keys so
both compute fresh. pypdfbox's ``int(components[0] * 255)`` truncates identically
to Java's ``(int)`` cast, so the key sequence — and thus every cached/fresh RGB
— matches byte-for-byte.

A mismatch on ANY line is a real bug (a domain clamp crept into the tint path,
or the cache key quantisation drifted from upstream's truncating cast).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from tests.oracle.harness import requires_oracle, run_probe_text


def _clamp255(value: float) -> int:
    """round(value * 255), clamped to [0, 255] — mirrors the Java probe."""
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _make() -> PDSeparation:
    """Build the Separation space mirroring SeparationTintCacheProbe.make():
    DeviceRGB alternate + Type-2 exponential ``C0=[0,0,0] C1=[1,0.5,0.25] N=2``
    on ``/Domain [0 1]``."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("Spot"))
    arr.add(COSName.get_pdf_name("DeviceRGB"))
    fn = COSDictionary()
    fn.set_int("FunctionType", 2)
    domain = COSArray()
    domain.add(COSFloat(0.0))
    domain.add(COSFloat(1.0))
    fn.set_item("Domain", domain)
    c0 = COSArray()
    for v in (0.0, 0.0, 0.0):
        c0.add(COSFloat(v))
    fn.set_item("C0", c0)
    c1 = COSArray()
    for v in (1.0, 0.5, 0.25):
        c1.add(COSFloat(v))
    fn.set_item("C1", c1)
    fn.set_item("N", COSFloat(2.0))
    arr.add(fn)
    return PDSeparation(arr)


def _rgb_int(cs: PDSeparation, tint: float) -> tuple[int, int, int]:
    rgb = cs.to_rgb([tint])
    assert rgb is not None, f"to_rgb([{tint}]) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


def _parse_probe(text: str) -> list[tuple[str, float, tuple[int, int, int]]]:
    """Parse ``tag tint -> r g b`` lines, preserving order (cache sequence is
    load-bearing)."""
    out: list[tuple[str, float, tuple[int, int, int]]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "->" not in line:
            continue
        left, right = line.split("->")
        tag, tint = left.split()
        r, g, b = (int(x) for x in right.split())
        out.append((tag, float(tint), (r, g, b)))
    return out


@requires_oracle
def test_separation_out_of_range_tint_no_domain_clamp() -> None:
    """Out-of-``[0, 1]`` tints flow through the tint transform WITHOUT a
    domain clamp — ``(-0.5)**2 == 0.25`` on both sides, not the clamped
    ``0.0``. Each OOR probe uses a fresh space so the cache can't mask the
    behaviour. A mismatch means a domain clamp crept into the tint path."""
    java = [row for row in _parse_probe(run_probe_text("SeparationTintCacheProbe"))
            if row[0] == "OOR"]
    assert java, "probe emitted no OOR rows"
    for _tag, tint, j_rgb in java:
        py_rgb = _rgb_int(_make(), tint)
        assert py_rgb == j_rgb, (
            f"OOR tint {tint}: pypdfbox {py_rgb} != PDFBox {j_rgb}"
        )


@requires_oracle
def test_separation_to_rgb_cache_key_quantisation() -> None:
    """The quantised ``(int)(tint*255)`` cache key sequence reproduces
    byte-for-byte. Driven in a FIXED order on one shared space: same-key tints
    are cache hits (return the first RGB), distinct-key tints compute fresh.
    pypdfbox's ``int(tint*255)`` truncates identically to Java's ``(int)``."""
    java = [row for row in _parse_probe(run_probe_text("SeparationTintCacheProbe"))
            if row[0] == "CACHE"]
    assert java, "probe emitted no CACHE rows"
    cs = _make()  # one shared space — cache population order matters.
    for _tag, tint, j_rgb in java:
        py_rgb = _rgb_int(cs, tint)
        assert py_rgb == j_rgb, (
            f"CACHE tint {tint}: pypdfbox {py_rgb} != PDFBox {j_rgb} "
            f"(cache-key quantisation or population order diverged)"
        )
