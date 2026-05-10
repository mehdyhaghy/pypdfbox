"""Wave 1275 — explicit ``to_string()`` parity for FontInfo."""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.font_box_font import FontBoxFont
from pypdfbox.fontbox.font_format import FontFormat
from pypdfbox.fontbox.font_info import FontInfo


class _StubInfo(FontInfo):
    def __init__(
        self,
        psn: str = "Helvetica",
        fmt: FontFormat = FontFormat.TTF,
        family_class: int = 0,
        mac_style: int = 0,
        cid: Any | None = None,
    ) -> None:
        self._psn = psn
        self._fmt = fmt
        self._fam = family_class
        self._mac = mac_style
        self._cid = cid

    def get_post_script_name(self) -> str:
        return self._psn

    def get_format(self) -> FontFormat:
        return self._fmt

    def get_cid_system_info(self) -> Any | None:
        return self._cid

    def get_font(self) -> FontBoxFont:  # pragma: no cover - unused
        raise NotImplementedError

    def get_family_class(self) -> int:
        return self._fam

    def get_weight_class(self) -> int:
        return -1

    def get_code_page_range1(self) -> int:
        return 0

    def get_code_page_range2(self) -> int:
        return 0

    def get_mac_style(self) -> int:
        return self._mac

    def get_panose(self) -> Any | None:
        return None


def test_to_string_matches_upstream_format() -> None:
    info = _StubInfo("MyFont", FontFormat.OTF, family_class=0x12, mac_style=0x3)
    assert info.to_string() == "MyFont (OTF, mac: 0x3, os/2: 0x12, cid: None)"


def test_str_delegates_to_to_string() -> None:
    info = _StubInfo("Helvetica", FontFormat.TTF)
    assert str(info) == info.to_string()


def test_to_string_uses_format_name() -> None:
    info = _StubInfo(fmt=FontFormat.PFB)
    assert "PFB" in info.to_string()
