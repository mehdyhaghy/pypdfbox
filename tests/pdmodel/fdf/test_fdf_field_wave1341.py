"""Wave-1341 coverage-boost tests for
:mod:`pypdfbox.pdmodel.fdf.fdf_field`.

Targets the residual uncovered branches:

* ``get_value`` / ``get_cos_value`` / ``get_rich_text`` ``COSObject``
  unwrap fallback paths (defence-in-depth in case a caller routes
  around ``COSDictionary.get_dictionary_object``);
* ``get_rich_text`` returning ``None`` for non-string non-stream values
  (line 351);
* ``write_xml`` skipping non-string entries in a value list (line 513);
* ``_cos_value_to_python`` ``COSInteger`` + ``COSStream`` passthrough
  (lines 580, 583-585);
* :class:`FDFNamedPageReference` filespec round trip + clear
  (lines 612-616, 620-623);
* :class:`FDFIconFit` ``PDRange(array)`` branch (line 677).

Note: ``get_dictionary_object`` already dereferences ``COSObject``
indirections before they reach the ``isinstance(v, COSObject)`` checks
at lines 105-106, 127-128 and 345-346 in the source. Those three
guards are defensive — currently dead code under the port's
``_resolve_item`` behaviour. Flagged in the wave report.

Similarly the ``elif isinstance(rich, COSStream)`` branch at
lines 523-526 of ``write_xml`` is dead code because
``get_rich_text`` decodes ``COSStream`` → ``str`` before returning.
"""

from __future__ import annotations

import io

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSObject,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.fdf.fdf_field import (
    FDFField,
    FDFIconFit,
    FDFNamedPageReference,
)

# ---------- /V COSObject unwrap branches ----------------------------------


def _wrap_in_cos_object(value: object) -> COSObject:
    """Return a COSObject indirection wrapping ``value`` — mirrors the
    indirect-reference state most parsed FDF fields land in."""
    # Object number 1, generation 0, value pre-resolved (which is the
    # state COSObject lands in after the loader has run).
    return COSObject(1, 0, resolved=value)  # type: ignore[arg-type]


def test_get_value_unwraps_cos_object_to_string() -> None:
    """``/V`` stored as a COSObject indirection unwraps to the inner
    value (line 106)."""
    field = FDFField()
    field.get_cos_object().set_item(
        COSName.get_pdf_name("V"), _wrap_in_cos_object(COSString("Lyon"))
    )
    assert field.get_value() == "Lyon"


def test_get_cos_value_unwraps_cos_object_to_name() -> None:
    """``get_cos_value`` unwraps COSObject indirections so callers see
    the typed COS leaf (line 128)."""
    field = FDFField()
    name = COSName.get_pdf_name("Yes")
    field.get_cos_object().set_item(
        COSName.get_pdf_name("V"), _wrap_in_cos_object(name)
    )
    result = field.get_cos_value()
    assert result is name


def test_get_rich_text_unwraps_cos_object_to_string() -> None:
    """``/RV`` wrapped in COSObject decodes to ``str`` (line 346)."""
    field = FDFField()
    field.get_cos_object().set_item(
        COSName.get_pdf_name("RV"), _wrap_in_cos_object(COSString("<b>x</b>"))
    )
    assert field.get_rich_text() == "<b>x</b>"


def test_get_rich_text_returns_none_for_unexpected_type() -> None:
    """``/RV`` neither string nor stream → ``None`` (line 351)."""
    field = FDFField()
    field.get_cos_object().set_item(
        COSName.get_pdf_name("RV"), COSArray()
    )
    assert field.get_rich_text() is None


# ---------- write_xml value/value-richtext branches ----------------------


def test_write_xml_skips_non_string_entries_in_value_list() -> None:
    """A multi-select ``/V`` array that contains a non-string COS value
    is skipped (line 513)."""
    field = FDFField()
    field.set_partial_field_name("opts")
    arr = COSArray()
    arr.add(COSString("first"))
    arr.add(COSFloat(1.5))  # numeric entry — _cos_value_to_python yields a non-str
    arr.add(COSString("second"))
    field.get_cos_object().set_item(COSName.get_pdf_name("V"), arr)

    buf = io.StringIO()
    field.write_xml(buf)
    out = buf.getvalue()
    # The non-string entry is dropped; the string entries survive.
    assert "<value>first</value>" in out
    assert "<value>second</value>" in out
    # Float was skipped.
    assert "<value>1.5</value>" not in out


def test_write_xml_emits_richtext_from_cos_stream() -> None:
    """A ``/RV`` carrying a ``COSStream`` is decoded and emitted under
    ``<value-richtext>`` (lines 524-526)."""
    field = FDFField()
    field.set_partial_field_name("body")
    rv_stream = COSStream()
    rv_stream.set_data(b"<b>hello</b>")
    field.get_cos_object().set_item(COSName.get_pdf_name("RV"), rv_stream)

    buf = io.StringIO()
    field.write_xml(buf)
    out = buf.getvalue()
    assert "<value-richtext>" in out
    assert "&lt;b&gt;hello&lt;/b&gt;" in out


# ---------- _cos_value_to_python passthrough -----------------------------


def test_cos_value_to_python_returns_stream_as_is() -> None:
    """``_cos_value_to_python`` returns COSStream values unchanged so
    callers can detect them with ``isinstance`` (line 583-585)."""
    from pypdfbox.pdmodel.fdf.fdf_field import _cos_value_to_python

    stream = COSStream()
    stream.set_data(b"abc")
    out = _cos_value_to_python(stream)
    assert out is stream

    # Default branch — unknown type passes through unchanged.
    dict_value = COSDictionary()
    assert _cos_value_to_python(dict_value) is dict_value


def test_cos_value_to_python_extracts_int_from_cos_integer() -> None:
    """``COSInteger`` entries are extracted to their Python ``int``
    value (line 580)."""
    from pypdfbox.cos import COSInteger
    from pypdfbox.pdmodel.fdf.fdf_field import _cos_value_to_python

    assert _cos_value_to_python(COSInteger(42)) == 42
    # Array of mixed COSInteger / COSString → list of native Python types.
    arr = COSArray()
    arr.add(COSInteger(1))
    arr.add(COSString("two"))
    assert _cos_value_to_python(arr) == [1, "two"]


# ---------- FDFNamedPageReference filespec --------------------------------


def test_named_page_reference_set_and_get_file_specification() -> None:
    """``set_file_specification`` writes the spec's COS object into
    ``/F``; ``get_file_specification`` rebuilds a typed PDFileSpecification
    (lines 612-616, 623)."""
    from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
        PDSimpleFileSpecification,
    )

    ref = FDFNamedPageReference()
    fs = PDSimpleFileSpecification()
    fs.set_file("page1.pdf")
    ref.set_file_specification(fs)
    # Round-trips via PDFileSpecification.create_fs.
    rebuilt = ref.get_file_specification()
    assert rebuilt is not None
    assert rebuilt.get_file() == "page1.pdf"


def test_named_page_reference_clear_file_specification() -> None:
    """``set_file_specification(None)`` removes ``/F`` (lines 620-621)."""
    from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
        PDSimpleFileSpecification,
    )

    ref = FDFNamedPageReference()
    fs = PDSimpleFileSpecification()
    fs.set_file("page2.pdf")
    ref.set_file_specification(fs)
    assert ref.get_file_specification() is not None
    # Clear path.
    ref.set_file_specification(None)
    assert ref.get_file_specification() is None


# ---------- FDFIconFit fractional space ----------------------------------


def test_icon_fit_fractional_space_round_trips_existing_array() -> None:
    """``get_fractional_space_to_allocate`` returns a fresh ``PDRange``
    wrapping the existing /A array when present (line 677)."""
    fit = FDFIconFit()
    arr = COSArray()
    arr.add(COSFloat(0.25))
    arr.add(COSFloat(0.75))
    fit.get_cos_object().set_item(COSName.get_pdf_name("A"), arr)

    pd_range = fit.get_fractional_space_to_allocate()
    assert pd_range.get_min() == 0.25
    assert pd_range.get_max() == 0.75
