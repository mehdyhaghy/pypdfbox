"""Live PDFBox DIFFERENTIAL-FUZZ parity for the ``PDSeparation`` /
``PDDeviceN`` (and ``PDDeviceNAttributes`` / ``PDDeviceNProcess``) colour-space
surfaces (PDF 32000-1 §8.6.6.4 Separation, §8.6.6.5 DeviceN / NChannel).

The Java side is ``oracle/probes/SeparationDeviceNFuzzProbe.java``: it builds
~20 malformed / edge-case colour-space arrays from in-memory COS objects and
projects every accessor the Python port mirrors. THIS test reproduces each
case on the pypdfbox side and pins BOTH sides, with honest divergence comments
where the two libraries deliberately differ.

The headline divergence this fuzz wave documents is **eager vs lazy
resolution**:

* PDFBox's ``PDSeparation(COSArray)`` / ``PDDeviceN(COSArray)`` constructors
  resolve the alternate colour space AND the tint transform *eagerly* and
  validate the tint transform's output-parameter count against the alternate's
  component count — so a missing colorant / missing or wrong-type alternate /
  missing tint / wrong-arity tint / non-name colorant entry all raise at
  CONSTRUCTION time (the probe emits ``CTOR_ERR`` / ``ERR``).
* pypdfbox resolves both *lazily* (documented in the
  ``PDSeparation`` / ``PDDeviceN`` docstrings): the constructor always
  succeeds, accessors return ``None`` / skip bad entries, and ``to_rgb``
  returns ``None`` instead of raising. This was a deliberate lite-path choice
  (see ``test_separation_all_none_oracle.py``) and is pinned as documented
  divergence here, not "fixed".

Tiers:

* **Exact-match tier** — well-formed spaces over a pure-grey alternate (no
  CMM): colorant names, component counts, initial colour, and ``to_rgb`` bytes
  match PDFBox exactly.
* **Documented-divergence tier (eager/lazy)** — the malformed cases above:
  PDFBox raises, pypdfbox is lenient. We pin BOTH the probe's ``CTOR_ERR`` /
  ``ERR`` token AND pypdfbox's lenient result.
* **Attribute surface** — ``/Process``, ``/Colorants`` projections match
  PDFBox exactly for the well-formed NChannel case (the CMM-routed ``to_rgb``
  of an attribute space is covered by the sibling DeviceNAttrProbe and not
  re-pinned here).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match the probe's clamp255) ----------


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _sep_rgb_int(cs: PDSeparation, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)
    assert rgb is not None
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


def _dn_rgb_int(cs: PDDeviceN, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)
    assert rgb is not None
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe ----------


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _type4(domain: list[float], rng: list[float], ps: str) -> COSStream:
    s = COSStream()
    s.set_int("FunctionType", 4)
    s.set_item("Domain", COSArray.of_cos_floats(domain))
    s.set_item("Range", COSArray.of_cos_floats(rng))
    with s.create_output_stream() as os_:
        os_.write(ps.encode("ascii"))
    return s


def _names(*n: str) -> COSArray:
    a = COSArray()
    for x in n:
        a.add(COSName.get_pdf_name(x))
    return a


def _sep_cmyk(colorant: str, c1: list[float]) -> COSArray:
    a = COSArray()
    a.add(COSName.get_pdf_name("Separation"))
    a.add(COSName.get_pdf_name(colorant))
    a.add(COSName.get_pdf_name("DeviceCMYK"))
    a.add(_type2([0, 0, 0, 0], c1).get_cos_object())
    return a


def _gray_tint() -> COSStream:
    return _type4([0, 1], [0, 1], "{ 1 exch sub }")


def _sep_array(
    colorant: object | None,
    with_colorant: bool,
    alternate: object | None,
    tint: object | None,
) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    if with_colorant:
        assert colorant is not None
        arr.add(colorant.get_cos_object())  # type: ignore[attr-defined]
    if alternate is not None:
        arr.add(alternate.get_cos_object())  # type: ignore[attr-defined]
        if tint is not None:
            arr.add(tint.get_cos_object())  # type: ignore[attr-defined]
    return arr


def _dn_array(
    names: COSArray,
    alternate: object | None,
    tint: object | None,
    attrs: COSDictionary | None = None,
) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(names)
    if alternate is not None:
        arr.add(alternate.get_cos_object())  # type: ignore[attr-defined]
    if tint is not None:
        arr.add(tint.get_cos_object())  # type: ignore[attr-defined]
    if attrs is not None:
        arr.add(attrs)
    return arr


# ---------- probe output parsing ----------


def _parse(text: str) -> dict[str, list[str]]:
    """Group probe lines by their KIND+tag key.

    SEP/DN describe lines key on ``"<kind> <tag>"``; the *_TORGB and
    DN_PROCESS / DN_COLORANTS lines accumulate under the same key so a test
    can fetch every line for a case at once.
    """
    out: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(maxsplit=2)
        kind = parts[0]
        tag = parts[1] if len(parts) > 1 else ""
        key = f"{kind} {tag}"
        out.setdefault(key, []).append(line)
    return out


@pytest.fixture(scope="module")
def _java() -> dict[str, list[str]]:
    return _parse(run_probe_text("SeparationDeviceNFuzzProbe"))


# ====================================================================
# Separation — exact-match tier (well-formed, grey alternate)
# ====================================================================


@requires_oracle
@pytest.mark.parametrize(
    "tag,tint_builder",
    [
        ("name_gray", _gray_tint),
        ("name_gray_t2", lambda: _type2([1], [0], 1.0)),
    ],
)
def test_separation_wellformed_gray(
    tag: str, tint_builder: object, _java: dict[str, list[str]]
) -> None:
    """A well-formed Separation over DeviceGray: colorant name, component
    count, initial colour, and every ``to_rgb`` byte match PDFBox exactly
    (no CMM in the path)."""
    arr = _sep_array(
        COSName.get_pdf_name("Spot"),
        True,
        COSName.get_pdf_name("DeviceGray"),
        tint_builder(),  # type: ignore[operator]
    )
    sep = PDSeparation(arr)
    describe = _java[f"SEP {tag}"][0]
    assert "colorant=Spot" in describe
    assert "ncomp=1" in describe
    assert "initial=1" in describe
    assert "hasalt=true" in describe

    assert sep.get_colorant_name() == "Spot"
    assert sep.get_number_of_components() == 1
    assert sep.get_initial_color().get_components() == [1.0]
    assert sep.has_alternate_color_space() is True

    # to_rgb at 0.0 / 0.5 / 1.0 -> grey 1-t.
    expected_lines = _java[f"SEP_TORGB {tag}"]
    by_t = {ln.split()[2]: ln for ln in expected_lines}
    for t, want in [(0.0, "0"), (0.5, "0.5"), (1.0, "1")]:
        line = by_t[want]
        _, right = line.split("->")
        j_rgb = tuple(int(x) for x in right.split())
        assert _sep_rgb_int(sep, [t]) == j_rgb, (
            f"{tag} t={t}: pypdfbox != PDFBox {j_rgb}"
        )


@requires_oracle
@pytest.mark.parametrize(
    "name,tag",
    [("All", "all_gray"), ("None", "none_gray")],
)
def test_separation_all_none_names(
    name: str, tag: str, _java: dict[str, list[str]]
) -> None:
    """``/All`` and ``/None`` colorant names round-trip through
    ``get_colorant_name`` exactly — the special names don't change the
    component/initial-colour surface."""
    arr = _sep_array(
        COSName.get_pdf_name(name),
        True,
        COSName.get_pdf_name("DeviceGray"),
        _gray_tint(),
    )
    sep = PDSeparation(arr)
    describe = _java[f"SEP {tag}"][0]
    assert f"colorant={name}" in describe
    assert sep.get_colorant_name() == name
    assert sep.get_number_of_components() == 1
    assert sep.get_initial_color().get_components() == [1.0]


# ====================================================================
# Separation — documented-divergence tier (eager PDFBox vs lazy pypdfbox)
# ====================================================================


@requires_oracle
def test_separation_string_colorant_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Colorant slot is a COSString, not a COSName.

    DIVERGENCE: PDFBox's ``getColorantName()`` casts the slot to ``COSName``
    and throws a ``ClassCastException`` (probe emits ``colorant=ERR``).
    pypdfbox's ``get_colorant_name()`` is type-checked and returns ``None``
    for a non-name slot — the lenient lite path. The construction itself
    succeeds on both sides because the alternate + tint are well-formed."""
    describe = _java["SEP str_colorant"][0]
    assert "colorant=ERR" in describe  # PDFBox raises in getColorantName

    arr = _sep_array(
        COSString("SpotStr"),
        True,
        COSName.get_pdf_name("DeviceGray"),
        _gray_tint(),
    )
    sep = PDSeparation(arr)
    assert sep.get_colorant_name() is None  # pypdfbox: lenient
    assert sep.has_alternate_color_space() is True


@requires_oracle
def test_separation_missing_colorant_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Array is just ``[/Separation]`` — no colorant / alternate / tint.

    DIVERGENCE: PDFBox's constructor eagerly resolves alternate+tint from
    null slots and throws (probe emits ``CTOR_ERR``). pypdfbox constructs
    fine and returns ``None`` for every slot."""
    assert "CTOR_ERR" in _java["SEP missing_colorant"][0]

    arr = _sep_array(None, False, None, None)
    sep = PDSeparation(arr)
    assert sep.get_colorant_name() is None
    assert sep.has_alternate_color_space() is False
    assert sep.has_tint_transform() is False
    assert sep.get_number_of_components() == 1
    assert sep.get_initial_color().get_components() == [1.0]


@requires_oracle
def test_separation_missing_alternate_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Array ``[/Separation /Spot]`` — alternate + tint absent.

    DIVERGENCE: PDFBox raises at construction (``CTOR_ERR``) and ``toRGB``
    is unreachable (``ERR``). pypdfbox constructs, reports no alternate, and
    ``to_rgb`` returns ``None`` rather than raising."""
    assert "CTOR_ERR" in _java["SEP missing_alt"][0]
    assert "-> ERR" in _java["SEP_TORGB missing_alt"][0]

    arr = _sep_array(COSName.get_pdf_name("Spot"), True, None, None)
    sep = PDSeparation(arr)
    assert sep.get_colorant_name() == "Spot"
    assert sep.has_alternate_color_space() is False
    assert sep.to_rgb([0.5]) is None


@requires_oracle
def test_separation_wrong_alternate_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Alternate slot is a bare name that is not a colour space.

    DIVERGENCE: PDFBox raises at construction (``CTOR_ERR``). pypdfbox's
    lazy ``get_alternate_color_space`` cannot resolve it, so
    ``has_alternate_color_space`` is False and ``to_rgb`` returns ``None``."""
    assert "CTOR_ERR" in _java["SEP wrong_alt"][0]
    assert "-> ERR" in _java["SEP_TORGB wrong_alt"][0]

    arr = _sep_array(
        COSName.get_pdf_name("Spot"),
        True,
        COSName.get_pdf_name("Bogus"),
        _gray_tint(),
    )
    sep = PDSeparation(arr)
    assert sep.has_alternate_color_space() is False
    assert sep.to_rgb([0.5]) is None


@requires_oracle
def test_separation_missing_tint_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Array ``[/Separation /Spot /DeviceGray]`` — tint transform absent.

    DIVERGENCE: PDFBox raises at construction (``CTOR_ERR``). pypdfbox
    constructs, reports no tint transform, and ``to_rgb`` returns ``None``."""
    assert "CTOR_ERR" in _java["SEP missing_tint"][0]
    assert "-> ERR" in _java["SEP_TORGB missing_tint"][0]

    arr = _sep_array(
        COSName.get_pdf_name("Spot"), True, COSName.get_pdf_name("DeviceGray"),
        None,
    )
    sep = PDSeparation(arr)
    assert sep.has_tint_transform() is False
    assert sep.to_rgb([0.5]) is None


@requires_oracle
def test_separation_bad_arity_divergence(_java: dict[str, list[str]]) -> None:
    """Tint transform declares 1 output but the DeviceCMYK alternate needs 4.

    DIVERGENCE: PDFBox's constructor validates
    ``tintTransform.getNumberOfOutputParameters() >= alternate components``
    and raises (``CTOR_ERR``). pypdfbox does no such check at construction;
    the well-formed accessors all succeed. pypdfbox degrades gracefully —
    ``to_rgb`` returns ``None`` thanks to the defensive arity guard added in
    this wave (BUG FIX: without it the short 1-element tint-transform output
    crashed the DeviceCMYK alternate with an IndexError)."""
    assert "CTOR_ERR" in _java["SEP bad_arity"][0]

    arr = _sep_array(
        COSName.get_pdf_name("Spot"),
        True,
        COSName.get_pdf_name("DeviceCMYK"),
        _type4([0, 1], [0, 1], "{ }"),
    )
    sep = PDSeparation(arr)
    assert sep.has_alternate_color_space() is True
    # pypdfbox does not raise: the arity guard returns None when the tint
    # transform yields fewer components than the alternate needs.
    assert sep.to_rgb([0.5]) is None


# ====================================================================
# DeviceN — exact-match tier (well-formed, grey alternate)
# ====================================================================


@requires_oracle
def test_devicen_empty_colorants(_java: dict[str, list[str]]) -> None:
    """Empty colorant-names array: zero components, empty initial colour."""
    describe = _java["DN empty"][0]
    assert "colorants= " in describe
    assert "ncomp=0" in describe
    assert "initial= " in describe
    assert "hasattr=false" in describe
    assert "nchannel=false" in describe

    arr = _dn_array(
        _names(), COSName.get_pdf_name("DeviceGray"), _gray_tint()
    )
    dn = PDDeviceN(arr)
    assert dn.get_colorant_names() == []
    assert dn.get_number_of_components() == 0
    assert dn.get_initial_color().get_components() == []
    assert dn.has_attributes() is False
    assert dn.is_n_channel() is False
    assert dn.get_subtype() == "DeviceN"


@requires_oracle
def test_devicen_single_gray(_java: dict[str, list[str]]) -> None:
    """Single-colorant DeviceN over DeviceGray: names, count, initial colour
    and every ``to_rgb`` byte match PDFBox exactly."""
    describe = _java["DN single"][0]
    assert "colorants=S1 " in describe
    assert "ncomp=1" in describe
    assert "hasattr=false" in describe

    arr = _dn_array(
        _names("S1"), COSName.get_pdf_name("DeviceGray"), _gray_tint()
    )
    dn = PDDeviceN(arr)
    assert dn.get_colorant_names() == ["S1"]
    assert dn.get_number_of_components() == 1
    assert dn.get_initial_color().get_components() == [1.0]

    by_t = {ln.split()[2]: ln for ln in _java["DN_TORGB single"]}
    for t, want in [(0.0, "0"), (0.5, "0.5"), (1.0, "1")]:
        _, right = by_t[want].split("->")
        j_rgb = tuple(int(x) for x in right.split())
        assert _dn_rgb_int(dn, [t]) == j_rgb


@requires_oracle
def test_devicen_two_colorants_gray(_java: dict[str, list[str]]) -> None:
    """Two-colorant DeviceN with a ``(a,b)->a`` tint over DeviceGray; the
    single ``to_rgb`` tuple matches PDFBox exactly."""
    describe = _java["DN two"][0]
    assert "colorants=S1,S2 " in describe
    assert "ncomp=2" in describe

    tint = _type4([0, 1, 0, 1], [0, 1], "{ pop }")
    arr = _dn_array(_names("S1", "S2"), COSName.get_pdf_name("DeviceGray"), tint)
    dn = PDDeviceN(arr)
    assert dn.get_colorant_names() == ["S1", "S2"]
    assert dn.get_number_of_components() == 2

    line = _java["DN_TORGB two"][0]
    _, right = line.split("->")
    j_rgb = tuple(int(x) for x in right.split())
    assert _dn_rgb_int(dn, [0.5, 0.25]) == j_rgb


# ====================================================================
# DeviceN — documented-divergence tier (eager PDFBox vs lazy pypdfbox)
# ====================================================================


@requires_oracle
def test_devicen_mixed_names_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Colorant-names array contains a COSString amid the COSNames.

    DIVERGENCE: PDFBox's ``getColorantNames()`` (called inside the eager
    constructor for the initial-colour count) casts every entry to
    ``COSName`` and throws (``CTOR_ERR``). pypdfbox type-checks each entry
    and silently skips the non-name, yielding ``["A", "C"]``."""
    assert "CTOR_ERR" in _java["DN mixed_names"][0]

    mixed = COSArray()
    mixed.add(COSName.get_pdf_name("A"))
    mixed.add(COSString("B"))
    mixed.add(COSName.get_pdf_name("C"))
    arr = _dn_array(mixed, COSName.get_pdf_name("DeviceGray"), _gray_tint())
    dn = PDDeviceN(arr)
    assert dn.get_colorant_names() == ["A", "C"]
    assert dn.get_number_of_components() == 2


@requires_oracle
def test_devicen_missing_alternate_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Array ``[/DeviceN [S1]]`` — alternate + tint absent.

    DIVERGENCE: PDFBox eagerly resolves the alternate and raises
    (``CTOR_ERR``), so ``toRGB`` is unreachable (``ERR``). pypdfbox
    constructs, reports no alternate, and ``to_rgb`` returns ``None``."""
    assert "CTOR_ERR" in _java["DN no_alt"][0]
    assert "-> ERR" in _java["DN_TORGB no_alt"][0]

    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(_names("S1"))
    dn = PDDeviceN(arr)
    assert dn.get_colorant_names() == ["S1"]
    assert dn.has_alternate_color_space() is False
    assert dn.to_rgb([0.5]) is None


@requires_oracle
def test_devicen_missing_tint_divergence(
    _java: dict[str, list[str]]
) -> None:
    """Array ``[/DeviceN [S1] /DeviceGray]`` — tint transform absent.

    DIVERGENCE: PDFBox eagerly resolves the tint transform and raises
    (``CTOR_ERR``). pypdfbox constructs, reports no tint, and ``to_rgb``
    returns ``None``."""
    assert "CTOR_ERR" in _java["DN no_tint"][0]
    assert "-> ERR" in _java["DN_TORGB no_tint"][0]

    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(_names("S1"))
    arr.add(COSName.get_pdf_name("DeviceGray"))
    dn = PDDeviceN(arr)
    assert dn.has_tint_transform() is False
    assert dn.to_rgb([0.5]) is None


@requires_oracle
def test_devicen_nondict_attributes_divergence(
    _java: dict[str, list[str]]
) -> None:
    """``/Attributes`` slot holds a name, not a dictionary.

    DIVERGENCE: PDFBox eagerly reads ``getAttributes()`` and throws on the
    bad cast during construction (``CTOR_ERR``); the process projection is
    unreachable (``ERR``). pypdfbox type-checks the slot, returns ``None``
    from ``get_attributes`` and reports no process."""
    assert "CTOR_ERR" in _java["DN nondict_attr"][0]
    assert "DN_PROCESS nondict_attr ERR" in _java["DN_PROCESS nondict_attr"][0]

    arr = _dn_array(
        _names("S1"), COSName.get_pdf_name("DeviceGray"), _gray_tint()
    )
    arr.add(COSName.get_pdf_name("NotADict"))
    dn = PDDeviceN(arr)
    assert dn.get_attributes() is None
    assert dn.has_attributes() is False
    assert dn.get_process_color_space() is None


# ====================================================================
# DeviceN — attribute surface (exact match for well-formed NChannel)
# ====================================================================


@requires_oracle
def test_devicen_attribute_surface(_java: dict[str, list[str]]) -> None:
    """Well-formed NChannel DeviceN with ``/Process`` + ``/Colorants``:
    colorant names, NChannel flag, process colour-space name + component
    names, and the sorted ``/Colorants`` key set all match PDFBox exactly.

    (The attribute-driven ``to_rgb`` routes the final step through the JVM
    CMM and is pinned by the sibling DeviceNAttrProbe; not re-pinned here.)"""
    describe = _java["DN attr_full"][0]
    assert "colorants=Spot1,Spot2,Spot3 " in describe
    assert "ncomp=3" in describe
    assert "hasattr=true" in describe
    assert "nchannel=true" in describe
    proc_line = _java["DN_PROCESS attr_full"][0]
    assert "cs=DeviceCMYK comps=Cyan,Magenta,Yellow,Black" in proc_line
    col_line = _java["DN_COLORANTS attr_full"][0]
    assert "keys=Spot1,Spot2,Spot3" in col_line

    proc = COSDictionary()
    proc.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    proc.set_item("Components", _names("Cyan", "Magenta", "Yellow", "Black"))
    colorants = COSDictionary()
    colorants.set_item("Spot1", _sep_cmyk("Spot1", [1, 0, 0, 0]))
    colorants.set_item("Spot2", _sep_cmyk("Spot2", [0, 1, 0, 0]))
    colorants.set_item("Spot3", _sep_cmyk("Spot3", [0, 0, 1, 0]))
    attrs = COSDictionary()
    attrs.set_name("Subtype", "NChannel")
    attrs.set_item("Process", proc)
    attrs.set_item("Colorants", colorants)
    tint = _type4(
        [0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 0, 1, 0, 1], "{ 0 }"
    )
    arr = _dn_array(
        _names("Spot1", "Spot2", "Spot3"),
        COSName.get_pdf_name("DeviceCMYK"),
        tint,
        attrs,
    )
    dn = PDDeviceN(arr)
    assert dn.get_colorant_names() == ["Spot1", "Spot2", "Spot3"]
    assert dn.get_number_of_components() == 3
    assert dn.is_n_channel() is True
    assert dn.get_subtype() == "NChannel"

    pd_attrs = dn.get_attributes()
    assert pd_attrs is not None
    process = pd_attrs.get_process()
    assert process is not None
    cs = process.get_color_space()
    assert cs is not None and cs.get_name() == "DeviceCMYK"
    assert process.get_components() == ["Cyan", "Magenta", "Yellow", "Black"]
    assert sorted(pd_attrs.get_colorants()) == ["Spot1", "Spot2", "Spot3"]


@requires_oracle
def test_devicen_empty_attributes_colorants_side_effect(
    _java: dict[str, list[str]]
) -> None:
    """``/Attributes`` is an empty dict (no /Subtype, /Process, /Colorants).

    Matches PDFBox: ``getColorants()`` returns an empty map AND inserts a
    fresh empty ``/Colorants`` COSDictionary as a side effect, so an empty
    keys set is reported on both sides; ``get_process`` is ``None``."""
    proc_line = _java["DN_PROCESS attr_empty"][0]
    assert "cs=NONE comps=" in proc_line
    col_line = _java["DN_COLORANTS attr_empty"][0]
    assert col_line.endswith("keys=")

    arr = _dn_array(
        _names("S1"),
        COSName.get_pdf_name("DeviceGray"),
        _gray_tint(),
        COSDictionary(),
    )
    dn = PDDeviceN(arr)
    pd_attrs = dn.get_attributes()
    assert pd_attrs is not None
    assert pd_attrs.get_process() is None
    assert pd_attrs.get_colorants() == {}
    # side effect: empty /Colorants now present.
    assert pd_attrs.has_colorants() is True


@requires_oracle
def test_devicen_mismatched_process_components(
    _java: dict[str, list[str]]
) -> None:
    """``/Process`` declares DeviceCMYK (4 comp) but only 2 named
    ``/Components`` — pypdfbox returns the declared color space and the two
    names verbatim, matching PDFBox (neither side validates the count at the
    attributes layer)."""
    proc_line = _java["DN_PROCESS attr_badproc"][0]
    assert "cs=DeviceCMYK comps=Cyan,Magenta" in proc_line

    proc = COSDictionary()
    proc.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    proc.set_item("Components", _names("Cyan", "Magenta"))
    attrs = COSDictionary()
    attrs.set_item("Process", proc)
    arr = _dn_array(
        _names("S1"),
        COSName.get_pdf_name("DeviceCMYK"),
        _type4([0, 1], [0, 1, 0, 1, 0, 1, 0, 1], "{ 0 0 0 }"),
        attrs,
    )
    dn = PDDeviceN(arr)
    process = dn.get_attributes().get_process()  # type: ignore[union-attr]
    assert process is not None
    cs = process.get_color_space()
    assert cs is not None and cs.get_name() == "DeviceCMYK"
    assert process.get_components() == ["Cyan", "Magenta"]
