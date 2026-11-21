"""Port of upstream ``PDVisibleSignDesignerTest`` (PDFBOX-6307, 3.0 branch)."""

import io

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
)
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def _one_pixel_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buf, format="PNG")
    return buf.getvalue()


def test_use_user_space_coordinates() -> None:
    image = _one_pixel_png()
    with PDDocument() as doc:
        doc.add_page(PDPage(PDRectangle.A4))

        designer = PDVisibleSignDesigner(doc, image, 1)
        assert not designer.is_use_user_space_coordinates()

        designer.use_user_space_coordinates(True)
        assert designer.is_use_user_space_coordinates()

        designer.x_axis(100).y_axis(200).width(50).height(30)

        builder = PDVisibleSigBuilder()
        acro_form = PDAcroForm(doc)
        signature_field = PDSignatureField(acro_form)

        builder.create_signature_rectangle(signature_field, designer)
        rect = builder.get_structure().get_signature_rectangle()

        assert rect.get_lower_left_x() == pytest.approx(100.0, abs=0.01)
        assert rect.get_lower_left_y() == pytest.approx(200.0, abs=0.01)
        assert rect.get_upper_right_x() == pytest.approx(150.0, abs=0.01)
        assert rect.get_upper_right_y() == pytest.approx(230.0, abs=0.01)


def test_standard_coordinates() -> None:
    image = _one_pixel_png()
    with PDDocument() as doc:
        page = PDPage(PDRectangle.A4)
        doc.add_page(page)
        page_height = page.get_media_box().get_height()

        designer = PDVisibleSignDesigner(doc, image, 1)
        assert not designer.is_use_user_space_coordinates()

        designer.x_axis(100).y_axis(200).width(50).height(30)

        builder = PDVisibleSigBuilder()
        acro_form = PDAcroForm(doc)
        signature_field = PDSignatureField(acro_form)

        builder.create_signature_rectangle(signature_field, designer)
        rect = builder.get_structure().get_signature_rectangle()

        # Without custom coordinates, Y is transformed: pageHeight - yAxis
        assert rect.get_lower_left_x() == pytest.approx(100.0, abs=0.01)
        assert rect.get_lower_left_y() == pytest.approx(
            page_height - 200.0 - 30.0, abs=0.01
        )
        assert rect.get_upper_right_x() == pytest.approx(150.0, abs=0.01)
        assert rect.get_upper_right_y() == pytest.approx(page_height - 200.0, abs=0.01)
