"""Live PDFBox differential fuzz parity for the ``PDColorSpace.create`` FACTORY
DISPATCH and ``PDResources``-backed name resolution (wave 1564, agent E).

Sibling of ``oracle/probes/ColorSpaceCreateFuzzProbe.java``. Where the earlier
wave-1512 fuzz drove the *malformed array-form constructor leniency*, this one
isolates the ``create()`` **dispatch** surface itself:

- device names long form (``DeviceGray``/``DeviceRGB``/``DeviceCMYK``)
- device abbreviations (``G``/``RGB``/``CMYK``) and the indexed abbreviation
  ``I`` handed to the *bare* ``create()`` factory — these are only legal in
  inline-image context, so the bare factory's treatment of them is the
  interesting dispatch corner
- ``Pattern`` as a *name* vs an *array* ``[/Pattern base]``
- array-form dispatch to the correct subclass for CalGray/CalRGB/Lab/ICCBased/
  Indexed/Separation/DeviceN (verifying ``getClass()`` + component count)
- a *named* colour space resolved from a ``PDResources`` ``/ColorSpace`` entry
- an *unknown* name (error / fallback), with and without resources
- a name that is also a device name but with a resource entry present
- empty / wrong-arity / mistyped arrays
- non-array / non-name inputs

Two ``create()`` call shapes are projected per case::

    create(base, None)        -> "noRes"   (no resource resolution)
    create(base, resources)   -> "withRes" (resource dict supplied)

The probe emits one line per case::

    CASE <name> noRes=<proj> withRes=<proj>

where ``<proj>`` is ``ERR`` (create threw), ``NULL`` (returned ``None``), or
``class=<C>,nc=<n|ERR>``.

This module rebuilds the *identical* corpus + resources, projects the identical
grammar from ``pypdfbox.pdmodel.graphics.color.PDColorSpace.create(...)``, and
asserts line-for-line parity against the live Java oracle.

Where pypdfbox diverges, the case name maps to its exact pypdfbox CASE line in
``_EXPECTED_DIVERGENCES`` with a documented reason; every such case is pinned
*both sides* (assert pypdfbox emits the pinned line AND that Java differs), so if
upstream ever converges the pin fails loudly. Cases not in the map must match
Java byte-for-byte.

Three pre-existing, deliberate divergence families (none is an undiscovered
correctness bug — see CHANGES.md "Wave 1512 — PDColorSpace.create fuzz" and the
new "Wave 1564" row):

1. **Permissive ``create`` contract.** Upstream ``PDColorSpace.create`` *throws*
   (``IOException``/``MissingResourceException``) for every unknown/malformed/
   non-colour-space input (``noRes=ERR``). pypdfbox returns ``None`` for the
   structural dispatch (``noRes=NULL``) and lets callers decide; the array-form
   constructors are lenient and surface defects later. Pinned by the upstream
   test ports since wave 1512.
2. **Inline abbreviation expansion.** pypdfbox's bare ``create()`` expands the
   inline-image colour-space abbreviations ``G``/``RGB``/``CMYK`` (and the
   indexed ``I``) to their device / array forms directly, while upstream's
   ``PDColorSpace.create`` does **not** — upstream only honours abbreviations
   inside ``PDInlineImage`` (so ``create(/G)`` throws ``IOException``). This is
   intentional pypdfbox leniency: the abbreviation table lives once in
   ``create()`` and the inline-image path reuses it rather than maintaining a
   second copy. (``name_abbrev_*`` / ``array_abbrev_*`` / ``array_indexed_abbrev_i``.)
3. **PDPattern component surface.** Upstream ``PDPattern.getNumberOfComponents``
   throws ``UnsupportedOperationException`` (``nc=ERR``); pypdfbox returns ``0``
   so callers that just want a size get a sane answer (``nc=0``).
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders (mirror ColorSpaceCreateFuzzProbe.java helpers) ----------


def _n(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _floats(*vals: float) -> COSArray:
    a = COSArray()
    for v in vals:
        a.add(COSFloat(v))
    return a


def _type2(c0: list[float], c1: list[float], n_exp: float) -> COSDictionary:
    d = COSDictionary()
    d.set_int(_n("FunctionType"), 2)
    d.set_item(_n("Domain"), _floats(0, 1))
    a0 = COSArray()
    for v in c0:
        a0.add(COSFloat(v))
    d.set_item(_n("C0"), a0)
    a1 = COSArray()
    for v in c1:
        a1.add(COSFloat(v))
    d.set_item(_n("C1"), a1)
    d.set_item(_n("N"), COSFloat(n_exp))
    return d


def _icc_stream(n_val: int) -> COSStream:
    s = COSStream()
    s.set_int(_n("N"), n_val)
    s.create_output_stream().close()
    return s


def _cal_dict(white_point: COSArray | None, gamma: COSArray | None) -> COSDictionary:
    d = COSDictionary()
    if white_point is not None:
        d.set_item(_n("WhitePoint"), white_point)
    if gamma is not None:
        d.set_item(_n("Gamma"), gamma)
    return d


def _lab_dict(white_point: COSArray | None, range_arr: COSArray | None) -> COSDictionary:
    d = COSDictionary()
    if white_point is not None:
        d.set_item(_n("WhitePoint"), white_point)
    if range_arr is not None:
        d.set_item(_n("Range"), range_arr)
    return d


def _build_resources() -> PDResources:
    """A /ColorSpace subdictionary mirroring ColorSpaceCreateFuzzProbe.buildResources()."""
    cs = COSDictionary()
    cs.set_item(
        _n("MyRGB"),
        _arr(_n("CalRGB"), _cal_dict(_floats(1, 1, 1), _floats(1, 1, 1))),
    )
    cs.set_item(
        _n("MyLab"),
        _arr(
            _n("Lab"),
            _lab_dict(_floats(0.9642, 1, 0.8249), _floats(-128, 127, -128, 127)),
        ),
    )
    # Shadow the DeviceRGB device name with a CalGray entry.
    cs.set_item(
        _n("DeviceRGB"),
        _arr(_n("CalGray"), _cal_dict(_floats(0.95, 1, 1.09), None)),
    )
    cs.set_item(
        _n("Sep"),
        _arr(
            _n("Separation"),
            _n("Spot"),
            _n("DeviceCMYK"),
            _type2([0, 0, 0, 0], [0, 1, 1, 0], 1),
        ),
    )
    res_dict = COSDictionary()
    res_dict.set_item(_n("ColorSpace"), cs)
    return PDResources(res_dict)


# ---------- projection (mirror ColorSpaceCreateFuzzProbe.project) ----------


def _project(base: COSBase | None, res: PDResources | None) -> str:
    try:
        cs = PDColorSpace.create(base, res)
    except Exception:
        return "ERR"
    if cs is None:
        return "NULL"
    out = "class=" + type(cs).__name__ + ",nc="
    try:
        out += str(cs.get_number_of_components())
    except Exception:
        out += "ERR"
    return out


def _case_line(name: str, base: COSBase | None, res: PDResources | None) -> str:
    return f"CASE {name} noRes={_project(base, None)} withRes={_project(base, res)}"


def _build_corpus() -> list[str]:
    """Rebuild the identical corpus, case-for-case, in probe order."""
    res = _build_resources()
    pal = bytes([0, 0, 0, 255, 0, 0])
    lines: list[str] = []

    def emit(name: str, base: COSBase | None) -> None:
        lines.append(_case_line(name, base, res))

    # device names, long form
    emit("name_devicegray", _n("DeviceGray"))
    emit("name_devicergb", _n("DeviceRGB"))
    emit("name_devicecmyk", _n("DeviceCMYK"))
    # device abbreviations
    emit("name_abbrev_g", _n("G"))
    emit("name_abbrev_rgb", _n("RGB"))
    emit("name_abbrev_cmyk", _n("CMYK"))
    # /Pattern name vs array
    emit("name_pattern", _n("Pattern"))
    emit("array_pattern_bare", _arr(_n("Pattern")))
    emit("array_pattern_base_rgb", _arr(_n("Pattern"), _n("DeviceRGB")))
    emit("array_pattern_base_cmyk", _arr(_n("Pattern"), _n("DeviceCMYK")))
    # array-form dispatch -> correct subclass
    emit("array_calgray", _arr(_n("CalGray"), _cal_dict(_floats(0.95, 1, 1.09), None)))
    emit("array_calrgb", _arr(_n("CalRGB"), _cal_dict(_floats(1, 1, 1), _floats(1, 1, 1))))
    emit(
        "array_lab",
        _arr(_n("Lab"), _lab_dict(_floats(0.9642, 1, 0.8249), _floats(-128, 127, -128, 127))),
    )
    emit("array_iccbased_n3", _arr(_n("ICCBased"), _icc_stream(3)))
    emit("array_iccbased_n1", _arr(_n("ICCBased"), _icc_stream(1)))
    emit("array_iccbased_n4", _arr(_n("ICCBased"), _icc_stream(4)))
    emit(
        "array_indexed",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(1), COSString(pal)),
    )
    emit(
        "array_indexed_abbrev_i",
        _arr(_n("I"), _n("DeviceRGB"), COSInteger.get(1), COSString(pal)),
    )
    emit(
        "array_separation",
        _arr(
            _n("Separation"),
            _n("Spot"),
            _n("DeviceCMYK"),
            _type2([0, 0, 0, 0], [0, 1, 1, 0], 1),
        ),
    )
    emit(
        "array_devicen",
        _arr(
            _n("DeviceN"),
            _arr(_n("S1"), _n("S2")),
            _n("DeviceRGB"),
            _type2([0, 0], [1, 1], 1),
        ),
    )
    # array head = device names (full + abbrev)
    emit("array_devicegray", _arr(_n("DeviceGray")))
    emit("array_devicergb", _arr(_n("DeviceRGB")))
    emit("array_abbrev_g", _arr(_n("G")))
    emit("array_abbrev_rgb", _arr(_n("RGB")))
    emit("array_abbrev_cmyk", _arr(_n("CMYK")))
    # named colour space resolved from /Resources/ColorSpace
    emit("resource_myrgb", _n("MyRGB"))
    emit("resource_mylab", _n("MyLab"))
    emit("resource_sep", _n("Sep"))
    # unknown name (error / fallback)
    emit("name_unknown", _n("FooBar"))
    emit("name_unknown2", _n("NotAColorSpace"))
    # device name shadowed by a resource entry
    emit("shadowed_devicergb", _n("DeviceRGB"))
    # empty / wrong-arity / mistyped arrays
    emit("empty_array", COSArray())
    emit("array_head_not_name", _arr(COSInteger.get(1), _n("DeviceRGB")))
    emit("array_head_null", _arr(COSNull.NULL))
    emit("array_unknown_head", _arr(_n("FooBar"), _n("DeviceRGB")))
    emit("array_indexed_two", _arr(_n("Indexed"), _n("DeviceRGB")))
    # non-array / non-name inputs
    emit("integer_input", COSInteger.get(7))
    emit("string_input", COSString("DeviceRGB"))
    emit("null_input", None)
    return lines


# ---------- documented both-sides-pinned divergences ----------
#
# Map: case name -> (noRes projection, withRes projection). Built into a full
# CASE line by ``_pin_line`` below. Every entry is asserted to (a) match
# pypdfbox and (b) differ from the live Java oracle.

_DG = "class=PDDeviceGray,nc=1"
_DR = "class=PDDeviceRGB,nc=3"
_DC = "class=PDDeviceCMYK,nc=4"
_PAT = "class=PDPattern,nc=0"
_IDX = "class=PDIndexed,nc=1"

_DIVERGENCE_PROJECTIONS: dict[str, tuple[str, str]] = {
    # --- inline abbreviation expansion (family 2): pypdfbox expands; Java throws ---
    "name_abbrev_g": (_DG, _DG),
    "name_abbrev_rgb": (_DR, _DR),
    "name_abbrev_cmyk": (_DC, _DC),
    "array_abbrev_g": (_DG, _DG),
    "array_abbrev_rgb": (_DR, _DR),
    "array_abbrev_cmyk": (_DC, _DC),
    "array_indexed_abbrev_i": (_IDX, _IDX),
    # --- PDPattern 0-component surface (family 3): Java getNumberOfComponents throws ---
    "name_pattern": (_PAT, _PAT),
    "array_pattern_bare": (_PAT, _PAT),
    "array_pattern_base_rgb": (_PAT, _PAT),
    "array_pattern_base_cmyk": (_PAT, _PAT),
    # --- permissive create() (family 1): pypdfbox None where Java throws ---
    "resource_myrgb": ("NULL", "class=PDCalRGB,nc=3"),
    "resource_mylab": ("NULL", "class=PDLab,nc=3"),
    "resource_sep": ("NULL", "class=PDSeparation,nc=1"),
    "name_unknown": ("NULL", "ERR"),
    "name_unknown2": ("NULL", "ERR"),
    "empty_array": ("NULL", "NULL"),
    "array_head_not_name": ("NULL", "NULL"),
    "array_head_null": ("NULL", "NULL"),
    "array_unknown_head": ("NULL", "NULL"),
    "array_indexed_two": (_IDX, _IDX),
    "integer_input": ("NULL", "NULL"),
    "string_input": ("NULL", "NULL"),
    # Java's create(null, ...) throws; pypdfbox returns None per the §43
    # "None -> None" contract (PDColorSpace.create line 93).
    "null_input": ("NULL", "NULL"),
}


def _pin_line(name: str) -> str:
    no_res, with_res = _DIVERGENCE_PROJECTIONS[name]
    return f"CASE {name} noRes={no_res} withRes={with_res}"


_EXPECTED_DIVERGENCES: dict[str, str] = {
    name: _pin_line(name) for name in _DIVERGENCE_PROJECTIONS
}


def _name_of(line: str) -> str:
    return line.split(" ", 2)[1]


# ---------- self-contained pypdfbox pins (run even without the oracle) ----------


def test_pypdfbox_corpus_is_stable() -> None:
    """The pypdfbox projection of every case matches the wave-1564 snapshot.

    This pins pypdfbox behaviour independently of the live oracle (so the
    create-dispatch contract is regression-locked on machines without Java).
    """
    lines = _build_corpus()
    by_name = {_name_of(line): line for line in lines}
    # Spot-check the load-bearing dispatch outcomes.
    assert by_name["name_devicegray"].endswith(
        "noRes=class=PDDeviceGray,nc=1 withRes=class=PDDeviceGray,nc=1"
    )
    assert by_name["array_calgray"].endswith(
        "noRes=class=PDCalGray,nc=1 withRes=class=PDCalGray,nc=1"
    )
    assert by_name["array_indexed"].endswith(
        "noRes=class=PDIndexed,nc=1 withRes=class=PDIndexed,nc=1"
    )
    assert by_name["array_separation"].endswith(
        "noRes=class=PDSeparation,nc=1 withRes=class=PDSeparation,nc=1"
    )
    assert by_name["array_devicen"].endswith(
        "noRes=class=PDDeviceN,nc=2 withRes=class=PDDeviceN,nc=2"
    )
    # Resource resolution: a named array CS resolves only with resources.
    assert by_name["resource_myrgb"] == _EXPECTED_DIVERGENCES["resource_myrgb"]
    # Device name is NOT shadowed by a resource entry in create() (Java parity).
    assert by_name["shadowed_devicergb"].endswith(
        "noRes=class=PDDeviceRGB,nc=3 withRes=class=PDDeviceRGB,nc=3"
    )
    # null is None on both call shapes.
    assert by_name["null_input"] == "CASE null_input noRes=NULL withRes=NULL"


def test_documented_divergences_match_pypdfbox() -> None:
    """Each pinned divergence line is exactly what pypdfbox emits today."""
    by_name = {_name_of(line): line for line in _build_corpus()}
    for name, expected in _EXPECTED_DIVERGENCES.items():
        assert by_name[name] == expected, name


# ---------- live oracle differential ----------


@requires_oracle
def test_color_space_create_dispatch_matches_pdfbox() -> None:
    """Line-for-line parity with the live PDFBox 3.0.7 oracle.

    Non-divergent cases must match byte-for-byte; pinned divergences must
    (a) match the pypdfbox snapshot and (b) genuinely differ from Java, so a
    silent upstream convergence trips the pin.
    """
    java_lines = run_probe_text("ColorSpaceCreateFuzzProbe").splitlines()
    java_by_name = {_name_of(line): line for line in java_lines if line.startswith("CASE ")}
    py_by_name = {_name_of(line): line for line in _build_corpus()}

    assert set(java_by_name) == set(py_by_name)

    for name, py_line in py_by_name.items():
        java_line = java_by_name[name]
        if name in _EXPECTED_DIVERGENCES:
            assert py_line == _EXPECTED_DIVERGENCES[name], name
            assert py_line != java_line, (
                f"{name}: upstream converged — re-validate and drop the pin "
                f"(java={java_line!r})"
            )
        else:
            assert py_line == java_line, name


@requires_oracle
def test_divergence_map_is_complete() -> None:
    """Every case that actually differs from Java is in the divergence map.

    Guards against an undocumented drift: if pypdfbox starts diverging on a
    case not in ``_EXPECTED_DIVERGENCES`` the suite fails here, forcing a
    conscious pin (or a fix) rather than a silent mismatch.
    """
    java_by_name = {
        _name_of(line): line
        for line in run_probe_text("ColorSpaceCreateFuzzProbe").splitlines()
        if line.startswith("CASE ")
    }
    py_by_name = {_name_of(line): line for line in _build_corpus()}
    actual_divergences = {
        name for name, line in py_by_name.items() if line != java_by_name[name]
    }
    assert actual_divergences == set(_EXPECTED_DIVERGENCES), (
        "divergence map drift: "
        f"unexpected={actual_divergences - set(_EXPECTED_DIVERGENCES)} "
        f"stale={set(_EXPECTED_DIVERGENCES) - actual_divergences}"
    )
