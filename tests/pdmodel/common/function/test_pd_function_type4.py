from __future__ import annotations

from unittest.mock import patch

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunctionType4
from pypdfbox.pdmodel.common.function import pd_function_type4 as ps_module


def _make_type4(
    body: str,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType4:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    if domain is not None:
        domain_arr = COSArray()
        domain_arr.set_float_array(domain)
        raw.set_item("Domain", domain_arr)
    if rng is not None:
        range_arr = COSArray()
        range_arr.set_float_array(rng)
        raw.set_item("Range", range_arr)
    raw.set_data(body.encode("ascii"))
    return PDFunctionType4(raw)


def test_eval_caches_parsed_instruction_sequence() -> None:
    """The second eval against the same wrapper must not re-parse."""
    fn = _make_type4("{ dup mul }", domain=[-10.0, 10.0])

    with patch.object(
        ps_module, "_parse", wraps=ps_module._parse
    ) as parse_spy:
        first = fn.eval([3.0])
        second = fn.eval([3.0])

    assert first == pytest.approx([9.0])
    assert second == pytest.approx([9.0])
    assert parse_spy.call_count == 1


def test_cached_sequence_handles_different_inputs() -> None:
    """A cached program must still evaluate correctly on fresh inputs."""
    fn = _make_type4("{ dup mul }", domain=[-10.0, 10.0])

    # Prime the cache.
    assert fn.eval([3.0]) == pytest.approx([9.0])
    # Cache populated; a different input must still produce the right output.
    assert fn.eval([4.0]) == pytest.approx([16.0])
    assert fn.eval([-2.0]) == pytest.approx([4.0])


def test_clear_instruction_cache_forces_reparse() -> None:
    fn = _make_type4("{ dup mul }", domain=[-10.0, 10.0])

    with patch.object(
        ps_module, "_parse", wraps=ps_module._parse
    ) as parse_spy:
        fn.eval([3.0])
        fn.eval([3.0])
        assert parse_spy.call_count == 1

        fn.clear_instruction_cache()
        fn.eval([3.0])
        assert parse_spy.call_count == 2


def test_clear_instruction_cache_picks_up_new_body() -> None:
    """If a caller mutates the underlying body and invalidates manually,
    the next eval must observe the new program."""
    fn = _make_type4("{ dup mul }", domain=[-10.0, 10.0])

    # Prime cache with the squaring program.
    assert fn.eval([3.0]) == pytest.approx([9.0])

    # Swap the body for a doubling program. Without invalidation the cache
    # would still hold the squaring program; clearing forces a re-parse.
    cos_stream = fn.get_pd_stream().get_cos_object()
    cos_stream.set_data(b"{ 2 mul }")
    fn.clear_instruction_cache()

    assert fn.eval([3.0]) == pytest.approx([6.0])


def test_empty_program_is_cached_not_reparsed() -> None:
    """An empty body parses to ``[]``; the sentinel is ``None`` so an empty
    program is still a cache hit on subsequent evals."""
    fn = _make_type4("{ }", domain=[0.0, 10.0])

    with patch.object(
        ps_module, "_parse", wraps=ps_module._parse
    ) as parse_spy:
        fn.eval([1.0])
        fn.eval([2.0])
        fn.eval([3.0])

    assert parse_spy.call_count == 1
