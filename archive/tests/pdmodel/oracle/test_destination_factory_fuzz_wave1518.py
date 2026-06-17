"""Live PDFBox differential fuzz for PDDestination.create (wave 1518)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSNull, COSString
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageDestination,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _array(*values) -> COSArray:
    out = COSArray()
    for value in values:
        out.add(value)
    return out


_N = COSName.get_pdf_name
_CASES = [
    ("null", None),
    ("named_name", _N("ChapterOne")),
    ("named_string", COSString("Chapter Two")),
    ("fit", _array(COSInteger.get(3), _N("Fit"))),
    ("fitb", _array(COSInteger.get(3), _N("FitB"))),
    ("fith", _array(COSInteger.get(3), _N("FitH"), COSInteger.get(10))),
    ("fitbh", _array(COSInteger.get(3), _N("FitBH"), COSInteger.get(10))),
    ("fitv", _array(COSInteger.get(3), _N("FitV"), COSInteger.get(10))),
    ("fitbv", _array(COSInteger.get(3), _N("FitBV"), COSInteger.get(10))),
    ("fitr", _array(COSInteger.get(3), _N("FitR"), *[COSInteger.get(i) for i in range(1, 5)])),
    ("xyz", _array(COSInteger.get(3), _N("XYZ"), *[COSInteger.get(i) for i in range(1, 4)])),
    ("float_page", _array(COSFloat(3.9), _N("Fit"))),
    ("null_page", _array(COSNull.NULL, _N("Fit"))),
    ("unknown_type", _array(COSInteger.get(0), _N("Bogus"))),
    ("short_empty", _array()),
    ("short_one", _array(COSInteger.get(0))),
    ("wrong_type_slot", _array(COSInteger.get(0), COSString("Fit"))),
    ("wrong_base", COSInteger.get(9)),
]


def _py_dump() -> str:
    lines: list[str] = []
    for name, base in _CASES:
        try:
            dest = PDDestination.create(base)
            if dest is None:
                lines.append(f"CASE {name} null")
            elif isinstance(dest, PDNamedDestination):
                lines.append(
                    f"CASE {name} class=PDNamedDestination "
                    f"value={dest.get_named_destination()}"
                )
            else:
                assert isinstance(dest, PDPageDestination)
                lines.append(
                    f"CASE {name} class={type(dest).__name__} "
                    f"page={dest.get_page_number()} "
                    f"retrieve={dest.retrieve_page_number()} "
                    f"type={dest.get_cos_object().get_name(1)}"
                )
        except Exception as exc:
            java_name = "IOException" if isinstance(exc, OSError) else type(exc).__name__
            lines.append(f"CASE {name} ERR:{java_name}")
    return "".join(line + "\n" for line in lines)


@requires_oracle
def test_destination_factory_fuzz_matches_pdfbox() -> None:
    assert _py_dump() == run_probe_text("DestinationFactoryFuzzProbe")
