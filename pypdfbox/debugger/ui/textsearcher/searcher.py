"""Coordinator that owns the search engine + panel.

Ported from ``org.apache.pdfbox.debugger.ui.textsearcher.Searcher``.

The upstream class implements ``DocumentListener``, ``ChangeListener`` and
``ComponentListener``. In Tkinter the equivalents are plain callbacks, so
this port exposes them as ordinary methods and the panel wires them up via
:func:`tkinter.Variable.trace_add` / widget ``<<EventName>>`` bindings.
"""

from __future__ import annotations

import logging
from typing import Any

from pypdfbox.debugger.ui.textsearcher.search_engine import (
    Highlight,
    SearchEngine,
)

LOG = logging.getLogger(__name__)

# Two named "painters" — mirrors the constants in the Java source.
# :class:`SearchPanel` configures the corresponding ``tk.Text`` tags.
PAINTER = "match"
SELECTION_PAINTER = "selection"


class Searcher:
    """Wire a text widget to the search engine and a search panel."""

    def __init__(self, text_component: Any) -> None:
        """Bind the searcher to a Tkinter text widget (or compatible mock).

        ``text_component`` must implement the subset of the ``tk.Text``
        protocol used here: ``get("1.0", "end-1c")``, ``tag_add``,
        ``tag_remove``, ``see`` and ``index``.
        """
        self._text_component = text_component
        self._search_engine = SearchEngine(
            get_text=lambda: text_component.get("1.0", "end-1c"),
            add_highlight=lambda start, end, painter: text_component.tag_add(
                painter, self._offset_to_index(start), self._offset_to_index(end)
            ),
            remove_all_highlights=self._remove_all_highlights,
            painter=PAINTER,
        )
        self._search_panel: Any | None = None  # SearchPanel — imported lazily
        self._total_match = 0
        self._current_match = -1
        self._highlights: list[Highlight] = []
        self._next_enabled = False
        self._previous_enabled = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init(self) -> None:
        """Build the search panel. Mirrors ``Searcher.init``."""
        # Local import keeps the module importable in headless environments
        # where Tk is missing (the search panel pulls in tkinter at import
        # time, but :class:`SearchEngine` does not).
        from pypdfbox.debugger.ui.textsearcher.search_panel import SearchPanel

        self._search_panel = SearchPanel(
            document_listener=self,
            change_listener=self,
            component_listener=self,
            next_action=self._next_action,
            previous_action=self._previous_action,
        )

    def get_search_panel(self) -> Any:
        if self._search_panel is None:
            raise RuntimeError("init() must be called before get_search_panel()")
        return self._search_panel.get_panel()

    # ------------------------------------------------------------------
    # Navigation actions (mirror nextAction / previousAction)
    # ------------------------------------------------------------------

    def _previous_action(self) -> None:
        if self._total_match != 0 and self._current_match != 0:
            self._current_match -= 1
            self.scroll_to_word(self._highlights[self._current_match].start_offset)
            self.update_high_lighter(self._current_match, self._current_match + 1)
            self.update_navigation_buttons()

    def _next_action(self) -> None:
        if self._total_match != 0 and self._current_match != self._total_match - 1:
            self._current_match += 1
            self.scroll_to_word(self._highlights[self._current_match].start_offset)
            self.update_high_lighter(self._current_match, self._current_match - 1)
            self.update_navigation_buttons()

    def action_performed(self, event: Any = None) -> None:  # noqa: ARG002
        """Advance to the next match (default action) on a menu / accelerator event.

        Mirrors the two anonymous ``ActionListener.actionPerformed``
        bodies upstream uses (one for the "next" navigation button,
        one for the "previous" button). The canonical accelerator
        ("Find Next") maps to :meth:`_next_action`; callers needing
        the previous-match path can invoke :meth:`_previous_action`
        directly.
        """
        self._next_action()

    # ------------------------------------------------------------------
    # Document listener equivalents
    # ------------------------------------------------------------------

    def insert_update(self, _event: Any = None) -> None:
        self._search_from_widget()

    def remove_update(self, _event: Any = None) -> None:
        self._search_from_widget()

    def changed_update(self, _event: Any = None) -> None:
        self._search_from_widget()

    def _search_from_widget(self) -> None:
        if self._search_panel is None:
            return
        word = self._search_panel.get_search_word()
        if word == "":
            self._next_enabled = False
            self._previous_enabled = False
            self._search_panel.reset()
            self._remove_all_highlights()
            return
        self.search(word)

    def search(self, word: str) -> list[Highlight]:
        """Run the search for ``word`` and refresh highlight/nav state.

        Mirrors the private ``search(String word)`` overload in upstream
        ``Searcher``. Returns the resulting highlight list so tests can
        observe matches without reaching into private state; upstream is
        ``void`` so the addition is a non-breaking extension.
        """
        if self._search_panel is None:
            # Direct invocation without a panel: search using the engine
            # in literal, case-sensitive mode (mirrors the no-flags default
            # the upstream JTextComponent test harness uses).
            highlights = self._search_engine.search(word, True)
            self._highlights = highlights
            if highlights:
                self._total_match = len(highlights)
                self._current_match = 0
            else:
                self._total_match = 0
                self._current_match = -1
            return highlights
        if self._search_panel.is_regex():
            highlights = self._search_engine.search_regex(
                word, self._search_panel.is_case_sensitive()
            )
        else:
            highlights = self._search_engine.search(
                word, self._search_panel.is_case_sensitive()
            )
        self._highlights = highlights
        if highlights:
            self._total_match = len(highlights)
            self._current_match = 0
            self.scroll_to_word(highlights[0].start_offset)
            self.update_high_lighter(self._current_match, self._current_match - 1)
            self.update_navigation_buttons()
        else:
            self._search_panel.update_counter_label(0, 0)
            self._total_match = 0
        return highlights

    # Backwards-compatible private alias retained for in-tree callers.
    _search = search

    # ------------------------------------------------------------------
    # Change listener (checkbox state) and component listener equivalents
    # ------------------------------------------------------------------

    def state_changed(self, _event: Any = None) -> None:
        if self._search_panel is None:
            return
        self.search(self._search_panel.get_search_word())

    # Component listener: only ``componentShown`` / ``componentHidden`` did
    # anything meaningful upstream.

    def component_resized(self, _event: Any = None) -> None:  # pragma: no cover
        pass

    def component_moved(self, _event: Any = None) -> None:  # pragma: no cover
        pass

    def component_shown(self, _event: Any = None) -> None:
        if self._search_panel is not None:
            self._search_panel.re_focus()

    def component_hidden(self, _event: Any = None) -> None:
        self._remove_all_highlights()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def update_navigation_buttons(self) -> None:
        """Sync Prev/Next enabled state and the counter label.

        Mirrors ``Searcher.updateNavigationButtons`` upstream.
        """
        if self._current_match == 0:
            self._previous_enabled = False
        elif 1 <= self._current_match <= self._total_match - 1:
            self._previous_enabled = True
        if self._current_match == self._total_match - 1:
            self._next_enabled = False
        elif self._current_match < self._total_match - 1:
            self._next_enabled = True
        if self._search_panel is not None:
            self._search_panel.update_counter_label(
                self._current_match + 1, self._total_match
            )
            self._search_panel.set_next_enabled(self._next_enabled)
            self._search_panel.set_previous_enabled(self._previous_enabled)

    _update_navigation_buttons = update_navigation_buttons

    def scroll_to_word(self, offset: int) -> None:
        """Scroll the text widget so the character at ``offset`` is visible.

        Mirrors ``Searcher.scrollToWord``. Upstream calls
        ``scrollRectToVisible(modelToView(offset))``; Tk's ``Text.see``
        is the direct equivalent.
        """
        try:
            self._text_component.see(self._offset_to_index(offset))
        except Exception:  # pragma: no cover
            LOG.exception("failed to scroll to offset %s", offset)

    _scroll_to_word = scroll_to_word

    def update_high_lighter(
        self, present_index: int = -1, previous_index: int = -1
    ) -> None:
        """Re-apply highlight tags around the current/previous match.

        Mirrors ``Searcher.updateHighLighter``. When called with the
        defaults (``-1``/``-1``) re-applies the default ``PAINTER`` tag
        to every known highlight — useful after a tag reset.
        """
        if present_index == -1 and previous_index == -1:
            for idx in range(len(self._highlights)):
                self.change_highlighter(idx, PAINTER)
            return
        if previous_index != -1 and 0 <= previous_index < len(self._highlights):
            self.change_highlighter(previous_index, PAINTER)
        if 0 <= present_index < len(self._highlights):
            self.change_highlighter(present_index, SELECTION_PAINTER)

    _update_highlighter = update_high_lighter

    def change_highlighter(self, index_or_strategy: Any, new_painter: str | None = None) -> None:
        """Swap the painter on one highlight, or replace the search strategy.

        Two-argument form mirrors upstream ``changeHighlighter(int, painter)``:
        re-tags ``self._highlights[index]`` with ``new_painter``.

        Single-argument form is a project extension: if a ``SearchEngine``
        instance (or any object exposing ``search``/``search_regex``) is
        passed, it replaces the underlying engine — letting callers swap
        between literal, regex, case-sensitive, or whole-word strategies
        without rebuilding the :class:`Searcher`.
        """
        if new_painter is None:
            # Strategy-swap form (project extension).
            self._search_engine = index_or_strategy
            return
        index = int(index_or_strategy)
        existing = self._highlights[index]
        # Remove the old span by clearing both tag names on that range.
        try:
            start_idx = self._offset_to_index(existing.start_offset)
            end_idx = self._offset_to_index(existing.end_offset)
            self._text_component.tag_remove(PAINTER, start_idx, end_idx)
            self._text_component.tag_remove(SELECTION_PAINTER, start_idx, end_idx)
            self._text_component.tag_add(new_painter, start_idx, end_idx)
        except Exception:  # pragma: no cover
            LOG.exception("failed to swap highlight painter at index %s", index)
            return
        self._highlights[index] = Highlight(
            existing.start_offset, existing.end_offset, new_painter
        )

    _change_highlighter = change_highlighter

    def _remove_all_highlights(self) -> None:
        try:
            self._text_component.tag_remove(PAINTER, "1.0", "end")
            self._text_component.tag_remove(SELECTION_PAINTER, "1.0", "end")
        except Exception:  # pragma: no cover
            LOG.exception("failed to clear highlights")

    def _offset_to_index(self, offset: int) -> str:
        """Convert a character offset to a ``tk.Text`` index string."""
        # ``tk.Text`` indexes are line.column. The widget supports the
        # convenient ``"1.0 + N chars"`` arithmetic form.
        return f"1.0 + {offset} chars"

    # ------------------------------------------------------------------
    # Menu plumbing (mirrors addMenuListeners / removeMenuListeners)
    # ------------------------------------------------------------------

    def add_menu_listeners(self, frame: Any) -> None:
        if self._search_panel is not None:
            self._search_panel.add_menu_listeners(frame)

    def remove_menu_listeners(self, frame: Any) -> None:
        if self._search_panel is not None:
            self._search_panel.remove_menu_listeners(frame)
