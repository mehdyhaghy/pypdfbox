from __future__ import annotations

from typing import TYPE_CHECKING

from .ttf_table import TTFTable

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class MaximumProfileTable(TTFTable):
    """``maxp`` — required TrueType table. Mirrors upstream."""

    TAG: str = "maxp"

    def __init__(self) -> None:
        super().__init__()
        self._version: float = 0.0
        self._num_glyphs: int = 0
        self._max_points: int = 0
        self._max_contours: int = 0
        self._max_composite_points: int = 0
        self._max_composite_contours: int = 0
        self._max_zones: int = 0
        self._max_twilight_points: int = 0
        self._max_storage: int = 0
        self._max_function_defs: int = 0
        self._max_instruction_defs: int = 0
        self._max_stack_elements: int = 0
        self._max_size_of_instructions: int = 0
        self._max_component_elements: int = 0
        self._max_component_depth: int = 0

    def read(self, ttf: TrueTypeFont, data: TTFDataStream) -> None:
        self._version = data.read_32_fixed()
        self._num_glyphs = data.read_unsigned_short()
        if self._version >= 1.0:
            self._max_points = data.read_unsigned_short()
            self._max_contours = data.read_unsigned_short()
            self._max_composite_points = data.read_unsigned_short()
            self._max_composite_contours = data.read_unsigned_short()
            self._max_zones = data.read_unsigned_short()
            self._max_twilight_points = data.read_unsigned_short()
            self._max_storage = data.read_unsigned_short()
            self._max_function_defs = data.read_unsigned_short()
            self._max_instruction_defs = data.read_unsigned_short()
            self._max_stack_elements = data.read_unsigned_short()
            self._max_size_of_instructions = data.read_unsigned_short()
            self._max_component_elements = data.read_unsigned_short()
            self._max_component_depth = data.read_unsigned_short()
            if self._max_component_depth == 0:
                # PDFBOX-6105
                self._max_component_depth = 1
        self.initialized = True

    # ---- accessors ----
    def get_version(self) -> float:
        return self._version

    def set_version(self, value: float) -> None:
        self._version = value

    def get_num_glyphs(self) -> int:
        return self._num_glyphs

    def set_num_glyphs(self, value: int) -> None:
        self._num_glyphs = value

    def get_max_points(self) -> int:
        return self._max_points

    def set_max_points(self, value: int) -> None:
        self._max_points = value

    def get_max_contours(self) -> int:
        return self._max_contours

    def set_max_contours(self, value: int) -> None:
        self._max_contours = value

    def get_max_composite_points(self) -> int:
        return self._max_composite_points

    def set_max_composite_points(self, value: int) -> None:
        self._max_composite_points = value

    def get_max_composite_contours(self) -> int:
        return self._max_composite_contours

    def set_max_composite_contours(self, value: int) -> None:
        self._max_composite_contours = value

    def get_max_zones(self) -> int:
        return self._max_zones

    def set_max_zones(self, value: int) -> None:
        self._max_zones = value

    def get_max_twilight_points(self) -> int:
        return self._max_twilight_points

    def set_max_twilight_points(self, value: int) -> None:
        self._max_twilight_points = value

    def get_max_storage(self) -> int:
        return self._max_storage

    def set_max_storage(self, value: int) -> None:
        self._max_storage = value

    def get_max_function_defs(self) -> int:
        return self._max_function_defs

    def set_max_function_defs(self, value: int) -> None:
        self._max_function_defs = value

    def get_max_instruction_defs(self) -> int:
        return self._max_instruction_defs

    def set_max_instruction_defs(self, value: int) -> None:
        self._max_instruction_defs = value

    def get_max_stack_elements(self) -> int:
        return self._max_stack_elements

    def set_max_stack_elements(self, value: int) -> None:
        self._max_stack_elements = value

    def get_max_size_of_instructions(self) -> int:
        return self._max_size_of_instructions

    def set_max_size_of_instructions(self, value: int) -> None:
        self._max_size_of_instructions = value

    def get_max_component_elements(self) -> int:
        return self._max_component_elements

    def set_max_component_elements(self, value: int) -> None:
        self._max_component_elements = value

    def get_max_component_depth(self) -> int:
        return self._max_component_depth

    def set_max_component_depth(self, value: int) -> None:
        self._max_component_depth = value
