"""Parity tests for ``PDActionSubmitForm`` upstream-named accessors —
``get_file``/``set_file`` (typed :class:`PDFileSpecification`),
``get_url``/``set_url`` (file-spec URL), ``get_fields``/``set_fields``
(typed :class:`PDField` list), ``get_flags``/``set_flags``, and the
Table 237 per-bit predicates (PDF 32000-1 §12.7.5.2)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_F = COSName.get_pdf_name("F")
_FIELDS = COSName.get_pdf_name("Fields")
_FLAGS = COSName.get_pdf_name("Flags")
_FT = COSName.get_pdf_name("FT")
_T = COSName.get_pdf_name("T")


# ---------- /F as PDFileSpecification ----------


def test_get_file_returns_none_when_absent() -> None:
    """No ``/F`` entry → ``get_file()`` returns ``None`` (mirrors
    upstream's createFS(null) early-out)."""
    action = PDActionSubmitForm()
    assert action.get_file() is None


def test_get_file_returns_simple_file_specification_for_cos_string() -> None:
    """``/F`` stored as ``COSString`` resolves to
    :class:`PDSimpleFileSpecification`."""
    action = PDActionSubmitForm()
    action.set_url("https://example.com/submit")
    fs = action.get_file()
    assert isinstance(fs, PDSimpleFileSpecification)
    assert fs.get_file() == "https://example.com/submit"


def test_get_file_returns_complex_file_specification_for_dict() -> None:
    """``/F`` stored as ``COSDictionary`` resolves to
    :class:`PDComplexFileSpecification`."""
    action = PDActionSubmitForm()
    fs_in = PDComplexFileSpecification()
    fs_in.set_file("payload.fdf")
    action.set_file(fs_in)
    fs_out = action.get_file()
    assert isinstance(fs_out, PDComplexFileSpecification)
    assert fs_out.get_file() == "payload.fdf"


def test_set_file_accepts_pd_file_specification_round_trip() -> None:
    """Setting via :class:`PDFileSpecification` round-trips through the
    underlying COS dictionary."""
    action = PDActionSubmitForm()
    fs = PDComplexFileSpecification()
    fs.set_file("submit.xfdf")
    action.set_file(fs)
    raw = action.get_cos_object().get_dictionary_object(_F)
    assert raw is fs.get_cos_object()


def test_set_file_none_removes_entry() -> None:
    """``set_file(None)`` strips ``/F``."""
    action = PDActionSubmitForm()
    action.set_url("file.fdf")
    assert action.get_cos_object().get_dictionary_object(_F) is not None
    action.set_file(None)
    assert action.get_cos_object().get_dictionary_object(_F) is None


# ---------- /F URL convenience ----------


def test_set_url_round_trip() -> None:
    """``set_url``/``get_url`` round-trips through the simple
    ``COSString`` form of ``/F``."""
    action = PDActionSubmitForm()
    action.set_url("https://example.com/submit?id=42")
    assert action.get_url() == "https://example.com/submit?id=42"
    raw = action.get_cos_object().get_dictionary_object(_F)
    assert isinstance(raw, COSString)


def test_get_url_reads_from_complex_file_specification() -> None:
    """When ``/F`` is a complex filespec the URL convenience falls back
    to the wrapped ``/F`` string entry."""
    action = PDActionSubmitForm()
    fs = PDComplexFileSpecification()
    fs.set_file("https://example.com/payload")
    action.set_file(fs)
    assert action.get_url() == "https://example.com/payload"


def test_set_url_none_removes_entry() -> None:
    action = PDActionSubmitForm()
    action.set_url("x")
    action.set_url(None)
    assert action.get_url() is None
    assert action.get_cos_object().get_dictionary_object(_F) is None


# ---------- /Fields typed wrapping ----------


def test_get_fields_none_when_absent() -> None:
    """When ``/Fields`` is absent ``get_fields()`` returns ``None``."""
    action = PDActionSubmitForm()
    assert action.get_fields() is None


def test_get_fields_wraps_each_entry_in_pd_field_subclass() -> None:
    """Each ``COSDictionary`` entry in ``/Fields`` is dispatched through
    :class:`PDFieldFactory` to its typed subclass — text fields become
    :class:`PDTextField`, signature fields become :class:`PDSignatureField`."""
    action = PDActionSubmitForm()

    text_field = COSDictionary()
    text_field.set_item(_FT, COSName.get_pdf_name("Tx"))
    text_field.set_string(_T, "username")

    sig_field = COSDictionary()
    sig_field.set_item(_FT, COSName.get_pdf_name("Sig"))
    sig_field.set_string(_T, "approval")

    array = COSArray()
    array.add(text_field)
    array.add(sig_field)
    action.get_cos_object().set_item(_FIELDS, array)

    typed = action.get_fields()
    assert typed is not None
    assert len(typed) == 2
    assert isinstance(typed[0], PDTextField)
    assert isinstance(typed[1], PDSignatureField)
    assert typed[0].get_partial_name() == "username"
    assert typed[1].get_partial_name() == "approval"


def test_set_fields_from_pd_field_list_round_trip_via_cos() -> None:
    """``set_fields`` accepts a list of :class:`PDField` instances and
    stores their underlying COS dictionaries in a ``COSArray``."""
    from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

    form = PDAcroForm()
    text_dict = COSDictionary()
    text_dict.set_item(_FT, COSName.get_pdf_name("Tx"))
    text_dict.set_string(_T, "f1")
    text_field = PDTextField(form, text_dict, None)

    action = PDActionSubmitForm()
    action.set_fields([text_field])
    raw = action.get_cos_fields()
    assert isinstance(raw, COSArray)
    assert raw.size() == 1
    assert raw.get_object(0) is text_dict


def test_set_fields_accepts_cos_array_directly() -> None:
    """A ``COSArray`` is stored verbatim — same identity round-trips."""
    array = COSArray([COSString("name"), COSString("email")])
    action = PDActionSubmitForm()
    action.set_fields(array)
    assert action.get_cos_fields() is array


def test_set_fields_none_removes_entry() -> None:
    action = PDActionSubmitForm()
    action.set_fields(COSArray())
    action.set_fields(None)
    assert action.get_cos_fields() is None
    assert action.get_cos_object().get_dictionary_object(_FIELDS) is None


# ---------- /Flags ----------


def test_get_flags_default_zero_when_absent() -> None:
    """Per Table 236 ``/Flags`` defaults to ``0``."""
    action = PDActionSubmitForm()
    assert action.get_flags() == 0


def test_set_flags_round_trip() -> None:
    action = PDActionSubmitForm()
    action.set_flags(0x1234)
    assert action.get_flags() == 0x1234
    assert action.get_cos_object().get_int(_FLAGS, -1) == 0x1234


# ---------- Table 237 per-bit predicates ----------


def test_is_include_default_false_round_trip() -> None:
    """Bit 1 (Include/Exclude) defaults to clear, then round-trips."""
    action = PDActionSubmitForm()
    assert action.is_include() is False
    action.set_include(True)
    assert action.is_include() is True
    assert action.get_flags() & 0x01 == 0x01
    action.set_include(False)
    assert action.is_include() is False
    assert action.get_flags() == 0


def test_is_include_no_value_fields_round_trip() -> None:
    """Bit 2 (IncludeNoValueFields) — when set, the submission includes
    successful fields that have no value (PDF 32000-1 §12.7.5.2 Table
    237). Defaults to clear; round-trips through the bit-twiddle helper."""
    action = PDActionSubmitForm()
    assert action.is_include_no_value_fields() is False
    action.set_include_no_value_fields(True)
    assert action.is_include_no_value_fields() is True
    assert action.get_flags() == 0b10  # 1 << 1
    action.set_include_no_value_fields(False)
    assert action.is_include_no_value_fields() is False
    assert action.get_flags() == 0


def test_is_export_format_round_trip() -> None:
    """Bit 3 (ExportFormat)."""
    action = PDActionSubmitForm()
    assert action.is_export_format() is False
    action.set_export_format(True)
    assert action.is_export_format() is True
    assert action.get_flags() == 0b100  # 1 << 2


def test_is_get_method_round_trip() -> None:
    """Bit 4 (GetMethod)."""
    action = PDActionSubmitForm()
    action.set_get_method(True)
    assert action.is_get_method() is True
    assert action.get_flags() == 0b1000  # 1 << 3
    action.set_get_method(False)
    assert action.is_get_method() is False


def test_is_xfdf_round_trip() -> None:
    """Bit 6 (XFDF)."""
    action = PDActionSubmitForm()
    action.set_xfdf(True)
    assert action.is_xfdf() is True
    assert action.get_flags() == 0b100000  # 1 << 5


def test_flag_predicates_are_independent() -> None:
    """Setting one named flag does not perturb others — verifies the
    bit-twiddle helper does an OR rather than overwrite."""
    action = PDActionSubmitForm()
    action.set_include(True)
    action.set_xfdf(True)
    action.set_embed_form(True)
    flags = action.get_flags()
    assert flags & 0x01            # bit 1
    assert flags & (1 << 5)        # bit 6
    assert flags & (1 << 13)       # bit 14
    assert action.is_include() is True
    assert action.is_xfdf() is True
    assert action.is_embed_form() is True
    # Toggling one off does not clear neighbours.
    action.set_xfdf(False)
    assert action.is_xfdf() is False
    assert action.is_include() is True
    assert action.is_embed_form() is True


def test_create_dispatch_via_pd_action() -> None:
    """``PDAction.create`` routes a ``/S /SubmitForm`` dictionary back to
    the typed wrapper — protects this class's place in the dispatch."""
    from pypdfbox.pdmodel.interactive.action.pd_action import PDAction

    raw = COSDictionary()
    raw.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("SubmitForm"))
    action = PDAction.create(raw)
    assert isinstance(action, PDActionSubmitForm)


def test_get_file_returns_pd_file_specification_when_present() -> None:
    """End-to-end: a SubmitForm action round-trips ``/F`` typed."""
    action = PDActionSubmitForm()
    fs = PDComplexFileSpecification()
    fs.set_file("submit.fdf")
    action.set_file(fs)
    out = action.get_file()
    assert isinstance(out, PDFileSpecification)
    assert out.get_file() == "submit.fdf"
