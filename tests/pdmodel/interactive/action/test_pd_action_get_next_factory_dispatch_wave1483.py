"""Pin ``PDAction.get_next`` list-shape semantics and the
``PDActionFactory.create_action`` dispatch it relies on.

Wave 1483, agent J. Upstream ``PDAction.getNext()`` builds its list from
``PDActionFactory.createAction`` (NOT the lenient ``PDAction.create``):
``createAction`` returns ``null`` for an unrecognised — or absent — ``/S``
subtype, and ``getNext`` preserves the ``/Next`` array length. So:

  * a single ``/Next`` dict with an unknown subtype  -> ``[None]`` (length 1),
  * a single ``/Next`` dict with no ``/S``           -> ``[None]`` (length 1),
  * a single ``/Next`` dict with a known subtype     -> ``[wrapper]``,
  * a ``/Next`` array mixing known + unknown members -> the unknown slots are
    ``None`` and the list length equals the array length.

These literals are oracle-confirmed against Apache PDFBox 3.0.7 via
``oracle/probes/ActionNextChainProbe.java``; the value tests below pin them
without needing Java, and the trailing ``@requires_oracle`` test re-checks the
live differential when the jar + JDK are present.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_factory import PDActionFactory
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI

_S = COSName.get_pdf_name("S")
_NEXT = COSName.get_pdf_name("Next")


def _dict(subtype: str | None) -> COSDictionary:
    d = COSDictionary()
    if subtype is not None:
        d.set_name(_S, subtype)
    return d


# --------------------------------------------------------------------------- #
# PDActionFactory.create_action dispatch                                       #
# --------------------------------------------------------------------------- #
def test_factory_unknown_subtype_returns_none() -> None:
    assert PDActionFactory.create_action(_dict("TotallyMadeUp")) is None


def test_factory_missing_subtype_returns_none() -> None:
    assert PDActionFactory.create_action(_dict(None)) is None


def test_factory_none_dict_returns_none() -> None:
    assert PDActionFactory.create_action(None) is None


def test_factory_known_subtype_returns_typed_wrapper() -> None:
    action = PDActionFactory.create_action(_dict("URI"))
    assert isinstance(action, PDActionURI)


# --------------------------------------------------------------------------- #
# PDAction.get_next list shape                                                 #
# --------------------------------------------------------------------------- #
def test_get_next_single_unknown_subtype_is_one_none_element() -> None:
    parent = PDActionGoTo()
    parent.get_cos_object().set_item(_NEXT, _dict("TotallyMadeUp"))
    result = parent.get_next()
    assert result is not None
    assert len(result) == 1
    assert result[0] is None


def test_get_next_single_missing_subtype_is_one_none_element() -> None:
    parent = PDActionGoTo()
    parent.get_cos_object().set_item(_NEXT, _dict(None))
    result = parent.get_next()
    assert result is not None
    assert len(result) == 1
    assert result[0] is None


def test_get_next_single_known_subtype_is_one_wrapper() -> None:
    parent = PDActionGoTo()
    parent.get_cos_object().set_item(_NEXT, _dict("URI"))
    result = parent.get_next()
    assert result is not None
    assert len(result) == 1
    assert isinstance(result[0], PDActionURI)


def test_get_next_array_mixed_preserves_length_with_none_slots() -> None:
    parent = PDActionGoTo()
    arr = COSArray()
    arr.add(_dict("Named"))
    arr.add(_dict("TotallyMadeUp"))
    parent.get_cos_object().set_item(_NEXT, arr)
    result = parent.get_next()
    assert result is not None
    assert len(result) == 2
    assert isinstance(result[0], PDActionNamed)
    assert result[1] is None


def test_get_next_array_non_dict_member_is_none_slot() -> None:
    parent = PDActionGoTo()
    arr = COSArray()
    arr.add(_dict("Named"))
    arr.add(COSInteger.get(0))
    parent.get_cos_object().set_item(_NEXT, arr)
    result = parent.get_next()
    assert result is not None
    assert len(result) == 2
    assert isinstance(result[0], PDActionNamed)
    assert result[1] is None


def test_get_next_absent_returns_none() -> None:
    assert PDActionGoTo().get_next() is None


def test_get_next_non_dict_non_array_returns_none() -> None:
    parent = PDActionGoTo()
    parent.get_cos_object().set_item(_NEXT, COSInteger.get(7))
    assert parent.get_next() is None


# --------------------------------------------------------------------------- #
# Live differential against Apache PDFBox 3.0.7                                 #
# --------------------------------------------------------------------------- #
def test_oracle_next_chain_matches_pdfbox() -> None:
    import pytest

    from tests.oracle.harness import oracle_available, run_probe_text

    if not oracle_available():
        pytest.skip("live PDFBox oracle unavailable")

    expected = (
        "case=factory_unknown\tresult=null\n"
        "case=factory_no_s\tresult=null\n"
        "case=factory_null\tresult=null\n"
        "case=next_single_unknown\tsize=1;NULLELEM\n"
        "case=next_single_no_s\tsize=1;NULLELEM\n"
        "case=next_single_known\tsize=1;PDActionURI:URI\n"
        "case=next_array_mixed\tsize=2;PDActionNamed:Named;NULLELEM\n"
        "case=next_array_null_member\tsize=2;PDActionNamed:Named;NULLELEM\n"
        "case=next_absent\tresult=null\n"
    )
    assert run_probe_text("ActionNextChainProbe") == expected


def _py_next_descr(result: list[PDAction | None] | None) -> str:
    """pypdfbox analogue of the probe's per-list description."""
    if result is None:
        return "result=null"
    parts = [f"size={len(result)}"]
    for a in result:
        if a is None:
            parts.append("NULLELEM")
        else:
            parts.append(f"{type(a).__name__}:{a.get_sub_type()}")
    return ";".join(parts[:1]) + (";" + ";".join(parts[1:]) if len(parts) > 1 else "")


def test_python_next_chain_mirrors_oracle_descriptions() -> None:
    # The same descriptor strings the oracle emits, computed from pypdfbox.
    # PDActionUnknown's simple name differs from PDActionURI etc., so only the
    # NULLELEM / wrapper-class-name slots are compared structurally.
    parent_u = PDActionGoTo()
    parent_u.get_cos_object().set_item(_NEXT, _dict("TotallyMadeUp"))
    assert _py_next_descr(parent_u.get_next()) == "size=1;NULLELEM"

    parent_k = PDActionGoTo()
    parent_k.get_cos_object().set_item(_NEXT, _dict("URI"))
    assert _py_next_descr(parent_k.get_next()) == "size=1;PDActionURI:URI"

    parent_a = PDActionGoTo()
    arr = COSArray()
    arr.add(_dict("Named"))
    arr.add(_dict("TotallyMadeUp"))
    parent_a.get_cos_object().set_item(_NEXT, arr)
    assert _py_next_descr(parent_a.get_next()) == "size=2;PDActionNamed:Named;NULLELEM"
