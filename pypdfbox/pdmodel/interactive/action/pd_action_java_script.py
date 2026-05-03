from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSStream, COSString

from .pd_action import PDAction

_JS: COSName = COSName.get_pdf_name("JS")


class PDActionJavaScript(PDAction):
    """JavaScript action. Mirrors PDFBox ``PDActionJavaScript``.

    The ``/JS`` entry (PDF 32000-1 §12.6.4.16) may be either a text string
    (``COSString``) or a stream (``COSStream``) whose decoded body holds
    the script source. :meth:`get_action` accepts both forms.
    """

    SUB_TYPE = "JavaScript"

    def __init__(
        self,
        action: COSDictionary | str | None = None,
    ) -> None:
        """Construct a JavaScript action.

        Mirrors upstream's three constructors:

        - ``PDActionJavaScript()`` — no-arg, sets ``/S = /JavaScript``.
        - ``PDActionJavaScript(String js)`` — also writes the JS source to
          ``/JS``. Pass a ``str`` here.
        - ``PDActionJavaScript(COSDictionary)`` — wraps an existing dict.
        """
        if isinstance(action, str):
            super().__init__(None, self.SUB_TYPE)
            self.set_action(action)
            return
        super().__init__(action, None if action is not None else self.SUB_TYPE)

    def get_action(self) -> str | None:
        """Return the JavaScript source, decoding a ``COSStream`` body via
        UTF-8 when ``/JS`` is given as a stream rather than a text string.
        Returns ``None`` if the entry is missing or of an unexpected type."""
        value = self._action.get_dictionary_object(_JS)
        if isinstance(value, COSString):
            return value.get_string()
        if isinstance(value, COSStream):
            # Wrap via PDStream so we get filter-aware decoding plus the
            # empty-body safety net rather than COSStream's raw OSError.
            from pypdfbox.pdmodel.common.pd_stream import PDStream  # noqa: PLC0415

            with PDStream(value).create_input_stream() as src:
                return src.read().decode("utf-8")
        return None

    def set_action(self, javascript: str | None) -> None:
        self._action.set_string(_JS, javascript)

    # ---------- predicates ----------

    def has_action(self) -> bool:
        """``True`` when ``/JS`` is present on the underlying dictionary,
        regardless of whether it is stored as a ``COSString`` or
        ``COSStream``. Lets callers branch on payload-presence without
        paying the cost of decoding a stream body."""
        return self._action.get_dictionary_object(_JS) is not None

    def is_empty(self) -> bool:
        """``True`` when the action carries no usable JavaScript payload —
        either ``/JS`` is absent, or it is present in an unexpected COS
        form, or its decoded source string is empty. Convenience predicate
        complementing :meth:`has_action` (``has_action`` only checks for
        entry presence; ``is_empty`` also rejects empty strings and
        unreadable stream forms)."""
        source = self.get_action()
        return source is None or source == ""

    def is_stream_payload(self) -> bool:
        """``True`` when ``/JS`` is stored as a ``COSStream`` rather than
        a ``COSString``. PDF 32000-1 §12.6.4.16 allows both forms; large
        scripts are typically stored as streams (potentially compressed
        via the stream's filter chain). Returns ``False`` when ``/JS``
        is absent or stored as a string / other COS type."""
        return isinstance(self._action.get_dictionary_object(_JS), COSStream)

    def is_string_payload(self) -> bool:
        """``True`` when ``/JS`` is stored as a ``COSString``. Returns
        ``False`` when ``/JS`` is absent, a stream, or another COS type.
        Counterpart to :meth:`is_stream_payload`."""
        return isinstance(self._action.get_dictionary_object(_JS), COSString)

    def is_valid(self) -> bool:
        """``True`` when this action's ``/S`` entry equals
        :attr:`SUB_TYPE` (``"JavaScript"``). Useful as a sanity check
        after round-tripping through :meth:`PDAction.create` or when
        constructing the wrapper around a hand-built
        :class:`COSDictionary`."""
        return self.get_sub_type() == self.SUB_TYPE

    def clear_action(self) -> None:
        """Remove ``/JS`` from the underlying dictionary. After this call
        :meth:`get_action` returns ``None`` and :meth:`has_action` returns
        ``False``. Equivalent to ``set_action(None)`` — exposed as a
        named method for symmetry with the other clear-style helpers in
        the action cluster (e.g. ``PDActionEmbeddedGoTo`` style)."""
        self._action.remove_item(_JS)


__all__ = ["PDActionJavaScript"]
