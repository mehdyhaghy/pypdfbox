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


__all__ = ["PDActionJavaScript"]
