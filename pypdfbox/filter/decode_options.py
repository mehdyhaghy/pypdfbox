"""DecodeOptions for filter decode requests.

Mirrors ``org.apache.pdfbox.filter.DecodeOptions``. Carries an optional
source region (rectangle) and subsampling factors that a filter may apply
when decoding an image stream. Filters set ``filter_subsampled`` once they
honor the options so the caller can skip software downscaling.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _Rectangle:
    """Simple rectangle stand-in for ``java.awt.Rectangle``.

    The Java upstream uses ``java.awt.Rectangle`` directly; in Python we
    use a small data class with the four ints PDFBox actually reads.
    """

    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0


# Public alias so callers can write ``DecodeOptions.Rectangle(...)``-style
# code without importing from a private module. Mirrors Java's
# ``java.awt.Rectangle``.
Rectangle = _Rectangle


class DecodeOptions:
    """Options that may be passed to a ``Filter`` to request special
    handling when decoding the stream.

    Filters may not honor some or all of the specified options, so callers
    should check ``filter_subsampled`` after decoding if further processing
    relies on the options being applied.
    """

    #: Sentinel set after class definition to the read-only default
    #: instance. Mirrors Java's ``DecodeOptions.DEFAULT``.
    DEFAULT: DecodeOptions

    def __init__(
        self,
        x_or_region: int | _Rectangle | None = None,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        self._source_region: _Rectangle | None = None
        self._subsampling_x: int = 1
        self._subsampling_y: int = 1
        self._subsampling_offset_x: int = 0
        self._subsampling_offset_y: int = 0
        self._filter_subsampled: bool = False

        # Java overloads mapped to one Python signature:
        #   ()                            -> empty
        #   (Rectangle)                   -> source region
        #   (int x, int y, int w, int h)  -> source region from coords
        #   (int subsampling)             -> uniform subsampling
        if x_or_region is None and y is None and width is None and height is None:
            return
        if isinstance(x_or_region, _Rectangle):
            self._source_region = x_or_region
            return
        if (
            isinstance(x_or_region, int)
            and isinstance(y, int)
            and isinstance(width, int)
            and isinstance(height, int)
        ):
            self._source_region = _Rectangle(x_or_region, y, width, height)
            return
        if isinstance(x_or_region, int) and y is None and width is None and height is None:
            self._subsampling_x = x_or_region
            self._subsampling_y = x_or_region
            return
        raise TypeError("invalid DecodeOptions constructor arguments")

    # ------------------------------------------------------------------
    # Getters / setters — snake_case mirrors of upstream camelCase API.
    # ------------------------------------------------------------------

    def get_source_region(self) -> _Rectangle | None:
        return self._source_region

    def set_source_region(self, source_region: _Rectangle | None) -> None:
        self._source_region = source_region

    def get_subsampling_x(self) -> int:
        return self._subsampling_x

    def set_subsampling_x(self, ss_x: int) -> None:
        self._subsampling_x = ss_x

    def get_subsampling_y(self) -> int:
        return self._subsampling_y

    def set_subsampling_y(self, ss_y: int) -> None:
        self._subsampling_y = ss_y

    def get_subsampling_offset_x(self) -> int:
        return self._subsampling_offset_x

    def set_subsampling_offset_x(self, ss_offset_x: int) -> None:
        self._subsampling_offset_x = ss_offset_x

    def get_subsampling_offset_y(self) -> int:
        return self._subsampling_offset_y

    def set_subsampling_offset_y(self, ss_offset_y: int) -> None:
        self._subsampling_offset_y = ss_offset_y

    def is_filter_subsampled(self) -> bool:
        return self._filter_subsampled

    def set_filter_subsampled(self, filter_subsampled: bool) -> None:
        # Package-private in Java; exposed publicly here because Python has
        # no equivalent visibility modifier.
        self._filter_subsampled = filter_subsampled
