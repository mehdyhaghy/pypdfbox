from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_measure_dictionary import PDMeasureDictionary
    from .pd_media_clip import PDMediaClip
    from .pd_media_clip_data import PDMediaClipData
    from .pd_media_clip_section import PDMediaClipSection
    from .pd_media_play_parameters import PDMediaPlayParameters
    from .pd_media_rendition import PDMediaRendition
    from .pd_number_format_dictionary import PDNumberFormatDictionary
    from .pd_rectlinear_measure_dictionary import PDRectlinearMeasureDictionary
    from .pd_rendition import PDRendition
    from .pd_selector_rendition import PDSelectorRendition
    from .pd_viewport_dictionary import PDViewportDictionary

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDMeasureDictionary": ".pd_measure_dictionary",
        "PDMediaClip": ".pd_media_clip",
        "PDMediaClipData": ".pd_media_clip_data",
        "PDMediaClipSection": ".pd_media_clip_section",
        "PDMediaPlayParameters": ".pd_media_play_parameters",
        "PDMediaRendition": ".pd_media_rendition",
        "PDNumberFormatDictionary": ".pd_number_format_dictionary",
        "PDRectlinearMeasureDictionary": ".pd_rectlinear_measure_dictionary",
        "PDRendition": ".pd_rendition",
        "PDSelectorRendition": ".pd_selector_rendition",
        "PDViewportDictionary": ".pd_viewport_dictionary",
    },
)

__all__ = [
    "PDMeasureDictionary",
    "PDMediaClip",
    "PDMediaClipData",
    "PDMediaClipSection",
    "PDMediaPlayParameters",
    "PDMediaRendition",
    "PDNumberFormatDictionary",
    "PDRectlinearMeasureDictionary",
    "PDRendition",
    "PDSelectorRendition",
    "PDViewportDictionary",
]
