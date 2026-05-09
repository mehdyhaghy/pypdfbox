from __future__ import annotations

import pytest

from pypdfbox.fontbox.afm import (
    AFMParser,
    CharMetric,
    Composite,
    CompositePart,
    KernPair,
    Ligature,
    TrackKern,
)


def _afm(body: str) -> bytes:
    return (
        "StartFontMetrics 4.1\n"
        f"{body}"
        "EndFontMetrics\n"
    ).encode("latin-1")


def test_malformed_bracketed_ch_code_is_reported_as_bad_char_metric() -> None:
    raw = _afm(
        "StartCharMetrics 1\n"
        "CH <41 ; WX 500 ; N A ;\n"
        "EndCharMetrics\n"
    )

    with pytest.raises(OSError) as exc:
        AFMParser(raw).parse()

    assert "Malformed CharMetrics line" in str(exc.value)
    assert "CH <41" in str(exc.value)


def test_kph_rejects_too_short_hex_string() -> None:
    raw = _afm(
        "StartKernData\n"
        "StartKernPairs 1\n"
        "KPH < <42> -10 0\n"
        "EndKernPairs\n"
        "EndKernData\n"
    )

    with pytest.raises(OSError) as exc:
        AFMParser(raw).parse()

    assert "Expected hex string" in str(exc.value)


def test_truncated_char_metric_line_reaches_eof_guard() -> None:
    raw = (
        b"StartFontMetrics 4.1\n"
        b"StartCharMetrics 1\n"
    )

    with pytest.raises(OSError) as exc:
        AFMParser(raw).parse()

    assert "EndCharMetrics" in str(exc.value)


def test_afm_value_object_repr_methods_are_diagnostic() -> None:
    metric = CharMetric()
    metric.set_character_code(65)
    metric.set_name("A")
    metric.set_wx(500)

    part = CompositePart("acute", 100, 250)
    composite = Composite("Aacute")
    composite.add_part(part)
    track = TrackKern(0, 8, -1.5, 32, -3)

    assert repr(metric) == "CharMetric(code=65, name='A', wx=500.0)"
    assert repr(part) == "CompositePart('acute', 100, 250)"
    assert repr(composite) == (
        "Composite('Aacute', parts=[CompositePart('acute', 100, 250)])"
    )
    assert repr(track) == (
        "TrackKern(degree=0, min_pt=8.0, min_kern=-1.5, "
        "max_pt=32.0, max_kern=-3.0)"
    )


def test_kern_pair_and_ligature_equality_fallbacks_and_repr() -> None:
    pair = KernPair("A", "V", -80, 0)
    ligature = Ligature("i", "fi")

    assert pair.__eq__(object()) is NotImplemented
    assert ligature.__eq__(object()) is NotImplemented
    assert {pair: "pair"}[KernPair("A", "V", -80, 0)] == "pair"
    assert {ligature: "ligature"}[Ligature("i", "fi")] == "ligature"
    assert repr(pair) == "KernPair('A', 'V', -80.0, 0.0)"
    assert repr(ligature) == "Ligature('i' -> 'fi')"
