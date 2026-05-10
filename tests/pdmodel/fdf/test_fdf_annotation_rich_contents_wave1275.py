"""Wave 1275 parity test: FDFAnnotation.rich_contents_to_string helper."""

from __future__ import annotations

from xml.dom.minidom import parseString

from pypdfbox.pdmodel.fdf.fdf_annotation import FDFAnnotation


def test_rich_contents_to_string_root_strips_outer_tag() -> None:
    doc = parseString("<body>hello</body>")
    body = doc.documentElement
    assert FDFAnnotation.rich_contents_to_string(body, True) == "hello"


def test_rich_contents_to_string_nested_preserves_attrs() -> None:
    doc = parseString('<body><p style="color: red">x &amp; y</p></body>')
    body = doc.documentElement
    out = FDFAnnotation.rich_contents_to_string(body, True)
    # Attribute order may vary slightly but content stays intact.
    assert "<p" in out and 'style="color: red"' in out
    assert "x &amp; y</p>" in out


def test_rich_contents_to_string_cdata_section_round_trips() -> None:
    doc = parseString("<body><![CDATA[<not-xml & raw>]]></body>")
    body = doc.documentElement
    out = FDFAnnotation.rich_contents_to_string(body, True)
    assert out == "<![CDATA[<not-xml & raw>]]>"
