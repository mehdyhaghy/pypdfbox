"""Wave 1397 branch-coverage tests for ``NamespaceFinder``.

Closes False-branch arrows:

* 27->32 — ``push`` exits early when the element carries no attribute map
* 30->28 — ``push`` skips attributes whose ``namespaceURI`` is not xmlns
"""

from __future__ import annotations

from xml.dom.minidom import parseString

from pypdfbox.xmpbox.xml.namespace_finder import NamespaceFinder


def test_push_skips_when_element_has_no_attributes() -> None:
    """Closes 27->32: build an Element-like object whose ``.attributes``
    is ``None``."""

    class _NoAttrs:
        attributes = None

    finder = NamespaceFinder()
    finder.push(_NoAttrs())  # type: ignore[arg-type]
    # The stack still receives an empty mapping (line 32) but the
    # iteration body never runs.
    assert finder.contains_namespace("http://example.org/ns") is False
    # Pop returns the empty dict we just pushed.
    assert finder.pop() == {}


def test_push_skips_non_xmlns_attributes() -> None:
    """Closes 30->28: an element with a normal (non-xmlns) attribute
    only — the loop iterates but the namespaceURI guard fails."""
    # ``rdf:Description rdf:about="..."`` — the ``rdf:about`` attr lives
    # in the RDF namespace, NOT the xmlns namespace, so the guard at
    # line 30 must short-circuit and skip it.
    doc = parseString(
        b"""<?xml version="1.0" encoding="UTF-8"?>
        <root xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
          <rdf:Description rdf:about="urn:example:test"/>
        </root>
        """
    )
    description = doc.getElementsByTagNameNS(
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "Description"
    )[0]

    finder = NamespaceFinder()
    finder.push(description)
    # The rdf:about attribute did not contribute a mapping — the only
    # mapping pushed should be empty.
    assert finder.contains_namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#") is False
    assert finder.pop() == {}
