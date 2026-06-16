"""Complementary ``PDSoftMask`` fuzz parity with PDFBox 3.0.7.

Targets fuzz angles NOT already pinned by
``tests/pdmodel/graphics/state/oracle/test_soft_mask_dictionary_fuzz_wave1521.py``:

* ``/G`` streams whose ``/Subtype`` is a *COSString* (e.g. ``(Form)`` /
  ``(Image)`` / ``(Bad)``). Upstream ``getGroup`` → ``createXObject`` reads
  the subtype with ``COSStream.getNameAsString``, so a string ``(Form)``
  transparency group is recognised, a string ``(Image)`` resolves to ``None``
  (it is an image, not a group), and a string ``(Bad)`` raises. The pypdfbox
  fast-path pre-check now uses :meth:`COSDictionary.get_name_as_string`
  (wave 1557 fix) so these match — previously the name-only ``get_name``
  rejected the string and mis-wrapped every string-subtype ``/G`` as a plain
  form.
* indirect-reference variants of the above.
* repeated-call identity (caching) of ``getGroup`` / ``getBackdropColor``.
* ``/Type`` key fuzz — the wrapper does not validate ``/Type /Mask``.

A second block exercises the pypdfbox-only accessors that have no upstream
oracle counterpart (``is_alpha`` / ``is_luminosity``, the raw
``get_transfer_function`` companion to the typed getter, the setters'
round-trip, and the initial-transformation-matrix CTM field). Those are
value-pinned against the PDF 32000-1 §11.6.5.3 contract.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
    PDTransparencyGroup,
)
from pypdfbox.pdmodel.graphics.state.pd_soft_mask import PDSoftMask
from tests.oracle.harness import requires_oracle, run_probe_text

_S = COSName.get_pdf_name("S")
_G = COSName.get_pdf_name("G")
_BC = COSName.get_pdf_name("BC")
_TR = COSName.get_pdf_name("TR")
_TYPE = COSName.get_pdf_name("Type")
_TAG = COSName.get_pdf_name("Tag")
_RESOURCES = COSName.get_pdf_name("Resources")
_GROUP = COSName.get_pdf_name("Group")


def _indirect(value: COSBase) -> COSObject:
    return COSObject(0, resolved=value)


def _string_subtype(subtype: str | None, transparency: bool) -> COSStream:
    stream = COSStream()
    if subtype is not None:
        stream.set_item(COSName.SUBTYPE, COSString(subtype))
    stream.set_item(_RESOURCES, COSDictionary())
    stream.set_name(_TAG, "tagged")
    if transparency:
        group = COSDictionary()
        group.set_name(_S, "Transparency")
        stream.set_item(_GROUP, group)
    return stream


def _group(mask: PDSoftMask) -> str:
    try:
        value = mask.get_group()
        return "null" if value is None else "group"
    except Exception:
        return "ERR"


def _emit_group(name: str, group_value: COSBase | None) -> str:
    dictionary = COSDictionary()
    if group_value is not None:
        dictionary.set_item(_G, group_value)
    return f"FUZZ {name} g={_group(PDSoftMask(dictionary))}"


def _emit_group_identity(name: str, group_value: COSBase) -> str:
    dictionary = COSDictionary()
    dictionary.set_item(_G, group_value)
    mask = PDSoftMask(dictionary)
    try:
        first = mask.get_group()
        second = mask.get_group()
        if first is None:
            same = "both_null" if second is None else "drift"
        else:
            same = "same" if first is second else "other"
        return f"FUZZ {name} g={_group(mask)} identity={same}"
    except Exception:
        return f"FUZZ {name} g=ERR identity=ERR"


def _emit_backdrop_identity(name: str) -> str:
    dictionary = COSDictionary()
    dictionary.set_item(_BC, COSArray([COSInteger.get(0), COSInteger.get(1)]))
    mask = PDSoftMask(dictionary)
    first = mask.get_backdrop_color()
    second = mask.get_backdrop_color()
    rendered = "null" if first is None else f"array:{first.size()}"
    return f"FUZZ {name} bc={rendered} identity={'same' if first is second else 'other'}"


def _emit_type_key(name: str, type_value: COSBase | None) -> str:
    dictionary = COSDictionary()
    dictionary.set_name(_S, "Luminosity")
    if type_value is not None:
        dictionary.set_item(_TYPE, type_value)
    subtype = PDSoftMask(dictionary).get_subtype()
    return f"FUZZ {name} s={'null' if subtype is None else subtype.name}"


# (name, python-line-builder) — keyed on the leading two tokens of each line.
_CASES: tuple[tuple[str, object], ...] = (
    ("str_form_plain", lambda: _emit_group("str_form_plain", _string_subtype("Form", False))),
    ("str_form_transp", lambda: _emit_group("str_form_transp", _string_subtype("Form", True))),
    ("str_image", lambda: _emit_group("str_image", _string_subtype("Image", False))),
    ("str_ps", lambda: _emit_group("str_ps", _string_subtype("PS", False))),
    ("str_bad", lambda: _emit_group("str_bad", _string_subtype("Bad", False))),
    ("str_empty", lambda: _emit_group("str_empty", _string_subtype("", False))),
    (
        "str_indirect_transp",
        lambda: _emit_group("str_indirect_transp", _indirect(_string_subtype("Form", True))),
    ),
    (
        "str_indirect_image",
        lambda: _emit_group("str_indirect_image", _indirect(_string_subtype("Image", False))),
    ),
    (
        "str_indirect_bad",
        lambda: _emit_group("str_indirect_bad", _indirect(_string_subtype("Bad", False))),
    ),
    (
        "identity_transp",
        lambda: _emit_group_identity("identity_transp", _string_subtype("Form", True)),
    ),
    (
        "identity_image",
        lambda: _emit_group_identity("identity_image", _string_subtype("Image", False)),
    ),
    ("identity_backdrop", lambda: _emit_backdrop_identity("identity_backdrop")),
    ("type_absent", lambda: _emit_type_key("type_absent", None)),
    ("type_mask", lambda: _emit_type_key("type_mask", COSName.get_pdf_name("Mask"))),
    ("type_wrong", lambda: _emit_type_key("type_wrong", COSName.get_pdf_name("NotMask"))),
    ("type_integer", lambda: _emit_type_key("type_integer", COSInteger.get(1))),
    ("type_null", lambda: _emit_type_key("type_null", COSNull.NULL)),
)


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("SoftMaskFuzzProbe").splitlines()
    return {" ".join(line.split(" ", 2)[:2]): line for line in lines}


@requires_oracle
@pytest.mark.parametrize(
    ("name", "builder"),
    _CASES,
    ids=[name for name, _ in _CASES],
)
def test_soft_mask_fuzz_matches_oracle(
    name: str, builder: object, java_lines: dict[str, str]
) -> None:
    python_line = builder()  # type: ignore[operator]
    key = f"FUZZ {name}"
    assert python_line == java_lines[key]


# --------------------------------------------------------------------------
# Value-pinned coverage for the pypdfbox-only accessors (no upstream oracle:
# PDFBox 3.0.7 PDSoftMask exposes neither isAlpha/isLuminosity, a raw /TR
# getter, the setters, nor a public CTM field — verified by reflection).
# --------------------------------------------------------------------------


def _mask_with_subtype(name: str | None) -> PDSoftMask:
    dictionary = COSDictionary()
    if name is not None:
        dictionary.set_name(_S, name)
    return PDSoftMask(dictionary)


def test_is_alpha_is_luminosity_classification() -> None:
    assert _mask_with_subtype("Alpha").is_alpha()
    assert not _mask_with_subtype("Alpha").is_luminosity()
    assert _mask_with_subtype("Luminosity").is_luminosity()
    assert not _mask_with_subtype("Luminosity").is_alpha()
    # Unknown / missing subtype is neither.
    assert not _mask_with_subtype("Unknown").is_alpha()
    assert not _mask_with_subtype("Unknown").is_luminosity()
    assert not _mask_with_subtype(None).is_alpha()
    assert not _mask_with_subtype(None).is_luminosity()


def test_raw_transfer_function_companion() -> None:
    # Absent /TR → None (caller treats as /Identity per spec).
    assert PDSoftMask(COSDictionary()).get_transfer_function() is None
    # /TR /Identity name returned verbatim by the raw getter.
    dictionary = COSDictionary()
    identity = COSName.get_pdf_name("Identity")
    dictionary.set_item(_TR, identity)
    assert PDSoftMask(dictionary).get_transfer_function() is identity
    # A function dictionary is returned raw (not resolved to a PDFunction).
    func = COSDictionary()
    func.set_int(COSName.get_pdf_name("FunctionType"), 2)
    dictionary2 = COSDictionary()
    dictionary2.set_item(_TR, func)
    assert PDSoftMask(dictionary2).get_transfer_function() is func


def test_setters_round_trip_and_invalidate_cache() -> None:
    mask = PDSoftMask()  # no-arg ctor stamps /Type /Mask
    assert mask.get_cos_object().get_name(_TYPE) == "Mask"

    alpha = COSName.get_pdf_name("Alpha")
    mask.set_subtype(alpha)
    assert mask.get_subtype() is alpha

    bc = COSArray([COSInteger.get(1)])
    mask.set_backdrop_color(bc)
    assert mask.get_backdrop_color() is bc
    mask.set_backdrop_color(None)
    assert mask.get_backdrop_color() is None
    assert mask.get_cos_object().get_dictionary_object(_BC) is None

    identity = COSName.get_pdf_name("Identity")
    mask.set_transfer_function(identity)
    assert mask.get_transfer_function() is identity
    mask.set_transfer_function(None)
    assert mask.get_transfer_function() is None


def test_set_group_accepts_stream_and_rejects_non_stream() -> None:
    mask = PDSoftMask()
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Form")
    mask.set_group(stream)
    assert mask.get_cos_object().get_dictionary_object(_G) is stream
    mask.set_group(None)
    assert mask.get_cos_object().get_dictionary_object(_G) is None
    with pytest.raises(TypeError):
        mask.set_group(COSDictionary())


def test_create_dispatch_none_dict_and_wrong_type() -> None:
    assert PDSoftMask.create(None) is None
    assert PDSoftMask.create(COSName.get_pdf_name("None")) is None
    assert PDSoftMask.create(COSInteger.get(1)) is None
    assert PDSoftMask.create(COSArray()) is None
    dictionary = COSDictionary()
    mask = PDSoftMask.create(dictionary)
    assert mask is not None
    assert mask.get_cos_object() is dictionary


def test_initial_transformation_matrix_round_trip() -> None:
    mask = PDSoftMask()
    assert mask.get_initial_transformation_matrix() is None
    sentinel = object()
    mask.set_initial_transformation_matrix(sentinel)
    assert mask.get_initial_transformation_matrix() is sentinel


def test_transparency_group_typed_for_real_transparency_form() -> None:
    stream = _string_subtype("Form", transparency=True)
    # A name-valued /Subtype variant resolves to a typed transparency group.
    name_stream = COSStream()
    name_stream.set_name(COSName.SUBTYPE, "Form")
    group = COSDictionary()
    group.set_name(_S, "Transparency")
    name_stream.set_item(_GROUP, group)
    dictionary = COSDictionary()
    dictionary.set_item(_G, name_stream)
    assert isinstance(PDSoftMask(dictionary).get_group(), PDTransparencyGroup)
    # And the COSString-subtype variant matches (wave 1557 fix).
    dictionary2 = COSDictionary()
    dictionary2.set_item(_G, stream)
    assert isinstance(PDSoftMask(dictionary2).get_group(), PDTransparencyGroup)
