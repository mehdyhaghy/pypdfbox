"""Wave 1403 branch round-out for ``PDFunctionType3.get_functions``.

The originally-assigned arc was 49->44 (``if sub is not None`` False arm).
That arm is in fact unreachable: ``PDFunction.create`` only returns None
for a None / unresolved-COSObject argument, while ``get_functions`` only
calls it for entries that already passed the ``isinstance(entry,
(COSDictionary, COSStream))`` check — those always yield a function or
raise. The production line is therefore annotated ``# pragma: no branch``.

These tests exercise the surrounding reachable behaviour: the earlier
``continue`` (46->44) for non-dict entries and the normal append path.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.common.function.pd_function_type3 import PDFunctionType3


def test_get_functions_skips_non_dictionary_entry() -> None:
    """A non-dictionary, non-stream entry hits the ``continue`` at 46->44
    and is dropped from the materialised list."""
    stitch = COSDictionary()
    stitch.set_int(COSName.get_pdf_name("FunctionType"), 3)
    functions = COSArray()
    functions.add(COSInteger.get(7))  # not a dict/stream -> skipped
    stitch.set_item(COSName.get_pdf_name("Functions"), functions)

    fn = PDFunctionType3(stitch)
    assert fn.get_functions() == []


def test_get_functions_appends_valid_subfunction() -> None:
    """A valid Type 2 subfunction dictionary is wrapped and appended
    (covers the True arm at 49->50)."""
    stitch = COSDictionary()
    stitch.set_int(COSName.get_pdf_name("FunctionType"), 3)

    sub = COSDictionary()
    sub.set_int(COSName.get_pdf_name("FunctionType"), 2)
    sub.set_item(COSName.get_pdf_name("Domain"), COSArray([COSInteger.get(0), COSInteger.get(1)]))
    sub.set_item(COSName.get_pdf_name("C0"), COSArray([COSInteger.get(0)]))
    sub.set_item(COSName.get_pdf_name("C1"), COSArray([COSInteger.get(1)]))
    sub.set_int(COSName.get_pdf_name("N"), 1)

    functions = COSArray()
    functions.add(sub)
    stitch.set_item(COSName.get_pdf_name("Functions"), functions)

    fn = PDFunctionType3(stitch)
    result = fn.get_functions()
    assert len(result) == 1
    assert result[0].get_function_type() == 2
