"""Wave 1396 branch-coverage tests for ``TrueTypeFont.read_table_headers``.

The method projects header fields onto a caller-supplied DTO; each
``elif`` arm guards the projection with ``head is not None and
out_headers is not None``. Calling with ``out_headers=None`` exercises
the False arm of each guard (line 307->exit, 315->exit, 319->exit,
323->exit) and the no-op branches for unknown tags (line 281->288 in
the ``init_table`` flow when ``raw`` is falsy is left untested as the
fontTools loader never returns empty bytes).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture(scope="module")
def liberation_sans() -> TrueTypeFont:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    return TrueTypeFont.from_bytes(FIXTURE.read_bytes())


def test_read_table_headers_head_with_none_out_headers(
    liberation_sans: TrueTypeFont,
) -> None:
    """``read_table_headers('head', None)`` short-circuits the projection.

    Closes False arm of ``out_headers is not None`` at line 307.
    """
    # Must not raise — projection is skipped.
    liberation_sans.read_table_headers("head", None)


def test_read_table_headers_hhea_with_none_out_headers(
    liberation_sans: TrueTypeFont,
) -> None:
    """Closes False arm at line 315 for the ``hhea`` arm."""
    liberation_sans.read_table_headers("hhea", None)


def test_read_table_headers_os2_with_none_out_headers(
    liberation_sans: TrueTypeFont,
) -> None:
    """Closes False arm at line 319 for the ``OS/2`` arm."""
    liberation_sans.read_table_headers("OS/2", None)


def test_read_table_headers_post_with_none_out_headers(
    liberation_sans: TrueTypeFont,
) -> None:
    """Closes False arm at line 323 for the ``post`` arm."""
    liberation_sans.read_table_headers("post", None)


def test_read_table_headers_unknown_tag_is_noop(
    liberation_sans: TrueTypeFont,
) -> None:
    """Unknown tag short-circuits at the early ``if tag not in ...``."""
    liberation_sans.read_table_headers("ZZZZ", None)
