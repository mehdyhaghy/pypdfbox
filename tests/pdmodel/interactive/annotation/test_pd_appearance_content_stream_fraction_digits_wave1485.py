"""Wave 1485 — ``PDAppearanceContentStream`` emits numeric operands at FOUR
fractional digits, not five.

Upstream's ``PDAppearanceContentStream`` extends ``PDAbstractContentStream``,
whose shared base constructor configures the operand formatter with
``setMaximumFractionDigits(4)`` (PDFBox 3.0.7 ``PDAbstractContentStream``
Java line 112). The concrete ``PDPageContentStream`` bumps that to 5 via
``setMaximumFractionDigits(5)``. In this lite port the appearance writer
extends ``PDPageContentStream`` for cohesion, so its ``__init__`` resets the
instance ``_max_fraction_digits`` back to the base default (4) to preserve
upstream byte parity.

This was a divergent 5-digit pin (DEFERRED.md, wave 1483 agent B). The
oracle-confirmed values below were captured from a REAL upstream
``PDAppearanceContentStream`` (mode ``abstract`` of
``AbstractContentStreamFormatProbe`` drives ``new
PDAppearanceContentStream(appearance, baos)``), and from a direct probe of
``setNonStrokingColor(153/255f, 193/255f, 215/255f)`` which emits
``0.6 0.7569 0.8431 rg`` (4 digits) — the exact listbox-highlight colour the
appearance generator writes.

The page writer (``PDPageContentStream``) keeps its 5-digit default — pinned
here too so the thread-through did not regress it.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_abstract_content_stream import PDAbstractContentStream


def _new_appearance() -> PDAppearanceStream:
    return PDAppearanceStream(COSStream())


def _body(appearance: PDAppearanceStream) -> bytes:
    return appearance.get_stream().to_byte_array()


# (value, expected-4-digit-bytes) — single-precision narrowed, half-up on the
# narrowed fraction. Same algorithm as _format_number, only the digit count
# differs from the page writer (5).
_CASES: list[tuple[float, bytes]] = [
    (0.000005, b"0"),
    (0.123455, b"0.1235"),
    (12345.6789, b"12345.6787"),
    (0.33333334, b"0.3333"),
    (3.14, b"3.14"),
    (193 / 255, b"0.7569"),
    (215 / 255, b"0.8431"),
    (153 / 255, b"0.6"),
]


def test_appearance_writer_default_is_four_digits() -> None:
    appearance = _new_appearance()
    cs = PDAppearanceContentStream(appearance)
    assert (
        cs._max_fraction_digits
        == PDAbstractContentStream.DEFAULT_MAX_FRACTION_DIGITS
        == 4
    )
    cs.close()


@pytest.mark.parametrize(
    ("value", "expected"),
    _CASES,
    ids=[repr(v) for v, _ in _CASES],
)
def test_line_width_operand_four_digits(value: float, expected: bytes) -> None:
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_line_width(value)
    assert _body(appearance) == expected + b" w\n"


def test_highlight_color_emits_four_digit_components() -> None:
    # The listbox-selection highlight colour the appearance generator writes.
    # Oracle-confirmed: PDAppearanceContentStream.setNonStrokingColor(
    #   153/255f, 193/255f, 215/255f) -> "0.6 0.7569 0.8431 rg".
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_non_stroking_color((153 / 255, 193 / 255, 215 / 255))
    assert _body(appearance) == b"0.6 0.7569 0.8431 rg\n"


def test_dash_pattern_operands_four_digits() -> None:
    # set_dash_pattern routes per-element bytes through _format_number with the
    # instance digit count; the appearance writer's 4 must apply.
    appearance = _new_appearance()
    with PDAppearanceContentStream(appearance) as cs:
        cs.set_dash_pattern([0.123455], 0.33333334)
    assert _body(appearance) == b"[0.1235 ] 0.3333 d\n"


def test_page_writer_keeps_five_digits() -> None:
    # Guard the thread-through: PDPageContentStream's default must stay 5.
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.pd_document import PDDocument
    from pypdfbox.pdmodel.pd_page import PDPage
    from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream

    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    with PDPageContentStream(doc, page) as cs:
        assert cs._max_fraction_digits == 5
        cs.set_line_width(0.123455)
    contents = page.get_cos_object().get_dictionary_object(COSName.CONTENTS)
    body = contents.to_byte_array()
    assert b"0.12346 w" in body


# --------------------------------------------------------------------------
# Optional live differential — skipped when the Java oracle is unavailable.
# --------------------------------------------------------------------------

try:
    from tests.oracle.harness import requires_oracle, run_probe_text
except Exception:  # pragma: no cover - harness import guard
    requires_oracle = pytest.mark.skip(reason="oracle harness unavailable")

    def run_probe_text(*_a: str, **_k: str) -> str:  # type: ignore[misc]
        raise RuntimeError


@requires_oracle
def test_appearance_writer_matches_live_oracle() -> None:
    # Mode "abstract" drives a REAL upstream PDAppearanceContentStream at 4
    # digits via setLineWidth.
    values = [v for v, _ in _CASES]
    args = [repr(float(v)) for v in values]
    oracle = run_probe_text(
        "AbstractContentStreamFormatProbe", "abstract", *args
    )
    expected = [line for line in oracle.splitlines() if line != ""]

    actual: list[str] = []
    for v in values:
        appearance = _new_appearance()
        with PDAppearanceContentStream(appearance) as cs:
            cs.set_line_width(v)
        body = _body(appearance)
        actual.append(body.split(b" w")[0].decode("ascii"))
    assert actual == expected
