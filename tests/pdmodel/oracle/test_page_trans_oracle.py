"""Live PDFBox differential parity for page ``/Trans`` transition dictionary.

PDF 32000-1 §12.4.4.1 declares the per-page transition (slideshow / preview)
effect under ``/Trans``. The transition dictionary carries:

* ``/S``   transition style — ``Split`` / ``Blinds`` / ``Box`` / ``Wipe`` /
  ``Dissolve`` / ``Glitter`` / ``R`` (replace, the default) / ``Fly`` /
  ``Push`` / ``Cover`` / ``Uncover`` / ``Fade``
* ``/D``   duration of the transition effect in seconds (default ``1``)
* ``/Dm``  dimension — ``H`` horizontal or ``V`` vertical (default ``H``;
  only applies to ``Split`` / ``Blinds``)
* ``/M``   motion — ``I`` inward or ``O`` outward (default ``I``; only applies
  to ``Split`` / ``Box`` / ``Fly``)
* ``/Di``  direction in degrees (default ``0`` left-to-right; spec sentinel
  ``/None`` permitted for ``Fly`` with non-unit ``SS``; only applies to
  ``Wipe`` / ``Glitter`` / ``Fly`` / ``Push`` / ``Cover`` / ``Uncover``)
* ``/SS``  fly scale (default ``1``; only applies to ``Fly``)
* ``/B``   fly-area-opaque boolean (default ``false``; only applies to ``Fly``)

PDFBox's ``PDTransition`` exposes typed accessors over these keys. This test
builds a multi-page PDF whose pages exercise the cases the PRD asks for —
(a) ``Split`` horizontal inward, (b) ``Blinds`` vertical, (c) ``Dissolve``
with ``/D 2.5``, (d) ``Wipe`` with ``/Di 90`` — plus a ``Fly`` page (the only
style that exercises ``/SS`` and ``/B``) and a no-``/Trans`` default page, then
asserts that the PageTransProbe's PDFBox 3.0.7 read and pypdfbox's
``get_transition()`` accessors agree line-for-line.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from pypdfbox.pdmodel.interactive.pagenavigation import (
    PDTransition,
    PDTransitionDimension,
    PDTransitionDirection,
    PDTransitionMotion,
    PDTransitionStyle,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text


def _build_fixture(path: Path) -> None:
    """Write the differential fixture: six pages exercising the matrix the
    probe and the parity comparison are aimed at."""
    doc = PDDocument()
    try:
        # (a) Split horizontal inward
        page_a = PDPage()
        trans_a = PDTransition()
        trans_a.set_style(PDTransitionStyle.SPLIT)
        trans_a.set_dimension(PDTransitionDimension.H)
        trans_a.set_motion(PDTransitionMotion.I)
        page_a.set_transition(trans_a)
        doc.add_page(page_a)

        # (b) Blinds vertical
        page_b = PDPage()
        trans_b = PDTransition()
        trans_b.set_style(PDTransitionStyle.BLINDS)
        trans_b.set_dimension(PDTransitionDimension.V)
        page_b.set_transition(trans_b)
        doc.add_page(page_b)

        # (c) Dissolve with /D 2.5
        page_c = PDPage()
        trans_c = PDTransition()
        trans_c.set_style(PDTransitionStyle.DISSOLVE)
        trans_c.set_duration(2.5)
        page_c.set_transition(trans_c)
        doc.add_page(page_c)

        # (d) Wipe with /Di 90
        page_d = PDPage()
        trans_d = PDTransition()
        trans_d.set_style(PDTransitionStyle.WIPE)
        trans_d.set_direction(PDTransitionDirection.BOTTOM_TO_TOP)
        page_d.set_transition(trans_d)
        doc.add_page(page_d)

        # (e) Fly with /SS 1.5 and /B true (the only style that honours both)
        page_e = PDPage()
        trans_e = PDTransition()
        trans_e.set_style(PDTransitionStyle.FLY)
        trans_e.set_fly_scale(1.5)
        trans_e.set_fly_area_opaque(True)
        page_e.set_transition(trans_e)
        doc.add_page(page_e)

        # (f) No /Trans — the absent-default page
        doc.add_page(PDPage())

        buf = io.BytesIO()
        doc.save(buf)
        path.write_bytes(buf.getvalue())
    finally:
        doc.close()


def _direction_repr(value: int) -> str:
    """Mirror the probe's ``direction()`` rendering — integer degrees for
    every numeric ``/Di`` and the literal ``None`` for the spec sentinel."""
    if value == PDTransitionDirection.NONE:
        return "None"
    return str(value)


def _py_report(path: Path) -> str:
    """Render the same per-page transition report from pypdfbox the probe
    emits from PDFBox 3.0.7. Two lines per page when ``/Trans`` is present
    (header + accessor values), one line when absent."""
    lines: list[str] = []
    doc = PDDocument.load(path)
    try:
        for index, page in enumerate(doc.get_pages()):
            trans = page.get_transition()
            if trans is None:
                lines.append(f"page {index} trans no")
                continue
            lines.append(f"page {index} trans yes")
            lines.append(
                f"page {index} "
                f"S {trans.get_style()} "
                f"D {_fmt_float(trans.get_duration())} "
                f"Dm {trans.get_dimension()} "
                f"M {trans.get_motion()} "
                f"Di {_direction_repr(trans.get_direction())} "
                f"SS {_fmt_float(trans.get_fly_scale())} "
                f"B {'true' if trans.is_fly_area_opaque() else 'false'}"
            )
    finally:
        doc.close()
    return "\n".join(lines) + "\n"


def _fmt_float(value: float) -> str:
    """Match the probe's ``fmt`` — integral floats render without the trailing
    ``.0`` and non-integral ones with up to 4 decimals, trailing zeros stripped.
    The probe receives Java ``float`` (32-bit) while pypdfbox carries Python
    ``float`` (64-bit); both render the same canonical text here because every
    case value (1, 2.5, 1.5) is exactly representable in IEEE-754 binary32."""
    if value == int(value):
        return str(int(value))
    formatted = f"{value:.4f}"
    formatted = formatted.rstrip("0").rstrip(".")
    return formatted


@requires_oracle
def test_page_trans_match_pdfbox(tmp_path: Path) -> None:
    """Per-page ``/Trans`` accessor report from PDFBox 3.0.7 and pypdfbox must
    agree byte-for-byte across every style+option combination plus the absent
    default."""
    fixture = tmp_path / "page_trans.pdf"
    _build_fixture(fixture)

    java = run_probe_text("PageTransProbe", str(fixture))
    py = _py_report(fixture)
    assert py == java, (
        "page /Trans accessor report diverges from PDFBox.\n"
        f"--- pypdfbox ---\n{py}--- java ---\n{java}"
    )


@pytest.mark.parametrize(
    "style",
    list(PDTransitionStyle.values()),
)
def test_style_round_trips(style: str) -> None:
    """Every spec-defined ``/S`` value round-trips through ``set_style`` /
    ``get_style`` without drift — the probe can only observe what we serialise
    so this pins the enum-mapping contract directly."""
    trans = PDTransition()
    trans.set_style(style)
    assert trans.get_style() == style


def test_absent_trans_dict_defaults_match_upstream() -> None:
    """A freshly minted ``PDTransition`` carries no per-key entries, so every
    accessor must return upstream's documented default: ``/S`` = ``R``,
    ``/D`` = 1, ``/Dm`` = ``H``, ``/M`` = ``I``, ``/Di`` = 0
    (``LEFT_TO_RIGHT``), ``/SS`` = 1, ``/B`` = false."""
    # Construct with an empty dict (no /S written by __init__) to expose pure
    # defaults from the accessors.
    from pypdfbox.cos import COSDictionary

    trans = PDTransition(COSDictionary())
    assert trans.get_style() == PDTransitionStyle.R
    assert trans.get_duration() == 1
    assert trans.get_dimension() == PDTransitionDimension.H
    assert trans.get_motion() == PDTransitionMotion.I
    assert trans.get_direction() == PDTransitionDirection.LEFT_TO_RIGHT
    assert trans.get_fly_scale() == 1
    assert trans.is_fly_area_opaque() is False


def test_direction_none_sentinel_round_trip() -> None:
    """The ``/None`` direction sentinel (only meaningful for ``Fly`` with
    non-unit ``/SS``) must round-trip through ``set_direction`` /
    ``get_direction`` and surface as ``COSName.NONE`` in the raw COS view —
    matching upstream ``PDTransitionDirection.NONE.getCOSBase()``."""
    from pypdfbox.cos import COSName

    trans = PDTransition()
    trans.set_direction(PDTransitionDirection.NONE)
    assert trans.get_direction() == PDTransitionDirection.NONE
    raw = trans.get_direction_cos()
    assert isinstance(raw, COSName)
    assert raw.name == "None"


def test_page_set_then_clear_transition_round_trips() -> None:
    """``PDPage.set_transition`` followed by ``get_transition`` returns an
    equivalent ``PDTransition``; ``set_transition(None)`` removes ``/Trans``
    so ``has_transition`` reports false."""
    page = PDPage()
    trans = PDTransition()
    trans.set_style(PDTransitionStyle.FADE)
    trans.set_duration(3.0)
    page.set_transition(trans)
    assert page.has_transition() is True
    got = page.get_transition()
    assert got is not None
    assert got.get_style() == PDTransitionStyle.FADE
    assert got.get_duration() == 3.0

    page.set_transition(None)
    assert page.has_transition() is False
    assert page.get_transition() is None
