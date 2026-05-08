from __future__ import annotations

from pypdfbox.fontbox.afm import AFMParser, CharMetric, Ligature


def _parse_wave316_char_metric(line: str) -> CharMetric:
    metrics = AFMParser(
        (
            "StartFontMetrics 4.1\n"
            "StartCharMetrics 1\n"
            f"{line}\n"
            "EndCharMetrics\n"
            "EndFontMetrics\n"
        ).encode("latin-1")
    ).parse()

    parsed = metrics.get_char_metrics()
    assert len(parsed) == 1
    return parsed[0]


def test_wave316_char_metric_accepts_afm_bracketed_hex_code() -> None:
    metric = _parse_wave316_char_metric(
        "CH <41> ; WX 500 ; N A ; B 0 0 100 700 ;"
    )

    assert metric.get_character_code() == 65
    assert metric.get_name() == "A"
    assert metric.get_wx() == 500.0


def test_wave316_char_metric_accepts_adjacent_semicolon_delimiters() -> None:
    metric = _parse_wave316_char_metric(
        "C 102;WX 250;N f;B 0 0 100 700;L i fi;"
    )

    assert metric.get_character_code() == 102
    assert metric.get_name() == "f"
    assert metric.get_wx() == 250.0
    assert metric.get_ligatures() == [Ligature("i", "fi")]
