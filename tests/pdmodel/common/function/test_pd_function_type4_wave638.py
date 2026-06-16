from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4
from pypdfbox.pdmodel.common.function import pd_function_type4 as type4


def _array(values: list[float]) -> COSArray:
    arr = COSArray()
    arr.set_float_array(values)
    return arr


def _make(
    body: str,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType4:
    stream = COSStream()
    stream.set_int("FunctionType", 4)
    if domain is not None:
        stream.set_item("Domain", _array(domain))
    if rng is not None:
        stream.set_item("Range", _array(rng))
    stream.set_data(body.encode("ascii"))
    return PDFunctionType4(stream)


def test_wave638_dictionary_backed_type4_reads_empty_body() -> None:
    dictionary = COSDictionary()
    dictionary.set_int("FunctionType", 4)
    dictionary.set_item("Domain", _array([0.0, 1.0, -1.0, 1.0]))

    fn = PDFunctionType4(dictionary)

    assert fn.is_stream_backed() is False
    assert fn.get_instructions() == []
    assert fn.eval([2.0, -2.0]) == pytest.approx([1.0, -1.0])


def test_wave638_input_and_output_clipping_honor_reversed_bounds() -> None:
    # Wave 1539: upstream PDFBox clips with the NON-normalising
    # ``clipToRange(x, min, max)`` (``if x < min -> min; if x > max -> max``),
    # which does NOT swap a reversed ``(min, max)`` pair. pypdfbox previously
    # normalised reversed bounds in the base ``clip_input``/``clip_output``,
    # diverging from the jar; ``PDFunctionType4`` now overrides with the
    # non-normalising clamp (verified against FunctionType4FuzzProbe).
    #
    # Domain [5, -5], Range [12, 4]:
    #   input  9 -> domain: 9 > -5 -> clamp to -5; 2*-5+10=0; range: 0 < 12 -> 12
    #   input -9 -> domain: -9 < 5 -> clamp to 5;  2*5+10=20; range: 20 > 4 -> 4
    #   input  1 -> domain: 1 < 5 -> clamp to 5;   2*5+10=20; range: 20 > 4 -> 4
    fn = _make(
        "{ 2 mul 10 add }",
        domain=[5.0, -5.0],
        rng=[12.0, 4.0],
    )

    assert fn.eval([9.0]) == pytest.approx([12.0])
    assert fn.eval([-9.0]) == pytest.approx([4.0])
    assert fn.eval([1.0]) == pytest.approx([4.0])


def test_wave638_parser_accepts_bare_program_without_outer_braces() -> None:
    fn = _make("1 2 add", domain=[])

    assert fn.get_instructions() == [1.0, 2.0, "add"]
    assert fn.eval([]) == pytest.approx([3.0])


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("{ 1 0 idiv }", "integer division by zero"),
        ("{ 1 0 mod }", "mod by zero"),
        ("{ 2.5 1 bitshift }", "expected integer"),
        ("{ true 1 lt }", "expected number, got boolean"),
    ],
)
def test_wave638_numeric_error_paths_surface_as_oserror(
    body: str,
    message: str,
) -> None:
    fn = _make(body, domain=[])

    with pytest.raises(OSError, match=message):
        fn.eval([])


def test_wave638_private_stack_helpers_reject_non_numeric_and_non_integral() -> None:
    # popNumber rejects a non-number (Java (Number) cast failure).
    with pytest.raises(OSError, match="expected number, got str"):
        type4._pop_number(["x"])

    # The strict integer pop (upstream (Integer) cast) rejects a Float — wave
    # 1511 restored this; the old lenient int-equality pop no longer exists.
    with pytest.raises(OSError, match="expected integer"):
        type4._pop_int_strict([1.25])

    # The lenient count pop (upstream ((Number)).intValue() in copy/index/roll)
    # accepts a Float and truncates toward zero rather than raising.
    assert type4._pop_int_value([1.25]) == 1
    assert type4._pop_int_value([-1.9]) == -1
