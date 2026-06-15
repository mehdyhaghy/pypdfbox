"""Malformed widget-annotation accessor parity with PDFBox 3.0.7.

Differential oracle for the ``PDAnnotationWidget`` accessors NOT covered by the
existing ``/AP`` / icon / ``/MK`` probes (``WidgetApProbe`` // ``WidgetIconProbe``
// ``WidgetMkProbe``): the OTHER dictionary accessors against malformed widget
dicts —

* ``get_highlighting_mode`` (``/H`` N/I/O/P/T, default ``I``) — upstream reads
  ``getNameAsString(COSName.H, "I")``, so a *string*-typed ``/H`` returns its
  decoded value (not the default). pypdfbox previously used ``get_name`` and
  discarded a string ``/H`` (fixed wave 1536);
* ``get_appearance_state`` (``/AS`` name vs non-name vs absent);
* ``get_border_style`` (``/BS`` dict vs non-dict vs absent);
* ``get_actions`` (``/AA`` dict vs non-dict vs absent);
* ``get_annotation_flags`` + the ``/F`` bit predicates (int / non-int / float /
  negative / absent);
* ``get_parent`` (``/Parent`` dict / non-dict / cyclic / absent).

PINNED DIVERGENCE (``parent_nondict``): PDFBox 3.0.7 has NO ``getParent()`` on
``PDAnnotationWidget`` (only ``setParent``); a raw ``(COSDictionary)`` cast of a
non-dict ``/Parent`` throws ``ClassCastException``. pypdfbox adds a *tolerant*
``get_parent()`` that type-checks and returns ``None`` for a non-dict, so it
never raises. We pin both sides rather than make pypdfbox throw.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_H = COSName.get_pdf_name("H")
_AS = COSName.get_pdf_name("AS")
_BS = COSName.get_pdf_name("BS")
_AA = COSName.get_pdf_name("AA")
_F = COSName.get_pdf_name("F")
_PARENT = COSName.get_pdf_name("Parent")

# Cases where the in-probe raw cast diverges from pypdfbox's tolerant accessor
# (see module docstring). For these the Java "Parent" token is replaced by the
# pinned pypdfbox expectation before comparison.
_PARENT_DIVERGENCE = {
    # raw cast -> ClassCastException; pypdfbox get_parent() -> None
    "parent_nondict": "none",
}


def _build(case_id: str) -> PDAnnotationWidget:
    d = COSDictionary()
    table = {
        "h_n": (_H, COSName.get_pdf_name("N")),
        "h_i": (_H, COSName.get_pdf_name("I")),
        "h_o": (_H, COSName.get_pdf_name("O")),
        "h_p": (_H, COSName.get_pdf_name("P")),
        "h_t": (_H, COSName.get_pdf_name("T")),
        "h_unknown": (_H, COSName.get_pdf_name("Z")),
        "h_lower": (_H, COSName.get_pdf_name("i")),
        "h_string": (_H, COSString("O")),
        "h_int": (_H, COSInteger.get(3)),
        "h_array": (_H, COSArray()),
        "h_null": (_H, COSNull.NULL),
        "as_on": (_AS, COSName.get_pdf_name("On")),
        "as_off": (_AS, COSName.get_pdf_name("Off")),
        "as_string": (_AS, COSString("On")),
        "as_int": (_AS, COSInteger.get(1)),
        "as_null": (_AS, COSNull.NULL),
        "bs_dict": (_BS, COSDictionary()),
        "bs_nondict": (_BS, COSString("x")),
        "bs_array": (_BS, COSArray()),
        "bs_null": (_BS, COSNull.NULL),
        "aa_dict": (_AA, COSDictionary()),
        "aa_nondict": (_AA, COSString("x")),
        "aa_array": (_AA, COSArray()),
        "aa_null": (_AA, COSNull.NULL),
        "f_0": (_F, COSInteger.get(0)),
        "f_2": (_F, COSInteger.get(2)),
        "f_4": (_F, COSInteger.get(4)),
        "f_hidden": (_F, COSInteger.get(2)),
        "f_all": (_F, COSInteger.get(0xFFFF)),
        "f_string": (_F, COSString("2")),
        "f_float": (_F, COSFloat(2.7)),
        "f_neg": (_F, COSInteger.get(-2)),
        "f_null": (_F, COSNull.NULL),
        "parent_dict": (_PARENT, COSDictionary()),
        "parent_nondict": (_PARENT, COSString("x")),
        "parent_null": (_PARENT, COSNull.NULL),
    }
    if case_id == "empty":
        pass
    elif case_id == "parent_cyclic":
        d.set_item(_PARENT, d)
    else:
        key, value = table[case_id]
        d.set_item(key, value)
    return PDAnnotationWidget(d)


def _b(value: bool) -> str:
    return "1" if value else "0"


def _emit(case_id: str, w: PDAnnotationWidget) -> str:
    appearance_state = w.get_appearance_state()
    parent = "dict" if w.get_parent() is not None else "none"
    return (
        f"CASE {case_id}"
        f" H={w.get_highlighting_mode()}"
        f" AS={'none' if appearance_state is None else appearance_state}"
        f" BS={'dict' if w.get_border_style() is not None else 'none'}"
        f" AA={'dict' if w.get_actions() is not None else 'none'}"
        f" F={w.get_annotation_flags()}"
        f" hidden={_b(w.is_hidden())}"
        f" inv={_b(w.is_invisible())}"
        f" print={_b(w.is_printed())}"
        f" noview={_b(w.is_no_view())}"
        f" locked={_b(w.is_locked())}"
        f" Parent={parent}"
    )


_CASE_IDS = (
    "empty",
    "h_n",
    "h_i",
    "h_o",
    "h_p",
    "h_t",
    "h_unknown",
    "h_lower",
    "h_string",
    "h_int",
    "h_array",
    "h_null",
    "as_on",
    "as_off",
    "as_string",
    "as_int",
    "as_null",
    "bs_dict",
    "bs_nondict",
    "bs_array",
    "bs_null",
    "aa_dict",
    "aa_nondict",
    "aa_array",
    "aa_null",
    "f_0",
    "f_2",
    "f_4",
    "f_hidden",
    "f_all",
    "f_string",
    "f_float",
    "f_neg",
    "f_null",
    "parent_dict",
    "parent_nondict",
    "parent_cyclic",
    "parent_null",
)


@pytest.fixture(scope="module")
def java_lines() -> dict[str, str]:
    lines = run_probe_text("WidgetAccessorFuzzProbe").splitlines()
    result: dict[str, str] = {}
    for line in lines:
        case_id = line.split(maxsplit=2)[1]
        # Substitute the pinned pypdfbox expectation for the cases where a raw
        # upstream cast throws but pypdfbox's tolerant accessor returns None.
        if case_id in _PARENT_DIVERGENCE:
            line = line.rsplit(" Parent=", 1)[0] + f" Parent={_PARENT_DIVERGENCE[case_id]}"
        result[case_id] = line
    return result


@requires_oracle
@pytest.mark.parametrize("case_id", _CASE_IDS)
def test_widget_accessor_matches_oracle(
    case_id: str, java_lines: dict[str, str]
) -> None:
    assert _emit(case_id, _build(case_id)) == java_lines[case_id]


def test_highlighting_mode_reads_string_typed_h() -> None:
    """Pin the wave-1536 fix: a string-typed ``/H`` is read via
    ``getNameAsString`` semantics, not discarded as ``get_name`` would."""
    d = COSDictionary()
    d.set_item(_H, COSString("O"))
    assert PDAnnotationWidget(d).get_highlighting_mode() == "O"


def test_parent_non_dict_is_tolerant_none() -> None:
    """Pin the divergence: pypdfbox adds a tolerant ``get_parent()`` that
    returns ``None`` for a non-dict ``/Parent`` where a raw upstream cast
    would throw ``ClassCastException`` (no ``getParent`` exists upstream)."""
    d = COSDictionary()
    d.set_item(_PARENT, COSString("x"))
    assert PDAnnotationWidget(d).get_parent() is None
