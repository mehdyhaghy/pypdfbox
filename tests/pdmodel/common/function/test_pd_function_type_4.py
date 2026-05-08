"""Hand-written coverage for ``PDFunctionType4`` (PostScript calculator).

Per-opcode coverage lives in ``test_pd_function_type4_opcodes.py``;
cache-behaviour coverage in ``test_pd_function_type4.py``; upstream-ported
coverage in ``upstream/test_pd_function_type_4.py`` /
``upstream/test_pd_function_type4.py``.

This file focuses on the structural / integration surface:
* construction from a ``COSStream`` and the ``PDFunction.create`` factory
* the program-text body parser (whitespace, brace handling, comments-style
  edge cases)
* multi-input / multi-output evaluation
* ``/Domain`` / ``/Range`` clipping at the eval boundary
* error surfacing for malformed bodies
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSStream
from pypdfbox.pdmodel.common.function import PDFunction, PDFunctionType4


def _make(
    body: str,
    *,
    domain: list[float] | None = None,
    rng: list[float] | None = None,
) -> PDFunctionType4:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    if domain is not None:
        d = COSArray()
        d.set_float_array(domain)
        raw.set_item("Domain", d)
    if rng is not None:
        r = COSArray()
        r.set_float_array(rng)
        raw.set_item("Range", r)
    raw.set_data(body.encode("utf-8"))
    return PDFunctionType4(raw)


# --------------------------------------------------------------------------
# Construction / factory
# --------------------------------------------------------------------------


def test_get_function_type_is_4() -> None:
    fn = _make("{ }", domain=[0.0, 1.0])
    assert fn.get_function_type() == 4


def test_factory_dispatches_to_type4() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    raw.set_data(b"{ dup mul }")
    fn = PDFunction.create(raw)
    assert isinstance(fn, PDFunctionType4)


def test_get_pd_stream_is_stream_backed() -> None:
    """Type 4 wraps a COSStream — pd_stream must be non-None."""
    fn = _make("{ }", domain=[0.0, 1.0])
    assert fn.get_pd_stream() is not None


# --------------------------------------------------------------------------
# Program parsing
# --------------------------------------------------------------------------


def test_empty_program_returns_input_unchanged() -> None:
    """An empty `{ }` body leaves the input stack unchanged."""
    fn = _make("{ }", domain=[0.0, 10.0])
    assert fn.eval([3.0]) == pytest.approx([3.0])


def test_body_without_outer_braces_is_accepted() -> None:
    """Some real-world Type 4 streams omit the outer `{ }`. Our parser
    falls through to ``parse_block`` in that case."""
    fn = _make("dup mul", domain=[-10.0, 10.0])
    assert fn.eval([4.0]) == pytest.approx([16.0])


def test_extra_whitespace_is_ignored() -> None:
    body = "{\n   2  \t  3  add\n}"
    fn = _make(body, domain=[0.0, 0.0])
    # Take no inputs (Domain is empty / single point) — actually we set
    # [0,0] so input gets clamped to 0 then ignored by program.
    assert fn.eval([0.0]) == pytest.approx([0.0, 5.0])


def test_braces_without_separating_whitespace_tokenise_correctly() -> None:
    """`{2 3 add}` (no space between `{` and `2`) must still tokenise
    `{`, `2`, `3`, `add`, `}` as five separate tokens."""
    fn = _make("{2 3 add}", domain=[])
    assert fn.eval([]) == pytest.approx([5.0])


def test_percent_comments_are_ignored() -> None:
    """PostScript comments start with ``%`` and run through end-of-line."""
    body = "{ 2 % ignored operator text: frobnicate }\n 3 add }"
    fn = _make(body, domain=[])
    assert fn.eval([]) == pytest.approx([5.0])


def test_inline_percent_comment_delimits_token() -> None:
    """A comment immediately after a token must still preserve that token."""
    fn = _make("{ 2%comment\n 3 add }", domain=[])
    assert fn.eval([]) == pytest.approx([5.0])


def test_unknown_operator_raises() -> None:
    fn = _make("{ frobnicate }", domain=[])
    with pytest.raises(OSError):
        fn.eval([])


def test_trailing_tokens_after_closing_brace_raise() -> None:
    """Parser must reject body with extra tokens past the outer `}`."""
    fn = _make("{ 1 } 99", domain=[])
    with pytest.raises(OSError):
        fn.eval([])


def test_missing_closing_brace_raises() -> None:
    """A malformed body with an unterminated procedure must be rejected."""
    fn = _make("{ 1 2 add", domain=[])
    with pytest.raises(OSError, match="missing closing brace"):
        fn.eval([])


def test_unmatched_closing_brace_without_outer_wrapper_raises() -> None:
    """Outer braces are optional for lenient real-world streams, but a stray
    closing brace is still malformed."""
    fn = _make("1 }", domain=[])
    with pytest.raises(OSError, match="unexpected closing brace"):
        fn.eval([])


# --------------------------------------------------------------------------
# Multi-input / multi-output
# --------------------------------------------------------------------------


def test_two_input_two_output_program() -> None:
    """Pop two inputs as (a, b); push (a+b, a-b)."""
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    domain = COSArray()
    domain.set_float_array([-1e9, 1e9, -1e9, 1e9])
    raw.set_item("Domain", domain)
    # Stack on entry: [a, b]   (b is on top)
    # `2 copy` -> [a, b, a, b]
    # `add`    -> [a, b, a+b]
    # `3 1 roll` -> [a+b, a, b]
    # `sub`    -> [a+b, a-b]
    raw.set_data(b"{ 2 copy add 3 1 roll sub }")
    fn = PDFunctionType4(raw)
    assert fn.eval([7.0, 3.0]) == pytest.approx([10.0, 4.0])


def test_three_input_average() -> None:
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    domain = COSArray()
    domain.set_float_array([-1e9, 1e9] * 3)
    raw.set_item("Domain", domain)
    raw.set_data(b"{ add add 3 div }")
    fn = PDFunctionType4(raw)
    assert fn.eval([1.0, 2.0, 6.0]) == pytest.approx([3.0])


def test_zero_input_zero_output_constant_program() -> None:
    """A pushed-then-popped program leaves the stack empty."""
    fn = _make("{ 42 pop }", domain=[])
    assert fn.eval([]) == []


# --------------------------------------------------------------------------
# Domain / Range clipping
# --------------------------------------------------------------------------


def test_eval_clips_input_to_domain_before_running_program() -> None:
    """Input above /Domain max is clamped before being pushed onto the
    PostScript stack."""
    # Domain = [0, 5]; program squares the input.
    fn = _make("{ dup mul }", domain=[0.0, 5.0])
    # Input 100 clamps to 5 → 5*5 = 25.
    assert fn.eval([100.0]) == pytest.approx([25.0])


def test_eval_clips_output_to_range() -> None:
    """Output above /Range max gets clamped after the program runs."""
    fn = _make(
        "{ dup mul }",
        domain=[-100.0, 100.0],
        rng=[0.0, 50.0],
    )
    # 10*10 = 100 → clamped to /Range max 50.
    assert fn.eval([10.0]) == pytest.approx([50.0])


def test_eval_no_range_returns_raw_stack() -> None:
    fn = _make("{ dup mul }", domain=[-100.0, 100.0])
    assert fn.eval([10.0]) == pytest.approx([100.0])


# --------------------------------------------------------------------------
# Boolean → float coercion at output
# --------------------------------------------------------------------------


def test_boolean_output_coerced_to_float() -> None:
    """A Type 4 program that leaves a boolean on top of the stack returns
    1.0 / 0.0 in the output list — booleans are not surfaced through
    PDF function eval."""
    fn = _make("{ true }", domain=[])
    assert fn.eval([]) == pytest.approx([1.0])

    fn = _make("{ false }", domain=[])
    assert fn.eval([]) == pytest.approx([0.0])


def test_comparison_program_returns_floats() -> None:
    """A `lt` produces a boolean which must coerce cleanly through eval."""
    fn = _make("{ 3 5 lt }", domain=[])
    assert fn.eval([]) == pytest.approx([1.0])


# --------------------------------------------------------------------------
# Stack-underflow surfacing
# --------------------------------------------------------------------------


def test_stack_underflow_raises_oserror() -> None:
    """Programs that pop from an empty stack surface as OSError —
    parity with upstream PDFBox IOException."""
    fn = _make("{ add }", domain=[])
    with pytest.raises(OSError):
        fn.eval([])


def test_type_mismatch_raises_oserror() -> None:
    """Trying to add a boolean to a number is a type mismatch."""
    fn = _make("{ true 1 add }", domain=[])
    with pytest.raises(OSError):
        fn.eval([])


# --------------------------------------------------------------------------
# Realistic shading-style program
# --------------------------------------------------------------------------


def test_realistic_grayscale_to_rgb_swap() -> None:
    """Shading tint transforms in real PDFs are compact Type 4 programs.
    Here: take a gray value g in [0,1], emit (g, 1-g, 0) for a fake
    red→green ramp."""
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    rng = COSArray()
    rng.set_float_array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0])
    raw.set_item("Range", rng)
    # On entry: [g]  (input)
    # `dup`    -> [g, g]
    # `1 exch sub` -> [g, 1-g]
    # `0`     -> [g, 1-g, 0]
    raw.set_data(b"{ dup 1 exch sub 0 }")
    fn = PDFunctionType4(raw)
    assert fn.eval([0.0]) == pytest.approx([0.0, 1.0, 0.0])
    assert fn.eval([0.25]) == pytest.approx([0.25, 0.75, 0.0])
    assert fn.eval([1.0]) == pytest.approx([1.0, 0.0, 0.0])


def test_realistic_branching_clamp() -> None:
    """Branch-style Type 4: emit min(input, 0.5) using ifelse."""
    raw = COSStream()
    raw.set_int("FunctionType", 4)
    domain = COSArray()
    domain.set_float_array([0.0, 1.0])
    raw.set_item("Domain", domain)
    # On entry: [x]
    # `dup 0.5 gt` -> [x, x>0.5]
    # `{ pop 0.5 } { } ifelse` — true: replace x with 0.5; false: leave x.
    raw.set_data(b"{ dup 0.5 gt { pop 0.5 } { } ifelse }")
    fn = PDFunctionType4(raw)
    assert fn.eval([0.25]) == pytest.approx([0.25])
    assert fn.eval([0.5]) == pytest.approx([0.5])
    assert fn.eval([0.75]) == pytest.approx([0.5])
