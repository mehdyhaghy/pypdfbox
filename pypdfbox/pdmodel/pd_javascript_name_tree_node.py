from __future__ import annotations

from pypdfbox.cos import COSBase, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.common.pd_name_tree_node import PDNameTreeNode

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_ACTION: COSName = COSName.get_pdf_name("Action")
_S: COSName = COSName.get_pdf_name("S")
_JS: COSName = COSName.get_pdf_name("JS")
_JAVASCRIPT: COSName = COSName.get_pdf_name("JavaScript")


class PDJavascriptNameTreeNode(PDNameTreeNode[str]):
    """
    Name tree of JavaScript actions. Mirrors PDFBox
    ``PDJavascriptNameTreeNode``.

    Diverges from upstream: leaf values are exposed as plain Python
    ``str`` (the JavaScript source body) rather than full
    ``PDActionJavaScript`` wrappers. Recorded in ``CHANGES.md``.
    """

    def __init__(self, node: COSDictionary | None = None) -> None:
        super().__init__(node)

    def convert_cos_to_value(self, base: COSBase) -> str:
        if not isinstance(base, COSDictionary):
            raise OSError(
                f"Error creating Javascript object, expected a COSDictionary "
                f"and not {type(base).__name__}"
            )
        js = base.get_dictionary_object(_JS)
        if isinstance(js, COSString):
            return js.get_string()
        if isinstance(js, COSStream):
            data = js.create_input_stream().read()
            return data.decode("utf-8", errors="replace")
        raise OSError(
            f"Expected /JS to be a string or stream, got {type(js).__name__}"
        )

    def convert_value_to_cos(self, value: str) -> COSBase:
        action = COSDictionary()
        action.set_item(_TYPE, _ACTION)
        action.set_item(_S, _JAVASCRIPT)
        action.set_string(_JS, value)
        return action

    def create_child_node(self, dic: COSDictionary) -> PDJavascriptNameTreeNode:
        return PDJavascriptNameTreeNode(dic)


__all__ = ["PDJavascriptNameTreeNode"]
