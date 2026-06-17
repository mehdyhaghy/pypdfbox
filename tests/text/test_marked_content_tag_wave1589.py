"""Wave 1589 — inline BMC/BDC marked-content tag extraction parity.

Closes a wave-1588 DEFERRED divergence: the lite ``PDFTextStripper``'s
inline ``_dispatch`` for ``BMC`` previously took the tag from
``operands[0]``, whereas upstream PDFBox
``BeginMarkedContentSequence.process`` (and the registered pypdfbox
operator :class:`BeginMarkedContent`, via ``_props.extract_tag``)
iterate the whole operand list and keep the **last** ``COSName``. They
diverged for any ``BMC`` whose tag is not the first operand
(e.g. ``1 (x) /Artifact BMC``).

The distinction between the two operators is deliberate and preserved:

* ``BMC`` — tag is the *last* ``COSName`` (leading junk skipped).
* ``BDC`` — tag is ``operands[0]`` (the *first* operand): the property
  operand of the ``/Name`` form is itself a ``COSName`` and must not be
  mistaken for the tag.

These tests drive the stripper's inline ``_dispatch`` directly and
cross-check the tag it records on ``_marked_content_stack`` against the
tag the registered operator path (``extract_tag`` / ``operands[0]``)
would select.
"""
from __future__ import annotations

from pypdfbox.contentstream.operator.markedcontent._props import (
    extract_tag,
    resolve_property_dict,
)
from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.text.pdf_text_stripper import PDFTextStripper, _TextState


def _name(value: str) -> COSName:
    return COSName.get_pdf_name(value)


def _stripper() -> PDFTextStripper:
    return PDFTextStripper()


def _dispatch(stripper: PDFTextStripper, op: str, operands: list) -> None:
    stripper._dispatch(op, operands, _TextState(), [])


def _top_tag(stripper: PDFTextStripper) -> COSName | None:
    return stripper._marked_content_stack[-1][0]


def _top_props(stripper: PDFTextStripper) -> COSDictionary | None:
    return stripper._marked_content_stack[-1][1]


# ---- BMC: last COSName wins ------------------------------------------

def test_bmc_single_name_tag():
    s = _stripper()
    _dispatch(s, "BMC", [_name("Span")])
    assert _top_tag(s) == _name("Span")


def test_bmc_tag_is_last_name_after_junk():
    s = _stripper()
    ops = [COSInteger.get(1), COSString("x"), _name("Artifact")]
    _dispatch(s, "BMC", ops)
    assert _top_tag(s) == _name("Artifact")


def test_bmc_two_names_last_wins():
    s = _stripper()
    _dispatch(s, "BMC", [_name("A"), _name("B")])
    assert _top_tag(s) == _name("B")


def test_bmc_leading_integer_then_name():
    s = _stripper()
    _dispatch(s, "BMC", [COSInteger.get(42), _name("P")])
    assert _top_tag(s) == _name("P")


def test_bmc_no_name_yields_none():
    s = _stripper()
    _dispatch(s, "BMC", [COSInteger.get(1), COSString("nope")])
    assert _top_tag(s) is None


def test_bmc_empty_operands_yields_none():
    s = _stripper()
    _dispatch(s, "BMC", [])
    assert _top_tag(s) is None


def test_bmc_three_names_last_wins():
    s = _stripper()
    _dispatch(s, "BMC", [_name("A"), _name("B"), _name("C")])
    assert _top_tag(s) == _name("C")


def test_bmc_carries_no_properties():
    s = _stripper()
    _dispatch(s, "BMC", [_name("Span")])
    assert _top_props(s) is None


# ---- BMC inline path matches the registered-operator extract_tag -----

def test_bmc_inline_matches_extract_tag_junk_then_name():
    ops = [COSInteger.get(1), COSString("x"), _name("Artifact")]
    s = _stripper()
    _dispatch(s, "BMC", ops)
    assert _top_tag(s) == extract_tag(ops)


def test_bmc_inline_matches_extract_tag_two_names():
    ops = [_name("First"), _name("Second")]
    s = _stripper()
    _dispatch(s, "BMC", ops)
    assert _top_tag(s) == extract_tag(ops)


def test_bmc_inline_matches_extract_tag_no_name():
    ops = [COSInteger.get(7)]
    s = _stripper()
    _dispatch(s, "BMC", ops)
    assert _top_tag(s) == extract_tag(ops)


def test_bmc_inline_matches_extract_tag_single():
    ops = [_name("Span")]
    s = _stripper()
    _dispatch(s, "BMC", ops)
    assert _top_tag(s) == extract_tag(ops)


# ---- regression: the OLD inline behaviour (operands[0]) is wrong -----

def test_bmc_does_not_pick_first_operand_when_it_is_junk():
    # The pre-wave-1589 bug picked operands[0] (an integer => None tag);
    # the fix must pick the trailing /Real name instead.
    s = _stripper()
    ops = [COSInteger.get(1), _name("Real")]
    _dispatch(s, "BMC", ops)
    assert _top_tag(s) == _name("Real")
    assert _top_tag(s) is not None


# ---- BDC: tag is operands[0] -----------------------------------------

def test_bdc_tag_is_first_operand_with_inline_dict():
    s = _stripper()
    props = COSDictionary()
    props.set_string("ActualText", "hi")
    _dispatch(s, "BDC", [_name("Span"), props])
    assert _top_tag(s) == _name("Span")
    assert _top_props(s) is props


def test_bdc_tag_first_even_when_props_operand_is_name():
    # /Span /PL BDC — the second COSName is the property-list *name*, not
    # the tag. BDC must keep operands[0] (the FIRST name) as the tag even
    # though extract_tag (the BMC rule) would wrongly pick the PL name.
    s = _stripper()
    ops = [_name("Span"), _name("PL")]
    _dispatch(s, "BDC", ops)
    assert _top_tag(s) == _name("Span")
    # the BMC last-name rule would have picked the property-list name —
    # confirm BDC does NOT do that.
    assert _top_tag(s) != extract_tag(ops)
    assert extract_tag(ops) == _name("PL")


def test_bdc_does_not_use_last_name_as_tag():
    # Two distinct names: tag must be operands[0] (/Figure), never the
    # trailing /PropList that the BMC last-name rule would select.
    s = _stripper()
    ops = [_name("Figure"), _name("PropList")]
    _dispatch(s, "BDC", ops)
    assert _top_tag(s) == _name("Figure")
    assert _top_tag(s) != _name("PropList")


def test_bdc_tag_first_operand_matches_operands_zero():
    s = _stripper()
    props = COSDictionary()
    ops = [_name("Artifact"), props]
    _dispatch(s, "BDC", ops)
    assert _top_tag(s) == ops[0]


def test_bdc_actual_text_propagates():
    s = _stripper()
    props = COSDictionary()
    props.set_string("ActualText", "replacement")
    _dispatch(s, "BDC", [_name("Span"), props])
    assert s._actual_text == "replacement"


def test_bdc_first_operand_not_name_no_sequence():
    s = _stripper()
    before = len(s._marked_content_stack)
    props = COSDictionary()
    _dispatch(s, "BDC", [COSInteger.get(1), props])
    # operands[0] is not a COSName -> inline tag is None, but a properties
    # dict still resolves, so a sequence opens with a None tag.
    assert len(s._marked_content_stack) == before + 1
    assert _top_tag(s) is None


def test_bdc_inline_dict_resolves_via_resolve_property_dict():
    s = _stripper()
    props = COSDictionary()
    props.set_string("ActualText", "z")
    ops = [_name("Span"), props]
    _dispatch(s, "BDC", ops)
    # the recorded properties equal what resolve_property_dict returns
    assert _top_props(s) is resolve_property_dict(ops, None)


# ---- nested marked content + EMC -------------------------------------

def test_nested_bmc_then_bdc_then_emc():
    s = _stripper()
    _dispatch(s, "BMC", [COSInteger.get(0), _name("Outer")])
    props = COSDictionary()
    props.set_string("ActualText", "inner")
    _dispatch(s, "BDC", [_name("Inner"), props])
    assert len(s._marked_content_stack) == 2
    assert _top_tag(s) == _name("Inner")
    assert s._actual_text == "inner"
    # EMC pops the inner (which had /ActualText) -> actual_text cleared
    _dispatch(s, "EMC", [])
    assert len(s._marked_content_stack) == 1
    assert _top_tag(s) == _name("Outer")
    assert s._actual_text is None


def test_emc_on_empty_stack_is_noop():
    s = _stripper()
    _dispatch(s, "EMC", [])
    assert s._marked_content_stack == []


def test_nested_bmc_tags_each_use_last_name():
    s = _stripper()
    _dispatch(s, "BMC", [COSString("j"), _name("Sect")])
    _dispatch(s, "BMC", [COSInteger.get(9), _name("Span")])
    assert [t for (t, _p, _a) in s._marked_content_stack] == [
        _name("Sect"),
        _name("Span"),
    ]


def test_bmc_emc_balanced_clears_stack():
    s = _stripper()
    _dispatch(s, "BMC", [_name("A")])
    _dispatch(s, "BMC", [_name("B")])
    _dispatch(s, "EMC", [])
    _dispatch(s, "EMC", [])
    assert s._marked_content_stack == []


# ---- _last_cos_name helper unit behaviour ----------------------------

def test_last_cos_name_helper_matches_extract_tag():
    ops = [COSInteger.get(1), _name("A"), COSString("x"), _name("B")]
    assert PDFTextStripper._last_cos_name(ops) == extract_tag(ops)
    assert PDFTextStripper._last_cos_name(ops) == _name("B")


def test_last_cos_name_helper_none_when_no_name():
    assert PDFTextStripper._last_cos_name([COSInteger.get(1)]) is None
    assert PDFTextStripper._last_cos_name([]) is None


def test_last_cos_name_helper_single():
    assert PDFTextStripper._last_cos_name([_name("Solo")]) == _name("Solo")
