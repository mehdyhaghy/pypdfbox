"""Live PDFBox differential for deep and recursive resource graphs."""

from __future__ import annotations

from collections.abc import Callable

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSStream,
)
from pypdfbox.pdmodel import PDPage, PDResources
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.missing_resource_exception import MissingResourceException
from pypdfbox.pdmodel.pd_resource_cache import DefaultResourceCache
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name
_F1 = _N("F1")
_F2 = _N("F2")
_IM1 = _N("Im1")
_CS1 = _N("CS1")
_GS1 = _N("GS1")
_RESOURCES = COSName.RESOURCES
_PAGES = COSName.PAGES
_PARENT = COSName.PARENT
_TYPE = COSName.TYPE


def _java_exception(error: BaseException) -> str:
    if isinstance(error, MissingResourceException):
        return "MissingResourceException"
    if isinstance(error, OSError):
        return "IOException"
    if isinstance(error, RecursionError):
        return "StackOverflowError"
    return type(error).__name__


def _safe(cell: Callable[[], str]) -> str:
    try:
        return cell()
    except BaseException as error:
        return f"ERR:{_java_exception(error)}"


def _name(value: object | None) -> str:
    return "null" if value is None else type(value).__name__


def _font_dict() -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.TYPE, COSName.FONT)
    dictionary.set_name(COSName.SUBTYPE, "Type1")
    dictionary.set_name(_N("BaseFont"), "Helvetica")
    return dictionary


def _font_resources(value: COSBase) -> COSDictionary:
    fonts = COSDictionary()
    fonts.set_item(_F1, value)
    resources = COSDictionary()
    resources.set_item(COSName.FONT, fonts)
    return resources


def _image(color_space_name: str) -> COSStream:
    stream = COSStream()
    stream.set_name(COSName.SUBTYPE, "Image")
    stream.set_int(_N("Width"), 1)
    stream.set_int(_N("Height"), 1)
    stream.set_int(_N("BitsPerComponent"), 8)
    stream.set_item(_N("ColorSpace"), _N(color_space_name))
    return stream


def _xobject_resources(image_ref: COSObject, named_color_space: bool) -> COSDictionary:
    xobjects = COSDictionary()
    xobjects.set_item(_IM1, image_ref)
    resources = COSDictionary()
    resources.set_item(COSName.get_pdf_name("XObject"), xobjects)
    if named_color_space:
        color_spaces = COSDictionary()
        color_spaces.set_item(_CS1, _N("DeviceRGB"))
        resources.set_item(_N("ColorSpace"), color_spaces)
    return resources


def _color_space_resources(value: COSBase) -> COSDictionary:
    color_spaces = COSDictionary()
    color_spaces.set_item(_CS1, value)
    resources = COSDictionary()
    resources.set_item(_N("ColorSpace"), color_spaces)
    return resources


def _ext_state_dict() -> COSDictionary:
    dictionary = COSDictionary()
    dictionary.set_item(COSName.TYPE, _N("ExtGState"))
    dictionary.set_float(_N("ca"), 0.5)
    return dictionary


def _ext_state_resources(value: COSBase) -> COSDictionary:
    ext_states = COSDictionary()
    ext_states.set_item(_GS1, value)
    resources = COSDictionary()
    resources.set_item(_N("ExtGState"), ext_states)
    return resources


def _font_twice(resources: PDResources, name: COSName) -> str:
    def cell() -> str:
        first = resources.get_font(name)
        second = resources.get_font(name)
        return f"{_name(first)}/{int(first is second)}"

    return _safe(cell)


def _font_alias(resources: PDResources) -> str:
    def cell() -> str:
        first = resources.get_font(_F1)
        second = resources.get_font(_F2)
        return f"{_name(first)},{_name(second)}/{int(first is second)}"

    return _safe(cell)


def _color_space_twice(resources: PDResources) -> str:
    def cell() -> str:
        first = resources.get_color_space(_CS1)
        second = resources.get_color_space(_CS1)
        return f"{_name(first)}/{int(first is second)}"

    return _safe(cell)


def _xobject_twice(resources: PDResources) -> str:
    def cell() -> str:
        first = resources.get_x_object(_IM1)
        second = resources.get_x_object(_IM1)
        return f"{_name(first)}/{int(first is second)}"

    return _safe(cell)


def _ext_state_twice(resources: PDResources) -> str:
    def cell() -> str:
        first = resources.get_ext_gstate(_GS1)
        second = resources.get_ext_gstate(_GS1)
        return f"{_name(first)}/{int(first is second)}"

    return _safe(cell)


def _malformed_cell(resources: PDResources) -> str:
    return " ".join(
        (
            f"f={_safe(lambda: _name(resources.get_font(_F1)))}",
            f"x={_safe(lambda: _name(resources.get_x_object(_IM1)))}",
            f"c={_safe(lambda: _name(resources.get_color_space(_CS1)))}",
            f"p={_safe(lambda: _name(resources.get_pattern(_N('P1'))))}",
            f"g={_safe(lambda: _name(resources.get_ext_gstate(_GS1)))}",
        )
    )


def _page_font(page: PDPage) -> str:
    def cell() -> str:
        first_resources = page.get_resources()
        second_resources = page.get_resources()
        if first_resources is None or second_resources is None:
            return "res=null"
        first_font = first_resources.get_font(_F1)
        second_font = second_resources.get_font(_F1)
        return (
            f"res=PDResources/{int(first_resources is second_resources)} "
            f"font={_name(first_font)}/{int(first_font is second_font)}"
        )

    return _safe(cell)


def _page_with_parents(
    page_dictionary: COSDictionary, depth: int, resources: COSDictionary
) -> PDPage:
    child = page_dictionary
    for _ in range(depth):
        parent = COSDictionary()
        parent.set_item(_TYPE, _PAGES)
        child.set_item(_PARENT, parent)
        child = parent
    child.set_item(_RESOURCES, resources)
    return PDPage(page_dictionary)


def _python_lines() -> list[str]:
    lines: list[str] = []

    def emit(case_id: str, value: str) -> None:
        lines.append(f"CASE {case_id} {value}")

    direct_font = _font_dict()
    emit("fdir", _font_twice(PDResources(_font_resources(direct_font)), _F1))

    indirect_font = COSObject(1, resolved=_font_dict())
    emit(
        "find",
        _font_twice(
            PDResources(
                _font_resources(indirect_font),
                resource_cache=DefaultResourceCache(),
            ),
            _F1,
        ),
    )

    alias_direct_fonts = COSDictionary()
    alias_direct_fonts.set_item(_F1, direct_font)
    alias_direct_fonts.set_item(_F2, direct_font)
    alias_direct = COSDictionary()
    alias_direct.set_item(COSName.FONT, alias_direct_fonts)
    emit("fali", _font_alias(PDResources(alias_direct)))

    shared_indirect_font = COSObject(2, resolved=_font_dict())
    alias_indirect_fonts = COSDictionary()
    alias_indirect_fonts.set_item(_F1, shared_indirect_font)
    alias_indirect_fonts.set_item(_F2, shared_indirect_font)
    alias_indirect = COSDictionary()
    alias_indirect.set_item(COSName.FONT, alias_indirect_fonts)
    emit(
        "fain",
        _font_alias(
            PDResources(alias_indirect, resource_cache=DefaultResourceCache())
        ),
    )

    indirect_category = COSDictionary()
    direct_font_subdict = _font_resources(_font_dict()).get_dictionary_object(
        COSName.FONT
    )
    assert isinstance(direct_font_subdict, COSDictionary)
    indirect_category.set_item(
        COSName.FONT, COSObject(3, resolved=direct_font_subdict)
    )
    emit("cind", _font_twice(PDResources(indirect_category), _F1))

    chained_category = COSDictionary()
    chained_category.set_item(
        COSName.FONT,
        COSObject(4, resolved=COSObject(5, resolved=direct_font_subdict)),
    )
    emit("cchn", _font_twice(PDResources(chained_category), _F1))

    emit(
        "fnul",
        _font_twice(
            PDResources(_font_resources(COSObject(6, resolved=None))), _F1
        ),
    )
    emit(
        "fchn",
        _font_twice(
            PDResources(
                _font_resources(
                    COSObject(7, resolved=COSObject(8, resolved=_font_dict()))
                )
            ),
            _F1,
        ),
    )

    emit(
        "xyes",
        _xobject_twice(
            PDResources(
                _xobject_resources(
                    COSObject(9, resolved=_image("DeviceGray")), False
                ),
                resource_cache=DefaultResourceCache(),
            )
        ),
    )
    emit(
        "xnoc",
        _xobject_twice(
            PDResources(
                _xobject_resources(COSObject(10, resolved=_image("CS1")), True),
                resource_cache=DefaultResourceCache(),
            )
        ),
    )

    emit(
        "cpat",
        _color_space_twice(
            PDResources(
                _color_space_resources(
                    COSObject(11, resolved=_N("Pattern"))
                ),
                resource_cache=DefaultResourceCache(),
            )
        ),
    )

    null_color_spaces = COSDictionary()
    null_color_spaces.set_item(_CS1, COSNull.NULL)
    null_resources = COSDictionary()
    null_resources.set_item(_N("ColorSpace"), null_color_spaces)
    null_color_resource = PDResources(null_resources)
    emit(
        "cnull",
        f"has={int(null_color_resource.has_color_space(_CS1))} "
        f"get={_color_space_twice(null_color_resource)}",
    )

    emit(
        "gsin",
        _ext_state_twice(
            PDResources(
                _ext_state_resources(COSObject(12, resolved=_ext_state_dict())),
                resource_cache=DefaultResourceCache(),
            )
        ),
    )

    malformed = COSDictionary()
    malformed_fonts = COSDictionary()
    malformed_fonts.set_item(_F1, COSObject(13, resolved=COSArray()))
    malformed.set_item(COSName.FONT, malformed_fonts)
    malformed_xobjects = COSDictionary()
    malformed_xobjects.set_item(_IM1, COSObject(14, resolved=COSInteger.ONE))
    malformed.set_item(_N("XObject"), malformed_xobjects)
    malformed_color_spaces = COSDictionary()
    malformed_color_spaces.set_item(
        _CS1, COSObject(15, resolved=_N("UnknownCS"))
    )
    malformed.set_item(_N("ColorSpace"), malformed_color_spaces)
    malformed_patterns = COSDictionary()
    malformed_patterns.set_item(
        _N("P1"), COSObject(16, resolved=COSInteger.ONE)
    )
    malformed.set_item(_N("Pattern"), malformed_patterns)
    malformed_ext_states = COSDictionary()
    malformed_ext_states.set_item(_GS1, COSObject(17, resolved=COSArray()))
    malformed.set_item(_N("ExtGState"), malformed_ext_states)
    emit(
        "mbad",
        _malformed_cell(
            PDResources(malformed, resource_cache=DefaultResourceCache())
        ),
    )

    nested = COSDictionary()
    nested.set_item(_RESOURCES, _font_resources(_font_dict()))
    emit("nest", _font_twice(PDResources(nested), _F1))

    self_nested = COSDictionary()
    self_nested.set_item(_RESOURCES, self_nested)
    emit("self", _font_twice(PDResources(self_nested), _F1))

    wrong_subdict = COSDictionary()
    wrong_subdict.set_item(COSName.FONT, COSArray())
    create_over_wrong = PDResources(wrong_subdict)
    created = create_over_wrong.add(PDType1Font())
    emit("crbd", f"{created.get_name()} {_font_twice(create_over_wrong, created)}")

    emit(
        "inhd",
        _page_font(
            _page_with_parents(
                COSDictionary(), 64, _font_resources(_font_dict())
            )
        ),
    )

    local_empty = COSDictionary()
    local_empty.set_item(_RESOURCES, COSDictionary())
    emit(
        "inhe",
        _page_font(
            _page_with_parents(local_empty, 2, _font_resources(_font_dict()))
        ),
    )

    local_null = COSDictionary()
    local_null.set_item(_RESOURCES, COSNull.NULL)
    emit(
        "inhn",
        _page_font(
            _page_with_parents(local_null, 2, _font_resources(_font_dict()))
        ),
    )

    local_wrong = COSDictionary()
    local_wrong.set_item(_RESOURCES, COSInteger.ONE)
    emit(
        "inhw",
        _page_font(
            _page_with_parents(local_wrong, 2, _font_resources(_font_dict()))
        ),
    )

    page_stop = COSDictionary()
    non_pages_parent = COSDictionary()
    non_pages_parent.set_item(_RESOURCES, _font_resources(_font_dict()))
    page_stop.set_item(_PARENT, non_pages_parent)
    emit("inhs", _page_font(PDPage(page_stop)))

    page_cycle = COSDictionary()
    parent_a = COSDictionary()
    parent_b = COSDictionary()
    parent_a.set_item(_TYPE, _PAGES)
    parent_b.set_item(_TYPE, _PAGES)
    page_cycle.set_item(_PARENT, parent_a)
    parent_a.set_item(_PARENT, parent_b)
    parent_b.set_item(_PARENT, parent_a)
    emit("inhc", _page_font(PDPage(page_cycle)))

    page_cycle_hit = COSDictionary()
    hit_a = COSDictionary()
    hit_b = COSDictionary()
    hit_a.set_item(_TYPE, _PAGES)
    hit_b.set_item(_TYPE, _PAGES)
    page_cycle_hit.set_item(_PARENT, hit_a)
    hit_a.set_item(_PARENT, hit_b)
    hit_b.set_item(_PARENT, hit_a)
    hit_b.set_item(_RESOURCES, _font_resources(_font_dict()))
    emit("inhh", _page_font(PDPage(page_cycle_hit)))

    return lines


def test_resources_recursive_regressions() -> None:
    by_id = {line.split(" ", 2)[1]: line for line in _python_lines()}
    assert by_id["fdir"].endswith("PDType1Font/1")
    assert by_id["xnoc"].endswith("PDImageXObject/0")
    assert by_id["cpat"].endswith("PDPattern/0")
    assert "has=0" in by_id["cnull"]
    assert "res=PDResources/1 font=PDType1Font/1" in by_id["inhd"]


_PINNED: dict[str, tuple[str, str]] = {
    "cnull": (
        "CASE cnull has=0 get=null/1",
        "CASE cnull has=0 get=ERR:MissingResourceException",
    )
}


@requires_oracle
def test_resources_recursive_fuzz_matches_pdfbox() -> None:
    python_lines = _python_lines()
    java_lines = run_probe_text("ResourcesRecursiveFuzzProbe").splitlines()
    assert len(python_lines) == len(java_lines)
    mismatches: list[str] = []
    for python, java in zip(python_lines, java_lines, strict=True):
        case_id = python.split(" ", 2)[1]
        if _PINNED.get(case_id) == (python, java):
            continue
        if python != java:
            mismatches.append(f"{case_id}: java={java!r} python={python!r}")
    assert not mismatches, "\n".join(mismatches)
