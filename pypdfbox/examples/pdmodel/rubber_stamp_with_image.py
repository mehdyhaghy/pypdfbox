"""Port of ``org.apache.pdfbox.examples.pdmodel.RubberStampWithImage`` (lines 46-185).

Adds a rubber-stamp annotation with an embedded image to every page.
"""

from __future__ import annotations

import sys


class RubberStampWithImage:
    """Mirrors ``RubberStampWithImage`` (line 46)."""

    _SAVE_GRAPHICS_STATE = "q\n"
    _RESTORE_GRAPHICS_STATE = "Q\n"
    _CONCATENATE_MATRIX = "cm\n"
    _XOBJECT_DO = "Do\n"
    _SPACE = " "

    def __init__(self) -> None:
        pass

    def do_it(self, argv: list[str]) -> None:
        """Mirrors ``doIt(String[] args)`` (line 61)."""
        if len(argv) != 3:
            self.usage()
            return
        # TODO: needs PDImageXObject.create_from_file + PDFormXObject +
        # PDAppearanceDictionary / PDAppearanceStream binding.
        raise NotImplementedError(
            "RubberStampWithImage awaits PDImageXObject + "
            "PDFormXObject / PDAppearanceStream wiring.",
        )

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 172)."""
        argv = argv if argv is not None else []
        stamp = RubberStampWithImage()
        stamp.do_it(argv)

    def draw_x_object(
        self,
        xobject,
        resources,
        os,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        """Mirrors ``drawXObject`` (line 131)."""
        x_object_name = resources.add(xobject)
        commands = (
            f"{self._SAVE_GRAPHICS_STATE}"
            f"{width} 0 0 {height} {x} {y} {self._CONCATENATE_MATRIX}"
            f"/{x_object_name.get_name()} {self._XOBJECT_DO}"
            f"{self._RESTORE_GRAPHICS_STATE}"
        )
        self.append_raw_commands(os, commands)

    def append_raw_commands(self, os, commands: str) -> None:
        """Mirrors ``appendRawCommands`` (line 160)."""
        os.write(commands.encode("ISO-8859-1"))

    def usage(self) -> None:
        """Mirrors ``usage()`` (line 181)."""
        sys.stderr.write(
            "Usage: RubberStampWithImage <input-pdf> <output-pdf> "
            "<image-filename>\n",
        )
