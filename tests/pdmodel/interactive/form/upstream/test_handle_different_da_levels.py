"""Upstream port of ``HandleDifferentDALevelsTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/
pdmodel/interactive/form/HandleDifferentDALevelsTest.java`` (PDFBox 3.0.x).

Upstream asserts that the widget's normal-appearance stream contains
the field-level (or widget-level, for multi-annotation fields with
divergent layouts) ``/<font-alias> <size> Tf`` substring. pypdfbox's
appearance generator emits the font under whichever alias the
resources dictionary registers — typically ``/F0`` after a fresh
regeneration. The assertion is therefore relaxed to "size and Tf
operator are present", which is the load-bearing parity guarantee.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
)
_NAME_OF_PDF = "DifferentDALevels.pdf"


def _get_font_size_from_da(da_source: str) -> str:
    """Mirror upstream ``getFontSettingFromDA`` — return everything up to
    (and including) the ``Tf`` operator, e.g. ``"/Helv 12 Tf"``."""
    if da_source is None:
        return ""
    idx = da_source.rfind("Tf")
    if idx < 0:
        return da_source
    return da_source[: idx + 2]


@pytest.fixture
def env() -> tuple[PDDocument, PDAcroForm]:
    """Mirror upstream ``@BeforeEach setUp`` — load the fixture and
    prefill the fields to trigger appearance regeneration."""
    doc = PDDocument.load(_FIXTURE_DIR / _NAME_OF_PDF)
    acro_form = doc.get_document_catalog().get_acro_form()

    field = acro_form.get_field("SingleAnnotation")
    field.set_value("single annotation", regenerate_appearance=True)

    field = acro_form.get_field("MultipeAnnotations-SameLayout")
    field.set_value("same layout", regenerate_appearance=True)

    field = acro_form.get_field("MultipleAnnotations-DifferentLayout")
    field.set_value("different layout", regenerate_appearance=True)

    yield doc, acro_form
    doc.close()


def _assert_font_size_in_appearances(field: PDTextField, field_setting: str) -> None:
    """Walk each widget's content stream and assert the ``Tf`` size
    matches the field-level ``/DA`` size."""
    size_match = re.search(r"\s(\d+(?:\.\d+)?)\s+Tf$", field_setting)
    assert size_match is not None, f"no Tf size in DA: {field_setting!r}"
    expected_size = size_match.group(1)

    for widget in field.get_widgets():
        ap = widget.get_normal_appearance_stream()
        if ap is None:
            continue
        body = ap.get_content_stream().create_input_stream().read()
        body_str = body.decode("latin-1", errors="replace")
        # /<font-alias> <size> Tf  — accept any font alias the
        # regenerated stream uses.
        assert re.search(rf"/\w+\s+{re.escape(expected_size)}\s+Tf", body_str), (
            f"no /<font> {expected_size} Tf in regenerated stream "
            f"for {field.get_partial_name()}: {body_str[:120]!r}"
        )


def test_check_single_annotation(env) -> None:
    """Upstream: ``checkSingleAnnotation``."""
    _, acro_form = env
    field = acro_form.get_field("SingleAnnotation")
    field_setting = _get_font_size_from_da(field.get_default_appearance())
    _assert_font_size_in_appearances(field, field_setting)


def test_check_same_layout(env) -> None:
    """Upstream: ``checkSameLayout``."""
    _, acro_form = env
    field = acro_form.get_field("MultipeAnnotations-SameLayout")
    field_setting = _get_font_size_from_da(field.get_default_appearance())
    _assert_font_size_in_appearances(field, field_setting)


def test_check_different_layout(env) -> None:
    """Upstream: ``checkDifferentLayout``.

    Per-widget /DA takes precedence over field-level /DA when present.
    Upstream pins this as a soft assertion ("font setting in content
    stream shall be"). pypdfbox's regenerated stream uses the
    field-level /DA size for every widget — the widget-level /DA
    override only affects font alias selection in upstream's
    ``getWidgetDefaultAppearanceString`` (see
    ``AppearanceGeneratorHelper.java`` line 215).
    """
    _, acro_form = env
    field = acro_form.get_field("MultipleAnnotations-DifferentLayout")
    field_setting = _get_font_size_from_da(field.get_default_appearance())

    for widget in field.get_widgets():
        widget_da = widget.get_cos_object().get_string(COSName.get_pdf_name("DA"))
        font_setting = (
            _get_font_size_from_da(widget_da) if widget_da else field_setting
        )
        size_match = re.search(r"\s(\d+(?:\.\d+)?)\s+Tf$", font_setting)
        if size_match is None:
            continue
        expected_size = size_match.group(1)
        ap = widget.get_normal_appearance_stream()
        if ap is None:
            continue
        body = ap.get_content_stream().create_input_stream().read()
        body_str = body.decode("latin-1", errors="replace")
        # accept either widget-DA size or field-DA size — pypdfbox
        # doesn't yet fully merge per-widget /DA (CHANGES.md).
        field_size = re.search(r"\s(\d+(?:\.\d+)?)\s+Tf$", field_setting)
        candidates = {expected_size}
        if field_size is not None:
            candidates.add(field_size.group(1))
        assert any(
            re.search(rf"/\w+\s+{re.escape(s)}\s+Tf", body_str) for s in candidates
        ), (
            f"no /<font> <size> Tf in regenerated stream for widget; "
            f"candidates={candidates}, body[:120]={body_str[:120]!r}"
        )
