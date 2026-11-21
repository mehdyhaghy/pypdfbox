"""PDFBOX-6307 (3.0 branch, unreleased 3.0.9): ``PDVisibleSignDesigner`` can
take the signature position as the lower left corner in page user space."""

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_creator import (
    PDFTemplateCreator,
)


def _designer() -> PDVisibleSignDesigner:
    designer = (
        PDVisibleSignDesigner()
        .coordinates(10.0, 20.0)
        .width(100.0)
        .height(50.0)
        .page_width(595.0)
        .page_height(842.0)
    )
    designer.read_image_stream(b"\x89PNG\r\nFAKEBYTES")
    return designer


def test_default_is_false_and_setter_chains() -> None:
    designer = PDVisibleSignDesigner()
    assert designer.is_use_user_space_coordinates() is False
    assert designer.use_user_space_coordinates(True) is designer
    assert designer.is_use_user_space_coordinates() is True
    designer.use_user_space_coordinates(False)
    assert designer.is_use_user_space_coordinates() is False


def test_build_pdf_widget_rect_user_space() -> None:
    builder = PDVisibleSigBuilder()
    PDFTemplateCreator(builder).build_pdf(_designer().use_user_space_coordinates(True))
    structure = builder.get_structure()
    rect = structure.get_signature_rectangle()
    assert (
        rect.get_lower_left_x(),
        rect.get_lower_left_y(),
        rect.get_upper_right_x(),
        rect.get_upper_right_y(),
    ) == (10.0, 20.0, 110.0, 70.0)
    widget = structure.get_signature_field().get_widgets()[0]
    assert widget.get_rectangle().get_lower_left_y() == 20.0


def test_build_pdf_widget_rect_default_unchanged() -> None:
    builder = PDVisibleSigBuilder()
    PDFTemplateCreator(builder).build_pdf(_designer())
    rect = builder.get_structure().get_signature_rectangle()
    # y measured from the top of the template: 842 - 20 - 50 .. 842 - 20.
    assert (
        rect.get_lower_left_x(),
        rect.get_lower_left_y(),
        rect.get_upper_right_x(),
        rect.get_upper_right_y(),
    ) == (10.0, 772.0, 110.0, 822.0)
