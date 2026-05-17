"""Coverage-boost wave 1339 tests for :class:`GlyphList`.

Targets the various ``load`` / ``load_list`` input-shape branches that
the existing tests miss:
- string-path source -> ``open(...).read()`` + ``decode('iso-8859-1')``
- file-like object whose ``read()`` returns ``str`` (not bytes)
- file-like object whose ``read()`` returns ``bytes`` (load_list path)
- iterable-of-lines source
- duplicate-name warning emission
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from pypdfbox.fontbox.encoding.glyph_list import GlyphList

# ---------- load(): string path ----------


def test_load_from_string_path_decodes_iso_8859_1(tmp_path: Path) -> None:
    """``load`` with a ``str`` path reads bytes and decodes as iso-8859-1
    (covers lines 4588-4590)."""
    payload = "alpha;0041\nbeta;0042\n"
    fpath = tmp_path / "tiny.txt"
    fpath.write_text(payload, encoding="iso-8859-1")
    gl = GlyphList.load(str(fpath))
    assert gl.to_unicode("alpha") == "A"
    assert gl.to_unicode("beta") == "B"


def test_load_list_from_string_path_decodes_iso_8859_1(tmp_path: Path) -> None:
    """``load_list`` (classmethod) with a string path returns a mapping
    (covers lines 4620-4622)."""
    fpath = tmp_path / "tiny.txt"
    fpath.write_text("xi;0058\n", encoding="iso-8859-1")
    mapping = GlyphList.load_list(str(fpath))
    assert mapping == {"xi": "X"}


# ---------- load(): file-like returning str ----------


def test_load_from_filelike_returning_str() -> None:
    """File-like object whose ``read()`` returns ``str`` (not bytes) goes
    through the ``else`` branch (line 4598)."""

    class _StrStream:
        def read(self) -> str:
            return "phi;03A6\n"

    gl = GlyphList.load(_StrStream())
    assert gl.to_unicode("phi") == "Φ"


def test_load_list_from_filelike_returning_str() -> None:
    """Same str-read path through the load_list classmethod (line 4630)."""

    class _StrStream:
        def read(self) -> str:
            return "psi;03A8\n"

    mapping = GlyphList.load_list(_StrStream())
    assert mapping == {"psi": "Ψ"}


def test_load_list_from_filelike_returning_bytes() -> None:
    """File-like object returning bytes goes through the ``isinstance(data,
    bytes)`` branch (line 4628)."""
    src = io.BytesIO(b"chi;03A7\n")
    mapping = GlyphList.load_list(src)
    assert mapping == {"chi": "Χ"}


# ---------- load(): iterable-of-lines fallback ----------


def test_load_from_iterable_of_lines() -> None:
    """A source that is neither str/bytes/file-like flows through
    ``iter(source)`` (line 4600)."""
    src = ["omega;03A9\n", "# comment\n"]
    gl = GlyphList.load(src)
    assert gl.to_unicode("omega") == "Ω"


def test_load_list_from_iterable_of_lines() -> None:
    """Same iterable fallback for the load_list path (line 4632)."""
    src = iter(["theta;0398\n"])
    mapping = GlyphList.load_list(src)
    assert mapping == {"theta": "Θ"}


# ---------- load(): duplicate-name warning ----------


def test_load_emits_duplicate_warning(caplog) -> None:
    """A duplicate glyph name with a different unicode mapping logs a
    warning (covers lines 4664-4669)."""
    src = io.BytesIO(b"alpha;0041\nalpha;0042\n")
    caplog.set_level(logging.WARNING, logger="pypdfbox.fontbox.encoding.glyph_list")
    mapping = GlyphList.load_list(src)
    # Last value wins.
    assert mapping["alpha"] == "B"
    # And the warning was logged.
    assert any("duplicate value" in r.getMessage() for r in caplog.records)


# ---------- load(): base= keeps existing mappings ----------


def test_load_with_base_carries_over_entries() -> None:
    """When ``base=`` is given, the resulting GlyphList starts as a copy
    of ``base`` and merges new entries on top."""
    base_src = io.BytesIO(b"first;0046\n")
    base = GlyphList.load(base_src)
    extra_src = io.BytesIO(b"second;0053\n")
    merged = GlyphList.load(extra_src, base=base)
    assert merged.to_unicode("first") == "F"
    assert merged.to_unicode("second") == "S"
