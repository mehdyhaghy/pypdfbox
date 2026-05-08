from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata


def test_import_xmp_metadata_rewrites_body_through_existing_filter_wave314() -> None:
    packet = b"<rdf:RDF><rdf:Description /></rdf:RDF>"
    meta = PDMetadata()
    meta.set_filters(COSName.FLATE_DECODE)  # type: ignore[attr-defined]

    meta.import_xmp_metadata(packet)

    assert meta.get_filters() == [COSName.FLATE_DECODE]  # type: ignore[attr-defined]
    assert meta.create_raw_input_stream().read() != packet
    assert meta.export_xmp_metadata() == packet
