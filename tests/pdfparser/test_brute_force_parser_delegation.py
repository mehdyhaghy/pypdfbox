"""Wave 1343: cover the ``getattr(super(), ..., None) is callable`` branches
of :class:`pypdfbox.pdfparser.BruteForceParser`.

The fallback ``return -1`` / ``return []`` / ``return {}`` paths are
already covered (wave 1315). The remaining 9 uncovered lines are the
"delegate to inherited helper" branches that fire only when the parent
``COSParser`` exposes the corresponding helper. We exercise those by
monkey-patching ``COSParser`` to attach the helpers, instantiating a
``BruteForceParser``, calling the public surface, and confirming the
delegated implementation receives the call.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from pypdfbox.cos import COSDocument
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_object_key import COSObjectKey
from pypdfbox.io import RandomAccessReadBuffer
from pypdfbox.pdfparser import BruteForceParser
from pypdfbox.pdfparser.cos_parser import COSParser


@pytest.fixture
def patched_cos_parser() -> Iterator[dict[str, object]]:
    """Attach probe helpers to ``COSParser`` and yield a call-log.

    Each entry in the returned dict captures the arguments the
    ``BruteForceParser`` delegate forwards to the inherited helper.
    Helpers are restored on teardown.
    """
    recorder: dict[str, object] = {}
    sentinels: dict[str, object] = {
        "find_last_eof_marker": 4242,
        "bf_search_for_obj_stream_offsets": {17: "stream-key-1"},
        "bf_search_for_x_ref_streams": [11, 22, 33],
        "bf_search_for_x_ref_tables": [44, 55],
        "find_string": 88,
        "get_bfcos_object_offsets": {COSObjectKey(9, 0): 99},
        "search_for_trailer_items": True,
        "bf_search_for_trailer": True,
    }

    def make_zero_arg(name: str, value: object):
        def _impl(self):
            recorder.setdefault(name, []).append(())  # type: ignore[union-attr]
            return value

        return _impl

    def make_one_arg(name: str, value: object):
        def _impl(self, arg):
            recorder.setdefault(name, []).append((arg,))  # type: ignore[union-attr]
            return value

        return _impl

    def streams_impl(self, trailer_resolver, security_handler=None):  # noqa: ANN001
        recorder.setdefault("bf_search_for_obj_streams", []).append(  # type: ignore[union-attr]
            (trailer_resolver, security_handler)
        )

    originals: dict[str, object] = {}
    zero_arg_names = (
        "find_last_eof_marker",
        "bf_search_for_obj_stream_offsets",
        "bf_search_for_x_ref_streams",
        "bf_search_for_x_ref_tables",
        "get_bfcos_object_offsets",
    )
    one_arg_names = (
        "find_string",
        "search_for_trailer_items",
        "bf_search_for_trailer",
    )

    for name in zero_arg_names:
        originals[name] = getattr(COSParser, name, None)
        setattr(COSParser, name, make_zero_arg(name, sentinels[name]))
    for name in one_arg_names:
        originals[name] = getattr(COSParser, name, None)
        setattr(COSParser, name, make_one_arg(name, sentinels[name]))
    originals["bf_search_for_obj_streams"] = getattr(
        COSParser, "bf_search_for_obj_streams", None
    )
    COSParser.bf_search_for_obj_streams = streams_impl  # type: ignore[attr-defined]

    try:
        yield recorder
    finally:
        for name, original in originals.items():
            if original is None:
                delattr(COSParser, name)
            else:
                setattr(COSParser, name, original)


def _make_parser() -> BruteForceParser:
    return BruteForceParser(RandomAccessReadBuffer(b"%PDF-1.4\n%%EOF\n"), COSDocument())


def test_bf_search_for_last_eof_marker_delegates_to_inherited_impl(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    assert parser.bf_search_for_last_eof_marker() == 4242
    assert patched_cos_parser["find_last_eof_marker"] == [()]


def test_bf_search_for_obj_stream_offsets_delegates(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    result = parser.bf_search_for_obj_stream_offsets()
    assert result == {17: "stream-key-1"}
    assert patched_cos_parser["bf_search_for_obj_stream_offsets"] == [()]


def test_bf_search_for_obj_streams_delegates_with_trailer_and_handler(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    trailer = COSDictionary()
    handler = object()
    parser.bf_search_for_obj_streams(trailer, security_handler=handler)
    assert patched_cos_parser["bf_search_for_obj_streams"] == [(trailer, handler)]


def test_bf_search_for_x_ref_streams_delegates(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    assert parser.bf_search_for_x_ref_streams() == [11, 22, 33]
    assert patched_cos_parser["bf_search_for_x_ref_streams"] == [()]


def test_bf_search_for_x_ref_tables_delegates(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    assert parser.bf_search_for_x_ref_tables() == [44, 55]
    assert patched_cos_parser["bf_search_for_x_ref_tables"] == [()]


def test_find_string_delegates_with_needle(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    assert parser.find_string(b"%%EOF") == 88
    assert patched_cos_parser["find_string"] == [(b"%%EOF",)]


def test_get_bfcos_object_offsets_delegates(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    result = parser.get_bfcos_object_offsets()
    assert result == {COSObjectKey(9, 0): 99}
    assert patched_cos_parser["get_bfcos_object_offsets"] == [()]


def test_search_for_trailer_items_delegates(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    trailer = COSDictionary()
    assert parser.search_for_trailer_items(trailer) is True
    assert patched_cos_parser["search_for_trailer_items"] == [(trailer,)]


def test_bf_search_for_trailer_delegates(
    patched_cos_parser: dict[str, list[tuple]],
) -> None:
    parser = _make_parser()
    trailer = COSDictionary()
    assert parser.bf_search_for_trailer(trailer) is True
    assert patched_cos_parser["bf_search_for_trailer"] == [(trailer,)]
