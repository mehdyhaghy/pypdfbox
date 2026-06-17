"""Malformed transparency-group attribute parity with PDFBox 3.0.7.

Wave 1550 agent B. Complements ``test_form_xobject_dictionary_fuzz_wave1521``
(which fuzzes the FORM-LEVEL accessors and treats ``/Group`` only at the
presence level) by drilling into the transparency-group ATTRIBUTES dictionary
internals (PDF 32000-1 Table 96): the ``/S`` group subtype, ``/CS`` group
colour space, the ``/I`` isolated flag, the ``/K`` knockout flag — each with
valid / wrong-type / missing / indirect / inverted shapes — plus the
XObject-factory dispatch that picks ``PDTransparencyGroup`` over a plain
``PDFormXObject``.

Differential against the live Apache PDFBox oracle
(``oracle/probes/FormXObjectFuzzProbe.java``).

ONE honest divergence is pinned here (and asserted in a dedicated test):
pypdfbox's ``PDColorSpace.create`` is permissive — it returns ``None`` for a
malformed ``/CS`` (bad name, non-array/non-name, empty array, COSNull) where
upstream raises ``IOException``. This is the same already-documented
``PDColorSpace.create`` leniency pinned in wave 1513
(``test_image_fuzz_wave1513``); it originates in the colour cluster, not in
the transparency-group accessor (which faithfully delegates). The
differential ``cs`` field is normalised through ``_PERMISSIVE_CS_CASES`` so
the live-oracle comparison stays meaningful for every OTHER projected field.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
    PDTransparencyGroup,
)
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from tests.oracle.harness import requires_oracle, run_probe_text

CASE_IDS = (
    # /Group container shape (drives factory dispatch + getGroup)
    "g-none", "g-empty", "g-nondict", "g-null", "g-indirect-dict",
    # /S subtype
    "s-transparency", "s-other", "s-nonname-int", "s-nonname-bool",
    "s-null", "s-missing", "s-indirect",
    # /I isolated flag
    "i-true", "i-false", "i-int", "i-name", "i-null", "i-missing",
    "i-indirect-true",
    # /K knockout flag
    "k-true", "k-false", "k-int", "k-string", "k-null", "k-missing",
    "k-indirect-true",
    # /CS group colour space
    "cs-devgray", "cs-devrgb", "cs-devcmyk", "cs-bad-name", "cs-int",
    "cs-empty-array", "cs-null", "cs-missing", "cs-indirect-name",
    # combos
    "full-iso-knock", "tr-no-i-no-k", "non-tr-with-cs",
)

# Cases where upstream PDColorSpace.create throws (probe prints cs=err) but
# pypdfbox is permissive and returns None (cs=none). Pinned divergence — see
# the module docstring and ``test_permissive_color_space_divergence``.
_PERMISSIVE_CS_CASES = frozenset(
    {"cs-bad-name", "cs-int", "cs-empty-array", "cs-null"}
)

_CS = COSName.get_pdf_name("CS")
_ISO = COSName.get_pdf_name("I")
_KNOCK = COSName.get_pdf_name("K")
_GROUP = COSName.get_pdf_name("Group")
_S = COSName.get_pdf_name("S")
_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_BBOX = COSName.get_pdf_name("BBox")


def _indirect(value: COSBase | None, number: int = 200) -> COSObject:
    return COSObject(number, resolved=value)


def _numbers(*values: float) -> COSArray:
    return COSArray(COSInteger(int(value)) for value in values)


def _group() -> COSDictionary:
    """A bare transparency group dict: /Type /Group, /S /Transparency."""
    dictionary = COSDictionary()
    dictionary.set_item(_TYPE, COSName.get_pdf_name("Group"))
    dictionary.set_item(_S, COSName.get_pdf_name("Transparency"))
    return dictionary


def _form_stream(group_value: COSBase | None) -> COSStream:
    stream = COSStream()
    stream.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    stream.set_item(_BBOX, _numbers(0, 0, 100, 100))
    if group_value is not None:
        stream.set_item(_GROUP, group_value)
    return stream


def _build(case_id: str) -> COSStream:  # noqa: C901, PLR0911, PLR0912
    if case_id == "g-none":
        return _form_stream(None)
    if case_id == "g-empty":
        return _form_stream(COSDictionary())
    if case_id == "g-nondict":
        return _form_stream(COSInteger(5))
    if case_id == "g-null":
        return _form_stream(COSNull.NULL)
    if case_id == "g-indirect-dict":
        return _form_stream(_indirect(_group()))

    if case_id == "s-transparency":
        return _form_stream(_group())
    if case_id == "s-other":
        grp = _group()
        grp.set_item(_S, COSName.get_pdf_name("Mask"))
        return _form_stream(grp)
    if case_id == "s-nonname-int":
        grp = _group()
        grp.set_item(_S, COSInteger(7))
        return _form_stream(grp)
    if case_id == "s-nonname-bool":
        grp = _group()
        grp.set_item(_S, COSBoolean.TRUE)
        return _form_stream(grp)
    if case_id == "s-null":
        grp = _group()
        grp.set_item(_S, COSNull.NULL)
        return _form_stream(grp)
    if case_id == "s-missing":
        grp = COSDictionary()
        grp.set_item(_TYPE, COSName.get_pdf_name("Group"))
        return _form_stream(grp)
    if case_id == "s-indirect":
        grp = COSDictionary()
        grp.set_item(_S, _indirect(COSName.get_pdf_name("Transparency")))
        return _form_stream(grp)

    if case_id == "i-true":
        grp = _group()
        grp.set_item(_ISO, COSBoolean.TRUE)
        return _form_stream(grp)
    if case_id == "i-false":
        grp = _group()
        grp.set_item(_ISO, COSBoolean.FALSE)
        return _form_stream(grp)
    if case_id == "i-int":
        grp = _group()
        grp.set_item(_ISO, COSInteger(1))
        return _form_stream(grp)
    if case_id == "i-name":
        grp = _group()
        grp.set_item(_ISO, COSName.get_pdf_name("true"))
        return _form_stream(grp)
    if case_id == "i-null":
        grp = _group()
        grp.set_item(_ISO, COSNull.NULL)
        return _form_stream(grp)
    if case_id == "i-missing":
        return _form_stream(_group())
    if case_id == "i-indirect-true":
        grp = _group()
        grp.set_item(_ISO, _indirect(COSBoolean.TRUE))
        return _form_stream(grp)

    if case_id == "k-true":
        grp = _group()
        grp.set_item(_KNOCK, COSBoolean.TRUE)
        return _form_stream(grp)
    if case_id == "k-false":
        grp = _group()
        grp.set_item(_KNOCK, COSBoolean.FALSE)
        return _form_stream(grp)
    if case_id == "k-int":
        grp = _group()
        grp.set_item(_KNOCK, COSInteger(0))
        return _form_stream(grp)
    if case_id == "k-string":
        grp = _group()
        grp.set_string(_KNOCK, "true")
        return _form_stream(grp)
    if case_id == "k-null":
        grp = _group()
        grp.set_item(_KNOCK, COSNull.NULL)
        return _form_stream(grp)
    if case_id == "k-missing":
        return _form_stream(_group())
    if case_id == "k-indirect-true":
        grp = _group()
        grp.set_item(_KNOCK, _indirect(COSBoolean.TRUE))
        return _form_stream(grp)

    if case_id == "cs-devgray":
        grp = _group()
        grp.set_item(_CS, COSName.get_pdf_name("DeviceGray"))
        return _form_stream(grp)
    if case_id == "cs-devrgb":
        grp = _group()
        grp.set_item(_CS, COSName.get_pdf_name("DeviceRGB"))
        return _form_stream(grp)
    if case_id == "cs-devcmyk":
        grp = _group()
        grp.set_item(_CS, COSName.get_pdf_name("DeviceCMYK"))
        return _form_stream(grp)
    if case_id == "cs-bad-name":
        grp = _group()
        grp.set_item(_CS, COSName.get_pdf_name("NotAColorSpace"))
        return _form_stream(grp)
    if case_id == "cs-int":
        grp = _group()
        grp.set_item(_CS, COSInteger(3))
        return _form_stream(grp)
    if case_id == "cs-empty-array":
        grp = _group()
        grp.set_item(_CS, COSArray([]))
        return _form_stream(grp)
    if case_id == "cs-null":
        grp = _group()
        grp.set_item(_CS, COSNull.NULL)
        return _form_stream(grp)
    if case_id == "cs-missing":
        return _form_stream(_group())
    if case_id == "cs-indirect-name":
        grp = _group()
        grp.set_item(_CS, _indirect(COSName.get_pdf_name("DeviceRGB")))
        return _form_stream(grp)

    if case_id == "full-iso-knock":
        grp = _group()
        grp.set_item(_ISO, COSBoolean.TRUE)
        grp.set_item(_KNOCK, COSBoolean.TRUE)
        grp.set_item(_CS, COSName.get_pdf_name("DeviceRGB"))
        return _form_stream(grp)
    if case_id == "tr-no-i-no-k":
        return _form_stream(_group())
    if case_id == "non-tr-with-cs":
        grp = COSDictionary()
        grp.set_item(_S, COSName.get_pdf_name("Mask"))
        grp.set_item(_CS, COSName.get_pdf_name("DeviceGray"))
        return _form_stream(grp)

    raise ValueError(case_id)


def _cs_projection(attrs) -> str:
    try:
        cs = attrs.get_color_space()
        if cs is None:
            return "none"
        name = cs.get_name()
        return name if name else "present"
    except Exception:  # noqa: BLE001 — mirror the probe's broad catch
        return "err"


def _project(case_id: str, *, normalise_cs: bool) -> str:
    stream = _build(case_id)
    xobject = PDXObject.create_x_object(stream, None)
    type_name = (
        "TransparencyGroup"
        if isinstance(xobject, PDTransparencyGroup)
        else "PlainForm"
    )
    attrs = xobject.get_group_attributes()
    if attrs is None:
        return (
            f"CASE {case_id} type={type_name} group=none"
            " subtype=none iso=false knock=false cs=none istg=false"
        )
    subtype = attrs.get_cos_object().get_cos_name(_S)
    subtype_name = "none" if subtype is None else subtype.name
    istg = subtype is not None and subtype.name == "Transparency"
    cs = _cs_projection(attrs)
    if normalise_cs and case_id in _PERMISSIVE_CS_CASES:
        # Pin the documented divergence: upstream raises (cs=err); pypdfbox
        # is permissive (cs=none). Normalise so the rest of the line still
        # differential-checks against the live oracle.
        cs = "err"
    iso = "true" if attrs.is_isolated() else "false"
    knock = "true" if attrs.is_knockout() else "false"
    return (
        f"CASE {case_id} type={type_name} group=present"
        f" subtype={subtype_name} iso={iso} knock={knock}"
        f" cs={cs} istg={'true' if istg else 'false'}"
    )


# --- pinned expected values (PDFBox 3.0.7, captured from the live probe) ---
# Stored compactly as (type, group, subtype, iso, knock, cs, istg) field
# tuples and rendered through ``_render`` (the same field order the probe
# emits) to keep line length sane. cs="err" for the four permissive cases
# reflects UPSTREAM (Java throws); pypdfbox returns cs=none there — see
# _PERMISSIVE_CS_CASES + the divergence test below.
_TG = "TransparencyGroup"
_PF = "PlainForm"
# fmt: off
_EXPECTED_FIELDS = {
    "g-none":          (_PF, "none",    "none",         "false", "false", "none",      "false"),  # noqa: E501
    "g-empty":         (_PF, "present", "none",         "false", "false", "none",      "false"),  # noqa: E501
    "g-nondict":       (_PF, "none",    "none",         "false", "false", "none",      "false"),  # noqa: E501
    "g-null":          (_PF, "none",    "none",         "false", "false", "none",      "false"),  # noqa: E501
    "g-indirect-dict": (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "s-transparency":  (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "s-other":         (_PF, "present", "Mask",         "false", "false", "none",      "false"),  # noqa: E501
    "s-nonname-int":   (_PF, "present", "none",         "false", "false", "none",      "false"),  # noqa: E501
    "s-nonname-bool":  (_PF, "present", "none",         "false", "false", "none",      "false"),  # noqa: E501
    "s-null":          (_PF, "present", "none",         "false", "false", "none",      "false"),  # noqa: E501
    "s-missing":       (_PF, "present", "none",         "false", "false", "none",      "false"),  # noqa: E501
    "s-indirect":      (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "i-true":          (_TG, "present", "Transparency", "true",  "false", "none",      "true"),   # noqa: E501
    "i-false":         (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "i-int":           (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "i-name":          (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "i-null":          (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "i-missing":       (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "i-indirect-true": (_TG, "present", "Transparency", "true",  "false", "none",      "true"),   # noqa: E501
    "k-true":          (_TG, "present", "Transparency", "false", "true",  "none",      "true"),   # noqa: E501
    "k-false":         (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "k-int":           (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "k-string":        (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "k-null":          (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "k-missing":       (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "k-indirect-true": (_TG, "present", "Transparency", "false", "true",  "none",      "true"),   # noqa: E501
    "cs-devgray":      (_TG, "present", "Transparency", "false", "false", "DeviceGray", "true"),  # noqa: E501
    "cs-devrgb":       (_TG, "present", "Transparency", "false", "false", "DeviceRGB", "true"),   # noqa: E501
    "cs-devcmyk":      (_TG, "present", "Transparency", "false", "false", "DeviceCMYK", "true"),  # noqa: E501
    "cs-bad-name":     (_TG, "present", "Transparency", "false", "false", "err",       "true"),   # noqa: E501
    "cs-int":          (_TG, "present", "Transparency", "false", "false", "err",       "true"),   # noqa: E501
    "cs-empty-array":  (_TG, "present", "Transparency", "false", "false", "err",       "true"),   # noqa: E501
    "cs-null":         (_TG, "present", "Transparency", "false", "false", "err",       "true"),   # noqa: E501
    "cs-missing":      (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "cs-indirect-name":(_TG, "present", "Transparency", "false", "false", "DeviceRGB", "true"),   # noqa: E501
    "full-iso-knock":  (_TG, "present", "Transparency", "true",  "true",  "DeviceRGB", "true"),   # noqa: E501
    "tr-no-i-no-k":    (_TG, "present", "Transparency", "false", "false", "none",      "true"),   # noqa: E501
    "non-tr-with-cs":  (_PF, "present", "Mask",         "false", "false", "DeviceGray", "false"), # noqa: E501
}
# fmt: on


def _render(case_id: str) -> str:
    type_name, group, subtype, iso, knock, cs, istg = _EXPECTED_FIELDS[case_id]
    return (
        f"CASE {case_id} type={type_name} group={group}"
        f" subtype={subtype} iso={iso} knock={knock} cs={cs} istg={istg}"
    )


EXPECTED = {case_id: _render(case_id) for case_id in CASE_IDS}


@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_pinned_against_pdfbox_307(case_id: str) -> None:
    """pypdfbox matches the captured PDFBox 3.0.7 projection (cs normalised
    for the four documented permissive cases)."""
    assert _project(case_id, normalise_cs=True) == EXPECTED[case_id]


def test_permissive_color_space_divergence() -> None:
    """Pin BOTH sides of the documented PDColorSpace.create leniency.

    Upstream PDFBox raises IOException for a malformed /CS (the probe prints
    cs=err); pypdfbox's PDColorSpace.create is permissive and returns None
    (cs=none). Same divergence already pinned in wave 1513
    (test_image_fuzz_wave1513). The transparency-group accessor faithfully
    delegates — the difference originates in the colour cluster."""
    for case_id in _PERMISSIVE_CS_CASES:
        # Upstream side: pinned cs=err.
        assert "cs=err" in EXPECTED[case_id]
        # pypdfbox side: actually cs=none (un-normalised projection).
        raw = _project(case_id, normalise_cs=False)
        assert "cs=none" in raw


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    return {
        line.split()[1]: line
        for line in run_probe_text("FormXObjectFuzzProbe").splitlines()
    }


@requires_oracle
@pytest.mark.parametrize("case_id", CASE_IDS, ids=CASE_IDS)
def test_matches_oracle(case_id: str, java_lines: dict[str, str]) -> None:
    """Live differential: pypdfbox projection (cs normalised for the four
    permissive cases) equals Apache PDFBox 3.0.7's."""
    assert _project(case_id, normalise_cs=True) == java_lines[case_id]
