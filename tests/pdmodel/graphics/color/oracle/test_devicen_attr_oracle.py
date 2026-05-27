"""Live PDFBox differential parity for the DEEP DeviceN attribute surface
(PDF 32000-1 §8.6.6.5, NChannel) and a Separation ``/All`` edge case.

The sibling ``test_color_to_rgb_oracle.py`` covers a plain 3-colorant DeviceN
with only a tint transform; this file exercises the *attribute-driven* DeviceN
that ``ColorToRgbSpecialProbe`` never builds:

* a 3-colorant DeviceN whose ``/Attributes`` dict carries
    - ``/Subtype /NChannel``,
    - a ``/Process`` sub-dict (process colour space + named components), and
    - a ``/Colorants`` attribute dict mapping each spot colorant name to its
      OWN Separation colour space,
  plus a Type-4 tint transform (the ``toRGB`` fallback);
* a Separation with the ``/All`` colorant.

The Java side is ``oracle/probes/DeviceNAttrProbe.java``. It builds both colour
spaces from in-memory COS objects and emits canonical lines:

  ``COLORANTS <name>...``            getColorantNames
  ``NUMCOMPONENTS <n>``             getNumberOfComponents
  ``NCHANNEL <true|false>``         isNChannel
  ``PROCESS_CS <name>``            attributes.getProcess.getColorSpace.getName
  ``PROCESS_COMPONENTS <c>...``    process.getComponents
  ``COLORANTS_KEYS <k>...``        sorted attributes.getColorants key set
  ``COLORANT_CS <key> <name>``     per /Colorants entry colour-space name
  ``TORGB <name> <c>... -> r g b`` toRGB (0-255 ints, round(c*255) clamped)
  ``SEP_COLORANT <name>``          separation.getColorantName
  ``SEP_NUMCOMPONENTS <n>``

Two parity tiers, by colour-management model:

**Exact-match tier** — pure structure / arithmetic, no CMM:
  * Every accessor line (colorant names, component count, NChannel flag, the
    ``/Process`` colour-space name + component-name list, the ``/Colorants``
    key set, and each ``/Colorants`` entry's colour-space name). These are the
    high-value cases — the COS-driven attribute parsing must match byte-for-byte.
  * ``SepAll`` ``toRGB`` (tint -> DeviceGray, no CMM).

**Documented-divergence tier** — the attribute-driven DeviceN ``toRGB`` blends
each spot colorant through its Separation -> DeviceCMYK, and pypdfbox's
DeviceCMYK uses explicit subtractive math while PDFBox routes through the JVM
CMM (CGATS001 ICC). Deltas reach ~80/255, so these are NOT rounding epsilons —
the same project-wide DeviceCMYK divergence pinned in
``test_color_to_rgb_oracle.py`` (waves 1330C / 1386). We assert pypdfbox matches
its own deterministic pin AND that at least one tuple differs from PDFBox, so
the structural routing (per-colorant Separation -> CMYK multiply-blend) is still
verified while the final CMM step is allowed to diverge.

A mismatch on any accessor line, or on the deterministic ``SepAll`` gray path,
is a real bug (attribute-dict parsing / colorant-name list / NChannel flag /
process-component list / tint routing).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceN
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match DeviceNAttrProbe.clamp255) ----------


def _clamp255(value: float) -> int:
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: object, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)  # type: ignore[attr-defined]
    assert rgb is not None, f"{cs!r}.to_rgb({comps}) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe exactly ----------


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


def _separation_array(colorant: str, c1: list[float]) -> COSArray:
    """``[/Separation <name> /DeviceCMYK <type-2 tint>]`` — the COS form of a
    single-colorant Separation, used as a /Colorants attribute-dict value."""
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(_type2([0, 0, 0, 0], c1, 1.0))
    return arr


def _devicen_attr() -> PDDeviceN:
    """3-colorant NChannel DeviceN with /Process (DeviceCMYK + 4 names) and a
    /Colorants attribute dict (each spot -> its own Separation)."""
    names = COSArray()
    for nm in ("Spot1", "Spot2", "Spot3"):
        names.add(COSName.get_pdf_name(nm))

    tint = _type4(
        [0, 1, 0, 1, 0, 1], [0, 1, 0, 1, 0, 1, 0, 1], "{ 0 }"
    )

    process = COSDictionary()
    process.set_item("ColorSpace", COSName.get_pdf_name("DeviceCMYK"))
    proc_components = COSArray()
    for nm in ("Cyan", "Magenta", "Yellow", "Black"):
        proc_components.add(COSName.get_pdf_name(nm))
    process.set_item("Components", proc_components)

    colorants = COSDictionary()
    colorants.set_item("Spot1", _separation_array("Spot1", [1, 0, 0, 0]))
    colorants.set_item("Spot2", _separation_array("Spot2", [0, 1, 0, 0]))
    colorants.set_item("Spot3", _separation_array("Spot3", [0, 0, 1, 0]))

    attrs = COSDictionary()
    attrs.set_name("Subtype", "NChannel")
    attrs.set_item("Process", process)
    attrs.set_item("Colorants", colorants)

    arr = COSArray()
    arr.add(COSName.get_pdf_name("DeviceN"))
    arr.add(names)
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(tint)
    arr.add(attrs)
    return PDDeviceN(arr)


def _sep_all_gray() -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name("All"))
    arr.add(COSName.get_pdf_name("DeviceGray"))
    arr.add(_type4([0, 1], [0, 1], "{ 1 exch sub }"))
    return PDSeparation(arr)


# toRGB input tuples — MUST match DeviceNAttrProbe.java in order.
_DEVICEN_TINTS: list[list[float]] = [
    [0.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
    [1.0, 1.0, 1.0],
    [0.25, 0.5, 0.75],
]
_SEP_TINTS: list[list[float]] = [[0.0], [0.5], [1.0]]

# pypdfbox's own deterministic RGB for the CMM-divergent DeviceN attribute path
# (each spot colorant -> Separation -> subtractive DeviceCMYK, multiply-blended).
# Pinned so a regression in pypdfbox's explicit colour math is caught; PDFBox
# differs because it routes the final CMYK step through the JVM CMM.
_PYPDFBOX_DEVICEN_RGB: list[tuple[int, int, int]] = [
    (255, 255, 255),
    (0, 255, 255),
    (255, 0, 255),
    (255, 255, 0),
    (0, 0, 0),
    (191, 128, 64),
]


def _parse_probe(text: str) -> dict[str, list[str]]:
    """Group probe lines by their leading tag (COLORANTS, TORGB, ...)."""
    out: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        tag = line.split()[0]
        out.setdefault(tag, []).append(line)
    return out


@pytest.fixture(scope="module")
def _probe() -> dict[str, list[str]]:
    return _parse_probe(run_probe_text("DeviceNAttrProbe"))


# ---------- accessor parity (exact tier) ----------


@requires_oracle
def test_colorant_names(_probe: dict[str, list[str]]) -> None:
    """getColorantNames() == PDFBox's, in order."""
    java = _probe["COLORANTS"][0].split()[1:]
    assert _devicen_attr().get_colorant_names() == java


@requires_oracle
def test_number_of_components(_probe: dict[str, list[str]]) -> None:
    """getNumberOfComponents() == PDFBox's (3 colorants)."""
    java = int(_probe["NUMCOMPONENTS"][0].split()[1])
    assert _devicen_attr().get_number_of_components() == java


@requires_oracle
def test_is_n_channel(_probe: dict[str, list[str]]) -> None:
    """isNChannel() == PDFBox's (True — /Subtype is NChannel)."""
    java = _probe["NCHANNEL"][0].split()[1] == "true"
    assert _devicen_attr().is_n_channel() is java
    assert java is True


@requires_oracle
def test_process_color_space_name(_probe: dict[str, list[str]]) -> None:
    """attributes.getProcess().getColorSpace().getName() == PDFBox's."""
    java = _probe["PROCESS_CS"][0].split()[1]
    attrs = _devicen_attr().get_attributes()
    assert attrs is not None
    process = attrs.get_process()
    assert process is not None
    cs = process.get_color_space()
    assert cs is not None
    assert cs.get_name() == java


@requires_oracle
def test_process_components(_probe: dict[str, list[str]]) -> None:
    """process.getComponents() (the named process channels) == PDFBox's."""
    java = _probe["PROCESS_COMPONENTS"][0].split()[1:]
    attrs = _devicen_attr().get_attributes()
    assert attrs is not None
    process = attrs.get_process()
    assert process is not None
    assert process.get_components() == java


@requires_oracle
def test_colorants_key_set(_probe: dict[str, list[str]]) -> None:
    """sorted attributes.getColorants() key set == PDFBox's."""
    java = _probe["COLORANTS_KEYS"][0].split()[1:]
    attrs = _devicen_attr().get_attributes()
    assert attrs is not None
    assert sorted(attrs.get_colorants().keys()) == java


@requires_oracle
def test_colorant_color_space_names(_probe: dict[str, list[str]]) -> None:
    """Each /Colorants entry's colour-space name (a Separation) == PDFBox's."""
    java = {}
    for line in _probe["COLORANT_CS"]:
        _, key, name = line.split()
        java[key] = name
    attrs = _devicen_attr().get_attributes()
    assert attrs is not None
    colorants = attrs.get_colorants()
    py = {k: cs.get_name() for k, cs in colorants.items()}
    assert py == java


@requires_oracle
def test_separation_all_accessors(_probe: dict[str, list[str]]) -> None:
    """Separation /All colorant name + component count == PDFBox's."""
    sep_colorant = _probe["SEP_COLORANT"][0].split()[1]
    sep_num = int(_probe["SEP_NUMCOMPONENTS"][0].split()[1])
    sep = _sep_all_gray()
    assert sep.get_colorant_name() == sep_colorant
    assert sep.get_number_of_components() == sep_num


# ---------- toRGB parity ----------


def _torgb_rows(probe: dict[str, list[str]], name: str) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for line in probe["TORGB"]:
        parts = line.split()
        if parts[1] != name:
            continue
        # ... -> r g b
        idx = parts.index("->")
        r, g, b = (int(x) for x in parts[idx + 1 : idx + 4])
        out.append((r, g, b))
    return out


@requires_oracle
def test_sep_all_to_rgb_exact(_probe: dict[str, list[str]]) -> None:
    """Separation /All -> DeviceGray toRGB == PDFBox's, byte-for-byte (pure
    grey alternate, no CMM)."""
    java = _torgb_rows(_probe, "SepAll")
    sep = _sep_all_gray()
    assert len(java) == len(_SEP_TINTS)
    for comps, j_rgb in zip(_SEP_TINTS, java, strict=True):
        assert _rgb_int(sep, list(comps)) == j_rgb, comps


@requires_oracle
def test_devicen_attr_to_rgb_documented_divergence(
    _probe: dict[str, list[str]],
) -> None:
    """Attribute-driven DeviceN toRGB: each spot colorant routes through its
    Separation -> DeviceCMYK and is multiply-blended. pypdfbox uses explicit
    subtractive CMYK math while PDFBox routes the CMYK step through the JVM CMM
    (CGATS001 ICC). Assert pypdfbox matches its deterministic pin AND that at
    least one tuple differs from PDFBox — verifying the per-colorant routing is
    correct while allowing the documented final-step CMM divergence."""
    java = _torgb_rows(_probe, "DeviceNAttr")
    dn = _devicen_attr()
    assert len(java) == len(_DEVICEN_TINTS)
    any_diff = False
    for comps, j_rgb, exp in zip(
        _DEVICEN_TINTS, java, _PYPDFBOX_DEVICEN_RGB, strict=True
    ):
        py_rgb = _rgb_int(dn, list(comps))
        assert py_rgb == exp, (
            f"DeviceNAttr {comps}: pypdfbox {py_rgb} drifted from pinned {exp}"
        )
        if py_rgb != j_rgb:
            any_diff = True
    assert any_diff, (
        "DeviceNAttr: pypdfbox now matches PDFBox on every tuple — the "
        "documented DeviceCMYK CMM divergence no longer holds."
    )
