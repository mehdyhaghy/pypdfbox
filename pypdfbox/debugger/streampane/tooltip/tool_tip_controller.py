"""Dispatch operator-row context to the appropriate :class:`ToolTip`.

Ported from
``org.apache.pdfbox.debugger.streampane.tooltip.ToolTipController``.

Upstream's controller queries a Swing ``JTextComponent`` directly to
recover the word and row around the caret. Tkinter's ``tk.Text`` does
not expose ``Utilities.getWordStart`` / ``getRowStart`` analogues, so
we work against the raw text buffer instead — :meth:`get_tool_tip`
accepts either the surrounding text & caret offset, or a ``tk.Text``
instance (from which we pull ``"1.0"``-relative content and translate
the index). See ``CHANGES.md`` for the Swing-to-Tkinter signature
change.
"""

from __future__ import annotations

import logging
from typing import Any

from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.pdmodel.pd_resources import PDResources

from .font_tool_tip import FontToolTip
from .g_tool_tip import GToolTip
from .k_tool_tip import KToolTip
from .rg_tool_tip import RGToolTip
from .scn_tool_tip import SCNToolTip
from .tool_tip import ToolTipText

_LOG = logging.getLogger(__name__)


class ToolTipController:
    """A class that provides the tooltip for an operator."""

    def __init__(self, resources: PDResources | None) -> None:
        self._resources = resources

    # ---- public API -------------------------------------------------------

    def get_tool_tip(
        self,
        offset: int,
        text_component: Any,
    ) -> ToolTipText | None:
        """Return a tooltip for the caret position, or ``None``.

        ``text_component`` may be:

        * a ``str`` — the full content-stream text buffer; or
        * any object with a ``get("1.0", "end")`` method (e.g.
          ``tk.Text``), which we convert to a string transparently.

        ``offset`` is a 0-based character index into the buffer,
        consistent with upstream's ``int offset`` semantics.
        """
        text = self._extract_buffer_text(text_component)
        if text is None:
            return None

        word = self._get_word(text, offset)
        if word is None:
            return None

        row_text = self._get_row_text(text, offset)
        if row_text is None:
            return None

        return self._dispatch(word, row_text, text, offset)

    # ---- dispatcher -------------------------------------------------------

    def _dispatch(
        self,
        word: str,
        row_text: str,
        text: str,
        offset: int,
    ) -> ToolTipText | None:
        if word == OperatorName.SET_FONT_AND_SIZE:
            return FontToolTip(self._resources, row_text).get_tool_tip_text()

        if word == OperatorName.STROKING_COLOR_N:
            color_space_name = self._find_color_space(
                text, offset, OperatorName.STROKING_COLORSPACE
            )
            if color_space_name is not None:
                return SCNToolTip(
                    self._resources, color_space_name, row_text
                ).get_tool_tip_text()
            return None

        if word == OperatorName.NON_STROKING_COLOR_N:
            color_space_name = self._find_color_space(
                text, offset, OperatorName.NON_STROKING_COLORSPACE
            )
            if color_space_name is not None:
                return SCNToolTip(
                    self._resources, color_space_name, row_text
                ).get_tool_tip_text()
            return None

        if word in (OperatorName.STROKING_COLOR_RGB, OperatorName.NON_STROKING_RGB):
            return RGToolTip(row_text).get_tool_tip_text()

        if word in (OperatorName.STROKING_COLOR_CMYK, OperatorName.NON_STROKING_CMYK):
            return KToolTip(row_text).get_tool_tip_text()

        if word in (OperatorName.STROKING_COLOR_GRAY, OperatorName.NON_STROKING_GRAY):
            return GToolTip(row_text).get_tool_tip_text()

        return None

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def get_words(string: str) -> list[str]:
        """Split ``string`` on whitespace, dropping empties.

        Mirrors upstream ``ToolTipController.getWords``: trim, split on
        ``" "``, drop empties and bare ``"\\n"``. The single-space split
        (rather than ``split()`` with no arg) is preserved deliberately
        so multi-space separators behave identically to Java.
        """
        words: list[str] = []
        for token in string.strip().split(" "):
            token = token.strip()
            if token and token != "\n":
                words.append(token)
        return words

    @staticmethod
    def _extract_buffer_text(text_component: Any) -> str | None:
        if text_component is None:
            return None
        if isinstance(text_component, str):
            return text_component
        getter = getattr(text_component, "get", None)
        if callable(getter):
            try:
                return getter("1.0", "end")
            except Exception as exc:  # pragma: no cover - tk error guard
                _LOG.error("%s", exc)
                return None
        return None

    @staticmethod
    def _get_word(text: str, offset: int) -> str | None:
        """Return the whitespace-delimited word containing ``offset``.

        Approximates ``javax.swing.text.Utilities.getWordStart`` /
        ``getWordEnd`` against a plain string: walk left and right
        until a whitespace boundary is found. Returns ``None`` when
        ``offset`` is out of range or sits on whitespace.
        """
        if offset < 0 or offset > len(text):
            return None
        # Clamp the right boundary; caret can sit just past the last char.
        if offset == len(text) or text[offset].isspace():
            # Allow caret immediately after a word.
            if offset > 0 and not text[offset - 1].isspace():
                offset -= 1
            else:
                return None
        start = offset
        while start > 0 and not text[start - 1].isspace():
            start -= 1
        end = offset
        while end < len(text) and not text[end].isspace():
            end += 1
        if start == end:
            return None
        return text[start:end].strip() or None

    @staticmethod
    def _get_row_text(text: str, offset: int) -> str | None:
        """Return the line of ``text`` containing ``offset``.

        Approximates ``javax.swing.text.Utilities.getRowStart`` /
        ``getRowEnd``. Returns the full line including a trailing
        newline when present (mirrors upstream's
        ``getText(rowStart, rowEnd - rowStart + 1)``).
        """
        if offset < 0 or offset > len(text):
            return None
        start = text.rfind("\n", 0, offset) + 1
        end = text.find("\n", offset)
        if end == -1:
            end = len(text)
        else:
            end += 1  # include the newline, matching upstream's +1.
        return text[start:end]

    @classmethod
    def _is_color_space(cls, color_space_type: str, row_text: str) -> bool:
        words = cls.get_words(row_text)
        return len(words) == 2 and words[1] == color_space_type

    def _find_color_space(
        self,
        text: str,
        offset: int,
        color_space_type: str,
    ) -> str | None:
        """Walk upwards through the content stream looking for a
        ``<name> cs`` / ``<name> CS`` row that establishes the active
        color space for the operator at ``offset``. Mirrors upstream
        ``ToolTipController.findColorSpace``.
        """
        cursor = offset
        while cursor != -1:
            cursor = self._position_above(text, cursor)
            if cursor == -1:
                return None
            previous_row = self._get_row_text(text, cursor)
            if previous_row is None:
                return None
            previous_row = previous_row.strip()
            if self._is_color_space(color_space_type, previous_row):
                return previous_row.split(" ")[0]
        return None

    @staticmethod
    def _position_above(text: str, offset: int) -> int:
        """Approximate ``Utilities.getPositionAbove`` at column 0.

        Returns the offset of the start of the line directly above the
        line containing ``offset``, or ``-1`` when there is no line
        above.
        """
        line_start = text.rfind("\n", 0, offset) + 1
        if line_start == 0:
            return -1
        prev_line_end = line_start - 1  # the '\n'
        prev_line_start = text.rfind("\n", 0, prev_line_end) + 1
        return prev_line_start
