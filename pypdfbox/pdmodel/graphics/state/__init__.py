from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_extended_graphics_state import PDExtendedGraphicsState
    from .pd_font_setting import PDFontSetting
    from .pd_graphics_state import PDGraphicsState
    from .pd_soft_mask import PDSoftMask
    from .pd_text_state import PDTextState
    from .rendering_intent import RenderingIntent
    from .rendering_mode import RenderingMode

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDExtendedGraphicsState": ".pd_extended_graphics_state",
        "PDFontSetting": ".pd_font_setting",
        "PDGraphicsState": ".pd_graphics_state",
        "PDSoftMask": ".pd_soft_mask",
        "PDTextState": ".pd_text_state",
        "RenderingIntent": ".rendering_intent",
        "RenderingMode": ".rendering_mode",
    },
)

__all__ = [
    "PDExtendedGraphicsState",
    "PDFontSetting",
    "PDGraphicsState",
    "PDSoftMask",
    "PDTextState",
    "RenderingIntent",
    "RenderingMode",
]
