"""Protocol-style abstract base for image XObjects.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.PDImage`` — the
upstream Java interface that ``PDImageXObject`` and ``PDInlineImage``
both implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypdfbox.cos import COSArray, COSDictionary
    from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace


class PDImage(ABC):
    """Abstract image XObject contract."""

    @abstractmethod
    def get_image(self, region: Any | None = None, subsampling: int = 1) -> Any:
        """Return a fully-decoded image. ``region`` / ``subsampling`` match
        upstream's overload (region=None, subsampling=1 -> cached full image).
        """

    @abstractmethod
    def get_raw_raster(self) -> Any:
        """Return the raw pixel raster (no color conversion)."""

    @abstractmethod
    def get_raw_image(self) -> Any:
        """Return the raw image in the original color space, or ``None``."""

    @abstractmethod
    def get_stencil_image(self, paint: Any) -> Any:
        """Return an ARGB image filled with ``paint`` using this as a mask.

        Raises if the image isn't a stencil.
        """

    @abstractmethod
    def create_input_stream(
        self,
        stop_filters_or_options: Iterable[str] | Any | None = None,
    ) -> Any:
        """Return a decoded byte stream of the image data."""

    @abstractmethod
    def is_empty(self) -> bool:
        ...

    @abstractmethod
    def is_stencil(self) -> bool:
        ...

    @abstractmethod
    def set_stencil(self, is_stencil: bool) -> None:
        ...

    @abstractmethod
    def get_bits_per_component(self) -> int:
        ...

    @abstractmethod
    def set_bits_per_component(self, bits_per_component: int) -> None:
        ...

    @abstractmethod
    def get_color_space(self) -> PDColorSpace:
        ...

    @abstractmethod
    def set_color_space(self, color_space: PDColorSpace) -> None:
        ...

    @abstractmethod
    def get_height(self) -> int:
        ...

    @abstractmethod
    def set_height(self, height: int) -> None:
        ...

    @abstractmethod
    def get_width(self) -> int:
        ...

    @abstractmethod
    def set_width(self, width: int) -> None:
        ...

    @abstractmethod
    def set_decode(self, decode: COSArray) -> None:
        ...

    @abstractmethod
    def get_decode(self) -> COSArray:
        ...

    @abstractmethod
    def get_interpolate(self) -> bool:
        ...

    @abstractmethod
    def set_interpolate(self, value: bool) -> None:
        ...

    @abstractmethod
    def get_suffix(self) -> str:
        ...

    @abstractmethod
    def get_cos_object(self) -> COSDictionary:
        ...


__all__ = ["PDImage"]
