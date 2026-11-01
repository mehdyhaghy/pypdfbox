from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_optional_content_configuration import PDOptionalContentConfiguration
    from .pd_optional_content_group import (
        PDOptionalContentGroup,
        RenderState,
    )
    from .pd_optional_content_group_usage import (
        PDOptionalContentGroupUsage,
        PDUsageCreatorInfo,
        PDUsageExport,
        PDUsageLanguage,
        PDUsagePageElement,
        PDUsagePrint,
        PDUsageUser,
        PDUsageView,
        PDUsageZoom,
    )
    from .pd_optional_content_membership_dictionary import (
        MembershipDictionaryVisibilityPolicy,
        PDOptionalContentMembershipDictionary,
    )
    from .pd_optional_content_properties import (
        BaseState,
        PDOptionalContentProperties,
    )

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDOptionalContentConfiguration": ".pd_optional_content_configuration",
        "PDOptionalContentGroup": ".pd_optional_content_group",
        "RenderState": ".pd_optional_content_group",
        "PDOptionalContentGroupUsage": ".pd_optional_content_group_usage",
        "PDUsageCreatorInfo": ".pd_optional_content_group_usage",
        "PDUsageExport": ".pd_optional_content_group_usage",
        "PDUsageLanguage": ".pd_optional_content_group_usage",
        "PDUsagePageElement": ".pd_optional_content_group_usage",
        "PDUsagePrint": ".pd_optional_content_group_usage",
        "PDUsageUser": ".pd_optional_content_group_usage",
        "PDUsageView": ".pd_optional_content_group_usage",
        "PDUsageZoom": ".pd_optional_content_group_usage",
        "MembershipDictionaryVisibilityPolicy": ".pd_optional_content_membership_dictionary",
        "PDOptionalContentMembershipDictionary": ".pd_optional_content_membership_dictionary",
        "BaseState": ".pd_optional_content_properties",
        "PDOptionalContentProperties": ".pd_optional_content_properties",
    },
)

__all__ = [
    "BaseState",
    "MembershipDictionaryVisibilityPolicy",
    "PDOptionalContentConfiguration",
    "PDOptionalContentGroup",
    "PDOptionalContentGroupUsage",
    "PDOptionalContentMembershipDictionary",
    "PDOptionalContentProperties",
    "PDUsageCreatorInfo",
    "PDUsageExport",
    "PDUsageLanguage",
    "PDUsagePageElement",
    "PDUsagePrint",
    "PDUsageUser",
    "PDUsageView",
    "PDUsageZoom",
    "RenderState",
]
