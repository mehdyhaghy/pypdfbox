"""Fuzz / parity pins for ``PDPageLabels`` label computation (wave 1576).

Every expected string below was confirmed against Apache PDFBox 3.0.7's
``org.apache.pdfbox.pdmodel.common.PDPageLabels`` /
``PDPageLabelRange`` label-generation behaviour:

* single decimal range starting at index 0;
* multiple ranges (Roman i..iv then decimal 1..N);
* ``/P`` prefix concatenation and prefix-only (no ``/S``) ranges;
* ``/St`` start value (default 1) and ``/St`` offset arithmetic inside a
  range (page index ``k`` in a range starting at index ``s`` with ``/St==v``
  -> value ``v + (k - s)``);
* Roman numeral generation lower + upper, including subtractive cases
  (4->iv, 9->ix, 40->xl, 90->xc, 400->cd, 900->cm, 1990->mcmxc);
* letter style following PDFBox's *doubling* scheme (1->a, 26->z, 27->aa,
  28->bb, 52->zz, 53->aaa) -- NOT base-26 bijective (28 is "bb", not "ab");
* a page before the first explicit range (filled by the default decimal
  range the constructor installs at index 0);
* the full document label array.

These are plain value pins. The trailing ``@requires_oracle`` test
re-derives the decimal/roman/letter renderings from the live jar.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange
from pypdfbox.pdmodel.pd_page_labels import (
    PDPageLabels,
    _make_letter_label,
    _make_roman_label,
    to_letters,
    to_roman,
)


class _FakeDoc:
    def __init__(self, n: int) -> None:
        self._n = n

    def get_number_of_pages(self) -> int:
        return self._n


def _labels(n: int) -> PDPageLabels:
    return PDPageLabels(_FakeDoc(n))


def _range(
    style: str | None = None,
    prefix: str | None = None,
    start: int | None = None,
) -> PDPageLabelRange:
    r = PDPageLabelRange()
    if style is not None:
        r.set_style(style)
    if prefix is not None:
        r.set_prefix(prefix)
    if start is not None:
        r.set_start(start)
    return r


# ---------------------------------------------------------------- roman lower


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "i"),
        (2, "ii"),
        (3, "iii"),
        (4, "iv"),
        (5, "v"),
        (9, "ix"),
        (10, "x"),
        (14, "xiv"),
        (40, "xl"),
        (49, "xlix"),
        (90, "xc"),
        (400, "cd"),
        (900, "cm"),
        (1990, "mcmxc"),
        (2024, "mmxxiv"),
        (3888, "mmmdccclxxxviii"),
    ],
)
def test_roman_lower(n: int, expected: str) -> None:
    assert _make_roman_label(n) == expected
    assert to_roman(n).lower() == expected


def test_roman_upper_matches_lower_uppercased() -> None:
    for n in (1, 4, 9, 40, 90, 400, 900, 1990, 2024):
        assert to_roman(n) == _make_roman_label(n).upper()


def test_roman_m_per_thousand_quirk() -> None:
    # Upstream prepends one 'm' per thousand for n >= 4000 (matches Acrobat).
    assert _make_roman_label(4000) == "mmmm"
    assert _make_roman_label(4001) == "mmmmi"


def test_roman_non_positive_is_empty() -> None:
    assert _make_roman_label(0) == ""
    assert to_roman(0) == ""
    assert to_roman(-5) == ""


# --------------------------------------------------------------- letter style


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "a"),
        (2, "b"),
        (25, "y"),
        (26, "z"),
        (27, "aa"),
        (28, "bb"),
        (51, "yy"),
        (52, "zz"),
        (53, "aaa"),
        (78, "zzz"),
        (79, "aaaa"),
    ],
)
def test_letter_doubling_scheme(n: int, expected: str) -> None:
    # PDFBox uses the doubling scheme: 27->aa, 28->bb (NOT base-26 28->ab).
    assert _make_letter_label(n) == expected
    assert to_letters(n).lower() == expected


def test_letter_upper() -> None:
    assert to_letters(1) == "A"
    assert to_letters(27) == "AA"
    assert to_letters(28) == "BB"


def test_letter_non_positive_is_empty() -> None:
    assert _make_letter_label(0) == ""
    assert to_letters(-1) == ""


# ----------------------------------------------------------- range arithmetic


def test_single_decimal_range_from_zero() -> None:
    labels = _labels(5)
    assert labels.get_labels_by_page_indices() == ["1", "2", "3", "4", "5"]


def test_default_only_constructor() -> None:
    labels = _labels(3)
    assert labels.is_default_only()
    assert labels.get_labels_by_page_indices() == ["1", "2", "3"]


def test_roman_then_decimal() -> None:
    labels = _labels(7)
    labels.set_label_item(0, _range(PDPageLabelRange.STYLE_ROMAN_LOWER))
    labels.set_label_item(4, _range(PDPageLabelRange.STYLE_DECIMAL))
    assert labels.get_labels_by_page_indices() == [
        "i",
        "ii",
        "iii",
        "iv",
        "1",
        "2",
        "3",
    ]


def test_prefix_concatenation() -> None:
    labels = _labels(3)
    labels.set_label_item(
        0, _range(PDPageLabelRange.STYLE_DECIMAL, prefix="A-")
    )
    assert labels.get_labels_by_page_indices() == ["A-1", "A-2", "A-3"]


def test_prefix_only_no_style() -> None:
    labels = _labels(3)
    labels.set_label_item(0, _range(prefix="cover"))
    # No /S -> prefix repeated verbatim, no number appended.
    assert labels.get_labels_by_page_indices() == ["cover", "cover", "cover"]


def test_start_value_default_is_one() -> None:
    assert PDPageLabelRange().get_start() == 1
    labels = _labels(2)
    labels.set_label_item(0, _range(PDPageLabelRange.STYLE_DECIMAL))
    assert labels.get_labels_by_page_indices() == ["1", "2"]


def test_start_value_offset_within_range() -> None:
    # Range starts at index 3 with /St 10; page index 5 -> 10 + (5-3) = 12.
    labels = _labels(8)
    labels.set_label_item(
        3, _range(PDPageLabelRange.STYLE_DECIMAL, start=10)
    )
    out = labels.get_labels_by_page_indices()
    assert out[3] == "10"
    assert out[4] == "11"
    assert out[5] == "12"


def test_start_value_offset_via_get_label_for_page() -> None:
    labels = _labels(8)
    labels.set_label_item(
        3, _range(PDPageLabelRange.STYLE_DECIMAL, start=10)
    )
    assert labels.get_label_for_page(5) == "12"


def test_roman_range_with_start() -> None:
    labels = _labels(4)
    labels.set_label_item(
        0, _range(PDPageLabelRange.STYLE_ROMAN_UPPER, start=7)
    )
    assert labels.get_labels_by_page_indices() == ["VII", "VIII", "IX", "X"]


def test_letters_range_with_start() -> None:
    labels = _labels(3)
    labels.set_label_item(
        0, _range(PDPageLabelRange.STYLE_LETTERS_LOWER, start=25)
    )
    # 25->y, 26->z, 27->aa
    assert labels.get_labels_by_page_indices() == ["y", "z", "aa"]


def test_letters_upper_range() -> None:
    labels = _labels(4)
    labels.set_label_item(
        0, _range(PDPageLabelRange.STYLE_LETTERS_UPPER, start=26)
    )
    # 26->Z, 27->AA, 28->BB, 29->CC
    assert labels.get_labels_by_page_indices() == ["Z", "AA", "BB", "CC"]


def test_page_before_first_range_uses_default() -> None:
    # The default decimal range at index 0 covers pages before the first
    # explicit range.
    labels = _labels(5)
    labels.set_label_item(
        2, _range(PDPageLabelRange.STYLE_ROMAN_LOWER, prefix="R-")
    )
    out = labels.get_labels_by_page_indices()
    assert out[0] == "1"
    assert out[1] == "2"
    assert out[2] == "R-i"
    assert out[3] == "R-ii"
    assert out[4] == "R-iii"


def test_get_label_by_page_index_out_of_range() -> None:
    labels = _labels(3)
    assert labels.get_label_by_page_index(-1) is None
    assert labels.get_label_by_page_index(3) is None
    assert labels.get_label_by_page_index(0) == "1"


def test_get_label_for_page_negative() -> None:
    labels = _labels(3)
    assert labels.get_label_for_page(-1) == "0"


def test_full_three_range_document() -> None:
    # Front-matter roman (i..), body decimal (1..), appendix letters with
    # prefix.
    labels = _labels(9)
    labels.set_label_item(0, _range(PDPageLabelRange.STYLE_ROMAN_LOWER))
    labels.set_label_item(3, _range(PDPageLabelRange.STYLE_DECIMAL))
    labels.set_label_item(
        7, _range(PDPageLabelRange.STYLE_LETTERS_UPPER, prefix="App-")
    )
    assert labels.get_labels_by_page_indices() == [
        "i",
        "ii",
        "iii",
        "1",
        "2",
        "3",
        "4",
        "App-A",
        "App-B",
    ]


def test_get_page_indices_by_labels_inverse() -> None:
    labels = _labels(4)
    labels.set_label_item(0, _range(PDPageLabelRange.STYLE_DECIMAL))
    inv = labels.get_page_indices_by_labels()
    assert inv == {"1": 0, "2": 1, "3": 2, "4": 3}


def test_range_compute_label_for_offset_matches_full() -> None:
    r = _range(PDPageLabelRange.STYLE_ROMAN_LOWER, prefix="x", start=3)
    # offset 0 -> 3 -> iii; offset 2 -> 5 -> v
    assert r.compute_label_for_offset(0) == "xiii"
    assert r.compute_label_for_offset(2) == "xv"


def test_prefix_nul_trim() -> None:
    # PDFBOX-1047: prefix trimmed at first NUL byte.
    labels = _labels(1)
    labels.set_label_item(
        0, _range(PDPageLabelRange.STYLE_DECIMAL, prefix="A\x00B")
    )
    assert labels.get_labels_by_page_indices() == ["A1"]


def test_unknown_style_falls_back_to_decimal() -> None:
    labels = _labels(2)
    r = PDPageLabelRange()
    r.set_style("Z")  # not a valid style code
    labels.set_label_item(0, r)
    assert labels.get_labels_by_page_indices() == ["1", "2"]


# --------------------------------------------------------------- oracle parity
#
# Reuse the existing oracle/probes/PageLabelFuzzProbe.java RANGE section, which
# emits ``RANGE <name> <start>=<label>|...`` lines for roman/letter/decimal
# number formatting at boundary /St values. We re-derive the same renderings in
# pypdfbox and assert string-for-string equality with the live PDFBox jar.

from tests.oracle.harness import requires_oracle, run_probe_text  # noqa: E402

_STYLE_BY_NAME = {
    "roman_lower": PDPageLabelRange.STYLE_ROMAN_LOWER,
    "roman_upper": PDPageLabelRange.STYLE_ROMAN_UPPER,
    "letters_lower": PDPageLabelRange.STYLE_LETTERS_LOWER,
    "letters_upper": PDPageLabelRange.STYLE_LETTERS_UPPER,
    "decimal": PDPageLabelRange.STYLE_DECIMAL,
}


def _py_render_single(style: str, start: int) -> str:
    labels = _labels(1)
    labels.set_label_item(0, _range(style, start=start))
    out = labels.get_labels_by_page_indices()
    return out[0] if out else ""


@requires_oracle
def test_oracle_range_number_formatting() -> None:
    text = run_probe_text("PageLabelFuzzProbe")
    checked = 0
    for line in text.splitlines():
        if not line.startswith("RANGE "):
            continue
        _, name, rest = line.split(" ", 2)
        style = _STYLE_BY_NAME.get(name)
        if style is None:
            continue
        for cell in rest.split("|"):
            start_str, _, expected = cell.partition("=")
            start = int(start_str)
            # /St must be positive for set_start; the probe only uses >=1 here.
            assert _py_render_single(style, start) == expected, (name, start)
            checked += 1
    assert checked > 0
