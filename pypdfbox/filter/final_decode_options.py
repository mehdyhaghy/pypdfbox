"""FinalDecodeOptions — read-only ``DecodeOptions`` for the global default.

Mirrors Java's private static inner class
``DecodeOptions.FinalDecodeOptions``. Setters raise to make
``DecodeOptions.DEFAULT`` effectively immutable; ``set_filter_subsampled``
is silently ignored to match upstream behaviour.
"""

from __future__ import annotations

from .decode_options import DecodeOptions, _Rectangle


class FinalDecodeOptions(DecodeOptions):
    """Immutable ``DecodeOptions`` used as the global default sentinel."""

    def __init__(self, filter_subsampled: bool) -> None:
        super().__init__()
        # Use the parent's setter exactly once — afterward the overridden
        # ``set_filter_subsampled`` silently swallows further changes.
        super().set_filter_subsampled(filter_subsampled)

    def set_source_region(self, source_region: _Rectangle | None) -> None:
        raise NotImplementedError("This instance may not be modified.")

    def set_subsampling_x(self, ss_x: int) -> None:
        raise NotImplementedError("This instance may not be modified.")

    def set_subsampling_y(self, ss_y: int) -> None:
        raise NotImplementedError("This instance may not be modified.")

    def set_subsampling_offset_x(self, ss_offset_x: int) -> None:
        raise NotImplementedError("This instance may not be modified.")

    def set_subsampling_offset_y(self, ss_offset_y: int) -> None:
        raise NotImplementedError("This instance may not be modified.")

    def set_filter_subsampled(self, filter_subsampled: bool) -> None:
        # Silently ignore. Matches upstream's package-private override.
        return


# Wire up the module-level default sentinel, mirroring Java's
# ``DecodeOptions.DEFAULT = new FinalDecodeOptions(true);``.
DecodeOptions.DEFAULT = FinalDecodeOptions(True)
