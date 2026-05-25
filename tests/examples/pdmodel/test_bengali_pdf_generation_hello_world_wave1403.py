"""Wave 1403 branch round-out for ``bengali_pdf_generation_hello_world``.

Closes ``91->94``: when ``get_bengali_text_from_file`` returns a non-empty
list, the ``if not lines`` guard takes its False arc and the bundled
fallback sample is *not* substituted.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.pdmodel.bengali_pdf_generation_hello_world import (
    BengaliPdfGenerationHelloWorld,
)


def test_main_uses_loaded_lines_when_corpus_present(
    tmp_path: Path, monkeypatch,
) -> None:
    """With a non-empty corpus the fallback branch is skipped (91->94)."""
    monkeypatch.setattr(
        BengaliPdfGenerationHelloWorld,
        "get_bengali_text_from_file",
        staticmethod(lambda: ["Hello", "World"]),
    )
    out = tmp_path / "bengali.pdf"
    BengaliPdfGenerationHelloWorld.main([str(out)])
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")
