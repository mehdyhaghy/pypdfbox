from __future__ import annotations

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.pd_abstract_content_stream import PDAbstractContentStream
from pypdfbox.pdmodel.pd_form_content_stream import PDFormContentStream
from pypdfbox.pdmodel.pd_resources import PDResources

_FLATE: COSName = COSName.FLATE_DECODE  # type: ignore[attr-defined]


@pytest.fixture
def doc() -> PDDocument:
    document = PDDocument()
    yield document
    document.close()


def _new_form(document: PDDocument) -> PDFormXObject:
    # The form's body stream uses the owning document's scratch file, so the
    # document must outlive the form (keeping it alive here avoids the
    # scratch file being closed by GC).
    return PDFormXObject(document)


# ------------------------------------------------------------------
# constructor / target wiring
# ------------------------------------------------------------------


def test_constructor_creates_resources_when_absent(doc: PDDocument) -> None:
    form = _new_form(doc)
    assert form.get_resources() is None
    cs = PDFormContentStream(form)
    res = cs.get_resources()
    assert isinstance(res, PDResources)
    # Created /Resources is pushed back onto the form.
    assert form.get_resources() is not None


def test_constructor_reuses_existing_form_resources(doc: PDDocument) -> None:
    form = _new_form(doc)
    seeded = PDResources()
    form.set_resources(seeded)
    cs = PDFormContentStream(form)
    # The writer binds against the form's existing /Resources COS dict.
    assert (
        cs.get_resources().get_cos_object() is seeded.get_cos_object()
    )


def test_target_stream_is_form_cos_stream(doc: PDDocument) -> None:
    form = _new_form(doc)
    cs = PDFormContentStream(form)
    assert cs._target_stream is form.get_cos_object()


def test_document_is_none(doc: PDDocument) -> None:
    form = _new_form(doc)
    cs = PDFormContentStream(form)
    # Upstream passes null document; our ctor stores None.
    assert cs._document is None
    assert cs._form is form


def test_fraction_digits_pinned_to_abstract_base(doc: PDDocument) -> None:
    form = _new_form(doc)
    cs = PDFormContentStream(form)
    assert (
        cs._max_fraction_digits
        == PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS
    )


# ------------------------------------------------------------------
# constructor type guard
# ------------------------------------------------------------------


def test_constructor_rejects_non_form() -> None:
    with pytest.raises(TypeError, match="requires a PDFormXObject"):
        PDFormContentStream(object())  # type: ignore[arg-type]


# ------------------------------------------------------------------
# operator buffering + close flush
# ------------------------------------------------------------------


def test_operators_flush_into_form_stream_on_close(doc: PDDocument) -> None:
    form = _new_form(doc)
    with PDFormContentStream(form) as cs:
        cs.move_to(10, 20)
        cs.line_to(30, 40)
        cs.stroke()
    assert form.get_cos_object().get_raw_data() == b"10 20 m\n30 40 l\nS\n"


def test_fraction_digits_limit_applies_to_operands(doc: PDDocument) -> None:
    form = _new_form(doc)
    with PDFormContentStream(form) as cs:
        cs.move_to(0.123456, 1.0)
    assert form.get_cos_object().get_raw_data() == b"0.1235 1 m\n"


def test_close_is_idempotent(doc: PDDocument) -> None:
    form = _new_form(doc)
    cs = PDFormContentStream(form)
    cs.move_to(1, 2)
    cs.close()
    first = form.get_cos_object().get_raw_data()
    cs.close()
    assert form.get_cos_object().get_raw_data() == first


def test_close_compresses_when_compress_flag_set(doc: PDDocument) -> None:
    form = _new_form(doc)
    cs = PDFormContentStream(form)
    cs._compress = True
    cs.move_to(1, 2)
    cs.stroke()
    cs.close()
    stream = form.get_cos_object()
    assert stream.get_item(COSName.FILTER) == _FLATE  # type: ignore[attr-defined]
    with stream.create_input_stream() as inp:
        assert inp.read() == b"1 2 m\nS\n"


def test_form_xobject_can_be_seeded_from_bare_cos_stream() -> None:
    # PDFormXObject(COSStream) path — no document owner. The writer still
    # wires target + resources correctly.
    form = PDFormXObject(COSStream())
    cs = PDFormContentStream(form)
    assert cs._target_stream is form.get_cos_object()
    with cs:
        cs.move_to(5, 6)
    assert form.get_cos_object().get_raw_data() == b"5 6 m\n"
