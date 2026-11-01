from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .bf_char_entry import BFCharEntry
    from .bf_char_range import BFCharRange
    from .cid_range import CIDRange
    from .cmap import (
        CMap,
        CMapMappingError,
    )
    from .cmap_manager import CMapManager
    from .cmap_parser import CMapParser
    from .cmap_strings import CMapStrings
    from .codespace_range import CodespaceRange

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BFCharEntry": ".bf_char_entry",
        "BFCharRange": ".bf_char_range",
        "CIDRange": ".cid_range",
        "CMap": ".cmap",
        "CMapMappingError": ".cmap",
        "CMapManager": ".cmap_manager",
        "CMapParser": ".cmap_parser",
        "CMapStrings": ".cmap_strings",
        "CodespaceRange": ".codespace_range",
    },
)

__all__ = [
    "BFCharEntry",
    "BFCharRange",
    "CIDRange",
    "CMap",
    "CMapManager",
    "CMapMappingError",
    "CMapParser",
    "CMapStrings",
    "CodespaceRange",
]
