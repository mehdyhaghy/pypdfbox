"""Live PDFBox differential fuzz for PDRectangle(COSArray) (wave 1524).

Mirrors ``oracle/probes/RectangleFuzzProbe.java``. Every case feeds a
malformed ``COSArray`` (wrong length, non-numeric slots, reversed corners,
overflow magnitudes, indirect references) into the rectangle constructor and
projects the four normalized corners + width/height + ``contains`` results,
asserting pypdfbox matches Apache PDFBox 3.0.7 byte-for-byte.
"""

from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSObject,
    COSString,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from tests.oracle.harness import requires_oracle, run_probe_text

_I = COSInteger.get
_N = COSName.get_pdf_name


def _indirect(value):
    # pypdfbox COSObject is (object_number, generation, *, resolved=...);
    # ``resolved`` plays the role of Java's ``new COSObject(value)`` direct
    # wrapper so COSArray._resolve dereferences to ``value`` (or None).
    return COSObject(1, 0, resolved=value)


def _array(*values) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


# Keep IDs identical to the Java probe's CASE_IDS so failures line up 1:1.
_CASES: list[tuple[str, COSArray]] = [
    ("empty", _array()),
    ("one", _array(_I(5))),
    ("two", _array(_I(5), _I(6))),
    ("three", _array(_I(5), _I(6), _I(7))),
    ("four", _array(_I(1), _I(2), _I(3), _I(4))),
    ("five", _array(_I(1), _I(2), _I(3), _I(4), _I(99))),
    ("six", _array(_I(1), _I(2), _I(3), _I(4), _I(88), _I(99))),
    ("name0", _array(_N("Bad"), _I(2), _I(3), _I(4))),
    ("str1", _array(_I(1), COSString("nope"), _I(3), _I(4))),
    ("null2", _array(_I(1), _I(2), COSNull.NULL, _I(4))),
    ("name_all", _array(_N("a"), _N("b"), _N("c"), _N("d"))),
    ("rev_x", _array(_I(400), _I(100), _I(50), _I(300))),
    ("rev_y", _array(_I(50), _I(300), _I(400), _I(100))),
    ("rev_both", _array(_I(400), _I(300), _I(50), _I(100))),
    ("neg", _array(_I(-100), _I(-200), _I(-50), _I(-60))),
    ("negrev", _array(_I(-50), _I(-60), _I(-100), _I(-200))),
    ("mix_if", _array(_I(1), COSFloat(2.5), _I(3), COSFloat(4.5))),
    ("float_only", _array(COSFloat(1.25), COSFloat(2.5), COSFloat(7.75), COSFloat(8.5))),
    ("int_only", _array(_I(10), _I(20), _I(30), _I(40))),
    ("huge_urx", _array(_I(0), _I(0), COSFloat(5.0e9), _I(100))),
    ("huge_neg_llx", _array(COSFloat(-5.0e9), _I(0), _I(0), _I(100))),
    ("huge_all", _array(COSFloat(-9.0e9), COSFloat(-9.0e9), COSFloat(9.0e9), COSFloat(9.0e9))),
    ("zero_area", _array(_I(5), _I(5), _I(5), _I(5))),
    ("line_x", _array(_I(5), _I(5), _I(5), _I(20))),
    ("line_y", _array(_I(5), _I(5), _I(20), _I(5))),
    ("indirect_slot", _array(_indirect(_I(1)), _I(2), _indirect(COSFloat(3.5)), _I(4))),
    ("indirect_null_slot", _array(_I(1), _indirect(None), _I(3), _I(4))),
    ("indirect_name_slot", _array(_I(1), _I(2), _indirect(_N("Bad")), _I(4))),
    ("frac", _array(COSFloat(1.1), COSFloat(2.2), COSFloat(3.3), COSFloat(4.4))),
]


def _number(value: float) -> str:
    """Match the Java probe's ``number`` formatter: bare integer when whole,
    else ``%.4f``."""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}"


def _project(case_id: str, array: COSArray) -> str:
    parts = [f"CASE {case_id}"]
    try:
        rect = PDRectangle.from_cos_array(array)
        llx = rect.get_lower_left_x()
        lly = rect.get_lower_left_y()
        urx = rect.get_upper_right_x()
        ury = rect.get_upper_right_y()
        parts.append(f"llx={_number(llx)}")
        parts.append(f"lly={_number(lly)}")
        parts.append(f"urx={_number(urx)}")
        parts.append(f"ury={_number(ury)}")
        parts.append(f"w={_number(rect.get_width())}")
        parts.append(f"h={_number(rect.get_height())}")
        cx = (llx + urx) / 2.0
        cy = (lly + ury) / 2.0
        parts.append(f"cin={str(rect.contains(cx, cy)).lower()}")
        parts.append(f"cout={str(rect.contains(cx, cy - 1.0e6)).lower()}")
        re = rect.create_retranslated_rectangle()
        parts.append(
            "re="
            + ",".join(
                _number(v)
                for v in (
                    re.get_lower_left_x(),
                    re.get_lower_left_y(),
                    re.get_upper_right_x(),
                    re.get_upper_right_y(),
                )
            )
        )
        parts.append(f"ca={re.get_cos_array().size()}")
    except Exception as exc:  # noqa: BLE001 - mirror the probe's broad catch
        parts.append(f"err={type(exc).__name__}")
    return " ".join(parts)


def _py_dump() -> str:
    return "\n".join(_project(case_id, array) for case_id, array in _CASES) + "\n"


@requires_oracle
def test_rectangle_fuzz_matches_pdfbox() -> None:
    java = run_probe_text("RectangleFuzzProbe")
    assert _py_dump() == java
