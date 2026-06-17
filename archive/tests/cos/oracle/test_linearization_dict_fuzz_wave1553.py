"""Live PDFBox differential fuzz for linearization dictionary access (wave 1553).

Second wave of malformed-input fuzz for :class:`PDLinearizationDictionary`,
complementing ``test_linearization_dictionary_fuzz_wave1519`` with angles that
probe did not exercise: boolean / name / float linearization markers, zero and
negative float markers, mixed and degenerate ``/H`` arrays, huge float
coordinates (saturating ``intValue`` narrowing) and negative numeric coords.

Each line is pinned BOTH-SIDES against the live Apache PDFBox 3.0.7 oracle
(``LinearizationDictFuzzProbe.java``). Where Java's ``Float.toString`` of a
huge marker emits scientific notation that Python's ``:.1f`` does not, the
``version`` token is compared as a parsed float, not byte-for-byte — an honest
text-formatting divergence noted inline; the underlying numeric value matches.
"""

from __future__ import annotations

import struct

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.cos.pd_linearization_dictionary import PDLinearizationDictionary
from tests.oracle.harness import requires_oracle, run_probe_text

_CASES = [
    "empty",
    "bool_true_marker",
    "bool_false_marker",
    "name_marker",
    "float_one_marker",
    "float_zero_marker",
    "float_neg_marker",
    "name_coords",
    "neg_coords",
    "mixed_h4",
    "empty_h",
    "single_h",
    "neg_h",
    "bool_h_member",
    "nested_h_member",
    "huge_float_coords",
    "marker_only",
    "coords_no_marker",
    "huge_marker",
]


def _array(*values) -> COSArray:
    array = COSArray()
    for value in values:
        array.add(value)
    return array


def _dict(name: str) -> COSDictionary:
    n = COSName.get_pdf_name
    d = COSDictionary()
    if name == "bool_true_marker":
        d.set_item(n("Linearized"), COSBoolean.TRUE)
    elif name == "bool_false_marker":
        d.set_item(n("Linearized"), COSBoolean.FALSE)
    elif name == "name_marker":
        d.set_item(n("Linearized"), n("One"))
    elif name == "float_one_marker":
        d.set_item(n("Linearized"), COSFloat(1.0))
        d.set_item(n("L"), COSInteger.get(500))
    elif name == "float_zero_marker":
        d.set_item(n("Linearized"), COSFloat(0.0))
    elif name == "float_neg_marker":
        d.set_item(n("Linearized"), COSFloat(-2.5))
    elif name == "name_coords":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("L"), n("Big"))
        d.set_item(n("O"), n("Seven"))
        d.set_item(n("E"), COSBoolean.TRUE)
        d.set_item(n("N"), COSString("3"))
        d.set_item(n("T"), _array(COSInteger.ONE))
    elif name == "neg_coords":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("L"), COSInteger.get(-100))
        d.set_item(n("O"), COSInteger.get(-7))
        d.set_item(n("E"), COSInteger.get(-80))
        d.set_item(n("N"), COSInteger.get(-3))
        d.set_item(n("T"), COSInteger.get(-91))
    elif name == "mixed_h4":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(
            n("H"),
            _array(COSInteger.get(11), COSFloat(22.9), COSInteger.get(33), COSFloat(44.1)),
        )
    elif name == "empty_h":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), COSArray())
    elif name == "single_h":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), _array(COSInteger.get(11)))
    elif name == "neg_h":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), _array(COSInteger.get(-11), COSInteger.get(-22)))
    elif name == "bool_h_member":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), _array(COSInteger.ONE, COSBoolean.TRUE))
    elif name == "nested_h_member":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("H"), _array(COSInteger.ONE, _array(COSInteger.TWO)))
    elif name == "huge_float_coords":
        d.set_item(n("Linearized"), COSInteger.ONE)
        d.set_item(n("L"), COSFloat(3e38))
        d.set_item(n("O"), COSFloat(-3e38))
        d.set_item(n("H"), _array(COSFloat(3e38), COSFloat(-3e38)))
    elif name == "marker_only":
        d.set_item(n("Linearized"), COSInteger.ONE)
    elif name == "coords_no_marker":
        d.set_item(n("L"), COSInteger.get(100))
        d.set_item(n("N"), COSInteger.get(3))
    elif name == "huge_marker":
        d.set_item(n("Linearized"), COSInteger.get(2147483648))
    return d


def _hint(value: tuple[int, ...] | None) -> str:
    if value is None:
        return "absent"
    return ",".join(str(item) for item in value)


def _py_line(name: str) -> str:
    lin = PDLinearizationDictionary(_dict(name))
    return (
        f"CASE {name} linearized={str(lin.is_linearized()).lower()} "
        f"version={lin.get_linearized_version():.1f} "
        f"L={lin.get_length_of_file()} "
        f"O={lin.get_first_page_object_number()} "
        f"E={lin.get_end_of_first_page()} "
        f"N={lin.get_number_of_pages()} "
        f"T={lin.get_offset_of_first_xref()} "
        f"H={_hint(lin.get_hint_table())}"
    )


# PDFBox-3.0.7 oracle baseline (LinearizationDictFuzzProbe). Kept inline so the
# value layer stays green when the live oracle is unavailable; the @requires_oracle
# test below re-derives these from the running jar.
_EXPECTED_LINES = [
    "CASE empty linearized=false version=0.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE bool_true_marker linearized=false version=0.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE bool_false_marker linearized=false version=0.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE name_marker linearized=false version=0.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE float_one_marker linearized=true version=1.0 L=500 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE float_zero_marker linearized=false version=0.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE float_neg_marker linearized=true version=-2.5 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE name_coords linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE neg_coords linearized=true version=1.0 L=-100 O=-7 E=-80 N=-3 T=-91 H=absent",
    "CASE mixed_h4 linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=11,22,33,44",
    "CASE empty_h linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE single_h linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE neg_h linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=-11,-22",
    "CASE bool_h_member linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE nested_h_member linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE huge_float_coords linearized=true version=1.0 L=2147483647 O=-2147483648 "
    "E=-1 N=-1 T=-1 H=2147483647,-2147483648",
    "CASE marker_only linearized=true version=1.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
    "CASE coords_no_marker linearized=false version=0.0 L=100 O=-1 E=-1 N=3 T=-1 H=absent",
    "CASE huge_marker linearized=true version=2147483648.0 L=-1 O=-1 E=-1 N=-1 T=-1 H=absent",
]


def _normalize_version(line: str) -> str:
    """Canonicalize the ``version=<tok>`` token to a float32 magnitude.

    HONEST DIVERGENCE (text formatting only): for ``huge_marker`` PDFBox's probe
    prints ``version`` via Java ``Float.toString``, which renders the float32 of
    ``2147483648`` (an exact power of two) with only 8 significant digits as
    ``2.1474836E9`` — re-parsing that string yields ``2147483600.0``. pypdfbox's
    ``get_linearized_version`` returns the exact ``int``→``double`` value, so
    ``:.1f`` yields ``2147483648.0``. Both sides hold the *same* IEEE-754
    single-precision value; only Java's ``Float.toString`` shorthand loses
    digits. Round-tripping each token through float32 (``struct``) collapses both
    renderings to the identical canonical magnitude, keeping the line comparison
    honest without pinning a printer artifact as if it were behavioral.
    """
    parts = []
    for token in line.split(" "):
        if token.startswith("version="):
            value = float(token[len("version=") :])
            f32 = struct.unpack(">f", struct.pack(">f", value))[0]
            parts.append(f"version={f32:.1f}")
        else:
            parts.append(token)
    return " ".join(parts)


def test_linearization_dict_fuzz_matches_pinned_baseline() -> None:
    py = "\n".join(_py_line(name) for name in _CASES) + "\n"
    expected = "\n".join(_normalize_version(line) for line in _EXPECTED_LINES) + "\n"
    got = "\n".join(_normalize_version(line) for line in py.splitlines()) + "\n"
    assert got == expected


@requires_oracle
def test_linearization_dict_fuzz_matches_pdfbox() -> None:
    java = run_probe_text("LinearizationDictFuzzProbe")
    py = "\n".join(_py_line(name) for name in _CASES) + "\n"
    java_norm = "\n".join(_normalize_version(line) for line in java.splitlines()) + "\n"
    py_norm = "\n".join(_normalize_version(line) for line in py.splitlines()) + "\n"
    assert py_norm == java_norm
