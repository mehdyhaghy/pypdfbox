from __future__ import annotations

from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel.font import pd_type0_font as type0_module
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def test_wave555_to_unicode_stream_parse_error_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    calls: list[bytes] = []

    def parse(self: CMapParser, data: bytes) -> object:
        calls.append(data)
        raise OSError("broken to-unicode stream")

    stream = COSStream()
    stream.set_raw_data(b"broken")
    font = PDType0Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("ToUnicode"), stream)
    monkeypatch.setattr(CMapParser, "parse", parse)

    assert font.get_to_unicode_cmap() is None
    assert font.get_to_unicode_cmap() is None
    assert calls == [b"broken"]


def test_wave555_to_unicode_falls_through_none_hits_to_ucs2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(
        font,
        "get_to_unicode_cmap",
        lambda: SimpleNamespace(
            has_unicode_mappings=lambda: True,
            to_unicode=lambda _code: None,
        ),
    )
    monkeypatch.setattr(
        font,
        "get_cmap",
        lambda: SimpleNamespace(
            has_unicode_mappings=lambda: True,
            to_unicode=lambda _code: None,
        ),
    )
    monkeypatch.setattr(
        font,
        "get_cmap_ucs2",
        lambda: SimpleNamespace(
            has_unicode_mappings=lambda: True,
            to_unicode=lambda cid: "mapped" if cid == 123 else None,
        ),
    )
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 100)

    assert font.to_unicode(23) == "mapped"


def test_wave555_explicit_writing_mode_requires_stream_wmode_entry() -> None:
    font = PDType0Font()
    stream = COSStream()
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), stream)

    assert font.has_explicit_writing_mode() is False

    stream.set_int(COSName.get_pdf_name("WMode"), 0)

    assert font.has_explicit_writing_mode() is True


def test_wave555_embedded_cmap_fallback_handles_nonembedded_and_bad_ttf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descendant = PDCIDFontType2()
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: object())
    monkeypatch.setattr(descendant, "is_embedded", lambda: False)
    monkeypatch.setattr(descendant, "code_to_cid", lambda cid: cid)

    assert font._unicode_from_embedded_cmap(4) is None  # noqa: SLF001

    monkeypatch.setattr(
        font,
        "code_to_cid",
        lambda _code: (_ for _ in ()).throw(RuntimeError("bad cmap")),
    )

    assert font._unicode_from_embedded_cmap(4) is None  # noqa: SLF001


def test_wave555_embedded_cmap_fallback_handles_missing_best_cmap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InnerTTF(dict):
        def getGlyphOrder(self) -> list[str]:
            return [".notdef", "A"]

    inner = InnerTTF(cmap=SimpleNamespace(getBestCmap=lambda: None))
    descendant = PDCIDFontType2()
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code)
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: SimpleNamespace(_tt=inner))
    monkeypatch.setattr(descendant, "is_embedded", lambda: True)
    monkeypatch.setattr(descendant, "code_to_gid", lambda cid: cid)

    assert font._unicode_from_embedded_cmap(1) is None  # noqa: SLF001


def test_wave555_subset_rejects_type2_descendant_without_ttf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descendant = PDCIDFontType2()
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(descendant, "get_true_type_font", lambda: None)

    with pytest.raises(ValueError, match="no embedded /FontFile2"):
        font.subset()


def test_wave555_descriptor_population_handles_missing_metric_tables() -> None:
    descriptor = PDFontDescriptor()
    ttf = SimpleNamespace(
        get_header=lambda: None,
        get_horizontal_header=lambda: None,
    )

    type0_module._populate_descriptor_from_ttf(descriptor, ttf)  # noqa: SLF001

    assert descriptor.get_flags() == 4
    assert descriptor.get_cos_object().get_int(COSName.get_pdf_name("StemV")) == 80
