from __future__ import annotations

import pytest

from pypdfbox.fontbox.afm import AFMParser


def _parse_composite_line(line: str) -> None:
    AFMParser(
        (
            "StartFontMetrics 4.1\n"
            "StartCharMetrics 0\n"
            "EndCharMetrics\n"
            "StartComposites 1\n"
            f"{line}\n"
            "EndComposites\n"
            "EndFontMetrics\n"
        ).encode("latin-1")
    ).parse()


@pytest.mark.parametrize(
    "line",
    [
        "CC",
        "CC A",
        "CC A not-an-int ;",
        "CC A 1 ; PCC acute 10 ;",
        "CC A 1 ; PCC acute left 20 ;",
    ],
)
def test_malformed_composite_line_raises_oserror(line: str) -> None:
    with pytest.raises(OSError) as exc:
        _parse_composite_line(line)

    assert "Malformed Composite line" in str(exc.value)


def test_composite_line_wrong_directive_raises_oserror() -> None:
    with pytest.raises(OSError) as exc:
        _parse_composite_line("PCC acute 10 20 ;")

    assert "Expected 'CC'" in str(exc.value)
