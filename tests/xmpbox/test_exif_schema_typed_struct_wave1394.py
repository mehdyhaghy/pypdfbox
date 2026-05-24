"""Wave 1394 — typed-struct getter/setter coverage for ``ExifSchema``.

Covers lines 1395, 1399-1400, 1417-1418, 1423, 1428-1429, 1432 in
``pypdfbox.xmpbox.exif_schema``: the ``_typed_struct_get`` /
``_typed_struct_set`` helpers and their three callers
(``get_oecf_property`` / ``set_oecf_property``,
``get_spatial_frequency_response_property`` /
``set_spatial_frequency_response_property``,
``get_cfa_pattern_property`` / ``set_cfa_pattern_property``).
"""

from __future__ import annotations

from pypdfbox.xmpbox import ExifSchema, XMPMetadata
from pypdfbox.xmpbox.type.cfa_pattern_type import CFAPatternType
from pypdfbox.xmpbox.type.oecf_type import OECFType


def _exif() -> ExifSchema:
    return ExifSchema(XMPMetadata.create_xmp_metadata())


# ---------- OECF ----------


def test_oecf_setter_then_getter_round_trips() -> None:
    schema = _exif()
    metadata = XMPMetadata.create_xmp_metadata()
    oecf = OECFType(metadata)
    schema.set_oecf_property(oecf)
    assert schema.get_oecf_property() is oecf


def test_oecf_setter_none_removes_property() -> None:
    """``set_oecf_property(None)`` should clear the slot (lines 1399-1400)."""
    schema = _exif()
    metadata = XMPMetadata.create_xmp_metadata()
    schema.set_oecf_property(OECFType(metadata))
    schema.set_oecf_property(None)
    assert schema.get_oecf_property() is None


def test_oecf_getter_returns_none_when_wrong_type_stored() -> None:
    """Line 1395: stored value not an OECFType → ``None``."""
    schema = _exif()
    # Stuff a non-OECFType into the property slot directly.
    schema._properties[ExifSchema.OECF] = "not-an-oecf-instance"  # noqa: SLF001
    assert schema.get_oecf_property() is None


# ---------- SpatialFrequencyResponse ----------


def test_spatial_frequency_response_setter_then_getter() -> None:
    """Lines 1417-1418, 1423: both delegate to the typed-struct helpers."""
    schema = _exif()
    metadata = XMPMetadata.create_xmp_metadata()
    sfr = OECFType(metadata)
    schema.set_spatial_frequency_response_property(sfr)
    assert schema.get_spatial_frequency_response_property() is sfr


def test_spatial_frequency_response_setter_none_removes_property() -> None:
    schema = _exif()
    metadata = XMPMetadata.create_xmp_metadata()
    schema.set_spatial_frequency_response_property(OECFType(metadata))
    schema.set_spatial_frequency_response_property(None)
    assert schema.get_spatial_frequency_response_property() is None


def test_spatial_frequency_response_getter_wrong_type_returns_none() -> None:
    schema = _exif()
    schema._properties[ExifSchema.SPATIAL_FREQUENCY_RESPONSE] = 42  # noqa: SLF001
    assert schema.get_spatial_frequency_response_property() is None


# ---------- CFAPattern ----------


def test_cfa_pattern_setter_then_getter() -> None:
    """Lines 1428-1429, 1432."""
    schema = _exif()
    metadata = XMPMetadata.create_xmp_metadata()
    cfa = CFAPatternType(metadata)
    schema.set_cfa_pattern_property(cfa)
    assert schema.get_cfa_pattern_property() is cfa


def test_cfa_pattern_setter_none_removes_property() -> None:
    schema = _exif()
    metadata = XMPMetadata.create_xmp_metadata()
    schema.set_cfa_pattern_property(CFAPatternType(metadata))
    schema.set_cfa_pattern_property(None)
    assert schema.get_cfa_pattern_property() is None


def test_cfa_pattern_getter_wrong_type_returns_none() -> None:
    schema = _exif()
    schema._properties[ExifSchema.CFA_PATTERN] = [1, 2, 3]  # noqa: SLF001
    assert schema.get_cfa_pattern_property() is None
