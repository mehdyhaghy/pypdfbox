from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_sound_stream import PDSoundStream

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDSoundStream": ".pd_sound_stream",
    },
)

__all__ = ["PDSoundStream"]
