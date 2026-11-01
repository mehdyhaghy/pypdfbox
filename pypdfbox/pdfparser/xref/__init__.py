from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .abstract_x_reference import AbstractXReference
    from .free_x_reference import FreeXReference
    from .normal_x_reference import NormalXReference
    from .object_stream_x_reference import ObjectStreamXReference
    from .x_reference_entry import XReferenceEntry
    from .x_reference_type import XReferenceType

__getattr__, __dir__ = _attach(
    __name__,
    {
        "AbstractXReference": ".abstract_x_reference",
        "FreeXReference": ".free_x_reference",
        "NormalXReference": ".normal_x_reference",
        "ObjectStreamXReference": ".object_stream_x_reference",
        "XReferenceEntry": ".x_reference_entry",
        "XReferenceType": ".x_reference_type",
    },
)

__all__ = [
    "AbstractXReference",
    "FreeXReference",
    "NormalXReference",
    "ObjectStreamXReference",
    "XReferenceEntry",
    "XReferenceType",
]
