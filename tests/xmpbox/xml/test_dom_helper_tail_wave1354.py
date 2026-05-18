"""Wave 1354 tail-sweep for ``pypdfbox.xmpbox.xml.dom_helper``.

Covers four short branches the existing suite skips:

* ``get_unique_element_child`` returns ``None`` when no element children
  (line 40).
* ``get_first_child_element`` returns ``None`` when no element children
  (line 49).
* ``get_qname`` returns the ``(namespaceURI, localName, prefix)`` triple
  (line 58).
* ``get_q_name`` alias matching upstream's snake-case (line 63).
"""

from __future__ import annotations

from xml.dom.minidom import parseString

from pypdfbox.xmpbox.xml.dom_helper import DomHelper


def test_get_unique_element_child_returns_none_when_no_element_children() -> None:
    # ``<root/>`` has no children at all — pos remains -1.
    doc = parseString("<root/>")
    assert DomHelper.get_unique_element_child(doc.documentElement) is None


def test_get_unique_element_child_returns_none_when_only_text_children() -> None:
    # Text nodes don't satisfy ``nodeType == ELEMENT_NODE``.
    doc = parseString("<root>just-text</root>")
    assert DomHelper.get_unique_element_child(doc.documentElement) is None


def test_get_first_child_element_returns_none_for_text_only() -> None:
    doc = parseString("<root>only-text</root>")
    assert DomHelper.get_first_child_element(doc.documentElement) is None


def test_get_qname_returns_namespace_localname_prefix() -> None:
    doc = parseString(
        '<x:foo xmlns:x="urn:x"/>',
    )
    ns, local, prefix = DomHelper.get_qname(doc.documentElement)
    assert ns == "urn:x"
    assert local == "foo"
    assert prefix == "x"


def test_get_q_name_alias_matches_get_qname() -> None:
    doc = parseString('<a:bar xmlns:a="urn:a"/>')
    assert DomHelper.get_q_name(doc.documentElement) == DomHelper.get_qname(
        doc.documentElement
    )
