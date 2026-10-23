"""Wrapping an existing action dictionary must not modify it.

Upstream ``PDAction(COSDictionary)`` only stores the dictionary; ``/Type
/Action`` is written by the no-argument constructor alone. Reading a link's
action (``PDAnnotationLink.get_action``, ``PDActionFactory.create_action``)
therefore leaves shared dictionaries, e.g. those of a source document whose
pages were imported shallowly, untouched.
"""

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_factory import PDActionFactory
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)

_TYPE = COSName.get_pdf_name("Type")
_S = COSName.get_pdf_name("S")


@pytest.mark.parametrize("sub_type", ["URI", "GoTo", "Named", "JavaScript", "Launch"])
def test_factory_wrap_does_not_add_type(sub_type: str) -> None:
    raw = COSDictionary()
    raw.set_name(_S, sub_type)
    action = PDActionFactory.create_action(raw)
    assert action is not None
    assert action.get_cos_object() is raw
    assert list(raw.key_set()) == [_S]
    assert action.get_type() is None


def test_link_get_action_leaves_action_dictionary_unchanged() -> None:
    raw = COSDictionary()
    raw.set_name(_S, "URI")
    link = PDAnnotationLink()
    link.get_cos_object().set_item(COSName.get_pdf_name("A"), raw)
    assert isinstance(link.get_action(), PDActionURI)
    assert not raw.contains_key(_TYPE)


def test_new_actions_still_carry_type_and_subtype() -> None:
    for action, sub_type in ((PDActionURI(), "URI"), (PDActionGoTo(), "GoTo")):
        cos = action.get_cos_object()
        assert cos.get_name(_TYPE) == "Action"
        assert cos.get_name(_S) == sub_type
