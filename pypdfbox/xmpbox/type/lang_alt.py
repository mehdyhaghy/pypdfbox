from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from .abstract_field import Attribute
from .array_property import ArrayProperty, Cardinality
from .text_type import TextType

if TYPE_CHECKING:
    from ..xmp_metadata import XMPMetadata


XML_NS_URI = "http://www.w3.org/XML/1998/namespace"
LANG_ATTR_NAME = "xml:lang"
X_DEFAULT = "x-default"


class LangAlt(ArrayProperty):
    """
    Convenience subclass for language-alternative arrays (``rdf:Alt`` of
    :class:`TextType` children carrying ``xml:lang`` attributes).

    Upstream PDFBox does not ship a dedicated ``LangAlt`` class — the
    container is plain ``ArrayProperty(Cardinality.Alt)`` everywhere. We add a
    thin wrapper here so callers can talk in (lang, value) pairs while still
    serialising identically: each child is a :class:`TextType` with an
    ``xml:lang`` attribute, and ``x-default`` (per the XMP spec) is sorted to
    the front of the list to match :meth:`XMPSchema.reorganize_alt_order`.
    """

    X_DEFAULT: ClassVar[str] = X_DEFAULT

    def __init__(
        self,
        metadata: XMPMetadata,
        namespace: str | None,
        prefix: str | None,
        property_name: str,
    ) -> None:
        super().__init__(metadata, namespace, prefix, property_name, Cardinality.Alt)

    def set_language_value(self, language: str | None, value: str) -> None:
        lang = language or X_DEFAULT
        for child in list(self.get_all_properties()):
            attr = self._get_text_language_attribute(child)
            if attr is not None and attr.get_value() == lang:
                self.remove_property(child)
        text = TextType(
            self.get_metadata(),
            self.get_namespace(),
            self.get_prefix(),
            self.get_property_name() or "",
            value,
        )
        text.set_attribute(Attribute(XML_NS_URI, LANG_ATTR_NAME, lang))
        self.add_property(text)
        self._reorganize_alt_order()

    def get_language_value(self, language: str | None) -> str | None:
        lang = language or X_DEFAULT
        for child in self.get_all_properties():
            if not isinstance(child, TextType):
                continue
            attr = self._get_text_language_attribute(child)
            if attr is not None and attr.get_value() == lang:
                return child.get_string_value()
        return None

    def get_languages(self) -> list[str]:
        result: list[str] = []
        for child in self.get_all_properties():
            attr = self._get_text_language_attribute(child)
            if attr is not None:
                result.append(attr.get_value())
        return result

    def remove_language(self, language: str | None) -> None:
        lang = language or X_DEFAULT
        for child in list(self.get_all_properties()):
            attr = self._get_text_language_attribute(child)
            if attr is not None and attr.get_value() == lang:
                self.remove_property(child)
                return

    @staticmethod
    def _get_text_language_attribute(child: object) -> Attribute | None:
        if not isinstance(child, TextType):
            return None
        return child.get_attribute(LANG_ATTR_NAME)

    def _reorganize_alt_order(self) -> None:
        # Mirror upstream XMPSchema#reorganizeAltOrder: ensure x-default sorts
        # first when present.
        children = self.get_all_properties()
        x_default_idx = -1
        for i, child in enumerate(children):
            attr = self._get_text_language_attribute(child)
            if attr is not None and attr.get_value() == X_DEFAULT:
                x_default_idx = i
                break
        if x_default_idx <= 0:
            return
        x_default = children[x_default_idx]
        rest = [c for i, c in enumerate(children) if i != x_default_idx]
        self._properties = [x_default, *rest]
