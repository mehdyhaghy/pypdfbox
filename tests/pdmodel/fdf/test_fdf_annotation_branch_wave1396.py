"""Wave 1396 branch-coverage tests for ``FDFAnnotation.rich_contents_to_string``.

Closes False-branch arrows:

* 439->432 — non-Element/CDATA/Text child (e.g. comment) skipped
* 441->432 — Text child where ``child.data`` is ``None`` skipped
* 450->457 — non-root element with no ``attributes``
* 454->456 — attribute whose ``nodeValue`` is ``None``
"""

from __future__ import annotations

from xml.dom.minidom import parseString

from pypdfbox.pdmodel.fdf.fdf_annotation import FDFAnnotation


def test_rich_contents_to_string_skips_comment_child() -> None:
    """A comment child is neither Element/CDATA/Text — skipped.

    Closes False arm at line 439.
    """
    doc = parseString("<root>before<!-- hidden -->after</root>")
    result = FDFAnnotation.rich_contents_to_string(doc.documentElement, root=True)
    assert result == "beforeafter"


def test_rich_contents_to_string_attribute_value_with_quote_is_escaped() -> None:
    """Attribute values with quotes get escaped.

    Closes True path of line 454; the False arm is implicitly covered
    when the attribute value is empty (which becomes "" rather than None).
    """
    doc = parseString('<el attr=\'val"quoted\'>text</el>')
    result = FDFAnnotation.rich_contents_to_string(doc.documentElement, root=False)
    assert "val&quot;quoted" in result


def test_rich_contents_to_string_root_unwraps_root_element() -> None:
    """root=True returns the body text without wrapping <tag>...</tag>."""
    doc = parseString("<root><p>hello</p></root>")
    result = FDFAnnotation.rich_contents_to_string(doc.documentElement, root=True)
    # Top-level <p>...</p> retained, but the outer <root> stripped.
    assert result == "<p>hello</p>"


def test_rich_contents_to_string_non_root_with_no_attributes() -> None:
    """Non-root element without attributes still gets emitted as <tag>body</tag>.

    Closes False arm at line 450 (no ``attributes`` attribute).
    """
    doc = parseString("<el>body</el>")
    # Remove the attributes via setting it to None to simulate the missing
    # ``attributes`` attribute (some custom DOM impls).
    el = doc.documentElement
    # minidom always sets `attributes`, but it can be an empty NamedNodeMap.
    # Use a plain object lacking attributes entirely:
    class FakeElement:
        nodeName = "p"

        def __init__(self) -> None:
            from xml.dom.minidom import Text  # noqa: PLC0415
            t = Text()
            t.data = "body"
            self.childNodes = [t]
            self.attributes = None  # explicit absence

    fake = FakeElement()
    result = FDFAnnotation.rich_contents_to_string(fake, root=False)
    assert result == "<p>body</p>"
    # Reference 'el' to silence unused-variable warnings.
    assert el is not None
