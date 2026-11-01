from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from ._props import (
        ARTIFACT_TAG,
        MCID_DEFAULT,
        MCID_KEY,
        extract_tag,
        get_mcid,
        has_mcid,
        is_artifact_tag,
        resolve_property_dict,
    )
    from .begin_marked_content import BeginMarkedContent
    from .begin_marked_content_sequence import BeginMarkedContentSequence
    from .begin_marked_content_sequence_with_properties import (
        BeginMarkedContentSequenceWithProperties,
    )
    from .begin_marked_content_with_props import BeginMarkedContentWithProps
    from .define_marked_content_point import DefineMarkedContentPoint
    from .define_marked_content_point_with_props import DefineMarkedContentPointWithProps
    from .end_marked_content import EndMarkedContent
    from .end_marked_content_sequence import EndMarkedContentSequence
    from .marked_content_point import MarkedContentPoint
    from .marked_content_point_with_properties import MarkedContentPointWithProperties

__getattr__, __dir__ = _attach(
    __name__,
    {
        "ARTIFACT_TAG": "._props",
        "MCID_DEFAULT": "._props",
        "MCID_KEY": "._props",
        "extract_tag": "._props",
        "get_mcid": "._props",
        "has_mcid": "._props",
        "is_artifact_tag": "._props",
        "resolve_property_dict": "._props",
        "BeginMarkedContent": ".begin_marked_content",
        "BeginMarkedContentSequence": ".begin_marked_content_sequence",
        "BeginMarkedContentSequenceWithProperties": (
            ".begin_marked_content_sequence_with_properties"
        ),
        "BeginMarkedContentWithProps": ".begin_marked_content_with_props",
        "DefineMarkedContentPoint": ".define_marked_content_point",
        "DefineMarkedContentPointWithProps": ".define_marked_content_point_with_props",
        "EndMarkedContent": ".end_marked_content",
        "EndMarkedContentSequence": ".end_marked_content_sequence",
        "MarkedContentPoint": ".marked_content_point",
        "MarkedContentPointWithProperties": ".marked_content_point_with_properties",
    },
)

__all__ = [
    "ARTIFACT_TAG",
    "MCID_DEFAULT",
    "MCID_KEY",
    "BeginMarkedContent",
    "BeginMarkedContentSequence",
    "BeginMarkedContentSequenceWithProperties",
    "BeginMarkedContentWithProps",
    "DefineMarkedContentPoint",
    "DefineMarkedContentPointWithProps",
    "EndMarkedContent",
    "EndMarkedContentSequence",
    "MarkedContentPoint",
    "MarkedContentPointWithProperties",
    "extract_tag",
    "get_mcid",
    "has_mcid",
    "is_artifact_tag",
    "resolve_property_dict",
]
