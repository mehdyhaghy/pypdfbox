"""Live PDFBox differential parity for the SPECIAL Separation colorant-name
surface (PDF 32000-1 §8.6.6.4): a Separation colour space whose colorant name
is ``/All`` (paints every device colorant — registration marks) or ``/None``
(never marks the page — a no-op). The sibling
``test_color_to_rgb_oracle.py`` exercises a couple of ``toRGB`` tuples for
``/All`` / ``/None`` over a CMYK alternate; THIS test pins the
colorant-name + colour-model surface itself:

* ``get_colorant_name()`` returns the literal name (``"All"`` / ``"None"``,
  and the empty string for the default ctor) — **exact match**,
* ``get_number_of_components()`` is always 1 — **exact match**,
* ``get_initial_color().get_components()`` is ``[1.0]`` regardless of the
  colorant name (full tint) — **exact match**,
* ``to_rgb([tint])`` across five tint values routes through the tint
  transform unchanged: neither ``/All`` nor ``/None`` short-circuits the
  conversion (the name only matters at render time).

The Java side is ``oracle/probes/SeparationAllNoneProbe.java``. It builds each
space from in-memory COS objects and emits, per space, a ``describe`` line
(``TAG colorant=<name> ncomp=<n> initial=<c0,...>``) and one
``TAG tint <t> -> r g b`` line per tint (RGB are 0-255 ints,
``round(component*255)`` clamped to ``[0, 255]``).

``to_rgb`` parity tiers, by alternate colour-management model — same taxonomy
as ``test_color_to_rgb_oracle.py``:

**Exact-match tier** — pure-grey alternate, no CMM:

  * AllGray, NoneGray   — tint -> DeviceGray (g = 1 - tint)

**Documented-divergence tier** — pypdfbox uses deterministic subtractive
DeviceCMYK math while PDFBox routes the final CMYK step through the JVM CMM
(CGATS001 ICC). Deltas reach tens of 255-units, not rounding epsilons:

  * AllCmyk, NoneCmyk   — tint -> DeviceCMYK

A mismatch in the exact tier (or any colorant-name / initial-colour / ncomp
mismatch) is a real bug. A drift in the divergence tier means pypdfbox's
explicit CMYK math changed (update the pin) or PDFBox's CMM output shifted
(informational).
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
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- shared rounding (must match SeparationAllNoneProbe.clamp255) ----


def _clamp255(value: float) -> int:
    """round(value * 255), clamped to [0, 255] — mirrors the Java probe."""
    r = round(value * 255.0)
    if r < 0:
        return 0
    if r > 255:
        return 255
    return int(r)


def _rgb_int(cs: PDSeparation, comps: list[float]) -> tuple[int, int, int]:
    rgb = cs.to_rgb(comps)
    assert rgb is not None, f"{cs!r}.to_rgb({comps}) returned None"
    return (_clamp255(rgb[0]), _clamp255(rgb[1]), _clamp255(rgb[2]))


# ---------- COS builders mirroring the Java probe ----------


def _type2(
    c0: list[float], c1: list[float], n: float = 1.0
) -> COSDictionary:
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


def _sep(colorant: str, alternate: str, tint: object) -> PDSeparation:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name(alternate))
    arr.add(tint.get_cos_object())  # type: ignore[attr-defined]
    return PDSeparation(arr)


def _all_cmyk() -> PDSeparation:
    return _sep("All", "DeviceCMYK", _type2([0, 0, 0, 0], [1, 1, 1, 1], 1.0))


def _all_gray() -> PDSeparation:
    return _sep("All", "DeviceGray", _type4([0, 1], [0, 1], "{ 1 exch sub }"))


def _none_cmyk() -> PDSeparation:
    return _sep("None", "DeviceCMYK", _type2([0, 0, 0, 0], [0, 0, 0, 1], 1.0))


def _none_gray() -> PDSeparation:
    return _sep("None", "DeviceGray", _type4([0, 1], [0, 1], "{ 1 exch sub }"))


# tint inputs MUST match SeparationAllNoneProbe.java exactly, same order.
_TINTS = [[0.0], [0.25], [0.5], [0.75], [1.0]]

# TAG -> (builder, expected colorant name).
_SPACES: dict[str, tuple[object, str]] = {
    "AllCmyk": (_all_cmyk, "All"),
    "AllGray": (_all_gray, "All"),
    "NoneCmyk": (_none_cmyk, "None"),
    "NoneGray": (_none_gray, "None"),
}

# Exact-match tier (pure-grey alternate, no CMM).
_EXACT = {"AllGray", "NoneGray"}
# Documented-divergence tier (DeviceCMYK alternate via JVM CMM upstream).
_DIVERGENT = {"AllCmyk", "NoneCmyk"}

# pypdfbox's pinned deterministic RGB for the CMM-divergent CMYK alternates.
# tint -> DeviceCMYK subtractive (1-c)(1-k); PDFBox routes through CGATS001.
_PYPDFBOX_DIVERGENT_EXPECTED: dict[str, list[tuple[int, int, int]]] = {
    # /All: tint t -> (t,t,t,t) CMYK.
    "AllCmyk": [
        (255, 255, 255),
        (143, 143, 143),
        (64, 64, 64),
        (16, 16, 16),
        (0, 0, 0),
    ],
    # /None: tint t -> (0,0,0,t) CMYK (K ramp).
    "NoneCmyk": [
        (255, 255, 255),
        (191, 191, 191),
        (128, 128, 128),
        (64, 64, 64),
        (0, 0, 0),
    ],
}


def _parse_probe(text: str) -> dict[str, dict[str, object]]:
    """Parse the probe output into TAG -> {describe fields, 'tints': [...]}."""
    out: dict[str, dict[str, object]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        tag = parts[0]
        rec = out.setdefault(tag, {"tints": []})
        if len(parts) >= 2 and parts[1].startswith("colorant="):
            # describe line: TAG colorant=<name> ncomp=<n> initial=<...>
            fields = {}
            for tok in parts[1:]:
                key, _, val = tok.partition("=")
                fields[key] = val
            rec["colorant"] = fields.get("colorant", "")
            rec["ncomp"] = int(fields["ncomp"])
            rec["initial"] = [
                float(x) for x in fields["initial"].split(",") if x != ""
            ]
        elif "->" in line:
            # tint line: TAG tint <t> -> r g b
            _, right = line.split("->")
            r, g, b = (int(x) for x in right.split())
            rec["tints"].append((r, g, b))  # type: ignore[union-attr]
    return out


@pytest.fixture(scope="module")
def _java() -> dict[str, dict[str, object]]:
    return _parse_probe(run_probe_text("SeparationAllNoneProbe"))


# ---------- colorant-name / ncomp / initial-colour (exact, all spaces) ----


@requires_oracle
@pytest.mark.parametrize("tag", sorted(_SPACES))
def test_colorant_name_and_initial_color(
    tag: str, _java: dict[str, dict[str, object]]
) -> None:
    """get_colorant_name / get_number_of_components / get_initial_color match
    PDFBox exactly. The /All and /None names are stored and returned verbatim;
    the initial colour is the single full-tint component 1.0 regardless of the
    colorant name."""
    builder, expected_name = _SPACES[tag]
    cs: PDSeparation = builder()  # type: ignore[operator]
    j = _java[tag]

    assert cs.get_colorant_name() == expected_name
    assert cs.get_colorant_name() == j["colorant"]
    assert cs.get_number_of_components() == j["ncomp"] == 1
    assert cs.get_initial_color().get_components() == j["initial"] == [1.0]


@requires_oracle
def test_default_ctor_empty_colorant(
    _java: dict[str, dict[str, object]]
) -> None:
    """The default ctor leaves an empty colorant name (not None) and a
    single-component 1.0 initial colour — matching upstream PDSeparation()."""
    j = _java["Empty"]
    cs = PDSeparation()
    assert cs.get_colorant_name() == "" == j["colorant"]
    assert cs.get_number_of_components() == j["ncomp"] == 1
    assert cs.get_initial_color().get_components() == j["initial"] == [1.0]


# ---------- to_rgb exact-match tier (DeviceGray alternate) ----------


@requires_oracle
@pytest.mark.parametrize("tag", sorted(_EXACT))
def test_to_rgb_exact(tag: str, _java: dict[str, dict[str, object]]) -> None:
    """Over a pure-grey alternate the tint transform output is forwarded
    without any CMM, so pypdfbox and PDFBox agree byte-for-byte at every tint.
    A mismatch means the /All or /None name wrongly altered the conversion."""
    builder, _ = _SPACES[tag]
    cs: PDSeparation = builder()  # type: ignore[operator]
    java_tints = _java[tag]["tints"]
    assert len(java_tints) == len(_TINTS)  # type: ignore[arg-type]
    for comps, j_rgb in zip(_TINTS, java_tints, strict=True):  # type: ignore[arg-type]
        assert _rgb_int(cs, list(comps)) == j_rgb, (
            f"{tag} {comps}: pypdfbox != PDFBox {j_rgb}"
        )


# ---------- to_rgb documented-divergence tier (DeviceCMYK alternate) ----


@requires_oracle
@pytest.mark.parametrize("tag", sorted(_DIVERGENT))
def test_to_rgb_documented_divergence(
    tag: str, _java: dict[str, dict[str, object]]
) -> None:
    """Over a DeviceCMYK alternate pypdfbox produces its pinned deterministic
    subtractive RGB; PDFBox differs because it routes the CMYK step through the
    JVM CMM (CGATS001 ICC). We assert both pypdfbox==pin (regression guard) and
    that at least one tuple differs from PDFBox (keeps the divergence honest).
    Crucially the /All and /None names do NOT change the routing — both run the
    tint transform unchanged."""
    builder, _ = _SPACES[tag]
    cs: PDSeparation = builder()  # type: ignore[operator]
    java_tints = _java[tag]["tints"]
    expected = _PYPDFBOX_DIVERGENT_EXPECTED[tag]
    assert len(java_tints) == len(_TINTS)  # type: ignore[arg-type]
    any_diff = False
    for comps, j_rgb, exp in zip(_TINTS, java_tints, expected, strict=True):  # type: ignore[arg-type]
        py_rgb = _rgb_int(cs, list(comps))
        assert py_rgb == exp, (
            f"{tag} {comps}: pypdfbox {py_rgb} drifted from pinned {exp}"
        )
        if py_rgb != j_rgb:
            any_diff = True
    assert any_diff, (
        f"{tag}: pypdfbox now matches PDFBox on every tuple — the documented "
        f"CMM divergence no longer holds; move {tag} to the exact-match tier."
    )
