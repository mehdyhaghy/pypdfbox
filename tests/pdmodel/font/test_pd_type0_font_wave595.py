from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from pypdfbox.cos import COSInteger, COSName, COSStream
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font


def test_wave595_explicit_writing_mode_detects_stream_wmode() -> None:
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("WMode"), COSInteger.get(1))
    font = PDType0Font()
    font.get_cos_object().set_item(COSName.get_pdf_name("Encoding"), stream)

    assert font.has_explicit_writing_mode() is True


def test_wave595_vertical_alias_uses_cmap_wmode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "get_cmap", lambda: SimpleNamespace(get_wmode=lambda: 1))

    assert font.is_vertical() is True
    assert font.is_vertical_writing() is True


def test_wave595_to_unicode_uses_ucs2_fallback_after_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    calls: list[int] = []

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
            to_unicode=lambda cid: f"cid-{cid}",
        ),
    )

    def code_to_cid(code: int) -> int:
        calls.append(code)
        return 321

    monkeypatch.setattr(font, "code_to_cid", code_to_cid)

    assert font.to_unicode(123) == "cid-321"
    assert calls == [123]


def test_wave595_embedded_cmap_fallback_success_for_nonembedded_descendant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class InnerTTF(dict):
        def getGlyphOrder(self) -> list[str]:
            return [".notdef", "A"]

    descendant = PDCIDFontType2()
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 10)
    monkeypatch.setattr(descendant, "is_embedded", lambda: False)
    monkeypatch.setattr(descendant, "code_to_cid", lambda cid: 1 if cid == 15 else 0)
    monkeypatch.setattr(
        descendant,
        "get_true_type_font",
        lambda: SimpleNamespace(
            _tt=InnerTTF(cmap=SimpleNamespace(getBestCmap=lambda: {65: "A"}))
        ),
    )

    assert font._unicode_from_embedded_cmap(5) == "A"  # noqa: SLF001


def test_wave595_get_width_from_font_delegates_after_cid_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    descendant = SimpleNamespace(get_width_from_font=lambda cid: cid + 0.5)
    monkeypatch.setattr(font, "get_descendant_font", lambda: descendant)
    monkeypatch.setattr(font, "code_to_cid", lambda code: code + 2)

    assert font.get_width_from_font(7) == 9.5


def test_wave595_get_width_from_font_without_callable_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    monkeypatch.setattr(font, "get_descendant_font", lambda: object())

    assert font.get_width_from_font(7) == 0.0


def test_wave595_read_stream_seeks_back_overread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font = PDType0Font()
    source = io.BytesIO(b"abcd-rest")
    monkeypatch.setattr(font, "read_code", lambda _data, _offset=0: (0xABCD, 2))

    assert font.read(source) == 0xABCD
    assert source.tell() == 2
