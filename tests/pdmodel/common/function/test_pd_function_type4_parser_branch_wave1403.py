"""Wave 1403 branch round-out for the Type 4 ``Tokenizer``.

Closes the loop-exit arrows in
``pypdfbox/pdmodel/common/function/type4/parser.py``:

* 151->157 — ``scan_whitespace`` is invoked while positioned on the
  final whitespace character, so ``while self.has_more()`` is False on
  entry and the loop exits straight to the ``whitespace`` callback.
* 176->182 — ``scan_token`` is invoked while positioned on the final
  token character, so ``while self.has_more()`` is False on entry and
  the loop exits straight to the ``token`` callback.

The wave-1402 attempt at these arcs called ``Parser.parse(src)`` with a
single argument; ``Parser.parse`` requires ``(input, handler)`` so that
raised ``TypeError`` before the tokenizer ever ran. Here we drive the
``Tokenizer`` directly with a recording handler so the EOF arms are
genuinely exercised.
"""

from __future__ import annotations

from pypdfbox.pdmodel.common.function.type4.parser import Parser


class _Recorder(Parser.AbstractSyntaxHandler):  # type: ignore[name-defined]
    def __init__(self) -> None:
        self.whitespace_chunks: list[str] = []
        self.token_chunks: list[str] = []

    def whitespace(self, text: str) -> None:
        self.whitespace_chunks.append(text)

    def token(self, text: str) -> None:
        self.token_chunks.append(text)


def _make_tokenizer(text: str, handler: object) -> object:
    from pypdfbox.pdmodel.common.function.type4 import parser as _mod

    return _mod.Tokenizer(text, handler)


def test_scan_whitespace_single_trailing_space_exits_loop_immediately() -> None:
    """Closes 151->157: a one-character whitespace source means
    ``scan_whitespace`` appends that char then finds ``has_more()`` False,
    so the ``while`` loop body never runs and we exit to the callback.
    """
    rec = _Recorder()
    tok = _make_tokenizer(" ", rec)
    tok.tokenize()  # type: ignore[attr-defined]
    # The single space was emitted as one whitespace chunk.
    assert rec.whitespace_chunks == [" "]


def test_scan_token_single_trailing_token_char_exits_loop_immediately() -> None:
    """Closes 176->182: a one-character token source (a non-brace,
    non-whitespace char) means ``scan_token`` appends it then finds
    ``has_more()`` False, so the ``while`` loop body never runs and we
    exit to the ``token`` callback.
    """
    rec = _Recorder()
    tok = _make_tokenizer("x", rec)
    tok.tokenize()  # type: ignore[attr-defined]
    assert rec.token_chunks == ["x"]
