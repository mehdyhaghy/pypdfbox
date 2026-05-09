from __future__ import annotations


class COSDocumentState:
    """Lifecycle marker that distinguishes a document still being parsed
    from one that is ready for editing / incremental update.

    Mirrors PDFBox's ``COSDocumentState``. The flag flips from ``parsing``
    (the initial state) to ``not parsing`` exactly once — the parser calls
    :meth:`set_parsing` ``False`` after it has finished walking the xref
    so update-state machinery in dictionaries / streams knows it is now
    safe to mark mutations as updates rather than load steps.
    """

    def __init__(self) -> None:
        # Initial state: the parser is still populating the document.
        self._parsing: bool = True

    def set_parsing(self, parsing: bool) -> None:
        """Set the parsing flag. ``True`` while the parser is still
        consuming the source; ``False`` once parsing is complete and
        the document is open for edits."""
        self._parsing = parsing

    def setParsing(self, parsing: bool) -> None:  # noqa: N802 - upstream Java name
        self.set_parsing(parsing)

    def is_accepting_updates(self) -> bool:
        """``True`` when the document has finished parsing and may be
        mutated. Mirrors upstream ``isAcceptingUpdates()`` —
        equivalent to ``not parsing``."""
        return not self._parsing

    def isAcceptingUpdates(self) -> bool:  # noqa: N802 - upstream Java name
        return self.is_accepting_updates()
