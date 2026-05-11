"""Port of ``org.apache.pdfbox.examples.pdmodel.AddAnnotations`` (lines 53-356).

Adds a variety of annotations to a 3-page PDF document: a text highlight,
two link annotations (external URI + internal GoTo destination), a
circle, a square, a line with an open-arrow ending, a free-text callout,
and a polygon. Adds the standard ``/Helv`` font to the AcroForm default
resources so free-text annotation appearance handlers can look it up.

Deviation from upstream:

* Upstream additionally loads and embeds the LiberationSans TTF as
  ``/LibSans`` so the free-text annotation can render Greek glyphs. That
  TTF lives in the upstream test resources we don't ship. We register
  ``/Helv`` and keep the free-text default appearance pointing at
  ``/Helv`` instead, so the example still produces a valid PDF with
  appearance streams. Documented inline.
"""

from __future__ import annotations

import contextlib
import sys

from pypdfbox.cos import COSName
from pypdfbox.examples.pdmodel._font_helpers import make_standard14_type1_font
from pypdfbox.pdmodel.font.standard14_fonts import FontName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.action.pd_action_uri import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
    PDAnnotationSquare,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_fit_width_destination import (  # noqa: E501
    PDPageFitWidthDestination,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_variable_text import PDVariableText
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

#: Mirrors upstream's ``INCH = 72`` package-private constant (line 55).
INCH: float = 72.0


class AddAnnotations:
    """Mirrors ``AddAnnotations`` (final, utility class)."""

    INCH: float = INCH

    def __init__(self) -> None:
        pass

    @staticmethod
    def main(argv: list[str] | None = None) -> None:
        """Entry point — mirrors ``main(String[] args)`` (line 61)."""
        argv = argv if argv is not None else []
        if len(argv) != 1:
            sys.stderr.write("Usage: AddAnnotations <output-pdf>\n")
            raise SystemExit(1)

        output_path = argv[0]

        with PDDocument() as document:
            page1 = PDPage()
            page2 = PDPage()
            page3 = PDPage()
            document.add_page(page1)
            document.add_page(page2)
            document.add_page(page3)

            annotations: list = []

            # Reusable colors — each PDColor is fresh because PDAnnotation
            # consumes a /C array per annotation.
            red = PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)
            blue = PDColor([0.0, 0.0, 1.0], PDDeviceRGB.INSTANCE)
            green = PDColor([0.0, 1.0, 0.0], PDDeviceRGB.INSTANCE)
            black = PDColor([0.0, 0.0, 0.0], PDDeviceRGB.INSTANCE)

            border_thick = PDBorderStyleDictionary()
            border_thick.set_width(INCH / 12.0)  # 12th inch

            border_thin = PDBorderStyleDictionary()
            border_thin.set_width(INCH / 72.0)  # 1 point

            border_uline = PDBorderStyleDictionary()
            border_uline.set_style(PDBorderStyleDictionary.STYLE_UNDERLINE)
            border_uline.set_width(INCH / 72.0)

            pw = page1.get_media_box().get_upper_right_x()
            ph = page1.get_media_box().get_upper_right_y()

            font = make_standard14_type1_font(FontName.HELVETICA_BOLD)
            with PDPageContentStream(document, page1) as contents:
                contents.begin_text()
                contents.set_font(font, 18)
                contents.new_line_at_offset(INCH, ph - INCH - 18)
                contents.show_text("PDFBox")
                contents.new_line_at_offset(0, -(INCH / 2.0))
                contents.show_text("External URL")
                contents.new_line_at_offset(0, -(INCH / 2.0))
                contents.show_text("Jump to page three")
                contents.end_text()

            # ----- Highlight annotation over "PDFBox" -----
            txt_highlight = PDAnnotationHighlight()
            txt_highlight.set_color(
                PDColor([0.0, 1.0, 1.0], PDDeviceRGB.INSTANCE),
            )
            # Remove the next line for PDF/A-2b (and set_printed(True) too).
            txt_highlight.set_constant_opacity(0.2)

            text_width = font.get_string_width("PDFBox") / 1000.0 * 18.0
            position = PDRectangle()
            position.set_lower_left_x(INCH)
            position.set_lower_left_y(ph - INCH - 18.0)
            position.set_upper_right_x(INCH + text_width)
            position.set_upper_right_y(ph - INCH)
            txt_highlight.set_rectangle(position)

            quads = [0.0] * 8
            quads[0] = position.get_lower_left_x()
            quads[1] = position.get_upper_right_y() - 2.0
            quads[2] = position.get_upper_right_x()
            quads[3] = quads[1]
            quads[4] = quads[0]
            quads[5] = position.get_lower_left_y() - 2.0
            quads[6] = quads[2]
            quads[7] = quads[5]
            txt_highlight.set_quad_points(quads)
            txt_highlight.set_contents("Highlighted since it's important")
            annotations.append(txt_highlight)

            # ----- Link annotation: external URL -----
            txt_link = PDAnnotationLink()
            txt_link.set_border_style(border_uline)
            text_width = font.get_string_width("External URL") / 1000.0 * 18.0
            position = PDRectangle()
            position.set_lower_left_x(INCH)
            position.set_lower_left_y(ph - 1.5 * INCH - 20.0)
            position.set_upper_right_x(INCH + text_width)
            position.set_upper_right_y(ph - 1.5 * INCH)
            txt_link.set_rectangle(position)
            action_uri = PDActionURI()
            action_uri.set_uri("http://pdfbox.apache.org")
            txt_link.set_action(action_uri)
            annotations.append(txt_link)

            # ----- Circle -----
            a_circle = PDAnnotationCircle()
            a_circle.set_contents("Circle Annotation")
            a_circle.set_interior_color(red.get_components())
            a_circle.set_color(blue)
            a_circle.set_border_style(border_thin)
            position = PDRectangle()
            position.set_lower_left_x(INCH)
            position.set_lower_left_y(ph - 3.0 * INCH - INCH)
            position.set_upper_right_x(2.0 * INCH)
            position.set_upper_right_y(ph - 3.0 * INCH)
            a_circle.set_rectangle(position)
            annotations.append(a_circle)

            # ----- Square -----
            a_square = PDAnnotationSquare()
            a_square.set_contents("Square Annotation")
            a_square.set_color(red)
            a_square.set_border_style(border_thick)
            position = PDRectangle()
            position.set_lower_left_x(pw - 2.0 * INCH)
            position.set_lower_left_y(ph - 3.5 * INCH - INCH)
            position.set_upper_right_x(pw - INCH)
            position.set_upper_right_y(ph - 3.5 * INCH)
            a_square.set_rectangle(position)
            annotations.append(a_square)

            # ----- Line: circle -> square, with an open-arrow end cap -----
            a_line = PDAnnotationLine()
            a_line.set_end_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
            a_line.set_contents("Circle->Square")
            a_line.set_caption(True)
            position = PDRectangle()
            position.set_lower_left_x(2.0 * INCH)
            position.set_lower_left_y(ph - 3.5 * INCH - INCH)
            position.set_upper_right_x(pw - INCH - INCH)
            position.set_upper_right_y(ph - 3.0 * INCH)
            a_line.set_rectangle(position)
            line_pos = [
                2.0 * INCH,
                ph - 3.5 * INCH,
                pw - 2.0 * INCH,
                ph - 4.0 * INCH,
            ]
            a_line.set_line(line_pos)
            a_line.set_border_style(border_thick)
            a_line.set_color(black)
            annotations.append(a_line)

            # ----- Link annotation: internal GoTo destination -----
            page_link = PDAnnotationLink()
            page_link.set_border_style(border_uline)
            text_width = (
                font.get_string_width("Jump to page three") / 1000.0 * 18.0
            )
            position = PDRectangle()
            position.set_lower_left_x(INCH)
            position.set_lower_left_y(ph - 2.0 * INCH - 20.0)
            position.set_upper_right_x(INCH + text_width)
            position.set_upper_right_y(ph - 2.0 * INCH)
            page_link.set_rectangle(position)
            action_goto = PDActionGoTo()
            dest = PDPageFitWidthDestination()
            dest.set_page(page3)
            action_goto.set_destination(dest)
            page_link.set_action(action_goto)
            annotations.append(page_link)

            # ----- Free-text callout annotation -----
            free_text = PDAnnotationFreeText()
            yellow = PDColor([1.0, 1.0, 0.0], PDDeviceRGB.INSTANCE)
            free_text.set_color(yellow)
            position = PDRectangle()
            position.set_lower_left_x(1.0 * INCH)
            position.set_lower_left_y(ph - 5.0 * INCH - 3.0 * INCH)
            position.set_upper_right_x(pw - INCH)
            position.set_upper_right_y(ph - 5.0 * INCH)
            free_text.set_rectangle(position)
            free_text.set_title_popup("Sophia Lorem")
            free_text.set_subject("Lorem ipsum")
            free_text.set_contents(
                "uppercase Δ, lowercase δ\n"
                "Lorem ipsum dolor sit amet, consetetur sadipscing elitr,"
                " sed diam nonumy eirmod tempor invidunt ut labore et dolore "
                "magna aliquyam erat, sed diam voluptua. At vero eos et "
                "accusam et justo duo dolores et ea rebum. Stet clita kasd "
                "gubergren, no sea takimata sanctus est Lorem ipsum dolor "
                "sit amet. Lorem ipsum dolor sit amet, consetetur sadipscing "
                "elitr, sed diam nonumy eirmod tempor invidunt ut labore et "
                "dolore magna aliquyam erat, sed diam voluptua. At vero eos "
                "et accusam et justo duo dolores et ea rebum. Stet clita "
                "kasd gubergren, no sea takimata sanctus est Lorem ipsum "
                "dolor sit amet.",
            )
            # Deviation from upstream: upstream points the default
            # appearance at ``/LibSans`` (LiberationSans embedded above).
            # We don't ship that TTF, so we point at ``/Helv`` instead.
            free_text.set_default_appearance("0 0 1 rg /Helv 20 Tf")
            free_text.set_q(PDVariableText.QUADDING_RIGHT)
            free_text.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
            free_text.set_callout(
                [
                    0.0,
                    ph - 9.0 * INCH,
                    3.0 * INCH,
                    ph - 9.0 * INCH,
                    4.0 * INCH,
                    ph - 8.0 * INCH,
                ],
            )
            free_text.set_line_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
            annotations.append(free_text)

            # ----- Polygon -----
            polygon = PDAnnotationPolygon()
            position = PDRectangle()
            position.set_lower_left_x(pw - INCH)
            position.set_lower_left_y(ph - INCH)
            position.set_upper_right_x(pw - 2.0 * INCH)
            position.set_upper_right_y(ph - 2.0 * INCH)
            polygon.set_rectangle(position)
            polygon.set_color(blue)
            polygon.set_interior_color(green.get_components())
            vertices = [
                pw - INCH,
                ph - 2.0 * INCH,
                pw - 1.5 * INCH,
                ph - INCH,
                pw - 2.0 * INCH,
                ph - 2.0 * INCH,
            ]
            polygon.set_vertices(vertices)
            polygon.set_border_style(border_thick)
            polygon.set_contents("Polygon annotation")
            annotations.append(polygon)

            # Commit annotations to page1.
            page1.set_annotations(annotations)

            # AcroForm + /Helv default resource so free-text appearance
            # handlers can resolve the Tf operand.
            catalog = document.get_document_catalog()
            acro_form = catalog.get_acro_form()
            if acro_form is None:
                acro_form = PDAcroForm(document)
                catalog.set_acro_form(acro_form)
            dr = acro_form.get_default_resources()
            if dr is None:
                dr = PDResources()
                acro_form.set_default_resources(dr)
            dr.put(
                COSName.get_pdf_name("Helv"),
                make_standard14_type1_font(FontName.HELVETICA),
            )
            # Deviation: upstream additionally loads LiberationSans here as
            # ``/LibSans``. We don't ship that TTF — see the module
            # docstring for the rationale.

            # Materialise normal-appearance streams so non-Adobe viewers
            # render the annotations consistently. Upstream's forEach
            # swallows exceptions silently; match that posture so a single
            # uncooperative handler doesn't kill the whole pass.
            for annotation in annotations:
                with contextlib.suppress(Exception):
                    annotation.construct_appearances(document)

            AddAnnotations.show_page_no(document, page1, "Page 1")
            AddAnnotations.show_page_no(document, page2, "Page 2")
            AddAnnotations.show_page_no(document, page3, "Page 3")

            document.save(output_path)

    @staticmethod
    def show_page_no(
        document: PDDocument, page: PDPage, page_text: str,
    ) -> None:
        """Mirrors ``showPageNo(PDDocument, PDPage, String)`` (line 337).

        Centres ``page_text`` at the top of the page via a prepended
        content stream so it always sits beneath any user content.
        """
        font_size = 10
        with PDPageContentStream(
            document,
            page,
            append_mode=AppendMode.PREPEND,
            compress=True,
        ) as contents:
            media_box = page.get_media_box()
            page_width = media_box.get_width()
            page_height = media_box.get_height()
            font = make_standard14_type1_font(FontName.HELVETICA)
            contents.set_font(font, font_size)
            text_width = font.get_string_width(page_text) / 1000.0 * font_size
            contents.begin_text()
            contents.new_line_at_offset(
                page_width / 2.0 - text_width / 2.0,
                page_height - INCH / 2.0,
            )
            contents.show_text(page_text)
            contents.end_text()
