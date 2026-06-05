"""Write-side parity for ``PDPageLabels`` / ``PDPageLabelRange`` (wave 1486).

The read side (label-string computation for decimal/Roman/letter/prefix/start)
was pinned earlier; this module covers the WRITE / structure side and the
range-arithmetic edges, every value below confirmed string-for-string against
Apache PDFBox 3.0.7 via ``oracle/probes/PageLabelsWriteProbe.java`` and
``oracle/probes/PageLabelRangeAccessorProbe.java``:

* ``/Nums`` ordering after out-of-order ``set_label_item`` inserts and after
  replacing the default range at key 0 (TreeMap-sorted serialization).
* prefix-only ranges (``/P`` with no ``/S`` -> the prefix repeated).
* a gap before the first explicit range (the constructor's default decimal
  range at key 0 fills pages 0..start-1).
* duplicate label strings across two ranges -> ``get_page_indices_by_labels``
  keeps the *highest* page index.
* accessor defaults: ``get_start()==1``, ``get_style()/get_prefix() is None``,
  ``/St`` absent until written.
* ``set_start(<=0)`` raises (IllegalArgumentException -> ValueError, message
  identical); ``set_prefix(None)``/``set_style(None)`` remove the key.
* ``set_style`` stores ANY string verbatim (upstream does not validate).
* Roman ``/St 4000`` m-per-thousand quirk; letters beyond ZZ (``/St 700`` ->
  27x 'X', then 28x 'A').

These are plain value pins (no oracle required). The trailing
``@requires_oracle`` test re-derives the same report from the live jar.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.pd_page_label_range import PDPageLabelRange
from pypdfbox.pdmodel.pd_page_labels import PDPageLabels
from tests.oracle.harness import requires_oracle, run_probe_text

_S = COSName.get_pdf_name("S")
_P = COSName.get_pdf_name("P")
_ST = COSName.get_pdf_name("St")
_NUMS = COSName.get_pdf_name("Nums")


class _FakeDoc:
    def __init__(self, n: int) -> None:
        self._n = n

    def get_number_of_pages(self) -> int:
        return self._n


def _build(scenario: str, n: int = 8) -> PDPageLabels:
    labels = PDPageLabels(_FakeDoc(n))
    if scenario == "nums_order":
        r5 = PDPageLabelRange()
        r5.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
        labels.set_label_item(5, r5)
        r2 = PDPageLabelRange()
        r2.set_style(PDPageLabelRange.STYLE_LETTERS_UPPER)
        labels.set_label_item(2, r2)
        r0 = PDPageLabelRange()
        r0.set_style(PDPageLabelRange.STYLE_DECIMAL)
        r0.set_start(100)
        labels.set_label_item(0, r0)
    elif scenario == "prefix_only":
        r0 = PDPageLabelRange()
        r0.set_style(PDPageLabelRange.STYLE_DECIMAL)
        labels.set_label_item(0, r0)
        r3 = PDPageLabelRange()
        r3.set_prefix("Appendix-")
        labels.set_label_item(3, r3)
    elif scenario == "gap_before":
        r2 = PDPageLabelRange()
        r2.set_style(PDPageLabelRange.STYLE_ROMAN_UPPER)
        labels.set_label_item(2, r2)
    elif scenario == "dup_labels":
        r0 = PDPageLabelRange()
        r0.set_style(PDPageLabelRange.STYLE_DECIMAL)
        labels.set_label_item(0, r0)
        r4 = PDPageLabelRange()
        r4.set_style(PDPageLabelRange.STYLE_DECIMAL)
        labels.set_label_item(4, r4)
    elif scenario == "start_default":
        pass
    elif scenario == "roman_big":
        r0 = PDPageLabelRange()
        r0.set_style(PDPageLabelRange.STYLE_ROMAN_LOWER)
        r0.set_start(4000)
        labels.set_label_item(0, r0)
    elif scenario == "letters_big":
        r0 = PDPageLabelRange()
        r0.set_style(PDPageLabelRange.STYLE_LETTERS_UPPER)
        r0.set_start(700)
        labels.set_label_item(0, r0)
    else:  # pragma: no cover - defensive
        raise ValueError(scenario)
    return labels


def _report(labels: PDPageLabels) -> dict[str, Any]:
    cos = labels.get_cos_object()
    nums = cos.get_dictionary_object(_NUMS)
    nums_shape: list[tuple[int, str | None, str | None, int | None]] = []
    i = 0
    while i + 1 < nums.size():
        key = nums.get_object(i)
        rd = nums.get_object(i + 1)
        st = rd.get_dictionary_object(_ST)
        nums_shape.append(
            (
                key.value,
                rd.get_name(_S),
                rd.get_string(_P),
                st.value if st is not None else None,
            )
        )
        i += 2
    return {
        "nums": nums_shape,
        "labels": labels.get_labels_by_page_indices(),
        "inv": labels.get_page_indices_by_labels(),
        "range_count": labels.get_page_range_count(),
    }


# ---------------------------------------------------------------------------
# /Nums serialization order
# ---------------------------------------------------------------------------


def test_nums_order_out_of_order_insert_and_key0_replace() -> None:
    rep = _report(_build("nums_order"))
    # Serialized in ascending key order regardless of insert order; the key-0
    # default range was replaced by the decimal /St 100 range.
    assert rep["nums"] == [
        (0, "D", None, 100),
        (2, "A", None, None),
        (5, "r", None, None),
    ]
    assert rep["labels"] == [
        "100", "101", "A", "B", "C", "i", "ii", "iii",
    ]
    assert rep["range_count"] == 3


def test_prefix_only_range_repeats_prefix() -> None:
    rep = _report(_build("prefix_only"))
    assert rep["nums"] == [(0, "D", None, None), (3, None, "Appendix-", None)]
    assert rep["labels"] == [
        "1", "2", "3",
        "Appendix-", "Appendix-", "Appendix-", "Appendix-", "Appendix-",
    ]
    # Duplicate "Appendix-" labels collapse; highest index (7) wins.
    assert rep["inv"]["Appendix-"] == 7
    assert len(rep["inv"]) == 4


def test_gap_before_first_explicit_range_fills_with_default_decimal() -> None:
    # Constructor's default decimal range at key 0 covers pages 0..1; the
    # first explicit (upper-roman) range starts at page 2.
    rep = _report(_build("gap_before"))
    assert rep["nums"] == [(0, "D", None, None), (2, "R", None, None)]
    assert rep["labels"] == ["1", "2", "I", "II", "III", "IV", "V", "VI"]


def test_duplicate_labels_highest_index_wins() -> None:
    rep = _report(_build("dup_labels"))
    assert rep["labels"] == ["1", "2", "3", "4", "1", "2", "3", "4"]
    # Two ranges both render 1..4; inverse map keeps the higher page index.
    assert rep["inv"] == {"1": 4, "2": 5, "3": 6, "4": 7}


def test_default_only_decimal_one_per_page() -> None:
    rep = _report(_build("start_default"))
    assert rep["nums"] == [(0, "D", None, None)]
    assert rep["labels"] == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert rep["range_count"] == 1


def test_roman_start_4000_m_per_thousand() -> None:
    rep = _report(_build("roman_big"))
    assert rep["nums"] == [(0, "r", None, 4000)]
    assert rep["labels"] == [
        "mmmm", "mmmmi", "mmmmii", "mmmmiii",
        "mmmmiv", "mmmmv", "mmmmvi", "mmmmvii",
    ]


def test_letters_beyond_zz_triples() -> None:
    rep = _report(_build("letters_big"))
    assert rep["nums"] == [(0, "A", None, 700)]
    # 700 -> 27x 'X'; 703 (page 3) -> 28x 'A'.
    assert rep["labels"][0] == "X" * 27
    assert rep["labels"][2] == "Z" * 27
    assert rep["labels"][3] == "A" * 28
    assert rep["labels"][7] == "E" * 28


# ---------------------------------------------------------------------------
# PDPageLabelRange accessor / validation parity
# ---------------------------------------------------------------------------


def test_range_accessor_defaults() -> None:
    r = PDPageLabelRange()
    assert r.get_start() == 1
    assert r.get_style() is None
    assert r.get_prefix() is None
    assert not r.get_cos_object().contains_key(_ST)


def test_set_start_nonpositive_raises_with_upstream_message() -> None:
    r = PDPageLabelRange()
    for bad in (0, -3):
        try:
            r.set_start(bad)
            raise AssertionError("expected ValueError")
        except ValueError as e:
            # Message mirrors upstream IllegalArgumentException exactly.
            assert str(e) == (
                "The page numbering start value must be a positive integer"
            )


def test_set_start_one_writes_explicit_st_key() -> None:
    r = PDPageLabelRange()
    r.set_start(1)
    # Even though the value equals the spec default, /St is now present.
    assert r.get_cos_object().contains_key(_ST)
    assert r.get_start() == 1


def test_set_prefix_none_removes_key() -> None:
    r = PDPageLabelRange()
    r.set_prefix("X-")
    assert r.get_cos_object().contains_key(_P)
    r.set_prefix(None)
    assert not r.get_cos_object().contains_key(_P)
    assert r.get_prefix() is None


def test_set_style_none_removes_key() -> None:
    r = PDPageLabelRange()
    r.set_style(PDPageLabelRange.STYLE_ROMAN_UPPER)
    assert r.get_cos_object().contains_key(_S)
    r.set_style(None)
    assert not r.get_cos_object().contains_key(_S)
    assert r.get_style() is None


def test_set_style_accepts_arbitrary_string_like_upstream() -> None:
    # Upstream setStyle does NOT validate: setStyle("Q") -> getStyle()=="Q".
    r = PDPageLabelRange()
    r.set_style("Q")
    assert r.get_style() == "Q"
    # An unrecognised style renders as decimal in the generator (upstream
    # switch default branch).
    r.set_start(5)
    assert r.compute_label_for_offset(0) == "5"


# ---------------------------------------------------------------------------
# Live differential
# ---------------------------------------------------------------------------


def _parse_probe(text: str) -> dict[str, Any]:
    nums: list[tuple[int, str | None, str | None, int | None]] = []
    labels: list[str] = []
    inv: dict[str, int] = {}
    range_count = 0
    for line in text.splitlines():
        if line.startswith("nums"):
            body = line[len("nums"):].strip()
            if not body:
                continue
            for tok in body.split(" "):
                key_str, rest = tok.split("[", 1)
                rest = rest.rstrip("]")
                fields = dict(kv.split("=", 1) for kv in rest.split(","))
                s = None if fields["S"] == "null" else fields["S"]
                p = None if fields["P"] == "null" else fields["P"]
                st = None if fields["St"] == "null" else int(fields["St"])
                nums.append((int(key_str), s, p, st))
        elif line.startswith("label "):
            _, rest = line.split(" ", 1)
            _idx, lab = rest.split("\t", 1)
            labels.append(lab)
        elif line.startswith("inv "):
            rest = line[len("inv "):]
            lab, idx = rest.rsplit("\t", 1)
            inv[lab] = int(idx)
        elif line.startswith("rangeCount="):
            range_count = int(line.split("=", 1)[1])
    return {"nums": nums, "labels": labels, "inv": inv, "range_count": range_count}


@requires_oracle
def test_write_side_matches_pdfbox_live() -> None:
    for scenario in (
        "nums_order",
        "prefix_only",
        "gap_before",
        "dup_labels",
        "start_default",
        "roman_big",
        "letters_big",
    ):
        java = _parse_probe(run_probe_text("PageLabelsWriteProbe", scenario, "8"))
        py = _report(_build(scenario))
        assert py["nums"] == java["nums"], scenario
        assert py["labels"] == java["labels"], scenario
        assert py["inv"] == java["inv"], scenario
        assert py["range_count"] == java["range_count"], scenario
