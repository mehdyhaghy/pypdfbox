from __future__ import annotations

"""Tests for ``DigitalSignatureTable`` / ``TrueTypeFont.get_dsig``.

The ``DSIG`` table is rarely shipped in real-world fonts (the bundled
``LiberationSans-Regular.ttf`` fixture has none), so these tests fabricate
a DSIG-bearing TTF on the fly via ``fontTools`` to exercise both the
present-table and absent-table paths. No new fixtures are committed.
"""

import io
from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.digital_signature_table import DigitalSignatureTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont


_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _build_font_with_dsig(blocks: list[bytes], *, flag: int = 0) -> bytes:
    """Return a TTF byte buffer with a synthetic DSIG table appended."""
    fontTools = pytest.importorskip("fontTools")
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables.D_S_I_G_ import SignatureRecord, table_D_S_I_G_

    _ = fontTools  # silence unused-import lints — importorskip handles availability
    tt = TTFont(str(_FIXTURE), lazy=False)
    dsig = table_D_S_I_G_("DSIG")
    dsig.ulVersion = 1
    dsig.usNumSigs = len(blocks)
    dsig.usFlag = flag
    records = []
    for block in blocks:
        rec = SignatureRecord()
        rec.ulFormat = 1
        rec.usReserved1 = 0
        rec.usReserved2 = 0
        rec.cbSignature = len(block)
        rec.pkcs7 = block
        records.append(rec)
    dsig.signatureRecords = records
    tt["DSIG"] = dsig
    buf = io.BytesIO()
    tt.save(buf)
    return buf.getvalue()


# ---- Direct DigitalSignatureTable surface ---------------------------------


def test_tag_class_constant() -> None:
    assert DigitalSignatureTable.TAG == "DSIG"


def test_defaults_before_population() -> None:
    table = DigitalSignatureTable()
    assert table.get_tag() == "DSIG"
    assert table.get_initialized() is False
    assert table.get_version() == 0
    assert table.get_num_signatures() == 0
    assert table.get_flag() == 0
    assert table.get_signature_blocks() == []


def test_inherits_from_ttf_table() -> None:
    from pypdfbox.fontbox.ttf.ttf_table import TTFTable

    assert issubclass(DigitalSignatureTable, TTFTable)
    assert isinstance(DigitalSignatureTable(), TTFTable)


def test_read_is_no_op_matching_upstream() -> None:
    # Upstream's DigitalSignatureTable doesn't override read; ours mirrors
    # that — the call must not raise and must not flip `initialized`.
    table = DigitalSignatureTable()
    table.read(None, None)  # type: ignore[arg-type]
    assert table.get_initialized() is False


def test_populate_from_fonttools_copies_header_and_blocks() -> None:
    pytest.importorskip("fontTools")
    from fontTools.ttLib.tables.D_S_I_G_ import SignatureRecord, table_D_S_I_G_

    ft = table_D_S_I_G_("DSIG")
    ft.ulVersion = 1
    ft.usNumSigs = 2
    ft.usFlag = 1
    r1 = SignatureRecord()
    r1.pkcs7 = b"\x01\x02\x03"
    r2 = SignatureRecord()
    r2.pkcs7 = b"\xaa\xbb"
    ft.signatureRecords = [r1, r2]

    table = DigitalSignatureTable()
    table.populate_from_fonttools(ft)

    assert table.get_initialized() is True
    assert table.get_version() == 1
    assert table.get_num_signatures() == 2
    assert table.get_flag() == 1
    blocks = table.get_signature_blocks()
    assert blocks == [b"\x01\x02\x03", b"\xaa\xbb"]


def test_get_signature_blocks_returns_fresh_list() -> None:
    pytest.importorskip("fontTools")
    from fontTools.ttLib.tables.D_S_I_G_ import SignatureRecord, table_D_S_I_G_

    ft = table_D_S_I_G_("DSIG")
    ft.ulVersion = 1
    ft.usNumSigs = 1
    ft.usFlag = 0
    rec = SignatureRecord()
    rec.pkcs7 = b"abc"
    ft.signatureRecords = [rec]

    table = DigitalSignatureTable()
    table.populate_from_fonttools(ft)

    snapshot = table.get_signature_blocks()
    snapshot.append(b"mutated")
    # Internal state stays clean.
    assert table.get_signature_blocks() == [b"abc"]


def test_get_signature_block_index() -> None:
    pytest.importorskip("fontTools")
    from fontTools.ttLib.tables.D_S_I_G_ import SignatureRecord, table_D_S_I_G_

    ft = table_D_S_I_G_("DSIG")
    ft.ulVersion = 1
    ft.usNumSigs = 1
    ft.usFlag = 0
    rec = SignatureRecord()
    rec.pkcs7 = b"hello"
    ft.signatureRecords = [rec]

    table = DigitalSignatureTable()
    table.populate_from_fonttools(ft)

    assert table.get_signature_block(0) == b"hello"
    with pytest.raises(IndexError):
        table.get_signature_block(5)


def test_populate_handles_missing_attributes_defensively() -> None:
    # Synthesise a stripped fontTools-like object — defensive zero defaults
    # so callers can't crash us on future schema drift.
    class Empty:
        pass

    table = DigitalSignatureTable()
    table.populate_from_fonttools(Empty())
    assert table.get_version() == 0
    assert table.get_num_signatures() == 0
    assert table.get_flag() == 0
    assert table.get_signature_blocks() == []
    assert table.get_initialized() is True


# ---- TrueTypeFont.get_dsig integration ------------------------------------


def test_get_dsig_returns_none_when_absent() -> None:
    if not _FIXTURE.exists():
        pytest.skip("LiberationSans fixture not present")
    raw = _FIXTURE.read_bytes()
    font = TrueTypeFont.from_bytes(raw)
    # Liberation Sans does not ship a DSIG table.
    assert font.get_dsig() is None


def test_get_dsig_caches_negative_result() -> None:
    if not _FIXTURE.exists():
        pytest.skip("LiberationSans fixture not present")
    raw = _FIXTURE.read_bytes()
    font = TrueTypeFont.from_bytes(raw)
    assert font.get_dsig() is None
    # Second call must not re-probe; the cache flag should stay set.
    assert font.get_dsig() is None
    assert font._dsig_resolved is True  # noqa: SLF001 — cache invariant


def test_get_dsig_reads_synthetic_table() -> None:
    if not _FIXTURE.exists():
        pytest.skip("LiberationSans fixture not present")
    blocks = [b"\x01\x02\x03\x04\x05", b"\xff\xfe\xfd"]
    raw = _build_font_with_dsig(blocks, flag=0)
    font = TrueTypeFont.from_bytes(raw)

    dsig = font.get_dsig()
    assert dsig is not None
    assert isinstance(dsig, DigitalSignatureTable)
    assert dsig.get_version() == 1
    assert dsig.get_num_signatures() == 2
    assert dsig.get_flag() == 0
    assert dsig.get_signature_blocks() == blocks


def test_get_dsig_caches_positive_result() -> None:
    if not _FIXTURE.exists():
        pytest.skip("LiberationSans fixture not present")
    raw = _build_font_with_dsig([b"sig"], flag=0)
    font = TrueTypeFont.from_bytes(raw)

    first = font.get_dsig()
    second = font.get_dsig()
    assert first is second
