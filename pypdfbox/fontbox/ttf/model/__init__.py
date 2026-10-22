from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .language import Language
    from .map_backed_gsub_data import MapBackedGsubData
    from .map_backed_script_feature import MapBackedScriptFeature
    from .script_feature import ScriptFeature

__getattr__, __dir__ = _attach(
    __name__,
    {
        "Language": ".language",
        "MapBackedGsubData": ".map_backed_gsub_data",
        "MapBackedScriptFeature": ".map_backed_script_feature",
        "ScriptFeature": ".script_feature",
    },
)

__all__ = [
    "Language",
    "MapBackedGsubData",
    "MapBackedScriptFeature",
    "ScriptFeature",
]
