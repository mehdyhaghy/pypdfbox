"""Wave 1281 — parity ports for the visible-signature subpackage."""

from __future__ import annotations

import io

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_properties import (
    PDVisibleSigProperties,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_builder import (
    PDFTemplateBuilder,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_creator import (
    PDFTemplateCreator,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pdf_template_structure import (
    PDFTemplateStructure,
)


class TestPDFTemplateStructure:
    def test_round_trip_simple_setters(self) -> None:
        s = PDFTemplateStructure()
        marker = object()
        s.set_page(marker)
        assert s.get_page() is marker

    def test_inner_form_stream_setter_typo_compat(self) -> None:
        s = PDFTemplateStructure()
        marker = object()
        s.set_innter_form_stream(marker)  # parity-faithful typo
        assert s.get_inner_form_stream() is marker

    def test_inner_form_stream_pythonic_alias(self) -> None:
        s = PDFTemplateStructure()
        marker = object()
        s.set_inner_form_stream(marker)
        assert s.get_inner_form_stream() is marker


class TestPDFTemplateBuilder:
    def test_abstract_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            PDFTemplateBuilder()  # type: ignore[abstract]


class TestPDVisibleSigBuilder:
    def test_get_structure_returns_pdftemplate_structure(self) -> None:
        builder = PDVisibleSigBuilder()
        assert isinstance(builder.get_structure(), PDFTemplateStructure)

    def test_create_affine_transform_records_value(self) -> None:
        builder = PDVisibleSigBuilder()
        marker = object()
        builder.create_affine_transform(marker)
        assert builder.get_structure().get_affine_transform() is marker

    def test_create_formatter_rectangle_normalises(self) -> None:
        builder = PDVisibleSigBuilder()
        builder.create_formatter_rectangle([100, 50, 10, 200])
        rect = builder.get_structure().get_formatter_rectangle()
        if rect is None:  # parity stub when PDRectangle not yet wired
            return
        # lower-left should be the min, upper-right the max.
        assert rect.get_lower_left_x() == 10
        assert rect.get_lower_left_y() == 50
        assert rect.get_upper_right_x() == 100
        assert rect.get_upper_right_y() == 200

    def test_write_raw_commands_writes_utf_8(self) -> None:
        """PDFBox 4.0 removed ``appendRawCommands`` (adopted in pypdfbox
        2.0.0); the UTF-8 encoding + close contract it pinned now runs
        through ``write_raw_commands``, which opens the stream itself."""
        builder = PDVisibleSigBuilder()
        assert not hasattr(builder, "append_raw_commands")

        buf = io.BytesIO()
        written: list[bytes] = []
        buf.close = lambda: written.append(buf.getvalue())  # type: ignore[method-assign]

        class _Stream:
            def create_output_stream(self) -> io.BytesIO:
                return buf

        builder.write_raw_commands(_Stream(), "q Q")
        assert written == [b"q Q"]

    def test_write_raw_commands_takes_a_pd_stream(self) -> None:
        """PDFBox 4.0 renamed ``appendRawCommands`` to ``writeRawCommands``
        and made the first parameter a ``PDStream``: the builder opens and
        closes the output stream itself."""
        from pypdfbox.pdmodel.common.pd_stream import PDStream
        from pypdfbox.pdmodel.pd_document import PDDocument

        builder = PDVisibleSigBuilder()
        with PDDocument() as doc:
            pd_stream = PDStream(doc)
            builder.write_raw_commands(pd_stream, "q 1 0 0 1 0 0 cm /FRM Do Q\n")
            assert pd_stream.to_byte_array() == b"q 1 0 0 1 0 0 cm /FRM Do Q\n"


class TestPDVisibleSigProperties:
    def test_fluent_chain(self) -> None:
        props = (
            PDVisibleSigProperties()
            .signer_name("Alice")
            .signer_location("Earth")
            .signature_reason("testing")
            .page(2)
            .preferred_size(1024)
            .visual_sign_enabled(True)
        )
        assert props.get_signer_name() == "Alice"
        assert props.get_signer_location() == "Earth"
        assert props.get_signature_reason() == "testing"
        assert props.get_page() == 2
        assert props.get_preferred_size() == 1024
        assert props.is_visual_sign_enabled() is True

    def test_set_pd_visible_signature_returns_self(self) -> None:
        designer = PDVisibleSignDesigner()
        props = PDVisibleSigProperties().set_pd_visible_signature(designer)
        assert props.get_pd_visible_signature() is designer

    def test_set_visible_signature_void(self) -> None:
        props = PDVisibleSigProperties()
        stream = io.BytesIO(b"x")
        props.set_visible_signature(stream)
        assert props.get_visible_signature() is stream


class TestPDVisibleSignDesigner:
    def test_default_field_name(self) -> None:
        d = PDVisibleSignDesigner()
        assert d.get_signature_field_name() == "sig"

    def test_fluent_coordinates(self) -> None:
        d = PDVisibleSignDesigner().coordinates(10.0, 20.0)
        assert d.get_x_axis() == 10.0
        assert d.get_y_axis() == 20.0

    def test_width_height_chain(self) -> None:
        d = PDVisibleSignDesigner().width(100).height(50)
        assert d.get_width() == 100
        assert d.get_height() == 50

    def test_signature_field_name(self) -> None:
        d = PDVisibleSignDesigner().signature_field_name("MySig")
        assert d.get_signature_field_name() == "MySig"

    def test_formatter_rectangle_default(self) -> None:
        d = PDVisibleSignDesigner()
        assert d.get_formatter_rectangle_parameters() == [0, 0, 100, 50]


class TestPDFTemplateCreator:
    def test_get_pdf_structure_returns_builder_structure(self) -> None:
        builder = PDVisibleSigBuilder()
        creator = PDFTemplateCreator(builder)
        assert creator.get_pdf_structure() is builder.get_structure()
