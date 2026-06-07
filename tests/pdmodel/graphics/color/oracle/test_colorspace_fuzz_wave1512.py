"""Live PDFBox differential fuzz parity for ``PDColorSpace.create(COSBase)``
construction leniency (wave 1512, agent B).

Sibling of ``oracle/probes/ColorSpaceFuzzProbe.java``. The Java probe drives a
fixed, seed-free corpus of malformed / missing / mistyped colour-space COS
forms (name-form unknowns, /Indexed wrong arity & hival corners,
lookup-as-string/stream/missing/short, /Separation & /DeviceN arity +
tint-transform corners, /ICCBased /N mismatch + garbage profile bytes,
/Cal* & /Lab missing/short WhitePoint, /Pattern with/without base, and
non-array/non-name inputs) and prints one CASE line per case in the grammar::

    CASE <name> create=<ERR | NULL | ok class=<C> nc=<n|ERR> \\
        init=<a,b,..|ERR> rgb=<r;g;b|ERR|NA>>

This module rebuilds the *identical* corpus, case-for-case in the same order,
emits the identical CASE-line grammar from
``pypdfbox.pdmodel.graphics.color.PDColorSpace.create(...)``, and asserts
line-for-line parity against the live Java oracle.

Where pypdfbox diverges from Java the case name is listed in
``_EXPECTED_DIVERGENCES`` together with the exact pypdfbox CASE line and a
documented reason. Every such case is pinned *both sides*: we assert pypdfbox
emits the pinned line AND that the Java oracle differs (so the divergence
rationale stays honest — if Java ever converges, the test fails loudly and the
pin must be removed). Cases not in the map must match Java byte-for-byte.

Three documented divergence families (all pre-existing, deliberate design
decisions — none is an undiscovered correctness bug; see CHANGES.md row
"wave 1512 — PDColorSpace.create fuzz"):

1. **Permissive ``create`` contract.** Upstream ``PDColorSpace.create`` *throws*
   (``IOException`` / ``MissingResourceException``) on every malformed/unknown
   input (``create=ERR``). pypdfbox returns ``None`` for the structural
   dispatch (``create=NULL``) and lets callers decide, and the array-form
   constructors (``PDIndexed``/``PDSeparation``/``PDDeviceN``/``PDICCBased``/
   ``PDCal*``) are lenient — they construct from a malformed array and surface
   the defect later (``nc``/``init``/``rgb`` = ERR/NA). This is the documented
   permissive-factory contract pinned by the upstream-test ports
   (``tests/.../upstream/test_pd_color_space.py`` lines 130-140) and the design
   comment in ``pd_resources.py``: short device names (``G``/``RGB``/``CMYK``)
   are only resolved by callers that pre-expand to the long form (inline
   images via ``_to_long_name``), so the bare ``create(name)`` factory stays
   permissive.
2. **JVM CMM colour math.** For DeviceCMYK / Cal* / Lab / Separation+DeviceN
   routed through a CMYK alternate, PDFBox routes ``toRGB`` through the JVM
   colour-management module while pypdfbox uses explicit deterministic colour
   math (waves 1330C / 1386). Same divergence pinned by
   ``test_color_space_to_rgb_oracle.py``; deltas reach tens of 255, not
   rounding epsilons.
3. **PDPattern component surface.** Upstream ``PDPattern.getNumberOfComponents``
   / ``getInitialColor`` throw ``UnsupportedOperationException`` (``nc=ERR``);
   pypdfbox returns ``0`` components + an empty ``PDColor`` so callers that
   just want a size get a sane answer (``nc=0 init= rgb=NA``).
"""

from __future__ import annotations

import pytest

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
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders (mirror ColorSpaceFuzzProbe.java helpers) ----------


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
        a.add(COSFloat(float(v)))
    return a


def _type2(c0: list[float], c1: list[float], n_exp: float) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", _floats(0, 1))
    d.set_item("C0", _floats(*c0))
    d.set_item("C1", _floats(*c1))
    d.set_item("N", COSFloat(float(n_exp)))
    return d


def _type4(domain_pairs: int, range_pairs: int, body: str) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    dom = COSArray()
    for _ in range(domain_pairs):
        dom.add(COSFloat(0.0))
        dom.add(COSFloat(1.0))
    s.set_item("Domain", dom)
    rng = COSArray()
    for _ in range(range_pairs):
        rng.add(COSFloat(0.0))
        rng.add(COSFloat(1.0))
    s.set_item("Range", rng)
    with s.create_output_stream() as os:
        os.write(body.encode("ascii"))
    return s


def _icc(n_val: int, profile_bytes: bytes | None) -> COSStream:
    s = COSStream()
    s.set_int("N", n_val)
    with s.create_output_stream() as os:
        if profile_bytes is not None:
            os.write(profile_bytes)
    return s


def _icc_with_alternate(n_val: int, alt: COSName) -> COSStream:
    s = _icc(n_val, None)
    s.set_item("Alternate", alt)
    return s


def _cal_dict(
    white_point: COSArray | None, gamma: COSArray | None, single_gamma: float
) -> COSDictionary:
    d = COSDictionary()
    if white_point is not None:
        d.set_item("WhitePoint", white_point)
    if gamma is not None:
        d.set_item("Gamma", gamma)
    elif single_gamma != 0:
        d.set_item("Gamma", COSFloat(float(single_gamma)))
    return d


def _lab_dict(white_point: COSArray | None, rng: COSArray | None) -> COSDictionary:
    d = COSDictionary()
    if white_point is not None:
        d.set_item("WhitePoint", white_point)
    if rng is not None:
        d.set_item("Range", rng)
    return d


# ---------- CASE-line emitter (mirror ColorSpaceFuzzProbe.emit) ----------


def _clamp255(v: float) -> int:
    r = round(v * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _emit(name: str, base: COSBase | None) -> str:
    """Build the CASE line for ``base``, mirroring the Java probe exactly."""
    sb = f"CASE {name} "
    try:
        cs = PDColorSpace.create(base, None)
    except Exception:  # noqa: BLE001 — probe mirrors Java's catch(Throwable)
        return sb + "create=ERR"
    if cs is None:
        return sb + "create=NULL"
    sb += "create=ok class=" + type(cs).__name__
    try:
        nc = cs.get_number_of_components()
        sb += " nc=" + str(nc)
    except Exception:  # noqa: BLE001
        return sb + " nc=ERR"
    try:
        init = cs.get_initial_color().get_components()
        sb += " init=" + ",".join(f"{c:.3f}" for c in init)
    except Exception:  # noqa: BLE001
        sb += " init=ERR"
    if nc <= 0:
        return sb + " rgb=NA"
    try:
        sample = [0.5] * nc
        if isinstance(cs, PDIndexed):
            sample[0] = 0.0
        rgb = cs.to_rgb(sample)
        sb += f" rgb={_clamp255(rgb[0])};{_clamp255(rgb[1])};{_clamp255(rgb[2])}"
    except Exception:  # noqa: BLE001
        sb += " rgb=ERR"
    return sb


# ---------- the corpus (identical to ColorSpaceFuzzProbe.main, in order) ----


def _build_cases() -> list[tuple[str, COSBase | None]]:
    pal = bytes([0, 0, 0, 255, 0, 0])
    cases: list[tuple[str, COSBase | None]] = []

    def add(name: str, base: COSBase | None) -> None:
        cases.append((name, base))

    # ===== name-form =====
    add("name_devicegray", _n("DeviceGray"))
    add("name_devicergb", _n("DeviceRGB"))
    add("name_devicecmyk", _n("DeviceCMYK"))
    add("name_short_g", _n("G"))
    add("name_short_rgb", _n("RGB"))
    add("name_short_cmyk", _n("CMYK"))
    add("name_pattern", _n("Pattern"))
    add("name_unknown", _n("FooBar"))
    add("name_indexed_bare", _n("Indexed"))
    add("name_iccbased_bare", _n("ICCBased"))
    add("name_separation_bare", _n("Separation"))

    # ===== non-array / non-name inputs =====
    add("null_input", None)
    add("integer_input", COSInteger.get(7))
    add("string_input", COSString("DeviceRGB"))
    add("float_input", COSFloat(1.5))
    add("cosnull_input", COSNull.NULL)
    add("empty_array", COSArray())
    add("array_head_not_name", _arr(COSInteger.get(1), _n("DeviceRGB")))
    add("array_head_null", _arr(COSNull.NULL, _n("DeviceRGB")))
    add("array_one_name_rgb", _arr(_n("DeviceRGB")))
    add("array_one_name_unknown", _arr(_n("FooBar")))
    add("array_unknown_head", _arr(_n("FooBar"), _n("DeviceRGB")))

    # ===== /Indexed corners =====
    add(
        "indexed_wellformed",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(1), COSString(pal)),
    )
    add("indexed_two_elements", _arr(_n("Indexed"), _n("DeviceRGB")))
    add(
        "indexed_three_elements",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(1)),
    )
    add(
        "indexed_five_elements",
        _arr(
            _n("Indexed"),
            _n("DeviceRGB"),
            COSInteger.get(1),
            COSString(pal),
            COSInteger.get(99),
        ),
    )
    add(
        "indexed_hival_negative",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(-5), COSString(pal)),
    )
    add(
        "indexed_hival_huge",
        _arr(
            _n("Indexed"), _n("DeviceRGB"), COSInteger.get(100000), COSString(pal)
        ),
    )
    add(
        "indexed_hival_real",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSFloat(3.7), COSString(pal)),
    )
    add(
        "indexed_hival_string",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSString("3"), COSString(pal)),
    )
    add(
        "indexed_lookup_missing",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(1), COSNull.NULL),
    )
    add(
        "indexed_lookup_short",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(10), COSString(pal)),
    )
    add(
        "indexed_lookup_as_name",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(1), _n("notalookup")),
    )
    add(
        "indexed_base_unknown",
        _arr(_n("Indexed"), _n("FooBar"), COSInteger.get(1), COSString(pal)),
    )
    add(
        "indexed_base_devicegray",
        _arr(
            _n("Indexed"),
            _n("DeviceGray"),
            COSInteger.get(1),
            COSString(bytes([0, 255])),
        ),
    )
    inner_idx = _arr(
        _n("Indexed"), _n("DeviceRGB"), COSInteger.get(1), COSString(pal)
    )
    add(
        "indexed_base_nested_indexed",
        _arr(_n("Indexed"), inner_idx, COSInteger.get(1), COSString(bytes([0, 1]))),
    )
    lk_stream = COSStream()
    with lk_stream.create_output_stream() as lkos:
        lkos.write(bytes([0, 0, 0, 10, 20, 30]))
    add(
        "indexed_lookup_as_stream",
        _arr(_n("Indexed"), _n("DeviceRGB"), COSInteger.get(1), lk_stream),
    )

    # ===== /Separation corners =====
    add(
        "separation_wellformed",
        _arr(
            _n("Separation"),
            _n("Spot"),
            _n("DeviceCMYK"),
            _type2([0, 0, 0, 0], [0, 1, 1, 0], 1),
        ),
    )
    add(
        "separation_three_elements",
        _arr(_n("Separation"), _n("Spot"), _n("DeviceCMYK")),
    )
    add("separation_two_elements", _arr(_n("Separation"), _n("Spot")))
    add(
        "separation_alt_unknown",
        _arr(_n("Separation"), _n("Spot"), _n("FooBar"), _type2([0], [1], 1)),
    )
    add(
        "separation_tint_missing",
        _arr(_n("Separation"), _n("Spot"), _n("DeviceCMYK"), COSNull.NULL),
    )
    add(
        "separation_tint_not_function",
        _arr(_n("Separation"), _n("Spot"), _n("DeviceCMYK"), _n("notafunction")),
    )
    add(
        "separation_name_all",
        _arr(
            _n("Separation"),
            _n("All"),
            _n("DeviceCMYK"),
            _type2([0, 0, 0, 0], [1, 1, 1, 1], 1),
        ),
    )

    # ===== /DeviceN corners =====
    add(
        "devicen_wellformed",
        _arr(
            _n("DeviceN"),
            _arr(_n("S1"), _n("S2")),
            _n("DeviceCMYK"),
            _type4(2, 4, "{ 0 0 }"),
        ),
    )
    add(
        "devicen_names_empty",
        _arr(_n("DeviceN"), COSArray(), _n("DeviceCMYK"), _type4(0, 4, "{ 0 0 0 0 }")),
    )
    add(
        "devicen_names_nonnames",
        _arr(
            _n("DeviceN"),
            _arr(COSInteger.get(1), COSInteger.get(2)),
            _n("DeviceCMYK"),
            _type4(2, 4, "{ 0 0 }"),
        ),
    )
    add(
        "devicen_names_not_array",
        _arr(_n("DeviceN"), _n("S1"), _n("DeviceCMYK"), _type4(1, 4, "{ 0 0 0 }")),
    )
    add(
        "devicen_three_elements",
        _arr(_n("DeviceN"), _arr(_n("S1"), _n("S2")), _n("DeviceCMYK")),
    )
    add(
        "devicen_alt_unknown",
        _arr(_n("DeviceN"), _arr(_n("S1")), _n("FooBar"), _type4(1, 1, "{ }")),
    )
    add(
        "devicen_tint_missing",
        _arr(_n("DeviceN"), _arr(_n("S1"), _n("S2")), _n("DeviceCMYK"), COSNull.NULL),
    )

    # ===== /ICCBased corners =====
    add("iccbased_n3_no_profile", _arr(_n("ICCBased"), _icc(3, None)))
    add("iccbased_n1", _arr(_n("ICCBased"), _icc(1, None)))
    add("iccbased_n4", _arr(_n("ICCBased"), _icc(4, None)))
    add("iccbased_n0", _arr(_n("ICCBased"), _icc(0, None)))
    add("iccbased_n2", _arr(_n("ICCBased"), _icc(2, None)))
    add("iccbased_n5", _arr(_n("ICCBased"), _icc(5, None)))
    icc_no_n = COSStream()
    with icc_no_n.create_output_stream():
        pass
    add("iccbased_no_n", _arr(_n("ICCBased"), icc_no_n))
    add(
        "iccbased_garbage_profile",
        _arr(_n("ICCBased"), _icc(3, b"this is not an icc profile")),
    )
    add("iccbased_one_element", _arr(_n("ICCBased")))
    add("iccbased_second_not_stream", _arr(_n("ICCBased"), _n("DeviceRGB")))
    add(
        "iccbased_n3_with_alternate",
        _arr(_n("ICCBased"), _icc_with_alternate(3, _n("DeviceRGB"))),
    )

    # ===== /CalGray /CalRGB /Lab corners =====
    add(
        "calgray_wellformed",
        _arr(_n("CalGray"), _cal_dict(_floats(0.95, 1, 1.09), None, 2.2)),
    )
    add("calgray_missing_whitepoint", _arr(_n("CalGray"), COSDictionary()))
    add(
        "calgray_whitepoint_wrong_len",
        _arr(_n("CalGray"), _cal_dict(_floats(1, 1), None, 1)),
    )
    add(
        "calgray_whitepoint_zeros",
        _arr(_n("CalGray"), _cal_dict(_floats(0, 0, 0), None, 1)),
    )
    add("calgray_no_dict", _arr(_n("CalGray")))

    add(
        "calrgb_wellformed",
        _arr(_n("CalRGB"), _cal_dict(_floats(1, 1, 1), _floats(1, 1, 1), 0)),
    )
    add("calrgb_missing_whitepoint", _arr(_n("CalRGB"), COSDictionary()))
    add(
        "calrgb_whitepoint_negative",
        _arr(_n("CalRGB"), _cal_dict(_floats(-1, -1, -1), None, 0)),
    )
    add("calrgb_no_dict", _arr(_n("CalRGB")))

    add(
        "lab_wellformed",
        _arr(
            _n("Lab"),
            _lab_dict(_floats(0.9642, 1, 0.8249), _floats(-128, 127, -128, 127)),
        ),
    )
    add(
        "lab_missing_whitepoint",
        _arr(_n("Lab"), _lab_dict(None, _floats(-128, 127, -128, 127))),
    )
    add(
        "lab_range_wrong_len",
        _arr(_n("Lab"), _lab_dict(_floats(0.9642, 1, 0.8249), _floats(-128, 127))),
    )
    add(
        "lab_no_range",
        _arr(_n("Lab"), _lab_dict(_floats(0.9642, 1, 0.8249), None)),
    )
    add("lab_no_dict", _arr(_n("Lab")))

    # ===== /Pattern corners =====
    add("pattern_name", _n("Pattern"))
    add("pattern_array_bare", _arr(_n("Pattern")))
    add("pattern_array_with_base", _arr(_n("Pattern"), _n("DeviceRGB")))
    add("pattern_array_base_unknown", _arr(_n("Pattern"), _n("FooBar")))
    add("pattern_array_base_cmyk", _arr(_n("Pattern"), _n("DeviceCMYK")))

    # ===== deeply nested / array-of-array =====
    add("deeply_nested_array", _arr(_arr(_n("DeviceRGB"))))
    add("array_device_named", _arr(_n("DeviceRGB")))

    return cases


# ---------- documented both-sides-pinned divergences ----------
#
# case name -> (pypdfbox CASE line, reason). Every entry is asserted to (a)
# match pypdfbox's emitted line exactly AND (b) differ from the Java oracle —
# so a future Java/pypdfbox convergence fails the test and forces the pin to be
# removed. Reason codes:
#   create   -> permissive create contract (Java throws; pypdfbox NULL/lenient)
#   cmm      -> JVM colour-management vs explicit deterministic colour math
#   pattern  -> PDPattern returns 0 components instead of throwing
_CREATE = (
    "Java create() throws on malformed input; pypdfbox factory is permissive "
    "(returns None / lenient construct) — see upstream test port + "
    "pd_resources design comment"
)
_CMM = (
    "JVM colour-management module vs pypdfbox explicit deterministic colour "
    "math (waves 1330C/1386); same divergence as test_color_space_to_rgb_oracle.py"
)
_PATTERN = (
    "PDPattern.get_number_of_components returns 0 (sane size) where upstream "
    "throws UnsupportedOperationException"
)

_EXPECTED_DIVERGENCES: dict[str, tuple[str, str]] = {
    # --- CMM colour-math divergences (create succeeds both sides) ---
    "name_devicecmyk": (
        "CASE name_devicecmyk create=ok class=PDDeviceCMYK nc=4 "
        "init=0.000,0.000,0.000,1.000 rgb=64;64;64",
        _CMM,
    ),
    "separation_wellformed": (
        "CASE separation_wellformed create=ok class=PDSeparation nc=1 "
        "init=1.000 rgb=255;128;128",
        _CMM,
    ),
    "separation_name_all": (
        "CASE separation_name_all create=ok class=PDSeparation nc=1 "
        "init=1.000 rgb=64;64;64",
        _CMM,
    ),
    "devicen_wellformed": (
        "CASE devicen_wellformed create=ok class=PDDeviceN nc=2 "
        "init=1.000,1.000 rgb=128;128;255",
        _CMM,
    ),
    "iccbased_n4": (
        "CASE iccbased_n4 create=ok class=PDICCBased nc=4 "
        "init=0.000,0.000,0.000,0.000 rgb=64;64;64",
        _CMM,
    ),
    "calgray_missing_whitepoint": (
        "CASE calgray_missing_whitepoint create=ok class=PDCalGray nc=1 "
        "init=0.000 rgb=204;183;180",
        _CMM,
    ),
    "calrgb_wellformed": (
        "CASE calrgb_wellformed create=ok class=PDCalRGB nc=3 "
        "init=0.000,0.000,0.000 rgb=204;183;180",
        _CMM,
    ),
    "calrgb_missing_whitepoint": (
        "CASE calrgb_missing_whitepoint create=ok class=PDCalRGB nc=3 "
        "init=0.000,0.000,0.000 rgb=204;183;180",
        _CMM,
    ),
    "lab_wellformed": (
        "CASE lab_wellformed create=ok class=PDLab nc=3 "
        "init=0.000,0.000,0.000 rgb=4;1;0",
        _CMM,
    ),
    # --- permissive create() contract (Java ERR; pypdfbox NULL/lenient) ---
    "name_short_g": (
        "CASE name_short_g create=ok class=PDDeviceGray nc=1 init=0.000 "
        "rgb=128;128;128",
        _CREATE,
    ),
    "name_short_rgb": (
        "CASE name_short_rgb create=ok class=PDDeviceRGB nc=3 "
        "init=0.000,0.000,0.000 rgb=128;128;128",
        _CREATE,
    ),
    "name_short_cmyk": (
        "CASE name_short_cmyk create=ok class=PDDeviceCMYK nc=4 "
        "init=0.000,0.000,0.000,1.000 rgb=64;64;64",
        _CREATE,
    ),
    "name_unknown": ("CASE name_unknown create=NULL", _CREATE),
    "name_indexed_bare": ("CASE name_indexed_bare create=NULL", _CREATE),
    "name_iccbased_bare": ("CASE name_iccbased_bare create=NULL", _CREATE),
    "name_separation_bare": ("CASE name_separation_bare create=NULL", _CREATE),
    "null_input": ("CASE null_input create=NULL", _CREATE),
    "integer_input": ("CASE integer_input create=NULL", _CREATE),
    "string_input": ("CASE string_input create=NULL", _CREATE),
    "float_input": ("CASE float_input create=NULL", _CREATE),
    "cosnull_input": ("CASE cosnull_input create=NULL", _CREATE),
    "empty_array": ("CASE empty_array create=NULL", _CREATE),
    "array_head_not_name": ("CASE array_head_not_name create=NULL", _CREATE),
    "array_head_null": ("CASE array_head_null create=NULL", _CREATE),
    "array_one_name_unknown": ("CASE array_one_name_unknown create=NULL", _CREATE),
    "array_unknown_head": ("CASE array_unknown_head create=NULL", _CREATE),
    "deeply_nested_array": ("CASE deeply_nested_array create=NULL", _CREATE),
    "indexed_two_elements": (
        "CASE indexed_two_elements create=ok class=PDIndexed nc=1 init=0.000 "
        "rgb=0;0;0",
        _CREATE,
    ),
    "indexed_three_elements": (
        "CASE indexed_three_elements create=ok class=PDIndexed nc=1 init=0.000 "
        "rgb=0;0;0",
        _CREATE,
    ),
    "indexed_hival_negative": (
        "CASE indexed_hival_negative create=ok class=PDIndexed nc=1 init=0.000 "
        "rgb=0;0;0",
        _CREATE,
    ),
    "indexed_hival_string": (
        "CASE indexed_hival_string create=ok class=PDIndexed nc=1 init=0.000 "
        "rgb=0;0;0",
        _CREATE,
    ),
    "indexed_lookup_missing": (
        "CASE indexed_lookup_missing create=ok class=PDIndexed nc=1 init=0.000 "
        "rgb=0;0;0",
        _CREATE,
    ),
    "indexed_lookup_as_name": (
        "CASE indexed_lookup_as_name create=ok class=PDIndexed nc=1 init=0.000 "
        "rgb=0;0;0",
        _CREATE,
    ),
    "indexed_base_unknown": (
        "CASE indexed_base_unknown create=ok class=PDIndexed nc=1 init=0.000 "
        "rgb=0;0;0",
        _CREATE,
    ),
    "separation_three_elements": (
        "CASE separation_three_elements create=ok class=PDSeparation nc=1 "
        "init=1.000 rgb=ERR",
        _CREATE,
    ),
    "separation_two_elements": (
        "CASE separation_two_elements create=ok class=PDSeparation nc=1 "
        "init=1.000 rgb=ERR",
        _CREATE,
    ),
    "separation_alt_unknown": (
        "CASE separation_alt_unknown create=ok class=PDSeparation nc=1 "
        "init=1.000 rgb=ERR",
        _CREATE,
    ),
    "separation_tint_missing": (
        "CASE separation_tint_missing create=ok class=PDSeparation nc=1 "
        "init=1.000 rgb=ERR",
        _CREATE,
    ),
    "separation_tint_not_function": (
        "CASE separation_tint_not_function create=ok class=PDSeparation nc=1 "
        "init=1.000 rgb=ERR",
        _CREATE,
    ),
    "devicen_names_nonnames": (
        "CASE devicen_names_nonnames create=ok class=PDDeviceN nc=0 init= rgb=NA",
        _CREATE,
    ),
    "devicen_names_not_array": (
        "CASE devicen_names_not_array create=ok class=PDDeviceN nc=0 init= rgb=NA",
        _CREATE,
    ),
    "devicen_three_elements": (
        "CASE devicen_three_elements create=ok class=PDDeviceN nc=2 "
        "init=1.000,1.000 rgb=ERR",
        _CREATE,
    ),
    "devicen_alt_unknown": (
        "CASE devicen_alt_unknown create=ok class=PDDeviceN nc=1 init=1.000 "
        "rgb=ERR",
        _CREATE,
    ),
    "devicen_tint_missing": (
        "CASE devicen_tint_missing create=ok class=PDDeviceN nc=2 "
        "init=1.000,1.000 rgb=ERR",
        _CREATE,
    ),
    "iccbased_n0": (
        "CASE iccbased_n0 create=ok class=PDICCBased nc=0 init= rgb=NA",
        _CREATE,
    ),
    "iccbased_n2": (
        "CASE iccbased_n2 create=ok class=PDICCBased nc=2 init=0.000,0.000 rgb=ERR",
        _CREATE,
    ),
    "iccbased_n5": (
        "CASE iccbased_n5 create=ok class=PDICCBased nc=5 "
        "init=0.000,0.000,0.000,0.000,0.000 rgb=ERR",
        _CREATE,
    ),
    "iccbased_no_n": (
        "CASE iccbased_no_n create=ok class=PDICCBased nc=0 init= rgb=NA",
        _CREATE,
    ),
    "iccbased_second_not_stream": (
        "CASE iccbased_second_not_stream create=ok class=PDICCBased nc=0 init= "
        "rgb=NA",
        _CREATE,
    ),
    "calgray_whitepoint_wrong_len": (
        "CASE calgray_whitepoint_wrong_len create=ok class=PDCalGray nc=1 "
        "init=0.000 rgb=204;183;180",
        _CREATE,
    ),
    "calgray_no_dict": (
        "CASE calgray_no_dict create=ok class=PDCalGray nc=1 init=0.000 rgb=ERR",
        _CREATE,
    ),
    "calrgb_no_dict": (
        "CASE calrgb_no_dict create=ok class=PDCalRGB nc=3 init=0.000,0.000,0.000 "
        "rgb=ERR",
        _CREATE,
    ),
    "lab_range_wrong_len": (
        "CASE lab_range_wrong_len create=ok class=PDLab nc=3 "
        "init=0.000,0.000,0.000 rgb=4;1;0",
        _CREATE,
    ),
    "lab_no_range": (
        "CASE lab_no_range create=ok class=PDLab nc=3 init=0.000,0.000,0.000 "
        "rgb=4;1;0",
        _CREATE,
    ),
    "pattern_array_base_unknown": (
        "CASE pattern_array_base_unknown create=ok class=PDPattern nc=0 init= "
        "rgb=NA",
        _CREATE,
    ),
    # --- PDPattern component surface (Java throws nc=ERR; pypdfbox nc=0) ---
    "pattern_name": (
        "CASE pattern_name create=ok class=PDPattern nc=0 init= rgb=NA",
        _PATTERN,
    ),
    "name_pattern": (
        "CASE name_pattern create=ok class=PDPattern nc=0 init= rgb=NA",
        _PATTERN,
    ),
    "pattern_array_bare": (
        "CASE pattern_array_bare create=ok class=PDPattern nc=0 init= rgb=NA",
        _PATTERN,
    ),
    "pattern_array_with_base": (
        "CASE pattern_array_with_base create=ok class=PDPattern nc=0 init= rgb=NA",
        _PATTERN,
    ),
    "pattern_array_base_cmyk": (
        "CASE pattern_array_base_cmyk create=ok class=PDPattern nc=0 init= rgb=NA",
        _PATTERN,
    ),
}


def _parse_probe(text: str) -> dict[str, str]:
    """Map case name -> full CASE line from the probe's stdout."""
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line.startswith("CASE "):
            continue
        name = line.split(" ", 2)[1]
        out[name] = line
    return out


@pytest.fixture(scope="module")
def _java_lines() -> dict[str, str]:
    return _parse_probe(run_probe_text("ColorSpaceFuzzProbe"))


@requires_oracle
def test_corpus_count_matches(_java_lines: dict[str, str]) -> None:
    """The Java probe and the Python sibling drive the identical case set."""
    py_names = [name for name, _ in _build_cases()]
    assert len(py_names) == len(set(py_names)), "duplicate case name in corpus"
    assert set(py_names) == set(_java_lines), (
        "corpus drift: python-only="
        f"{sorted(set(py_names) - set(_java_lines))} "
        f"java-only={sorted(set(_java_lines) - set(py_names))}"
    )


@requires_oracle
@pytest.mark.parametrize("name,base", _build_cases(), ids=[c[0] for c in _build_cases()])
def test_colorspace_fuzz_case(
    name: str, base: COSBase | None, _java_lines: dict[str, str]
) -> None:
    """Each case's pypdfbox CASE line matches Java byte-for-byte, except the
    documented both-sides-pinned divergences."""
    py_line = _emit(name, base)
    java_line = _java_lines[name]

    if name in _EXPECTED_DIVERGENCES:
        pinned, reason = _EXPECTED_DIVERGENCES[name]
        assert py_line == pinned, (
            f"{name}: pypdfbox CASE line drifted from its pin.\n"
            f"  emitted: {py_line!r}\n  pinned : {pinned!r}\n  reason : {reason}"
        )
        assert py_line != java_line, (
            f"{name}: pypdfbox now matches the Java oracle — the documented "
            f"divergence ({reason}) no longer holds. Remove this pin and let "
            f"the case fall through to the exact-match assertion.\n"
            f"  java/py: {java_line!r}"
        )
        return

    assert py_line == java_line, (
        f"{name}: pypdfbox diverged from the Java oracle but is not in the "
        f"documented divergence map — this is a real parity regression.\n"
        f"  pypdfbox: {py_line!r}\n  PDFBox  : {java_line!r}"
    )
