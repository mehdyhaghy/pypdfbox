from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSObject, COSString
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group_usage import (
    PDOptionalContentGroupUsage,
    PDUsageUser,
)

_USER = COSName.get_pdf_name("User")
_NAME = COSName.get_pdf_name("Name")


def test_wave314_user_name_array_resolves_indirect_text_strings() -> None:
    usage_dict = COSDictionary()
    user_dict = COSDictionary()
    names = COSArray()
    names.add(COSObject(1, resolved=COSString("Alice")))
    user_dict.set_item(_NAME, names)
    usage_dict.set_item(_USER, user_dict)

    user = PDOptionalContentGroupUsage(usage_dict).get_user()

    assert isinstance(user, PDUsageUser)
    assert user.name == "Alice"
