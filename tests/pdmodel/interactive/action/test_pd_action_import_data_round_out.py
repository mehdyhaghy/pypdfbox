"""Round-out tests for ``PDActionImportData`` convenience surface added
in Wave 243: ``get_url`` / ``set_url`` / ``get_file_path`` / ``has_file`` /
``is_valid`` over the PDF 32000-1 §12.7.5.4 ``/F`` entry."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_import_data import (
    PDActionImportData,
)

_F = COSName.get_pdf_name("F")
_S = COSName.get_pdf_name("S")


# ---------- get_file_path / get_url ----------


def test_get_file_path_returns_none_when_f_absent() -> None:
    action = PDActionImportData()
    assert action.get_file_path() is None
    assert action.get_url() is None


def test_get_file_path_returns_string_for_simple_form() -> None:
    """``/F`` stored as ``COSString`` round-trips through ``get_file_path``."""
    action = PDActionImportData()
    action.set_file("data.fdf")
    assert action.get_file_path() == "data.fdf"
    assert action.get_url() == "data.fdf"


def test_get_file_path_returns_inner_string_for_complex_form() -> None:
    """A complex file spec with ``/F = "x.fdf"`` is unwrapped to the inner
    path string."""
    action = PDActionImportData()
    fs = PDComplexFileSpecification()
    fs.set_file("complex.fdf")
    action.set_file(fs)

    assert action.get_file_path() == "complex.fdf"
    assert action.get_url() == "complex.fdf"


def test_get_file_path_complex_spec_without_f_returns_none() -> None:
    """Complex spec with no ``/F`` inner entry yields ``None``."""
    action = PDActionImportData()
    fs = PDComplexFileSpecification()  # no inner /F
    action.set_file(fs)
    assert action.get_file_path() is None


# ---------- set_url ----------


def test_set_url_stores_simple_form() -> None:
    """``set_url`` writes ``/F`` as a plain ``COSString``."""
    action = PDActionImportData()
    action.set_url("https://example.com/data.xfdf")
    raw = action.get_cos_object().get_dictionary_object(_F)
    assert isinstance(raw, COSString)
    assert raw.get_string() == "https://example.com/data.xfdf"
    # And the typed wrapper sees a simple file spec.
    fs = action.get_file()
    assert isinstance(fs, PDSimpleFileSpecification)
    assert fs.get_file() == "https://example.com/data.xfdf"


def test_set_url_none_removes_f() -> None:
    """``set_url(None)`` is a no-throw clear of ``/F``."""
    action = PDActionImportData()
    action.set_url("data.fdf")
    assert action.get_cos_object().contains_key(_F)
    action.set_url(None)
    assert not action.get_cos_object().contains_key(_F)
    assert action.get_url() is None


# ---------- has_file ----------


def test_has_file_false_when_f_absent() -> None:
    action = PDActionImportData()
    assert action.has_file() is False


def test_has_file_true_after_simple_set() -> None:
    action = PDActionImportData()
    action.set_file("data.fdf")
    assert action.has_file() is True


def test_has_file_true_after_complex_set() -> None:
    action = PDActionImportData()
    fs = PDComplexFileSpecification()
    fs.set_file("data.fdf")
    action.set_file(fs)
    assert action.has_file() is True


def test_has_file_false_after_clear() -> None:
    action = PDActionImportData()
    action.set_file("data.fdf")
    assert action.has_file() is True
    action.set_file(None)
    assert action.has_file() is False


# ---------- is_valid ----------


def test_is_valid_true_for_default_construction() -> None:
    """Fresh ``PDActionImportData`` has ``/S = ImportData`` set by the
    constructor."""
    action = PDActionImportData()
    assert action.is_valid() is True


def test_is_valid_true_for_existing_dict_with_correct_subtype() -> None:
    """Wrapping an existing dict that already declares ``/S /ImportData``
    is valid."""
    raw = COSDictionary()
    raw.set_name(_S, "ImportData")
    action = PDActionImportData(raw)
    assert action.is_valid() is True


def test_is_valid_false_when_subtype_mismatched() -> None:
    """If a caller manually changes ``/S`` away from ``ImportData`` the
    predicate flags it."""
    action = PDActionImportData()
    action.set_sub_type("SubmitForm")
    assert action.is_valid() is False


def test_is_valid_false_when_subtype_absent() -> None:
    """A bare dict that lacks ``/S`` entirely is also flagged invalid —
    construction via :class:`PDActionImportData` always sets ``/S`` so this
    only happens when callers strip it after the fact."""
    action = PDActionImportData()
    action.get_cos_object().remove_item(_S)
    assert action.is_valid() is False


# ---------- set_file accepts COSBase ----------


def test_set_file_accepts_raw_cosbase() -> None:
    """Raw COSBase entries are stored unchanged — preserving the back-compat
    contract for callers passing pre-built COS values."""
    action = PDActionImportData()
    raw = COSString("raw.fdf")
    action.set_file(raw)
    # Stored as-is, observable via get_file_path.
    assert action.get_file_path() == "raw.fdf"
    fs = action.get_file()
    assert isinstance(fs, PDSimpleFileSpecification)


def test_set_file_bytes_round_trip() -> None:
    """``set_file`` accepts ``bytes`` and stores them as ``COSString``."""
    action = PDActionImportData()
    action.set_file(b"binary-name.fdf")
    assert action.get_file_path() == "binary-name.fdf"
