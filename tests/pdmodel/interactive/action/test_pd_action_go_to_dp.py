from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDAction, PDActionGoToDp

_S: COSName = COSName.get_pdf_name("S")
_DP: COSName = COSName.get_pdf_name("Dp")
_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]


def test_default_constructor_sets_subtype_and_type() -> None:
    """A default-constructed action carries ``/Type /Action`` and
    ``/S /GoToDp`` per PDF 2.0 §12.6.4.4."""
    action = PDActionGoToDp()
    cos = action.get_cos_object()

    assert cos.get_name(_TYPE) == "Action"
    assert cos.get_name(_S) == "GoToDp"
    assert action.get_sub_type() == "GoToDp"
    assert PDActionGoToDp.SUB_TYPE == "GoToDp"


def test_wrapping_existing_dictionary_preserves_entries() -> None:
    """Passing an existing dictionary in must NOT clobber its ``/S`` —
    matches the convention used by ``PDActionGoTo`` and friends."""
    raw = COSDictionary()
    raw.set_name(_S, "GoToDp")
    dp_target = COSDictionary()
    raw.set_item(_DP, dp_target)

    action = PDActionGoToDp(raw)
    assert action.get_cos_object() is raw
    assert action.get_sub_type() == "GoToDp"
    assert action.get_document_part() is dp_target


def test_get_set_document_part_round_trip() -> None:
    action = PDActionGoToDp()
    assert action.get_document_part() is None

    dp_dict = COSDictionary()
    action.set_document_part(dp_dict)
    assert action.get_document_part() is dp_dict
    # Verify the entry actually lives at the /Dp key.
    assert action.get_cos_object().get_dictionary_object(_DP) is dp_dict


def test_set_document_part_none_removes_entry() -> None:
    action = PDActionGoToDp()
    action.set_document_part(COSDictionary())
    assert action.get_document_part() is not None

    action.set_document_part(None)
    assert action.get_document_part() is None
    # Underlying dictionary no longer has the key.
    assert action.get_cos_object().get_dictionary_object(_DP) is None


def test_dp_alias_methods_match_document_part() -> None:
    """``get_dp`` / ``set_dp`` are raw key-name aliases."""
    action = PDActionGoToDp()
    dp_dict = COSDictionary()

    action.set_dp(dp_dict)
    assert action.get_dp() is dp_dict
    assert action.get_document_part() is dp_dict

    action.set_dp(None)
    assert action.get_dp() is None


def test_factory_dispatch_returns_typed_instance() -> None:
    """``PDAction.create`` must hand back a ``PDActionGoToDp`` for an
    ``S=GoToDp`` dictionary."""
    raw = COSDictionary()
    raw.set_name(_S, "GoToDp")

    result = PDAction.create(raw)
    assert isinstance(result, PDActionGoToDp)
    assert result.get_cos_object() is raw


# ---------- typed-accessor coverage ----------


def test_get_document_part_dictionary_returns_typed_dict() -> None:
    """When ``/Dp`` is a dictionary, the typed accessor returns it."""
    action = PDActionGoToDp()
    dp_dict = COSDictionary()
    action.set_document_part(dp_dict)
    assert action.get_document_part_dictionary() is dp_dict


def test_get_document_part_dictionary_returns_none_when_absent() -> None:
    action = PDActionGoToDp()
    assert action.get_document_part_dictionary() is None


def test_get_document_part_dictionary_returns_none_for_non_dict() -> None:
    """When ``/Dp`` is not a dictionary, the typed accessor returns ``None``
    even though the raw accessor surfaces the entry."""
    action = PDActionGoToDp()
    # Write a name into /Dp directly — not a dictionary.
    action.get_cos_object().set_name(_DP, "Bogus")
    assert action.get_document_part_dictionary() is None
    # Raw accessor still sees the entry.
    assert action.get_document_part() is not None
