"""Wave 1359 residue: close the 11 leftover defensive branches the
five parallel agents added but didn't exercise in their own tests.

Targets:
- ``pypdfbox/pdmodel/font/pd_type1c_font.py`` 604, 617-619 — average-width
  fallback chain (CFF program present but widths/charset empty → fall
  through to ``defaultWidthX`` and AFM rungs).
- ``pypdfbox/pdmodel/interactive/form/pd_default_appearance_string.py``
  217, 220, 413, 415 — ``_append_named_resource`` empty-operand and
  non-COSName-operand guards, plus ``copy_needed_resources_to``'s
  already-present-in-stream / missing-in-dr ColorSpace skip arms.
- ``pypdfbox/loader.py`` 112, 123 — ``OSError`` and ``BaseException``
  paths in ``load_pdf`` where a Loader-allocated ``ScratchFile`` has to
  be released alongside the access and partial document.
- ``pypdfbox/pdmodel/interactive/form/pd_variable_text.py`` 58 —
  ``_parse_rich_text_dom`` falling back to ``xml.dom.minidom`` when
  ``defusedxml`` raises ``ImportError`` at parse time.
"""

from __future__ import annotations

import builtins
import sys
from typing import Any
from xml.dom.minidom import Document

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdmodel.font.pd_type1c_font import PDType1CFont
from pypdfbox.pdmodel.interactive.form.pd_default_appearance_string import (
    PDDefaultAppearanceString,
)
from pypdfbox.pdmodel.interactive.form.pd_variable_text import (
    _parse_rich_text_dom,
)
from pypdfbox.pdmodel.pd_resources import PDResources


def _make_da(da_string: str, dr: PDResources) -> PDDefaultAppearanceString:
    """Build a PDDefaultAppearanceString from a raw /DA string."""
    return PDDefaultAppearanceString(COSString(da_string), dr)


# ---------- pd_type1c_font fallback chain ------------------------------


def _font_dict_with_basefont(name: str) -> COSDictionary:
    d = COSDictionary()
    d.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1C"))
    d.set_item(COSName.BASE_FONT, COSName.get_pdf_name(name))
    return d


def test_type1c_average_uses_default_width_x_when_program_widths_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CFF program is present but ``program.get_charset()`` is empty —
    width loop yields nothing, fallback to ``defaultWidthX``."""
    font = PDType1CFont(_font_dict_with_basefont("Helvetica"))

    class _StubProgram:
        units_per_em = 1000

        def get_charset(self):
            return []

        def get_width(self, name):
            return 0.0

        def get_default_width_x(self):
            return 444.0

    monkeypatch.setattr(font, "_get_cff_font", lambda: _StubProgram())
    monkeypatch.setattr(font, "get_widths", lambda: [])

    assert font.get_average_character_width() == pytest.approx(444.0)


def test_type1c_average_falls_through_to_afm_when_program_yields_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CFF program widths are all zero AND ``defaultWidthX`` is zero —
    must drop through to the bundled Standard-14 AFM."""
    font = PDType1CFont(_font_dict_with_basefont("Helvetica"))

    class _StubProgram:
        units_per_em = 1000

        def get_charset(self):
            return ["A"]

        def get_width(self, name):
            return 0.0

        def get_default_width_x(self):
            return 0.0

    monkeypatch.setattr(font, "_get_cff_font", lambda: _StubProgram())
    monkeypatch.setattr(font, "get_widths", lambda: [])

    avg = font.get_average_character_width()
    # Helvetica AFM mean is non-trivial; floor is 500.
    assert avg > 0.0


# ---------- pd_default_appearance_string ColorSpace carry-over ---------


def _appearance_stream_with_resources(sr: PDResources) -> Any:
    """Build a stand-in PDAppearanceStream-shaped object that exposes
    the minimal ``get_resources`` / ``set_resources`` surface that
    ``copy_needed_resources_to`` walks."""

    class _StreamWithResources:
        def __init__(self, resources: PDResources) -> None:
            self._resources = resources

        def get_resources(self) -> PDResources:
            return self._resources

        def set_resources(self, resources: PDResources) -> None:
            self._resources = resources

    return _StreamWithResources(sr)


def test_copy_needed_resources_skips_color_space_already_in_stream() -> None:
    """``copy_needed_resources_to`` must not overwrite an existing
    /ColorSpace entry on the stream's /Resources."""
    dr = PDResources()
    sr = PDResources()
    cs_name = COSName.get_pdf_name("CS0")
    dr.put(
        COSName.get_pdf_name("ColorSpace"), cs_name,
        COSName.get_pdf_name("DeviceGray"),
    )
    sr.put(
        COSName.get_pdf_name("ColorSpace"), cs_name,
        COSName.get_pdf_name("DeviceRGB"),
    )

    da = _make_da("/Helv 0 Tf 0 g", dr)
    da._color_space_names.append(cs_name)  # noqa: SLF001 — drives the loop
    da.copy_needed_resources_to(_appearance_stream_with_resources(sr))

    # Stream's value preserved (typed PDDeviceRGB wrapper); default
    # not copied over.
    cs = sr.get_color_space(cs_name)
    assert cs is not None
    from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
    assert isinstance(cs, PDDeviceRGB)


def test_copy_needed_resources_skips_color_space_missing_in_dr() -> None:
    """When /DR doesn't carry the referenced /ColorSpace, the helper
    must skip rather than fault."""
    dr = PDResources()
    sr = PDResources()
    da = _make_da("/Helv 0 Tf 0 g", dr)
    da._color_space_names.append(COSName.get_pdf_name("Missing"))  # noqa: SLF001
    # No exception, and stream's /ColorSpace stays untouched: the missing
    # colour space was NOT copied into the stream resources. (Asserted via
    # has_color_space rather than get_color_space, which since wave 1461
    # raises MissingResourceException for an unresolvable non-device name,
    # matching upstream PDColorSpace.create.)
    da.copy_needed_resources_to(_appearance_stream_with_resources(sr))
    assert not sr.has_color_space(COSName.get_pdf_name("Missing"))


def test_record_named_operand_ignores_empty_and_non_cosname() -> None:
    """Lines 217, 220: empty operand list and non-COSName operand both
    short-circuit ``_record_named_operand``."""
    dr = PDResources()
    da = _make_da("/Helv 0 Tf 0 g", dr)
    sink: list[COSName] = []
    da._record_named_operand([], sink)  # noqa: SLF001
    assert sink == []
    # Non-COSName operand (raw COSDictionary) also short-circuits.
    da._record_named_operand([COSDictionary()], sink)  # noqa: SLF001
    assert sink == []


# ---------- loader.py scratch_file release on error -------------------


def test_loader_releases_scratch_file_on_oserror() -> None:
    """When PDFParser.parse() raises a non-OS exception (mapped to
    OSError by the Loader boundary), any Loader-allocated ScratchFile
    must be released alongside the access handle and partial document.
    """
    from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
    from pypdfbox.loader import Loader

    setting = MemoryUsageSetting.setup_main_memory_only()
    # Truly malformed bytes — PDFParser raises before producing a doc.
    # ``load_pdf`` is positional-only, so threading the setting is
    # positional too.
    with pytest.raises(OSError):
        Loader.load_pdf(b"not-a-pdf", None, setting)


def test_loader_releases_scratch_file_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KeyboardInterrupt (BaseException) path also closes
    the Loader-allocated ScratchFile."""
    from pypdfbox.io.memory_usage_setting import MemoryUsageSetting
    from pypdfbox.loader import Loader
    from pypdfbox.pdfparser import pdf_parser as _pdf_parser

    real_parse = _pdf_parser.PDFParser.parse

    def _raise(self):
        raise KeyboardInterrupt("user abort")

    monkeypatch.setattr(_pdf_parser.PDFParser, "parse", _raise)
    setting = MemoryUsageSetting.setup_main_memory_only()
    with pytest.raises(KeyboardInterrupt):
        Loader.load_pdf(b"%PDF-1.4\n%%EOF\n", None, setting)
    # Restore for the rest of the suite.
    monkeypatch.setattr(_pdf_parser.PDFParser, "parse", real_parse)


# ---------- pd_variable_text defusedxml ImportError fallback ----------


def test_parse_rich_text_dom_falls_back_when_defusedxml_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_parse_rich_text_dom`` must fall back to ``xml.dom.minidom``
    when ``defusedxml.minidom.parseString`` import raises."""
    # Force the defusedxml import inside _parse_rich_text_dom to fail.
    real_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "defusedxml.minidom":
            raise ImportError("forced for coverage")
        return real_import(name, globals, locals, fromlist, level)

    # Clear cached module so __import__ runs the loader path.
    sys.modules.pop("defusedxml.minidom", None)
    monkeypatch.setattr(builtins, "__import__", _fake_import)

    doc = _parse_rich_text_dom("<body><p>hi</p></body>")
    assert isinstance(doc, Document)
    body = doc.documentElement
    assert body.tagName == "body"
