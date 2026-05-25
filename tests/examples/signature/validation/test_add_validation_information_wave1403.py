"""Wave 1403 branch round-out for ``add_validation_information``.

Closes ``70->72``: when the freshly-constructed entry lacks a
``set_needs_to_be_updated`` method, the ``if hasattr(...)`` guard takes its
False arc and the entry is stored without being marked for update.
"""

from __future__ import annotations

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.signature.validation.add_validation_information import (
    AddValidationInformation,
)


class _NoUpdateFlag:
    """A stand-in entry class without ``set_needs_to_be_updated`` — a valid
    ``clazz`` argument for the generic helper."""


def test_get_or_create_dictionary_entry_without_update_flag() -> None:
    parent = COSDictionary()
    entry = AddValidationInformation.get_or_create_dictionary_entry(
        _NoUpdateFlag, parent, "Custom",
    )
    assert isinstance(entry, _NoUpdateFlag)
    # The entry was stored under the key despite lacking the update flag.
    assert parent.get_dictionary_object(COSName.get_pdf_name("Custom")) is entry
