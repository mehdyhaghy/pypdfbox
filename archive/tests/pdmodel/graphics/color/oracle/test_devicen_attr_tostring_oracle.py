"""Live PDFBox differential parity for ``PDDeviceNAttributes.toString()`` and
the ``getColorants()`` self-population side effect (PDF 32000-1 §8.6.6.5).

The sibling ``test_devicen_attr_oracle.py`` pins every structural accessor
(colorant names, NChannel flag, process colour-space name + components,
colorants key set, per-entry colour-space name) and the ``toRGB`` path. It
never emits ``PDDeviceNAttributes.toString()`` nor exercises the
empty-``/Colorants`` self-population branch — this file pins both.

The Java side is ``oracle/probes/DeviceNAttrToStringProbe.java``.

**Why no ``/Process`` in the toString fixtures.** Upstream
``PDDeviceNAttributes.toString()`` appends ``getProcess()`` via
``StringBuilder.append(Object)``, and ``PDDeviceNProcess.toString()`` in turn
appends ``getColorSpace()`` the same way. Neither ``PDDeviceNProcess`` nor the
device colour spaces (``PDDeviceCMYK`` …) override ``Object.toString()`` with a
stable form, so a string containing a ``/Process`` embeds a non-deterministic
JVM hashcode (``...PDDeviceCMYK@1b6d3586``). To keep the assertion deterministic
the probe builds attributes WITHOUT a ``/Process`` — the whole string is then
stable: ``<Subtype>{Colorants{"<key>": <PDSeparation.toString()> ...}}``.

**The two parity facets this file enforces:**

1. ``PDDeviceNAttributes.toString()`` structure — the ``/Subtype`` prefix, the
   ``Colorants{...}`` wrapper, and CRUCIALLY (a) each colorant value is rendered
   via the FULL ``PDSeparation.toString()`` (not just the colour-space *name*),
   and (b) every entry is followed by a trailing space, so the closing ``}}`` is
   space-preceded. Both were pypdfbox bugs found and fixed in this wave.

2. ``getColorants()`` self-population — on an attributes dict with no
   ``/Colorants`` entry, calling ``getColorants()`` INSERTS an empty
   ``/Colorants`` COSDictionary into the backing dict and returns an empty map.

**One documented out-of-domain normalisation.** The full ``PDSeparation``
string recurses into the tint ``FunctionType2{...}`` → ``COSArray{[...]}`` →
``COSFloat``. PDFBox renders a float as ``COSFloat{0.0}`` (curly braces) while
pypdfbox's ``COSFloat`` renders ``COSFloat(0.0)`` (parens) — a known COS-layer
``toString`` divergence outside the DeviceN ``/Attributes`` domain. We normalise
``COSFloat{...}`` ↔ ``COSFloat(...)`` in BOTH strings before comparing so this
file asserts only the ``PDDeviceNAttributes`` skeleton, not the COSFloat form.
The HashMap-vs-dict iteration order also differs, so colorant entries are
compared as a set, not in order.
"""

from __future__ import annotations

import re

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_device_n import PDDeviceNAttributes
from tests.oracle.harness import requires_oracle, run_probe_text

# ---------- COS builders mirroring the Java probe exactly ----------


def _type2(c0: list[float], c1: list[float], n: float = 1.0) -> COSDictionary:
    d = COSDictionary()
    d.set_int("FunctionType", 2)
    d.set_item("Domain", COSArray.of_cos_floats([0.0, 1.0]))
    d.set_item("C0", COSArray.of_cos_floats(c0))
    d.set_item("C1", COSArray.of_cos_floats(c1))
    d.set_item("N", COSFloat(n))
    return d


def _separation_array(colorant: str, c1: list[float]) -> COSArray:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Separation"))
    arr.add(COSName.get_pdf_name(colorant))
    arr.add(COSName.get_pdf_name("DeviceCMYK"))
    arr.add(_type2([0, 0, 0, 0], c1, 1.0))
    return arr


def _attrs_dict(subtype: str) -> PDDeviceNAttributes:
    """Attributes dict (NO /Process) with two spot colorants, matching
    ``DeviceNAttrToStringProbe.attrsDict``."""
    colorants = COSDictionary()
    colorants.set_item("Spot1", _separation_array("Spot1", [1, 0, 0, 0]))
    colorants.set_item("Spot2", _separation_array("Spot2", [0, 1, 0, 0]))
    attrs = COSDictionary()
    attrs.set_name("Subtype", subtype)
    attrs.set_item("Colorants", colorants)
    return PDDeviceNAttributes(attrs)


# ---------- normalisation + structural decomposition ----------


def _norm_cosfloat(s: str) -> str:
    """Normalise the out-of-domain ``COSFloat{x}`` (PDFBox) ↔ ``COSFloat(x)``
    (pypdfbox) divergence so the comparison is about the DeviceN attribute
    skeleton, not the COS-layer float form."""
    return re.sub(r"COSFloat\{([^}]*)\}", r"COSFloat(\1)", s)


def _split_attr_tostring(s: str) -> tuple[str, frozenset[str]]:
    """Decompose ``<Subtype>{Colorants{<entries>}}`` into the subtype prefix and
    the unordered set of colorant entries. Each entry ends with a trailing
    space (the upstream convention); we keep that space in the entry token so a
    missing trailing space would still surface as a mismatch.

    Returns ``(subtype, frozenset_of_entries)``. Entries are split on the
    boundary ``" "Spot`` — i.e. a space then a fresh ``"`` quote — which is
    unambiguous because Separation values don't contain that bigram at top
    level."""
    prefix, _, rest = s.partition("{Colorants{")
    assert rest.endswith("}}"), s
    body = rest[:-2]  # strip the closing }}
    # body is: '"Spot2": Separation{...} "Spot1": Separation{...} '
    # Split before each '"Spot' that starts a key (preceded by start or space).
    entries = re.split(r'(?<=\s)(?=")', body) if body.strip() else []
    # Re-attach so each entry retains its trailing space; drop empties.
    return prefix, frozenset(e for e in entries if e.strip())


# ---------- toString parity ----------


@requires_oracle
@pytest.mark.parametrize("subtype", ["NChannel", "DeviceN"])
def test_attributes_to_string(subtype: str) -> None:
    """``PDDeviceNAttributes.toString()`` skeleton == PDFBox's: subtype prefix,
    ``Colorants{...}`` wrapper, full-Separation entry values, trailing space per
    entry (COSFloat brace form normalised; entry order treated as a set)."""
    probe = run_probe_text("DeviceNAttrToStringProbe")
    tag = f"ATTR_TOSTRING_{subtype.upper()}"
    line = next(
        ln for ln in probe.splitlines() if ln.startswith(tag + " ")
    )
    java = line[len(tag) + 1 :]

    py = _attrs_dict(subtype).to_string()

    j_prefix, j_entries = _split_attr_tostring(_norm_cosfloat(java))
    p_prefix, p_entries = _split_attr_tostring(_norm_cosfloat(py))

    assert p_prefix == j_prefix == subtype
    assert p_entries == j_entries


# ---------- getColorants() self-population side effect ----------


@requires_oracle
def test_get_colorants_self_populates_empty() -> None:
    """getColorants() on a dict with no /Colorants INSERTS an empty
    /Colorants COSDictionary and returns an empty map — matching PDFBox's
    before=false / after=true / size=0."""
    probe = run_probe_text("DeviceNAttrToStringProbe")
    fields: dict[str, str] = {}
    for ln in probe.splitlines():
        if ln.startswith("COLORANTS_AUTOPOPULATE_"):
            tag, val = ln.split(maxsplit=1)
            fields[tag] = val
    j_before = fields["COLORANTS_AUTOPOPULATE_BEFORE"] == "true"
    j_after = fields["COLORANTS_AUTOPOPULATE_AFTER"] == "true"
    j_size = int(fields["COLORANTS_AUTOPOPULATE_SIZE"])

    attrs = PDDeviceNAttributes(COSDictionary())
    assert attrs.has_colorants() is j_before
    assert attrs.has_colorants() is False
    result = attrs.get_colorants()
    assert len(result) == j_size == 0
    assert attrs.has_colorants() is j_after
    assert attrs.has_colorants() is True
