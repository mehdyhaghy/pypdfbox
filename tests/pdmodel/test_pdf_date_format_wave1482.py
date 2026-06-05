"""Regression pins for PDF date *write-side* formatting (wave 1482).

Upstream ``org.apache.pdfbox.util.DateConverter.toString`` is the single
canonical PDF-date serializer, reached from every write path:

* ``COSDictionary.setDate`` -> ``DateConverter.toString``
* ``PDDocumentInformation.setCreationDate/setModificationDate`` -> ``setDate``
* ``PDSignature.setSignDate`` -> ``setDate``
* ``PDAnnotation.setModifiedDate(Calendar)`` -> ``setDate``
* ``PDEmbeddedFile.setCreationDate/setModDate`` -> ``setEmbeddedDate`` -> ``setDate``

``DateConverter.formatTZoffset`` renders the zone as ``(+|-)HH'mm'`` and the
Javadoc is explicit (DateConverter.java line 234):

    "For offset of 0 millis, the String returned is +00'00', never Z."

The literal expectations below were captured from live Apache PDFBox 3.0.7 via
``oracle/probes/DateConvertProbe.java`` (``format`` mode) and must hold WITHOUT
the oracle. A previous port emitted a bare ``Z`` / ``Z00'00'`` for UTC — fixed
in wave 1482.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_dictionary import _format_pdf_date as _cos_format
from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import (
    _format_pdf_date as _emb_format,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
from pypdfbox.pdmodel.pd_document_information import PDDocumentInformation
from pypdfbox.pdmodel.pd_document_information import _format_pdf_date as _pdm_format

# (tzinfo, oracle string) — wall clock fixed at 2024-06-01 12:30:45.
_WALL = (2024, 6, 1, 12, 30, 45)
_CASES = [
    (_dt.UTC, "D:20240601123045+00'00'"),
    (_dt.timezone(_dt.timedelta(hours=5, minutes=30)), "D:20240601123045+05'30'"),
    (_dt.timezone(_dt.timedelta(hours=-5)), "D:20240601123045-05'00'"),
    (_dt.timezone(_dt.timedelta(hours=1)), "D:20240601123045+01'00'"),
    (_dt.timezone(_dt.timedelta(hours=-8)), "D:20240601123045-08'00'"),
    (_dt.timezone(_dt.timedelta(hours=14)), "D:20240601123045+14'00'"),
    (_dt.timezone(_dt.timedelta(hours=-12)), "D:20240601123045-12'00'"),
]


@pytest.mark.parametrize("tz, expected", _CASES)
def test_pdm_format_matches_oracle(tz: _dt.tzinfo, expected: str) -> None:
    when = _dt.datetime(*_WALL, tzinfo=tz)
    assert _pdm_format(when) == expected


@pytest.mark.parametrize("tz, expected", _CASES)
def test_cos_format_matches_oracle(tz: _dt.tzinfo, expected: str) -> None:
    when = _dt.datetime(*_WALL, tzinfo=tz)
    assert _cos_format(when) == expected


@pytest.mark.parametrize("tz, expected", _CASES)
def test_embedded_format_matches_oracle(tz: _dt.tzinfo, expected: str) -> None:
    when = _dt.datetime(*_WALL, tzinfo=tz)
    assert _emb_format(when) == expected


def test_utc_never_renders_bare_z() -> None:
    when = _dt.datetime(*_WALL, tzinfo=_dt.UTC)
    out = _pdm_format(when)
    assert "Z" not in out
    assert out.endswith("+00'00'")


def test_cos_set_date_utc_uses_plus_zero() -> None:
    d = COSDictionary()
    d.set_date("ModDate", _dt.datetime(*_WALL, tzinfo=_dt.UTC))
    assert d.get_string("ModDate") == "D:20240601123045+00'00'"


def test_cos_set_embedded_date_utc_uses_plus_zero() -> None:
    d = COSDictionary()
    d.set_embedded_date("Info", "ModDate", _dt.datetime(*_WALL, tzinfo=_dt.UTC))
    info = d.get_cos_dictionary("Info")
    assert info is not None
    assert info.get_string("ModDate") == "D:20240601123045+00'00'"


def test_document_information_creation_date_utc_uses_plus_zero() -> None:
    info = PDDocumentInformation()
    info.set_creation_date(_dt.datetime(*_WALL, tzinfo=_dt.UTC))
    assert info.get_property_string_value("CreationDate") == "D:20240601123045+00'00'"


def test_document_information_naive_datetime_treated_as_utc() -> None:
    info = PDDocumentInformation()
    info.set_modification_date(_dt.datetime(*_WALL))
    assert info.get_property_string_value("ModDate") == "D:20240601123045+00'00'"


def test_signature_sign_date_utc_uses_plus_zero() -> None:
    sig = PDSignature()
    sig.set_sign_date_as_datetime(_dt.datetime(*_WALL, tzinfo=_dt.UTC))
    assert sig.get_sign_date() == "D:20240601123045+00'00'"


def test_annotation_modified_date_datetime_utc_uses_plus_zero() -> None:
    ann = PDAnnotation()
    ann.set_modified_date(_dt.datetime(*_WALL, tzinfo=_dt.UTC))
    assert ann.get_modified_date() == "D:20240601123045+00'00'"


@pytest.mark.parametrize(
    "off_min",
    [0, 330, -300, 60, -480, 840, -720, 720, 45, -570],
)
def test_cos_format_matches_live_oracle(off_min: int) -> None:
    """Differential: the cos/pdmodel write path must byte-match
    ``DateConverter.toString`` from live Apache PDFBox 3.0.7."""
    from tests.oracle.harness import oracle_available, run_probe_text

    if not oracle_available():
        pytest.skip("live PDFBox oracle unavailable")
    epoch_ms = 1710504000000  # 2024-03-15 12:00 UTC
    tz = _dt.timezone(_dt.timedelta(minutes=off_min))
    when = _dt.datetime.fromtimestamp(epoch_ms / 1000, tz=tz)
    java = run_probe_text("DateConvertProbe", "format", str(epoch_ms), str(off_min))
    assert _cos_format(when) == java
    assert _pdm_format(when) == java
    assert _emb_format(when) == java


def test_round_trip_parse_format_stability() -> None:
    # parse(format(x)) preserves the instant + offset across zones.
    d = COSDictionary()
    for tz, _expected in _CASES:
        when = _dt.datetime(*_WALL, tzinfo=tz)
        d.set_date("D", when)
        parsed = d.get_date("D")
        assert parsed is not None
        assert parsed.utcoffset() == when.utcoffset()
        assert parsed == when
