"""Blend mode subpackage.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.blend``.

The user-facing ``BlendMode`` enum lives one level up (in
``pypdfbox.pdmodel.graphics.blend_mode``) for historical reasons; this
package exposes the supporting composite + functional-interface types.
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .blend_channel_function import BlendChannelFunction
    from .blend_composite import (
        BlendComposite,
        BlendCompositeContext,
    )
    from .blend_function import BlendFunction

__getattr__, __dir__ = _attach(
    __name__,
    {
        "BlendChannelFunction": ".blend_channel_function",
        "BlendComposite": ".blend_composite",
        "BlendCompositeContext": ".blend_composite",
        "BlendFunction": ".blend_function",
    },
)

__all__ = [
    "BlendChannelFunction",
    "BlendComposite",
    "BlendCompositeContext",
    "BlendFunction",
]
