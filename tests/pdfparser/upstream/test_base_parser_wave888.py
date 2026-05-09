from __future__ import annotations

from . import test_base_parser as base_parser_tests


def test_wave888_skipped_placeholder_bodies_are_executable() -> None:
    assert base_parser_tests.test_check_for_end_of_string() is None
    assert base_parser_tests.test_base_parser_stack_overflow() is None
    assert base_parser_tests.test_utf8_in_names() is None
    assert base_parser_tests.test_name_canonicalization() is None

