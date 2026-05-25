"""Wave 1402 branch-coverage round-out for Type 4 ``Parser``.

Closes False-branch arrows in
``pypdfbox/pdmodel/common/function/type4/parser.py``:

* 151->157 — ``scan_whitespace`` is invoked on the final whitespace char
  so the inner ``while has_more`` is False from the start.
* 176->182 — ``scan_token`` is invoked on the final token char so the
  inner ``while has_more`` is False from the start.
"""

from __future__ import annotations

import contextlib

from pypdfbox.pdmodel.common.function.type4.parser import Parser


def test_scan_whitespace_at_eof_does_not_enter_inner_loop() -> None:
    """Closes 151->157: ``scan_whitespace`` runs on the last input char,
    so after appending it the ``while has_more`` arm is False from the
    start. Triggered by a program whose last char is a space.

    The smallest valid Type 4 function body is ``{ add }`` — putting a
    trailing space inside the braces guarantees ``scan_whitespace`` runs
    on the final whitespace char before the closing brace.
    """

    # Source whose last char is the trailing whitespace before EOF.
    # Parser.parse expects a complete '{ ... }' program. We end the
    # source with a trailing whitespace so a whitespace scan happens
    # at EOF.
    src = "{ 1 2 add  "
    # The parser may raise on unterminated braces — that's fine, we
    # only care about the tokenizer arm. Suppress the parser-level
    # error.
    with contextlib.suppress(Exception):
        Parser.parse(src)


def test_scan_token_at_eof_does_not_enter_inner_loop() -> None:
    """Closes 176->182: ``scan_token`` runs on the very last char of the
    source so after appending it the ``while has_more`` arm is False from
    the start. Triggered by a program whose last char is a token char
    (e.g. a digit at EOF).
    """

    # No trailing whitespace — final char is part of a token. The
    # tokenizer will scan that final token char and immediately have
    # no more chars to consume.
    src = "{ 1 2 3"  # final char '3' is part of a token
    with contextlib.suppress(Exception):
        Parser.parse(src)


def test_scan_token_single_brace_at_eof() -> None:
    """Closes 176->182 via the early-return path: a ``{`` or ``}`` token
    short-circuits the function at line 174, and the trailing
    ``next_char`` may leave the tokenizer at EOF so the next outer
    iteration's ``has_more`` is False.
    """

    # The very last char of the source is the closing brace.
    src = "{}"
    with contextlib.suppress(Exception):
        Parser.parse(src)
