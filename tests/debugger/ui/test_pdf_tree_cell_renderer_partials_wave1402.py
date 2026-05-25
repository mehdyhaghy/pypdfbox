"""Wave 1402 — branch-coverage round-out for ``PDFTreeCellRenderer``.

Targets the residual partial branches in
``pypdfbox/debugger/ui/pdf_tree_cell_renderer.py``:

* 288->290, 292->294, 296->298 — ``contains_key`` True but
  ``get_cos_name`` returns ``None`` (e.g. /Type maps to a non-name).
* 300->302 — ``contains_key("PatternType")`` True but ``get_int``
  returns the sentinel -1.
* 304->306 — same for /ShadingType.
* 353->355 — ``_indirect_overlay`` sees a ``MapEntry`` whose ``item``
  is not a ``COSObject`` ⇒ falls through to the ``XrefEntry`` branch.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.debugger.ui.map_entry import MapEntry
from pypdfbox.debugger.ui.pdf_tree_cell_renderer import (
    _indirect_overlay,
    _to_tree_postfix,
)


def test_to_tree_postfix_type_key_with_non_name_value() -> None:
    """288->290 — /Type exists but isn't a COSName ⇒ ``get_cos_name``
    returns ``None`` and the inner formatter is skipped."""
    d = COSDictionary()
    d.set_item("Type", COSString("not a name"))
    result = _to_tree_postfix(d)
    assert "/T:" not in result


def test_to_tree_postfix_subtype_key_with_non_name_value() -> None:
    """292->294 — same skip for /Subtype."""
    d = COSDictionary()
    d.set_item("Subtype", COSString("not a name"))
    result = _to_tree_postfix(d)
    assert "/S:" not in result


def test_to_tree_postfix_s_key_with_non_name_value() -> None:
    """296->298 — same skip for /S (short alias)."""
    d = COSDictionary()
    d.set_item("S", COSString("not a name"))
    result = _to_tree_postfix(d)
    assert "/S:" not in result


def test_to_tree_postfix_pattern_type_negative_sentinel() -> None:
    """300->302 — ``PatternType`` resolves to -1 ⇒ skip formatter.

    ``COSDictionary.get_int`` returns the default when the entry's
    value isn't an integer; setting /PatternType to a non-int value
    drives that path.
    """
    d = COSDictionary()
    d.set_item("PatternType", COSString("not-an-int"))
    result = _to_tree_postfix(d)
    assert "/PatternType:" not in result


def test_to_tree_postfix_shading_type_negative_sentinel() -> None:
    """304->306 — same skip for /ShadingType."""
    d = COSDictionary()
    d.set_item("ShadingType", COSString("not-an-int"))
    result = _to_tree_postfix(d)
    assert "/ShadingType:" not in result


# Make sure the success path stays alive for regression sanity.


def test_to_tree_postfix_pattern_type_with_real_int() -> None:
    """Sanity — the True arm continues to fire when the int is real."""
    d = COSDictionary()
    d.set_item("PatternType", COSInteger.get(2))
    assert "/PatternType:2" in _to_tree_postfix(d)


def test_indirect_overlay_map_entry_with_non_cos_object_item() -> None:
    """353->355 — ``MapEntry.get_item`` returns something that's NOT a
    ``COSObject`` ⇒ skip the (True, ...) return and continue to the
    next isinstance check (which evaluates False here)."""
    me = MapEntry()
    me.set_key(COSName.get_pdf_name("K"))
    me.set_value(COSStream())  # a stream, but item is not COSObject below
    me.set_item(COSString("direct"))  # NOT a COSObject ⇒ no overlay
    indirect, stream = _indirect_overlay(me)
    assert indirect is False
    assert stream is False
