"""Annotation /F flag decoder.

Ported from ``org.apache.pdfbox.debugger.flagbitspane.AnnotFlag``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.debugger.flagbitspane.flag import Flag
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation

_F: COSName = COSName.get_pdf_name("F")


class AnnotFlag(Flag):
    """Decode the ``/F`` entry of an annotation dictionary."""

    def __init__(self, annot_dictionary: COSDictionary) -> None:
        """Store *annot_dictionary* for later decoding."""
        self._annot_dictionary = annot_dictionary

    # ---- Flag surface ------------------------------------------------------

    def get_flag_type(self) -> str:
        return "Annot flag"

    def get_flag_value(self) -> str:
        return "Flag value: " + str(self._annot_dictionary.get_int(_F))

    def get_flag_bits(self) -> list[list[Any]]:
        annotation = PDAnnotation(self._annot_dictionary)
        return [
            [1, "Invisible", annotation.is_invisible()],
            [2, "Hidden", annotation.is_hidden()],
            [3, "Print", annotation.is_printed()],
            [4, "NoZoom", annotation.is_no_zoom()],
            [5, "NoRotate", annotation.is_no_rotate()],
            [6, "NoView", annotation.is_no_view()],
            [7, "ReadOnly", annotation.is_read_only()],
            [8, "Locked", annotation.is_locked()],
            [9, "ToggleNoView", annotation.is_toggle_no_view()],
            [10, "LockedContents", annotation.is_locked_contents()],
        ]
