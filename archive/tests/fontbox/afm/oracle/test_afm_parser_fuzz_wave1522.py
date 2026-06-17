"""Differential AFM-parse fuzz vs Apache FontBox 3.0.7 (wave 1522).

The AFM sibling of the CFF/TTF parse-fuzz waves, applied to the *AFM lexer /
parser* surface — ``org.apache.fontbox.afm.AFMParser`` driven via the
``AFMParser(InputStream)`` constructor and ``parse(reducedDataset)``.

For a battery of malformed Adobe-Font-Metric byte blobs (missing/garbled
``StartFontMetrics`` framing, truncated sections, unknown keywords, malformed
``C`` char-metric lines, ``StartCharMetrics`` count mismatches, malformed
``KPX``/``KP`` kern lines, ``CC`` composite errors, garbage numeric tokens,
empty/whitespace input, duplicate sections, bad global metrics) both engines
parse the *identical* bytes and are compared on a stable projection:

    ok=true
    ver=<afmVersion 4dp>
    name=<FontName or NULL>
    full=<FullName or NULL>
    bbox=<x0,y0,x1,y1 or NULL>
    nchar=<CharMetric count>
    nkern=<KernPair count, all three lists>
    ncomp=<Composite count>
    cm0=<first CharMetric sorted by name, or NULL>

or the sole line ``ok=false`` on any throw. The Java side is
``oracle/probes/AfmParserFuzzProbe.java``; ``_py_dump`` reproduces the same
fingerprint on the pypdfbox side.

REAL BUG FIXED THIS WAVE (now asserted, both engines agree):

  * *Reduced-dataset kern/composite handling.* pypdfbox previously did
    ``_skip_to(EndKernData)`` / ``_skip_to(EndComposites)`` in reduced mode.
    Upstream does NOT skip to the terminator — it simply omits the
    ``parseKernData`` / ``parseComposites`` call and lets the main loop
    re-encounter the inner kern/composite tokens (``StartKernPairs``, ``CC``,
    ...) as *unknown keys*, which raise unless char metrics were already read.
    The ``kp_*`` / ``cc_*`` reduced cases below pin the fix.

DOCUMENTED UNALIGNABLE DIVERGENCES (pinned both-sides, NOT a pypdfbox bug):

  * *Integer overflow.* A char code / count token beyond Java's
    ``Integer.MAX_VALUE`` (e.g. ``C 99999999999999999999``) makes upstream's
    ``parseInt`` throw (``ok=false``); Python ints are unbounded so pypdfbox
    parses it (``ok=true``). Per CLAUDE.md this is the platform-dependent
    integer case — pinned, not fixed. See ``_OVERFLOW_CASES``.

  * *``CH <hex>`` bracket form.* Upstream parses the ``CH`` token as bare hex
    (``parseInt(token, 16)``) and so rejects the angle-bracketed ``<41>`` form;
    pypdfbox deliberately accepts both (a pre-existing intentional leniency,
    CHANGES.md wave316). Pinned in ``_LENIENT_CASES``.

Floats ``Infinity`` / ``NaN`` are accepted by both engines (Java
``Float.parseFloat`` and Python ``float`` both parse them); the projection
formats them with Java's ``%.4f`` spelling (``Infinity`` / ``NaN``) on both
sides so those cases agree.
"""

from __future__ import annotations

import math
import os
import tempfile
from contextlib import suppress

import pytest

from pypdfbox.fontbox.afm.afm_parser import AFMParser
from tests.oracle.harness import requires_oracle, run_probe_text


def _fmt(value: float) -> str:
    """4-decimal float formatting matching Java ``String.format("%.4f", v)``.

    Java spells the non-finite values ``Infinity`` / ``-Infinity`` / ``NaN``;
    Python's ``f"{v:.4f}"`` spells them ``inf`` / ``-inf`` / ``nan``. Map them
    so the fingerprint matches the probe byte-for-byte.
    """
    v = float(value)
    if math.isnan(v):
        return "NaN"
    if math.isinf(v):
        return "Infinity" if v > 0 else "-Infinity"
    if v == 0.0:
        v = 0.0
    return f"{v:.4f}"


def _nz(value: str | None) -> str:
    return "NULL" if value is None else value


def _bbox(bbox: object) -> str:
    if bbox is None:
        return "NULL"
    return ",".join(
        _fmt(v)
        for v in (
            bbox.get_lower_left_x(),  # type: ignore[attr-defined]
            bbox.get_lower_left_y(),  # type: ignore[attr-defined]
            bbox.get_upper_right_x(),  # type: ignore[attr-defined]
            bbox.get_upper_right_y(),  # type: ignore[attr-defined]
        )
    )


def _py_dump(data: bytes, reduced: bool) -> str:
    try:
        fm = AFMParser(data).parse(reduced_dataset=reduced)
    except Exception:
        return "ok=false\n"
    try:
        metrics = fm.get_char_metrics()
        nkern = (
            len(fm.get_kern_pairs())
            + len(fm.get_kern_pairs0())
            + len(fm.get_kern_pairs1())
        )
        lines = [
            "ok=true",
            f"ver={_fmt(fm.get_afm_version())}",
            f"name={_nz(fm.get_font_name())}",
            f"full={_nz(fm.get_full_name())}",
            f"bbox={_bbox(fm.get_font_b_box())}",
            f"nchar={len(metrics)}",
            f"nkern={nkern}",
            f"ncomp={len(fm.get_composites())}",
        ]
        if not metrics:
            lines.append("cm0=NULL")
        else:
            cm = sorted(metrics, key=lambda m: _nz(m.get_name()))[0]
            lines.append(
                "cm0="
                + ",".join(
                    [
                        _nz(cm.get_name()),
                        str(cm.get_character_code()),
                        _fmt(cm.get_wx()),
                        _bbox(cm.get_bounding_box()),
                    ]
                )
            )
        return "\n".join(lines) + "\n"
    except Exception:
        return "ok=false\n"


def _java_dump(data: bytes, reduced: bool) -> str:
    fd, tmp = tempfile.mkstemp(suffix=".afm")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return run_probe_text("AfmParserFuzzProbe", tmp, "1" if reduced else "0")
    finally:
        with suppress(OSError):
            os.unlink(tmp)


_VALID = (
    b"StartFontMetrics 4.1\n"
    b"FontName Test\n"
    b"FullName Test Font\n"
    b"FontBBox -10 -20 100 200\n"
    b"StartCharMetrics 2\n"
    b"C 32 ; WX 250 ; N space ; B 0 0 0 0 ;\n"
    b"C 65 ; WX 700 ; N A ; B 10 0 690 700 ;\n"
    b"EndCharMetrics\n"
    b"StartKernData\n"
    b"StartKernPairs 1\n"
    b"KPX A V -80\n"
    b"EndKernPairs\n"
    b"EndKernData\n"
    b"StartComposites 1\n"
    b"CC Aacute 2 ; PCC A 0 0 ; PCC acute 160 220 ;\n"
    b"EndComposites\n"
    b"EndFontMetrics\n"
)

# (id, bytes) -- exercised under BOTH full and reduced parse modes. Both engines
# agree on the projection for every case here.
_CASES: list[tuple[str, bytes]] = [
    ("valid", _VALID),
    ("empty", b""),
    ("ws_only", b"   \n\t  \n"),
    ("no_start", b"FontName Test\nEndFontMetrics\n"),
    ("no_end", b"StartFontMetrics 4.1\nFontName Test\n"),
    (
        "trunc_mid_char",
        b"StartFontMetrics 4.1\nStartCharMetrics 5\nC 32 ; WX 250 ; N space ;\n",
    ),
    ("unknown_kw", b"StartFontMetrics 4.1\nBogusKeyword foo\nEndFontMetrics\n"),
    (
        "bad_wx_nonnum",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 32 ; WX abc ; N space ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "missing_wx_field",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 32 ; WX ; N space ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "count_more_than_actual",
        b"StartFontMetrics 4.1\nStartCharMetrics 3\n"
        b"C 32 ; WX 250 ; N space ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "count_less_than_actual",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 32 ; WX 250 ; N space ;\nC 65 ; WX 700 ; N A ;\n"
        b"EndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "count_zero",
        b"StartFontMetrics 4.1\nStartCharMetrics 0\n"
        b"EndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "count_negative",
        b"StartFontMetrics 4.1\nStartCharMetrics -1\n"
        b"EndCharMetrics\nEndFontMetrics\n",
    ),
    (
        "count_nonnum",
        b"StartFontMetrics 4.1\nStartCharMetrics x\n"
        b"EndCharMetrics\nEndFontMetrics\n",
    ),
    ("bad_bbox", b"StartFontMetrics 4.1\nFontBBox a b c d\nEndFontMetrics\n"),
    ("bbox_short", b"StartFontMetrics 4.1\nFontBBox 0 0 100\nEndFontMetrics\n"),
    ("ver_nonnum", b"StartFontMetrics x.y\nEndFontMetrics\n"),
    ("ver_missing", b"StartFontMetrics\nEndFontMetrics\n"),
    (
        "kp_bad",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"BADCMD A V -80\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kpx_missing_val",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"KPX A V\nEndKernPairs\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "kern_no_endpairs",
        b"StartFontMetrics 4.1\nStartKernData\nStartKernPairs 1\n"
        b"KPX A V -80\nEndKernData\nEndFontMetrics\n",
    ),
    (
        "cc_wrong_pcc",
        b"StartFontMetrics 4.1\nStartComposites 1\n"
        b"CC Aacute 3 ; PCC A 0 0 ;\nEndComposites\nEndFontMetrics\n",
    ),
    (
        "cc_bad_count",
        b"StartFontMetrics 4.1\nStartComposites 1\n"
        b"CC Aacute x ; PCC A 0 0 ;\nEndComposites\nEndFontMetrics\n",
    ),
    (
        "no_fontname",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 32 ; WX 250 ; N space ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    ("dup_section", b"StartFontMetrics 4.1\nFontName A\nFontName B\nEndFontMetrics\n"),
    ("metricsets_bad", b"StartFontMetrics 4.1\nMetricSets 5\nEndFontMetrics\n"),
    (
        "no_semicolon",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 32 WX 250 N space\nEndCharMetrics\nEndFontMetrics\n",
    ),
    ("bool_garbage", b"StartFontMetrics 4.1\nIsFixedPitch maybe\nEndFontMetrics\n"),
    ("isfixedv_no_vvec", b"StartFontMetrics 4.1\nIsFixedV true\nEndFontMetrics\n"),
    (
        "char_no_end",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 32 ; WX 250 ; N space ;\nEndFontMetrics\n",
    ),
    ("mappingscheme_hex", b"StartFontMetrics 4.1\nMappingScheme 0xff\nEndFontMetrics\n"),
    (
        "wx_infinity",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 32 ; WX Infinity ; N space ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
    ("ver_nan", b"StartFontMetrics NaN\nEndFontMetrics\n"),
    (
        "very_long_line",
        b"StartFontMetrics 4.1\nComment " + b"A" * 20000 + b"\nEndFontMetrics\n",
    ),
]

# Char-code / count integer-overflow cases: upstream parseInt throws
# (Integer.MAX_VALUE), Python ints are unbounded. UNALIGNABLE — pinned both
# sides (Java ok=false, pypdfbox ok=true).
_OVERFLOW_CASES: list[tuple[str, bytes]] = [
    (
        "int_overflow_c",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"C 99999999999999999999 ; WX 250 ; N space ;\n"
        b"EndCharMetrics\nEndFontMetrics\n",
    ),
]

# pypdfbox intentionally more lenient than upstream: CH <hex> angle-bracket form.
_LENIENT_CASES: list[tuple[str, bytes]] = [
    (
        "ch_angle_bracket",
        b"StartFontMetrics 4.1\nStartCharMetrics 1\n"
        b"CH <41> ; WX 250 ; N A ;\nEndCharMetrics\nEndFontMetrics\n",
    ),
]

_IDS = [c[0] for c in _CASES]
_OVERFLOW_IDS = [c[0] for c in _OVERFLOW_CASES]
_LENIENT_IDS = [c[0] for c in _LENIENT_CASES]


@requires_oracle
@pytest.mark.parametrize(("name", "data"), _CASES, ids=_IDS)
@pytest.mark.parametrize("reduced", [False, True], ids=["full", "reduced"])
def test_afm_parse_fuzz_parity(name: str, data: bytes, reduced: bool) -> None:
    java = _java_dump(data, reduced)
    py = _py_dump(data, reduced)
    assert py == java, (
        f"divergence on AFM mutant {name!r} reduced={reduced}:\n"
        f" java={java!r}\n  py={py!r}"
    )


@requires_oracle
@pytest.mark.parametrize(("name", "data"), _OVERFLOW_CASES, ids=_OVERFLOW_IDS)
def test_afm_int_overflow_divergence_pinned(name: str, data: bytes) -> None:
    # UNALIGNABLE: upstream's parseInt overflows Integer.MAX_VALUE and throws;
    # Python ints are unbounded so pypdfbox parses on. Pin both observed sides.
    java = _java_dump(data, False)
    py = _py_dump(data, False)
    assert java == "ok=false\n"
    assert py.startswith("ok=true\n")
    assert "99999999999999999999" in py


@requires_oracle
@pytest.mark.parametrize(("name", "data"), _LENIENT_CASES, ids=_LENIENT_IDS)
def test_afm_ch_bracket_leniency_divergence_pinned(name: str, data: bytes) -> None:
    # pypdfbox intentionally accepts the angle-bracketed CH form that upstream
    # rejects (parseInt on a bare hex token). Pin both observed sides.
    java = _java_dump(data, False)
    py = _py_dump(data, False)
    assert java == "ok=false\n"
    assert py.startswith("ok=true\n")
    assert "nchar=1" in py


def test_clean_valid_projection_non_trivial() -> None:
    dump = _py_dump(_VALID, False)
    assert dump.startswith("ok=true\n")
    assert "name=Test\n" in dump
    assert "nchar=2\n" in dump
    assert "nkern=1\n" in dump
    assert "ncomp=1\n" in dump
