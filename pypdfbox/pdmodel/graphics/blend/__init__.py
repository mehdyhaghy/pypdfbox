"""Blend mode subpackage.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.blend``.

The user-facing ``BlendMode`` enum lives one level up (in
``pypdfbox.pdmodel.graphics.blend_mode``) for historical reasons; this
package exposes the supporting composite + functional-interface types.
"""

from __future__ import annotations

from .blend_channel_function import BlendChannelFunction
from .blend_composite import BlendComposite, BlendCompositeContext
from .blend_function import BlendFunction

__all__ = [
    "BlendChannelFunction",
    "BlendComposite",
    "BlendCompositeContext",
    "BlendFunction",
]
