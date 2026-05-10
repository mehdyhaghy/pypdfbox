"""Wave 1275 parity tests for public-named ScratchFile parity helpers."""

from __future__ import annotations

from pypdfbox.io.scratch_file import ScratchFile


def test_init_pages_public_alias_is_no_op() -> None:
    sf = ScratchFile()
    try:
        # Should not raise; lazy data structures self-initialise.
        result = sf.init_pages()
        assert result is None
    finally:
        sf.close()


def test_enlarge_public_alias_is_no_op() -> None:
    sf = ScratchFile()
    try:
        result = sf.enlarge()
        assert result is None
    finally:
        sf.close()


def test_init_pages_and_enlarge_after_close_still_callable() -> None:
    # Both helpers delegate to the same private no-op so they shouldn't raise
    # on a closed instance — they're cheap parity hooks, not state mutations.
    sf = ScratchFile()
    sf.close()
    sf.init_pages()
    sf.enlarge()
