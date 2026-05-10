from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_simple_file_specification import (
    PDSimpleFileSpecification,
)
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.action.pd_action_import_data import (
    PDActionImportData,
)
from pypdfbox.pdmodel.interactive.action.pd_action_thread import PDActionThread

_S: COSName = COSName.get_pdf_name("S")


def _sub_type(action: object) -> str | None:
    return action.get_cos_object().get_name(_S)  # type: ignore[attr-defined]


# ---------- PDActionImportData ----------


def test_pd_action_import_data_sub_type() -> None:
    action = PDActionImportData()
    assert _sub_type(action) == "ImportData"


def test_pd_action_import_data_file_round_trip_typed() -> None:
    """``set_file`` accepts a ``PDFileSpecification`` and ``get_file`` returns
    the typed wrapper around the same underlying COS object."""
    action = PDActionImportData()
    fs = PDComplexFileSpecification()
    fs.set_file("data.fdf")
    action.set_file(fs)

    resolved = action.get_file()
    assert isinstance(resolved, PDFileSpecification)
    assert isinstance(resolved, PDComplexFileSpecification)
    assert resolved.get_cos_object() is fs.get_cos_object()
    assert resolved.get_file() == "data.fdf"


def test_pd_action_import_data_file_round_trip_simple() -> None:
    """A bare COSString file spec round-trips as ``PDSimpleFileSpecification``."""
    action = PDActionImportData()
    action.set_file("import.fdf")

    resolved = action.get_file()
    assert isinstance(resolved, PDSimpleFileSpecification)
    assert resolved.get_file() == "import.fdf"


def test_pd_action_import_data_file_clear() -> None:
    action = PDActionImportData()
    action.set_file("data.fdf")
    assert action.get_file() is not None

    action.set_file(None)
    assert action.get_file() is None


# ---------- PDActionHide ----------


def test_pd_action_hide_sub_type() -> None:
    action = PDActionHide()
    assert _sub_type(action) == "Hide"


def test_pd_action_hide_target_round_trip_string() -> None:
    """``/T`` as a field-name string survives round-trip as raw COS."""
    action = PDActionHide()
    target = COSString("Widget1")
    action.set_target(target)

    assert action.get_target() is target


def test_pd_action_hide_target_round_trip_dict() -> None:
    """``/T`` as a single-annotation dictionary survives round-trip as raw COS."""
    action = PDActionHide()
    annot = COSDictionary()
    action.set_target(annot)

    assert action.get_target() is annot


def test_pd_action_hide_target_clear() -> None:
    action = PDActionHide()
    action.set_target(COSString("Widget1"))
    assert action.get_target() is not None

    action.set_target(None)
    assert action.get_target() is None


def test_pd_action_hide_h_default_true() -> None:
    """``/H`` defaults to True per PDF 32000-1 Table 200."""
    action = PDActionHide()
    assert action.get_h() is True


def test_pd_action_hide_h_round_trip() -> None:
    action = PDActionHide()
    action.set_h(False)
    assert action.get_h() is False
    action.set_h(True)
    assert action.get_h() is True


# ---------- PDActionThread ----------


def test_pd_action_thread_sub_type() -> None:
    action = PDActionThread()
    assert _sub_type(action) == "Thread"


def test_pd_action_thread_file_round_trip_typed() -> None:
    """``set_file`` accepts a ``PDFileSpecification`` and ``get_file`` returns
    the typed wrapper around the same underlying COS object."""
    action = PDActionThread()
    fs = PDComplexFileSpecification()
    fs.set_file("threads.pdf")
    action.set_file(fs)

    resolved = action.get_file()
    assert isinstance(resolved, PDFileSpecification)
    assert isinstance(resolved, PDComplexFileSpecification)
    assert resolved.get_cos_object() is fs.get_cos_object()
    assert resolved.get_file() == "threads.pdf"


def test_pd_action_thread_file_round_trip_simple() -> None:
    """A bare COSString file spec round-trips as ``PDSimpleFileSpecification``."""
    action = PDActionThread()
    action.set_file("threads.pdf")

    resolved = action.get_file()
    assert isinstance(resolved, PDSimpleFileSpecification)
    assert resolved.get_file() == "threads.pdf"


def test_pd_action_thread_thread_round_trip_integer() -> None:
    """``/D`` as an integer index round-trips as raw COS."""
    action = PDActionThread()
    destination = COSInteger.get(2)
    action.set_thread(destination)

    assert action.get_thread() is destination


def test_pd_action_thread_thread_round_trip_dict() -> None:
    """``/D`` as a thread dictionary round-trips as raw COS."""
    action = PDActionThread()
    thread_dict = COSDictionary()
    action.set_thread(thread_dict)

    assert action.get_thread() is thread_dict


def test_pd_action_thread_thread_clear() -> None:
    action = PDActionThread()
    action.set_thread(COSInteger.get(2))
    assert action.get_thread() is not None

    action.set_thread(None)
    assert action.get_thread() is None


def test_pd_action_thread_bead_round_trip_integer() -> None:
    """``/B`` as an integer bead index round-trips as raw COS."""
    action = PDActionThread()
    bead = COSInteger.get(0)
    action.set_bead(bead)

    assert action.get_bead() is bead


def test_pd_action_thread_bead_round_trip_dict() -> None:
    """``/B`` as a bead dictionary round-trips as raw COS."""
    action = PDActionThread()
    bead_dict = COSDictionary()
    action.set_bead(bead_dict)

    assert action.get_bead() is bead_dict


def test_pd_action_thread_bead_clear() -> None:
    action = PDActionThread()
    action.set_bead(COSDictionary())
    assert action.get_bead() is not None

    action.set_bead(None)
    assert action.get_bead() is None
