from __future__ import annotations

import pytest

from pypdfbox.fontbox.afm import AFMParser


def _parse_char_metric(line: str) -> None:
    AFMParser(
        (
            "StartFontMetrics 4.1\n"
            "StartCharMetrics 1\n"
            f"{line}\n"
            "EndCharMetrics\n"
            "EndFontMetrics\n"
        ).encode("latin-1")
    ).parse()


@pytest.mark.parametrize(
    "line",
    [
        "C",
        "CH",
        "WX",
        "W 500",
        "B 0 0 10",
        "L i",
    ],
)
def test_truncated_char_metric_directive_raises_oserror(line: str) -> None:
    with pytest.raises(OSError) as exc:
        _parse_char_metric(line)

    assert "Malformed CharMetrics line" in str(exc.value)


@pytest.mark.parametrize(
    "line",
    [
        "C not-an-int ;",
        "CH not-hex ;",
        "WX not-a-float ;",
        "B 0 0 high 10 ;",
    ],
)
def test_malformed_char_metric_number_raises_oserror(line: str) -> None:
    with pytest.raises(OSError) as exc:
        _parse_char_metric(line)

    assert "Malformed CharMetrics line" in str(exc.value)
