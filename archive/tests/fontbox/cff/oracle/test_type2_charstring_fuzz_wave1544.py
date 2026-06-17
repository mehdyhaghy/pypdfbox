"""Live Apache PDFBox differential parity for the FontBox **Type 2
char-string INTERPRETER -> glyph PATH** layer
(``org.apache.fontbox.cff.Type2CharString.getPath()``), fed raw, hand-built
(mostly malformed / edge) Type 2 bytecode rather than a parsed CFF file.

This wave-1544 suite is upstream-distinct from its two siblings:

* ``test_type2_charstring_interp_fuzz_wave1525`` pins the parser's intermediate
  TOKEN STREAM (operands + command mnemonics) and the exceptions the decoder
  throws — it never builds an outline.
* ``test_cff_subr_path_oracle`` pins ``getPath()`` but only for glyphs reached
  through a real, well-formed embedded CFF.

Here we drive raw bytecode all the way to the rendered outline through the full
interpreter: width prologue (width-on-first-operator detection), the Type 2 ->
Type 1 conversion of every curve operator (rrcurveto / hvcurveto / vhcurveto /
hhcurveto / vvcurveto / rcurveline / rlinecurve and the flex family), hintmask /
cntrmask byte skipping, callsubr / callgsubr bias + inlining, multi-subpath
sequencing, and the malformed-input edges (stack underflow, odd operand
remainder, missing endchar, 4/5-arg seac endchar). The companion probe
``Type2CharStringFuzzProbe`` emits a COORDINATE-TOLERANT, STRUCTURE-STRICT
fingerprint: segment count, the M/L/C/Z type sequence, and the rounded
control-point bounds — or ``ERR<TAB>ExceptionClass`` when the build threw.

pypdfbox delegates the Type 2 interpreter to fontTools' ``T2CharString.draw``
(library-first rule). fontTools and PDFBox agree on the rendered geometry but
differ in two STRUCTURAL, geometry-neutral ways that are pinned here as honest
divergences rather than papered over:

1. **Trailing zero-length moveto.** PDFBox's ``Type2CharString`` closes the
   final sub-path at ``endchar`` and then still appends the endchar's own
   (empty) ``rmoveto``, so its path carries one extra trailing ``M`` segment
   ("MLZM" where fontTools yields "MLZ"). The bounding box is identical — the
   trailing move is zero-length. For every well-formed glyph we therefore strip
   one trailing ``M`` from the Java fingerprint before comparing the command
   sequence, and assert the bounds match verbatim.
2. **flex1 dx/dy bias.** PDFBox's ``flex1`` last-point fix-up
   (Type2CharString.java) and fontTools' implementation pick the final on-curve
   coordinate differently when ``|dx| != |dy|``; the resulting bounds differ by
   a few units. Pinned both-sides as a documented library divergence.

Wave 1544 also fixed a real production bug: a standalone ``Type2CharString``
built from raw ``bytes`` / a program list never rendered ANY outline —
``get_path()`` silently returned ``[]`` for every glyph — because the bare
fontTools ``T2CharString`` had no ``.private`` (widths / local subrs) or
``.globalSubrs`` wired, so ``draw()`` raised ``AttributeError`` (swallowed). The
fix attaches a minimal private-dict shim carrying the glyph's widths, and
lowercases the ``CharStringCommand`` operator mnemonics that fontTools' program
list keys on. See CHANGES.md (wave 1544).
"""

from __future__ import annotations

import subprocess

import pytest

from pypdfbox.fontbox.cff.type2_char_string import Type2CharString
from tests.oracle.harness import (
    _classpath,
    oracle_available,
    requires_oracle,
)

_PROBE = "Type2CharStringFuzzProbe"


def _op(n: int) -> bytes:
    """Single-byte Type 2 operand encoding (-107..107)."""
    return bytes([n + 139])


def _short(v: int) -> bytes:
    """The ``28`` short-int (signed 16-bit) operand encoding."""
    return bytes([28]) + (v & 0xFFFF).to_bytes(2, "big")


_E = b"\x0e"  # endchar


# ---------------------------------------------------------------------------
# Probe driver — projects the rendered-path fingerprint, raw or parsed.
# ---------------------------------------------------------------------------


def _probe(cs: bytes, def_w: int = 0, nom_w: int = 0) -> tuple[str, ...]:
    """Run the live PDFBox probe; return its tab-split fingerprint tuple."""
    from tests.oracle import harness  # noqa: PLC0415

    harness._ensure_compiled(_PROBE)
    out = subprocess.run(
        [
            "java",
            "-cp",
            _classpath(),
            _PROBE,
            "run",
            cs.hex(),
            "-",
            "-",
            str(def_w),
            str(nom_w),
        ],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    return tuple(out.strip().split("\t"))


def _py_fingerprint(cs: bytes, def_w: int = 0, nom_w: int = 0) -> tuple[str, ...]:
    """pypdfbox's rendered-path fingerprint in the probe's exact field shape.

    The raw-bytecode constructor is the production-faithful interpreter path:
    fontTools sees the un-stripped hintmask bytes and the genuine operator
    stream (the parser-unrolled token list, by contrast, strips mask bytes the
    fontTools interpreter still needs)."""
    try:
        path = Type2CharString(None, "FuzzFont", "g", 0, cs, def_w, nom_w).get_path()
    except Exception as exc:  # noqa: BLE001 - the probe maps any throw to ERR
        return ("ERR", type(exc).__name__)
    types: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    for cmd in path:
        tag = cmd[0]
        if tag == "moveto":
            types.append("M")
            xs.append(cmd[1])
            ys.append(cmd[2])
        elif tag == "lineto":
            types.append("L")
            xs.append(cmd[1])
            ys.append(cmd[2])
        elif tag == "curveto":
            types.append("C")
            xs.extend((cmd[1], cmd[3], cmd[5]))
            ys.extend((cmd[2], cmd[4], cmd[6]))
        elif tag == "closepath":
            types.append("Z")
    nseg = len(types)
    if nseg == 0:
        bbox = (0, 0, 0, 0)
    else:
        bbox = (round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys)))
    return ("OK", str(nseg), "".join(types), *(str(v) for v in bbox))


def _strip_trailing_move(type_seq: str) -> str:
    """Drop one trailing ``M`` — PDFBox's zero-length endchar moveto (see
    module docstring divergence #1)."""
    return type_seq[:-1] if type_seq.endswith("M") else type_seq


# ---------------------------------------------------------------------------
# Well-formed glyphs: after normalising PDFBox's trailing zero-length moveto,
# the M/L/C/Z command sequence AND the control-point bounds match verbatim.
# ---------------------------------------------------------------------------

# id -> charstring bytecode (raw, masks intact)
_VALID: list[tuple[str, bytes]] = [
    ("rmove_rline", _op(0) + _op(0) + b"\x15" + _short(100) + _op(0) + b"\x05" + _E),
    ("rrcurveto", _op(0) + _op(0) + b"\x15" + _op(0) * 6 + b"\x08" + _E),
    ("hmoveto", _op(50) + b"\x16" + _short(100) + _op(0) + b"\x05" + _E),
    ("vmoveto", _op(50) + b"\x04" + _op(0) + _short(100) + b"\x05" + _E),
    ("hlineto", _op(0) + _op(0) + b"\x15" + _op(50) + _op(40) + b"\x06" + _E),
    ("vlineto", _op(0) + _op(0) + b"\x15" + _op(50) + _op(40) + b"\x07" + _E),
    ("hvcurveto", _op(0) + _op(0) + b"\x15" + _op(10) * 8 + b"\x1f" + _E),
    ("vhcurveto", _op(0) + _op(0) + b"\x15" + _op(10) * 8 + b"\x1e" + _E),
    ("hhcurveto", _op(0) + _op(0) + b"\x15" + _op(10) * 4 + b"\x1b" + _E),
    ("vvcurveto", _op(0) + _op(0) + b"\x15" + _op(10) * 4 + b"\x1a" + _E),
    ("rcurveline", _op(0) + _op(0) + b"\x15" + _op(10) * 8 + b"\x18" + _E),
    ("rlinecurve", _op(0) + _op(0) + b"\x15" + _op(10) * 8 + b"\x19" + _E),
    ("flex", _op(0) + _op(0) + b"\x15" + _op(10) * 13 + bytes([12, 35]) + _E),
    ("hflex", _op(0) + _op(0) + b"\x15" + _op(10) * 7 + bytes([12, 34]) + _E),
    ("hflex1", _op(0) + _op(0) + b"\x15" + _op(10) * 9 + bytes([12, 36]) + _E),
    # hintmask / cntrmask with their inline mask byte, followed by a real path:
    # the mask bytes must be consumed, not interpreted as path operands.
    (
        "hintmask_then_path",
        _op(0) + _op(10) + b"\x01" + b"\x13\xff" + _op(0) + _op(0) + b"\x15"
        + _short(100) + _op(0) + b"\x05" + _E,
    ),
    (
        "cntrmask_then_path",
        _op(0) + _op(10) + b"\x14\xff" + _op(0) + _op(0) + b"\x15"
        + _short(100) + _op(0) + b"\x05" + _E,
    ),
    ("two_subpaths",
     _op(0) + _op(0) + b"\x15" + _short(100) + _op(0) + b"\x05"
     + _op(50) + _op(50) + b"\x15" + _short(50) + _op(0) + b"\x05" + _E),
    ("neg_coords",
     _short(-100) + _short(-50) + b"\x15" + _short(200) + _op(0) + b"\x05" + _E),
    # 255 16.16 fixed-point operand as a coordinate (100.0): MLZ at x=100.
    ("fixed255_coord",
     _op(0) + _op(0) + b"\x15" + bytes([255, 0, 100, 0, 0]) + _op(0) + b"\x05" + _E),
    # leading width operand on the first stack-clearing operator (CFF §3.1):
    # 500 is consumed as the advance width, the path geometry is unchanged.
    ("width_on_first_op",
     _short(500) + _op(0) + _op(0) + b"\x15" + _short(100) + _op(0) + b"\x05" + _E),
]


@requires_oracle
@pytest.mark.parametrize(("cid", "cs"), _VALID, ids=[c[0] for c in _VALID])
def test_type2_path_matches_pdfbox(cid: str, cs: bytes) -> None:
    """Well-formed glyph: pypdfbox's rendered M/L/C/Z command sequence and
    control-point bounds match PDFBox's, after normalising the trailing
    zero-length endchar moveto (divergence #1)."""
    java = _probe(cs)
    py = _py_fingerprint(cs)
    assert java[0] == "OK", (cid, "probe ERR", java)
    assert py[0] == "OK", (cid, "py ERR", py)
    j_seq = _strip_trailing_move(java[2])
    assert py[2] == j_seq, (cid, "cmd seq", "py", py[2], "java(stripped)", j_seq)
    # Control-point bounds match verbatim (coordinate-tolerant rounding only).
    assert py[3:] == java[3:], (cid, "bounds", "py", py[3:], "java", java[3:])


# ---------------------------------------------------------------------------
# Documented divergences — pinned BOTH sides so a regression on either is loud.
# ---------------------------------------------------------------------------


@requires_oracle
def test_flex1_bounds_diverge_known_library_difference() -> None:
    """``flex1`` last-point fix-up differs between PDFBox and fontTools when
    ``|dx| != |dy|`` (divergence #2). The command sequence still matches after
    trailing-move normalisation; only the bounds differ. Pinned both-sides."""
    cs = _op(0) + _op(0) + b"\x15" + _op(10) * 11 + bytes([12, 37]) + _E
    java = _probe(cs)
    py = _py_fingerprint(cs)
    assert java[0] == "OK" and py[0] == "OK"
    # Same command structure (after the trailing-move strip)...
    assert py[2] == _strip_trailing_move(java[2])
    # ...but the bounds genuinely differ; pin both observed values.
    assert java[3:] == ("0", "0", "38", "60")
    assert py[3:] == ("0", "0", "50", "60")


@requires_oracle
def test_missing_endchar_close_diverges() -> None:
    """A charstring whose program ends without ``endchar``: fontTools
    auto-closes the open sub-path (``MLZ``); PDFBox leaves it open (``ML``).
    Pinned both-sides — the bounds still match."""
    cs = _op(0) + _op(0) + b"\x15" + _short(100) + _op(0) + b"\x05"
    java = _probe(cs)
    py = _py_fingerprint(cs)
    assert java[0] == "OK" and py[0] == "OK"
    assert java[2] == "ML"  # PDFBox: no auto-close
    assert py[2] == "MLZ"  # fontTools: auto-close
    assert py[3:] == java[3:]  # bounds identical regardless


@requires_oracle
@pytest.mark.parametrize(
    ("cid", "cs", "py_seq", "java_seq"),
    [
        # rmoveto with no operands: PDFBox renders a degenerate move+close+move
        # ("MZM"); fontTools yields an empty path. Both bounds (0,0,0,0).
        ("rmoveto_only", _op(0) + _op(0) + b"\x15" + _E, "MZ", "MZM"),
        # rmoveto stack underflow then endchar: PDFBox emits a lone "M";
        # fontTools yields an empty path.
        ("rmoveto_underflow", b"\x15" + _E, "", "M"),
        # rrcurveto with an odd (non-multiple-of-6) operand remainder: PDFBox
        # emits "MZM" (drops the partial curve); fontTools yields empty.
        ("rrcurveto_odd", _op(0) + _op(0) + b"\x15" + _op(0) * 5 + b"\x08" + _E,
         "", "MZM"),
    ],
    ids=["rmoveto_only", "rmoveto_underflow", "rrcurveto_odd"],
)
def test_degenerate_path_diverges(
    cid: str, cs: bytes, py_seq: str, java_seq: str
) -> None:
    """Degenerate / malformed move/curve inputs: PDFBox emits zero-length
    skeleton segments where fontTools collapses to an empty path. The geometry
    (bounds) is identical (all zero). Pinned both-sides."""
    java = _probe(cs)
    py = _py_fingerprint(cs)
    assert java[0] == "OK" and py[0] == "OK"
    assert java[2] == java_seq, (cid, "java", java)
    assert py[2] == py_seq, (cid, "py", py)
    assert py[3:] == ("0", "0", "0", "0")
    assert java[3:] == ("0", "0", "0", "0")


@requires_oracle
@pytest.mark.parametrize(
    ("cid", "cs"),
    [
        # 4-arg endchar = deprecated seac (accent composition): the probe's stub
        # reader can't resolve component glyphs, so PDFBox throws; pypdfbox's
        # fontTools path treats the endchar operands as a no-op -> empty path.
        ("endchar_4arg_seac", _op(1) + _op(2) + _op(3) + _op(4) + _E),
        ("endchar_5arg_seac",
         _op(0) + _op(1) + _op(2) + _op(3) + _op(4) + _E),
    ],
    ids=["endchar_4arg_seac", "endchar_5arg_seac"],
)
def test_seac_endchar_diverges(cid: str, cs: bytes) -> None:
    """A 4/5-operand ``endchar`` is the legacy ``seac`` accent-composition
    form. PDFBox resolves component glyphs through the font's
    ``Type1CharStringReader``; with no font wired the probe's reader throws, so
    PDFBox surfaces an exception (``ERR``). pypdfbox delegates to fontTools,
    which renders the base glyph and ignores the seac operands -> an empty path.
    Pinned both-sides."""
    java = _probe(cs)
    py = _py_fingerprint(cs)
    assert java[0] == "ERR", (cid, "expected probe ERR", java)
    assert py == ("OK", "0", "", "0", "0", "0", "0"), (cid, py)


# ---------------------------------------------------------------------------
# Empty / trivial — must agree without any normalisation.
# ---------------------------------------------------------------------------


@requires_oracle
@pytest.mark.parametrize(
    ("cid", "cs"),
    [("empty", b""), ("endchar_only", _E)],
    ids=["empty", "endchar_only"],
)
def test_empty_program_matches(cid: str, cs: bytes) -> None:
    """An empty program / a lone ``endchar`` renders no outline on both sides."""
    java = _probe(cs)
    py = _py_fingerprint(cs)
    assert java == ("OK", "0", "", "0", "0", "0", "0"), (cid, java)
    assert py == ("OK", "0", "", "0", "0", "0", "0"), (cid, py)


# ---------------------------------------------------------------------------
# Production-bug regression guard (runs WITHOUT the oracle): a standalone
# Type2CharString built from raw bytes / a list must render a real outline.
# ---------------------------------------------------------------------------


def test_standalone_bytes_constructor_renders_outline() -> None:
    """Wave-1544 regression: before the private-dict shim was wired, a
    ``Type2CharString`` built from raw bytes always returned ``[]`` from
    ``get_path()`` (bare fontTools ``T2CharString`` had no ``.private`` /
    ``.globalSubrs`` so ``draw()`` raised, swallowed). This guard does NOT need
    the live oracle."""
    cs = _op(0) + _op(0) + b"\x15" + _short(100) + _op(0) + b"\x05" + _E
    path = Type2CharString(None, "F", "g", 0, cs, 0, 0).get_path()
    assert path == [
        ("moveto", 0.0, 0.0),
        ("lineto", 100.0, 0.0),
        ("closepath",),
    ]


def test_standalone_list_constructor_renders_outline() -> None:
    """Wave-1544 regression: the parser-unrolled token list (numbers +
    ``CharStringCommand``) must also render. This pins the lowercase-operator
    fix in ``_coerce_program_token`` — fontTools keys operators by their
    lowercase mnemonic, so the upstream UPPERCASE ``CharStringCommand.name``
    had to be normalised."""
    from pypdfbox.fontbox.cff.type2_char_string_parser import (  # noqa: PLC0415
        Type2CharStringParser,
    )

    cs = _op(0) + _op(0) + b"\x15" + _short(100) + _op(0) + b"\x05" + _E
    seq = Type2CharStringParser("F").parse(cs, [], [], "g")
    path = Type2CharString(None, "F", "g", 0, seq, 0, 0).get_path()
    assert path == [
        ("moveto", 0.0, 0.0),
        ("lineto", 100.0, 0.0),
        ("closepath",),
    ]


def test_oracle_marker_present() -> None:
    """Sanity: the module imports the oracle harness cleanly even when the jar
    is absent (the differential tests skip via ``requires_oracle``)."""
    assert callable(oracle_available)
