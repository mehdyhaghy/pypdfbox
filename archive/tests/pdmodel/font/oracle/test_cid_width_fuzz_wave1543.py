"""Live PDFBox differential fuzz parity for the ``PDType0Font`` code -> CID ->
GID -> width *pipeline*.

Wave 1543, agent C. Where the wave-1528 ``CidFontWidthFuzzProbe`` fuzzes the
descendant CIDFont's ``/W`` / ``/W2`` / ``/DW`` / ``/DW2`` *array* parsing while
holding ``code_to_cid`` fixed at identity (reading off the bare descendant), and
``CidGidProbe`` / ``CidToGidStreamProbe`` load real on-disk fixtures, this probe
drives the *full* public ``PDType0Font`` pipeline over fuzzed encoding CMaps and
``/CIDToGIDMap`` entries:

* ``/Encoding`` as a custom embedded CMap **stream** (1-byte + 2-byte codespace,
  ``cidchar`` + ``cidrange``, out-of-codespace codes, a code mapping to CID 0);
* ``/Encoding`` as a predefined name (``Identity-H``);
* ``/CIDToGIDMap`` = ``/Identity`` name / absent / packed-uint16 **stream**
  (in-bounds, out-of-bounds CID, odd trailing byte, empty);
* ``/W`` list + range runs so the sweep crosses covered + uncovered CIDs;
* ``/DW`` present / absent.

For each case a fixed code sweep projects four accessors per code:
``code_to_cid`` (token ``c``), ``code_to_gid`` (token ``g``), ``get_width``
(token ``w``), ``get_width_from_font`` (token ``wf``).

The oracle is produced by ``oracle/probes/CidWidthFuzzProbe.java``.

Two token classes are pinned:

* **Parity tokens — ``c`` (code->CID) and ``w`` (get_width)** — pypdfbox must
  match Apache PDFBox exactly. These are the width/CID-mapping surface the wave
  targets and they are program-independent (driven entirely by the encoding CMap
  and the ``/W`` / ``/DW`` dictionary entries).

* **Divergent tokens — ``g`` (code->GID) and ``wf`` (get_width_from_font)** —
  pinned BOTH sides. When no font program is embedded, Apache PDFBox substitutes
  a system font (LiberationSans on the oracle box) and answers ``getWidthFromFont``
  / ``codeToGID`` from *that* substitute. pypdfbox's bundled ``DefaultFontMapper``
  has no on-disk CID-font scanner (see ``PDCIDFontType2.find_font_or_substitute``),
  so it answers ``get_width_from_font`` as ``0.0`` and resolves ``code_to_gid``
  from the *dictionary's own* ``/CIDToGIDMap`` (honouring an explicit stream that
  the Java substitute path overrides). The ``no_encoding`` case is fully
  divergent: Apache PDFBox raises (``getWidth`` needs the CMap) where pypdfbox
  resolves leniently. All three are pinned both-sides here.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE_CODES = (0, 1, 0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 100, 200, 1000, 65535)

# Custom CMap sources — kept byte-identical to the Java probe's string literals.
_CUSTOM_CMAP_1B = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\n"
    "begincmap\n"
    "/CMapName /CustomFuzz1B def\n"
    "/CMapType 1 def\n"
    "1 begincodespacerange\n"
    "<00> <ff>\n"
    "endcodespacerange\n"
    "1 begincidchar\n"
    "<41> 100\n"
    "endcidchar\n"
    "1 begincidrange\n"
    "<42> <44> 200\n"
    "endcidrange\n"
    "endcmap\n"
    "end end\n"
).encode("ascii")

_CUSTOM_CMAP_2B = (
    "/CIDInit /ProcSet findresource begin\n"
    "12 dict begin\n"
    "begincmap\n"
    "/CMapName /CustomFuzz2B def\n"
    "/CMapType 1 def\n"
    "1 begincodespacerange\n"
    "<0000> <ffff>\n"
    "endcodespacerange\n"
    "1 begincidchar\n"
    "<0041> 100\n"
    "endcidchar\n"
    "1 begincidrange\n"
    "<0042> <0044> 200\n"
    "endcidrange\n"
    "endcmap\n"
    "end end\n"
).encode("ascii")

# Cases where Apache PDFBox raises from the whole pipeline (CMap absent) while
# pypdfbox resolves leniently. Skipped in the parity test, pinned separately.
_FULLY_DIVERGENT = {"no_encoding"}


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _i(v: int) -> COSInteger:
    return COSInteger.get(v)


def _arr(*items: object) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _stream(body: bytes) -> COSStream:
    s = COSStream()
    s.set_data(body)
    return s


def _f(v: float) -> str:
    """Match the Java probe's ``f(float)`` (integral -> no decimals, -0.0 -> 0)."""
    if v == 0.0:
        v = 0.0
    if v == int(v) and v not in (float("inf"), float("-inf")):
        return str(int(v))
    import struct

    return repr(struct.unpack("f", struct.pack("f", v))[0])


def _cid_font() -> COSDictionary:
    d = COSDictionary()
    d.set_item(_n("Type"), _n("Font"))
    d.set_item(_n("Subtype"), _n("CIDFontType2"))
    d.set_item(_n("BaseFont"), _n("Test"))
    return d


def _sample_w() -> COSArray:
    # CID 100 -> 555 (list form); CIDs 200..202 -> 777 (range form).
    return _arr(_i(100), _arr(_i(555)), _i(200), _i(202), _i(777))


def _wrap(cid: COSDictionary, encoding: object) -> COSDictionary:
    t0 = COSDictionary()
    t0.set_item(_n("Type"), _n("Font"))
    t0.set_item(_n("Subtype"), _n("Type0"))
    t0.set_item(_n("BaseFont"), _n("Test"))
    t0.set_item(_n("Encoding"), encoding)
    t0.set_item(_n("DescendantFonts"), _arr(cid))
    return t0


def _build_cases() -> list[tuple[str, COSDictionary]]:
    """Build the identical fuzz corpus as CidWidthFuzzProbe.main, in order.

    Each entry is ``(name, full_type0_dict)``.
    """
    cases: list[tuple[str, COSDictionary]] = []

    e = _cid_font()
    e.set_item(_n("DW"), _i(333))
    e.set_item(_n("W"), _sample_w())
    cases.append(("identity_dw_w", _wrap(e, _n("Identity-H"))))

    e = _cid_font()
    e.set_item(_n("W"), _sample_w())
    cases.append(("identity_no_dw", _wrap(e, _n("Identity-H"))))

    e = _cid_font()
    e.set_item(_n("DW"), _i(444))
    cases.append(("identity_bare_dw", _wrap(e, _n("Identity-H"))))

    e = _cid_font()
    e.set_item(_n("DW"), _i(333))
    e.set_item(_n("W"), _sample_w())
    cases.append(("custom1b_dw_w", _wrap(e, _stream(_CUSTOM_CMAP_1B))))

    e = _cid_font()
    e.set_item(_n("DW"), _i(333))
    cases.append(("custom1b_no_w", _wrap(e, _stream(_CUSTOM_CMAP_1B))))

    e = _cid_font()
    e.set_item(_n("DW"), _i(333))
    e.set_item(_n("W"), _sample_w())
    cases.append(("custom2b_dw_w", _wrap(e, _stream(_CUSTOM_CMAP_2B))))

    e = _cid_font()
    e.set_item(_n("W"), _sample_w())
    e.set_item(_n("CIDToGIDMap"), _n("Identity"))
    cases.append(("gid_identity_name", _wrap(e, _n("Identity-H"))))

    gmap = bytes([0, 0, 0, 50, 0, 51, 0, 0, 0, 99])
    e = _cid_font()
    e.set_item(_n("W"), _sample_w())
    e.set_item(_n("CIDToGIDMap"), _stream(gmap))
    cases.append(("gid_stream", _wrap(e, _n("Identity-H"))))

    gmap_odd = bytes([0, 0, 0, 50, 0, 51, 9])
    e = _cid_font()
    e.set_item(_n("W"), _sample_w())
    e.set_item(_n("CIDToGIDMap"), _stream(gmap_odd))
    cases.append(("gid_stream_odd", _wrap(e, _n("Identity-H"))))

    e = _cid_font()
    e.set_item(_n("W"), _sample_w())
    e.set_item(_n("CIDToGIDMap"), _stream(b""))
    cases.append(("gid_stream_empty", _wrap(e, _n("Identity-H"))))

    e = _cid_font()
    e.set_item(_n("DW"), _i(333))
    e.set_item(_n("W"), _sample_w())
    e.set_item(_n("CIDToGIDMap"), _stream(gmap))
    cases.append(("custom1b_gid_stream", _wrap(e, _stream(_CUSTOM_CMAP_1B))))

    e = _cid_font()
    e.set_item(_n("DW"), _i(333))
    e.set_item(_n("W"), _arr(_i(0x40), _i(0x44), _i(888)))
    cases.append(("identity_range_w", _wrap(e, _n("Identity-H"))))

    # /Encoding omitted entirely.
    e = _cid_font()
    e.set_item(_n("DW"), _i(333))
    e.set_item(_n("W"), _sample_w())
    t0 = COSDictionary()
    t0.set_item(_n("Type"), _n("Font"))
    t0.set_item(_n("Subtype"), _n("Type0"))
    t0.set_item(_n("BaseFont"), _n("Test"))
    t0.set_item(_n("DescendantFonts"), _arr(e))
    cases.append(("no_encoding", t0))

    return cases


def _py_emit(name: str, t0_dict: COSDictionary) -> str:
    """Reconstruct one CidWidthFuzzProbe CASE line from pypdfbox."""
    try:
        t0 = PDType0Font(t0_dict)
    except Exception as exc:  # noqa: BLE001 - mirror the probe's Throwable catch
        return f"CASE {name} create=ERR:{type(exc).__name__}"
    if t0.get_descendant_font() is None:
        return f"CASE {name} create=nodesc"
    parts = ["CASE", name, "create=ok"]
    for code in _PROBE_CODES:
        try:
            parts.append(f"c{code}={t0.code_to_cid(code)}")
        except Exception:  # noqa: BLE001
            parts.append(f"c{code}=ERR")
        try:
            parts.append(f"g{code}={t0.code_to_gid(code)}")
        except Exception:  # noqa: BLE001
            parts.append(f"g{code}=ERR")
        try:
            parts.append(f"w{code}={_f(t0.get_width(code))}")
        except Exception:  # noqa: BLE001
            parts.append(f"w{code}=ERR")
        try:
            parts.append(f"wf{code}={_f(t0.get_width_from_font(code))}")
        except Exception:  # noqa: BLE001
            parts.append(f"wf{code}=ERR")
    return " ".join(parts)


def _java_lines() -> dict[str, str]:
    return {
        ln.split()[1]: ln
        for ln in run_probe_text("CidWidthFuzzProbe").splitlines()
        if ln.startswith("CASE ")
    }


def _is_parity_token(tok: str) -> bool:
    """Parity tokens are the ``c<code>=`` (code->CID) and ``w<code>=``
    (get_width) projections — program-independent, must match upstream.

    Divergent tokens are ``g<code>=`` (code->GID, substitute-font dependent)
    and ``wf<code>=`` (get_width_from_font, substitute-font dependent).
    """
    return (tok.startswith("c") or tok.startswith("w")) and not (
        tok.startswith("wf")
    )


@requires_oracle
def test_pipeline_cid_and_width_match_pdfbox() -> None:
    """The ``code->CID`` and ``get_width`` projections must match Apache PDFBox
    token-for-token across every (non-``no_encoding``) case.

    These two columns are driven purely by the encoding CMap and the
    ``/W`` / ``/DW`` dictionary entries, so they are independent of whether a
    font program (or substitute) is available. The substitute-font-dependent
    ``g`` / ``wf`` columns are pinned by the dedicated divergence test below.
    """
    java_lines = _java_lines()
    py_lines = {name: _py_emit(name, d) for name, d in _build_cases()}

    assert set(java_lines) == set(py_lines), (
        f"case-name set mismatch: java-only={set(java_lines) - set(py_lines)} "
        f"py-only={set(py_lines) - set(java_lines)}"
    )

    diffs: list[str] = []
    for name in sorted(py_lines):
        if name in _FULLY_DIVERGENT:
            continue
        j = java_lines[name].split()
        p = py_lines[name].split()
        # Header (CASE / name / create=) must match.
        if j[:3] != p[:3]:
            diffs.append(f"  {name} header: {j[:3]}|{p[:3]}")
            continue
        j_tok = {t.split("=")[0]: t for t in j[3:]}
        p_tok = {t.split("=")[0]: t for t in p[3:]}
        for key in sorted(j_tok):
            if not _is_parity_token(key):
                continue
            if j_tok[key] != p_tok.get(key):
                diffs.append(f"  {name}: {j_tok[key]}|{p_tok.get(key)}")
    assert not diffs, "CID/width pipeline parity broken:\n" + "\n".join(diffs[:20])


@requires_oracle
def test_substitute_font_columns_diverge_both_sides() -> None:
    """Pin the substitute-font divergence on the ``g`` / ``wf`` columns.

    Apache PDFBox, lacking an embedded program, substitutes a system font and
    answers ``getWidthFromFont`` from it (non-zero advances) and resolves
    ``codeToGID`` through the substitute (ignoring an explicit ``/CIDToGIDMap``
    stream). pypdfbox has no on-disk CID-font scanner, so ``get_width_from_font``
    is ``0.0`` for every code and ``code_to_gid`` honours the dictionary's own
    ``/CIDToGIDMap``. This asserts BOTH observable sides of that divergence
    (CHANGES.md Wave 1543) so a future substitute-font scanner can't silently
    flip the contract.
    """
    java_lines = _java_lines()

    # 1. Java's getWidthFromFont is non-zero for at least one printable code
    #    (substitute font has real advances); pypdfbox's is uniformly 0.
    j = java_lines["identity_dw_w"].split()
    j_wf = {t.split("=")[0]: t.split("=")[1] for t in j if t.startswith("wf")}
    assert any(v not in ("0", "0.0") for v in j_wf.values()), (
        "expected Apache PDFBox to report non-zero substitute-font widths"
    )

    py = _py_emit("identity_dw_w", dict(_build_cases())["identity_dw_w"])
    p_wf = {
        t.split("=")[0]: t.split("=")[1]
        for t in py.split()
        if t.startswith("wf")
    }
    assert all(v == "0" for v in p_wf.values()), (
        f"expected pypdfbox get_width_from_font == 0 (no substitute scanner): {p_wf}"
    )

    # 2. The /CIDToGIDMap stream is honoured by pypdfbox but overridden by the
    #    Java substitute path: code 1 -> CID 1 -> GID 50 (stream) in pypdfbox,
    #    GID 1 (substitute identity) in Apache PDFBox.
    j_gs = java_lines["gid_stream"].split()
    j_g1 = next(t for t in j_gs if t.startswith("g1="))
    assert j_g1 == "g1=1", f"expected Apache substitute identity GID, got {j_g1}"

    py_gs = _py_emit("gid_stream", dict(_build_cases())["gid_stream"])
    py_g1 = next(t for t in py_gs.split() if t.startswith("g1="))
    assert py_g1 == "g1=50", (
        f"expected pypdfbox to honour /CIDToGIDMap stream (GID 50), got {py_g1}"
    )


@requires_oracle
def test_no_encoding_case_diverges_both_sides() -> None:
    """``/Encoding`` absent: Apache PDFBox raises from the whole pipeline,
    pypdfbox resolves leniently.

    Upstream ``PDType0Font.getWidth`` / ``codeToGID`` dereference the encoding
    CMap; with no ``/Encoding`` the constructor leaves the CMap null and every
    accessor throws ``NullPointerException`` (rendered ``ERR`` by the probe).
    pypdfbox guards the null CMap (``code_to_cid`` passes the code through, the
    ``/W`` lookup answers from the dictionary), so construction + every accessor
    succeed. Pinned both sides (CHANGES.md Wave 1543).
    """
    java_lines = _java_lines()
    j = java_lines["no_encoding"].split()
    assert all(t.endswith("=ERR") for t in j[3:]), (
        f"expected upstream pipeline to throw for no_encoding, got {j}"
    )

    py = _py_emit("no_encoding", dict(_build_cases())["no_encoding"])
    assert "create=ok" in py, f"expected lenient pypdfbox resolution: {py}"
    # Width still answers from /W: CID 100 -> 555, uncovered -> /DW 333.
    assert "w100=555" in py.split(), py
    assert "w0=333" in py.split(), py
