"""Live PDFBox differential parity for the typed ``/Font`` accessor of
``PDExtendedGraphicsState`` (``getFontSetting`` → ``PDFontSetting``) plus the
``getBlendMode`` COSArray-fallback path.

The scalar / flag accessors of the ``/ExtGState`` parameter dictionary are
pinned by ``test_ext_gstate_oracle.py`` against ``ExtGStateProbe``. This module
covers the two facets that probe does not exercise:

* ``getFontSetting()`` — upstream returns a typed
  :class:`~pypdfbox.pdmodel.graphics.state.pd_font_setting.PDFontSetting`
  wrapping the ``/Font [font size]`` 2-array (``None`` when ``/Font`` is
  absent). Its ``getFont()`` resolves the slot-0 font dictionary to a typed
  ``PDFont`` and ``getFontSize()`` returns the slot-1 point size.
* ``getBlendMode()`` over a ``/BM`` *array* — PDF 32000-1 §11.3.5 lets a
  viewer supply a fallback chain of blend-mode names; upstream
  ``BlendMode.getInstance(COSArray)`` returns the first recognised name and
  falls back to ``Normal`` when none match. ``ExtGStateProbe`` only ever
  stores ``/BM`` as a single name.

The Java oracle is ``oracle/probes/ExtGStateFontSettingProbe.java``. We
reproduce each ``key=value`` line from pypdfbox's accessors and compare.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
)
from pypdfbox.pdmodel.graphics.state import PDExtendedGraphicsState
from tests.oracle.harness import requires_oracle, run_probe_text


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _build(mode: str) -> COSDictionary:
    """Mirror ``ExtGStateFontSettingProbe.build`` for the given mode."""
    d = COSDictionary()
    d.set_item(_name("Type"), _name("ExtGState"))
    if mode == "font":
        fd = COSDictionary()
        fd.set_item(_name("Type"), _name("Font"))
        fd.set_item(_name("Subtype"), _name("Type1"))
        fd.set_item(_name("BaseFont"), _name("Helvetica"))
        d.set_item(_name("Font"), COSArray([fd, COSFloat(12.0)]))
    elif mode == "bmarray":
        d.set_item(_name("BM"), COSArray([_name("Bogus"), _name("Multiply")]))
    elif mode == "bmarraynone":
        d.set_item(_name("BM"), COSArray([_name("Bogus"), _name("AlsoBogus")]))
    # "nofont" leaves the dictionary at /Type only.
    return d


_MODES = ["font", "nofont", "bmarray", "bmarraynone"]


def _fmt(value: float) -> str:
    """Canonical float rendering matching the probe's ``fmt``."""
    if value == int(value):
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _java_bool(value: bool) -> str:
    return "true" if value else "false"


def _py_report(dictionary: COSDictionary) -> str:
    gs = PDExtendedGraphicsState(dictionary)
    fs = gs.get_font_setting()
    lines = [f"fontSettingNull={_java_bool(fs is None)}"]
    if fs is None:
        lines += [
            "fontSize=null",
            "fontNull=true",
            "fontName=null",
            "fontSubType=null",
        ]
    else:
        font = fs.get_font()
        lines += [
            f"fontSize={_fmt(fs.get_font_size())}",
            f"fontNull={_java_bool(font is None)}",
            f"fontName={'null' if font is None else font.get_name()}",
            f"fontSubType={'null' if font is None else font.get_sub_type()}",
        ]
    # Upstream prints getBlendMode().getCOSName().getName() — never null.
    lines.append(f"blendMode={gs.get_blend_mode().get_cos_name().get_name()}")
    return "\n".join(lines) + "\n"


@requires_oracle
@pytest.mark.parametrize("mode", _MODES, ids=_MODES)
def test_ext_gstate_font_setting_matches_pdfbox(mode: str) -> None:
    java = run_probe_text("ExtGStateFontSettingProbe", mode)
    py = _py_report(_build(mode))
    assert py == java, (
        f"{mode}: PDExtendedGraphicsState font-setting / blend-mode accessors "
        f"diverge from PDFBox.\n--- pypdfbox ---\n{py}\n--- java ---\n{java}"
    )
