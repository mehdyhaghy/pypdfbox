"""Wave 1341 coverage-boost tests for :class:`PDTerminalField`.

Targets the residual ``_apply_fdf_value`` dispatch arms and the
:class:`PDFieldStub` set_value type-discriminator:

* COSStream ``/V`` (lines 221-223) — ``to_text_string`` is the only
  decoder upstream supports for stream-typed FDF values.
* COSArray ``/V`` routed to a :class:`PDChoice` (lines 224-229) —
  the typed multi-select set_value call.
* COSArray ``/V`` *not* routed to a PDChoice (lines 232-234) —
  upstream's IOException branch is downgraded to a raw COS write here.
* Unknown ``/V`` type (line 237) — raises ``OSError`` to mirror
  upstream's ``IOException``.
* :class:`PDFieldStub` ``set_value(None)`` (lines 286-288), ``set_value``
  with a :class:`COSBase` (lines 289-291), and the TypeError fallback
  for an unsupported argument type (lines 295-297).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.fdf.fdf_field import FDFField
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDFieldStub

_V = COSName.get_pdf_name("V")
_FT = COSName.get_pdf_name("FT")


def _make_stub() -> PDFieldStub:
    return PDFieldStub(PDAcroForm())


def _fdf_field_with_value(value: object) -> FDFField:
    """Build an :class:`FDFField` carrying ``/V = value`` directly (no
    type-coercion through the public setters)."""
    f = FDFField()
    f.get_cos_object().set_item(_V, value)
    return f


# ---------- _apply_fdf_value dispatch arms ----------


def test_import_fdf_value_cos_stream() -> None:
    """A COSStream ``/V`` decodes via :meth:`COSStream.to_text_string`
    (line 221-223)."""
    stub = _make_stub()
    stream = COSStream()
    with stream.create_raw_output_stream() as out:
        # PDFDocEncoding-safe ASCII so to_text_string round-trips.
        out.write(b"hello-from-stream")
    fdf_field = _fdf_field_with_value(stream)
    stub.import_fdf(fdf_field)
    assert stub.get_cos_object().get_string(_V) == "hello-from-stream"


def test_import_fdf_value_cos_array_to_pd_choice() -> None:
    """An array ``/V`` routed to a PDChoice subclass — set_value gets a
    ``list[str]`` (lines 224-229)."""
    arr = COSArray()
    arr.add(COSString("a"))
    arr.add(COSString("b"))
    fdf_field = _fdf_field_with_value(arr)

    form = PDAcroForm()
    choice_dict = COSDictionary()
    # Mark as a choice field so PDChoice mode dispatches correctly.
    choice_dict.set_item(_FT, COSName.get_pdf_name("Ch"))
    # /Ff with the multi-select bit set so set_value treats a list as
    # a multi-selection rather than an error.
    choice_dict.set_int("Ff", 1 << 21)  # MultiSelect flag
    choice = PDChoice(form, choice_dict)
    choice.import_fdf(fdf_field)
    # /V is now a COSArray holding the two strings.
    v = choice.get_cos_object().get_dictionary_object(_V)
    assert isinstance(v, COSArray)
    assert [v.get_object(i).get_string() for i in range(v.size())] == ["a", "b"]


def test_import_fdf_value_cos_array_non_choice_writes_raw() -> None:
    """An array ``/V`` for a non-choice field is written raw under ``/V``
    (lines 232-234)."""
    stub = _make_stub()
    arr = COSArray()
    arr.add(COSString("x"))
    arr.add(COSString("y"))
    fdf_field = _fdf_field_with_value(arr)
    stub.import_fdf(fdf_field)
    v = stub.get_cos_object().get_dictionary_object(_V)
    assert v is arr


def test_import_fdf_value_unknown_type_raises() -> None:
    """An unsupported COS type for the ``/V`` payload raises
    :class:`OSError` (line 237). The :meth:`FDFField.get_cos_value`
    accessor pre-screens for ``COSName`` / ``COSArray`` / ``COSString``
    / ``COSStream`` and rejects anything else with its own ``OSError``,
    so the terminal-field branch is only reachable when a caller hands
    ``_apply_fdf_value`` the COSBase directly — we exercise that here.
    """
    stub = _make_stub()
    with pytest.raises(OSError, match="Unknown type for field import"):
        stub._apply_fdf_value(COSInteger.get(42))


# ---------- PDFieldStub.set_value ----------


def test_field_stub_set_value_none_removes_v() -> None:
    """``set_value(None)`` removes ``/V`` (lines 286-288)."""
    stub = _make_stub()
    stub.get_cos_object().set_string(_V, "prior")
    stub.set_value(None)
    assert stub.get_cos_object().get_dictionary_object(_V) is None


def test_field_stub_set_value_cos_base() -> None:
    """A :class:`COSBase` value is written verbatim under ``/V``
    (lines 289-291)."""
    stub = _make_stub()
    val = COSString("raw")
    stub.set_value(val)
    assert stub.get_cos_object().get_dictionary_object(_V) is val


def test_field_stub_set_value_raises_on_unsupported_type() -> None:
    """An int (not None / str / COSBase) raises :class:`TypeError`
    (lines 295-297)."""
    stub = _make_stub()
    with pytest.raises(TypeError, match="expected None, str or COSBase"):
        stub.set_value(123)  # type: ignore[arg-type]
