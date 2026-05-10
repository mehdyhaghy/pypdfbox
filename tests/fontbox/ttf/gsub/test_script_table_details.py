"""Hand-written tests for :class:`ScriptTableDetails`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import ScriptTable, ScriptTableDetails
from pypdfbox.fontbox.ttf.model import Language


def test_accessors_return_constructor_values() -> None:
    table = ScriptTable()
    details = ScriptTableDetails(Language.LATIN, "latn", table)
    assert details.get_language() is Language.LATIN
    assert details.get_feature_name() == "latn"
    assert details.get_script_table() is table


def test_unspecified_language_for_explicit_script() -> None:
    details = ScriptTableDetails(Language.UNSPECIFIED, "deva", ScriptTable())
    assert details.get_language() is Language.UNSPECIFIED
    assert details.get_feature_name() == "deva"
