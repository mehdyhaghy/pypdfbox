"""Hand-written tests for :class:`Parser` and the
:class:`SyntaxHandler` / :class:`AbstractSyntaxHandler` shapes."""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.common.function.type4 import Parser
from pypdfbox.pdmodel.common.function.type4.parser import (
    AbstractSyntaxHandler,
    SyntaxHandler,
)


class _RecordingHandler(AbstractSyntaxHandler):
    """Records every callback invocation for inspection."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def token(self, text: str) -> None:
        self.events.append(("token", text))

    def whitespace(self, text: str) -> None:
        self.events.append(("whitespace", text))

    def new_line(self, text: str) -> None:
        self.events.append(("newline", text))

    def comment(self, text: str) -> None:
        self.events.append(("comment", text))


def test_parser_static_inner_classes() -> None:
    """``Parser.SyntaxHandler`` and ``Parser.AbstractSyntaxHandler``
    mirror the Java nested types."""
    assert Parser.SyntaxHandler is SyntaxHandler
    assert Parser.AbstractSyntaxHandler is AbstractSyntaxHandler


def test_syntax_handler_is_abstract() -> None:
    with pytest.raises(TypeError):
        SyntaxHandler()  # type: ignore[abstract]


def test_abstract_syntax_handler_token_required() -> None:
    """``AbstractSyntaxHandler`` provides defaults for every callback
    except ``token`` (mirrors upstream)."""

    class Incomplete(AbstractSyntaxHandler):
        pass

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_token_callback_receives_each_word() -> None:
    handler = _RecordingHandler()
    Parser.parse("3 4 add", handler)
    tokens = [text for kind, text in handler.events if kind == "token"]
    assert tokens == ["3", "4", "add"]


def test_braces_are_their_own_tokens() -> None:
    handler = _RecordingHandler()
    Parser.parse("{ 1 2 }", handler)
    tokens = [text for kind, text in handler.events if kind == "token"]
    assert tokens == ["{", "1", "2", "}"]


def test_braces_without_whitespace() -> None:
    """PDFBOX-804: ``mul}`` must be split into two tokens."""
    handler = _RecordingHandler()
    Parser.parse("mul}", handler)
    tokens = [text for kind, text in handler.events if kind == "token"]
    assert tokens == ["mul", "}"]


def test_newline_callback() -> None:
    handler = _RecordingHandler()
    Parser.parse("1\n2", handler)
    newlines = [text for kind, text in handler.events if kind == "newline"]
    assert newlines == ["\n"]


def test_crlf_treated_as_one_newline() -> None:
    handler = _RecordingHandler()
    Parser.parse("1\r\n2", handler)
    newlines = [text for kind, text in handler.events if kind == "newline"]
    assert newlines == ["\r\n"]


def test_whitespace_callback() -> None:
    handler = _RecordingHandler()
    Parser.parse("  1", handler)
    whitespace = [text for kind, text in handler.events if kind == "whitespace"]
    assert whitespace == ["  "]


def test_comment_callback() -> None:
    handler = _RecordingHandler()
    Parser.parse("% a comment\n3", handler)
    comments = [text for kind, text in handler.events if kind == "comment"]
    assert comments == ["% a comment"]


def test_empty_input_emits_nothing() -> None:
    handler = _RecordingHandler()
    Parser.parse("", handler)
    assert handler.events == []


def test_parse_uses_subclass_handler() -> None:
    """A custom handler's overrides are honored."""
    seen: list[str] = []

    class CustomHandler(AbstractSyntaxHandler):
        def token(self, text: str) -> None:
            seen.append(text)

    Parser.parse("alpha beta", CustomHandler())
    assert seen == ["alpha", "beta"]


def test_default_overrides_are_no_ops() -> None:
    """The base ``AbstractSyntaxHandler`` overrides are no-ops; the
    default whitespace / newline / comment handlers must not raise."""

    class TokenOnly(AbstractSyntaxHandler):
        def token(self, text: str) -> None:
            pass

    handler = TokenOnly()
    handler.whitespace(" ")
    handler.new_line("\n")
    handler.comment("% x")
