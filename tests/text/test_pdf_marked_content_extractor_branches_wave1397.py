"""Wave 1397 branch-coverage tests for ``PDFMarkedContentExtractor``.

Closes False-branch arrows:

* ``begin_marked_content_sequence`` 65->67 — top of stack is None: the
  ``add_marked_content`` dispatch is skipped
* ``_dispatch_marked`` 214->exit — operator is neither a state op nor a
  text-emitting op: falls through cleanly
* ``_resolve_bdc_properties`` 239->243 — COSName operand resolves to
  None on the resources lookup → returns None
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSName
from pypdfbox.text.pdf_marked_content_extractor import PDFMarkedContentExtractor


def test_begin_marked_content_sequence_skips_when_current_is_none() -> None:
    """Closes 65->67: when the top of the marked-content stack is None,
    the ``add_marked_content`` dispatch is skipped."""
    extractor = PDFMarkedContentExtractor()
    # Pre-populate the current stack with a None entry so the second
    # begin walks the else branch and finds top-of-stack == None.
    extractor._current_marked_contents.append(None)  # noqa: SLF001
    extractor.begin_marked_content_sequence(COSName.get_pdf_name("Span"), None)
    # The new marked-content was pushed onto _current_marked_contents.
    assert len(extractor._current_marked_contents) == 2  # noqa: SLF001
    # _marked_contents stays empty because the else branch was taken.
    assert extractor._marked_contents == []  # noqa: SLF001


def test_dispatch_marked_skips_non_text_non_state_operator() -> None:
    """Closes 214->exit: an operator that's neither marked-content
    (BMC/BDC/EMC/MP/DP) nor text-state nor text-emitting falls through
    without recording anything."""
    extractor = PDFMarkedContentExtractor()
    # Use a path-state operator (q = save graphics state) — unknown to
    # the dispatcher. It should be silently ignored.
    extractor._dispatch_marked("q", [], None)  # noqa: SLF001 — pass None state; the unknown branch never touches it
    # No marked content collected.
    assert extractor._marked_contents == []  # noqa: SLF001
    assert len(extractor._current_marked_contents) == 0  # noqa: SLF001


def test_resolve_bdc_properties_returns_none_for_unresolved_name() -> None:
    """Closes 239->243: a COSName operand resolves to no PropertyList
    on the active page's resources → returns None."""
    extractor = PDFMarkedContentExtractor()

    class _Resources:
        def get_property_list(self, name: Any) -> None:  # noqa: ARG002
            return None

    class _Page:
        def get_resources(self) -> _Resources:
            return _Resources()

    extractor._active_page = _Page()  # noqa: SLF001
    result = extractor._resolve_bdc_properties(  # noqa: SLF001
        [COSName.get_pdf_name("Span"), COSName.get_pdf_name("UnknownMC")]
    )
    assert result is None
