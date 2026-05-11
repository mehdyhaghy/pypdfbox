"""Port of ``org.apache.pdfbox.examples.pdmodel.RubberStampWithImage`` (lines 46-185).

Adds a rubber-stamp annotation with an embedded image to every page.

Deviation from upstream
-----------------------
Upstream takes ``<image-filename>`` as a CLI argument and loads it via
``PDImageXObject.createFromFile``. The port keeps the same CLI shape, but
also accepts ``image_bytes`` programmatically — useful for the unit-test
path that drives :meth:`do_it_bytes` against a Pillow-generated PNG instead
of staging an on-disk fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pypdfbox.cos import COSDictionary
from pypdfbox.loader import Loader
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources


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
        image_bytes = Path(argv[2]).read_bytes()
        self._stamp_document(argv[0], argv[1], image_bytes, image_name=argv[2])

    def do_it_bytes(
        self,
        input_pdf: str,
        output_pdf: str,
        image_bytes: bytes,
    ) -> None:
        """Convenience entry point that takes the stamp image as raw bytes.

        Mirrors :meth:`do_it` but skips the file-system round-trip — useful
        for tests that generate a stamp image in memory.
        """
        self._stamp_document(input_pdf, output_pdf, image_bytes, image_name=None)

    def _stamp_document(
        self,
        input_pdf: str,
        output_pdf: str,
        image_bytes: bytes,
        image_name: str | None,
    ) -> None:
        with Loader.load_pdf(Path(input_pdf)) as cos_doc:
            document = PDDocument(cos_doc)
            if document.is_encrypted():
                raise OSError(
                    "Encrypted documents are not supported for this example"
                )

            for i in range(document.get_number_of_pages()):
                page = document.get_page(i)
                annotations = page.get_annotations()
                rubber_stamp = PDAnnotationRubberStamp()
                rubber_stamp.set_name(PDAnnotationRubberStamp.NAME_TOP_SECRET)
                rubber_stamp.set_rectangle(PDRectangle(0, 0, 200, 100))
                rubber_stamp.set_contents("A top secret note")

                ximage = PDImageXObject.create_from_byte_array(
                    document, image_bytes, image_name,
                )

                lower_left_x = 250.0
                lower_left_y = 550.0
                form_width = 150.0
                form_height = 25.0
                img_width = 50.0
                img_height = 25.0

                rect = PDRectangle()
                rect.set_lower_left_x(lower_left_x)
                rect.set_lower_left_y(lower_left_y)
                rect.set_upper_right_x(lower_left_x + form_width)
                rect.set_upper_right_y(lower_left_y + form_height)

                form = PDFormXObject(document)
                form.set_resources(PDResources())
                form.set_b_box(rect)
                form.set_form_type(1)

                with form.get_stream().create_output_stream() as os:
                    self.draw_x_object(
                        ximage,
                        form.get_resources(),
                        os,
                        lower_left_x,
                        lower_left_y,
                        img_width,
                        img_height,
                    )

                appearance_stream = PDAppearanceStream(form.get_cos_object())
                appearance = PDAppearanceDictionary(COSDictionary())
                appearance.set_normal_appearance(appearance_stream)
                rubber_stamp.set_appearance(appearance)
                rubber_stamp.set_rectangle(rect)

                annotations.append(rubber_stamp)
                # ``PDPage.get_annotations`` returns a freshly-built list rather
                # than a live ``/Annots`` view, so we must write it back. Upstream
                # ``getAnnotations`` exposes the mutable backing list directly.
                page.set_annotations(annotations)

            document.save(output_pdf)

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 172)."""
        argv = argv if argv is not None else []
        stamp = RubberStampWithImage()
        stamp.do_it(argv)

    def draw_x_object(
        self,
        xobject: PDImageXObject,
        resources: PDResources,
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
