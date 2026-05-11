from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import FDFPage, FDFPageInfo, FDFTemplate


def test_default_constructor_empty() -> None:
    page = FDFPage()
    assert isinstance(page.get_cos_object(), COSDictionary)


def test_templates_when_absent() -> None:
    page = FDFPage()
    assert page.get_templates() is None


def test_templates_roundtrip() -> None:
    page = FDFPage()
    template1 = FDFTemplate()
    template2 = FDFTemplate()
    page.set_templates([template1, template2])
    out = page.get_templates()
    assert out is not None
    assert len(out) == 2
    assert out[0].get_cos_object() is template1.get_cos_object()


def test_templates_none_clears() -> None:
    page = FDFPage()
    page.set_templates([FDFTemplate()])
    page.set_templates(None)
    assert page.get_templates() is None


def test_page_info_when_absent() -> None:
    page = FDFPage()
    assert page.get_page_info() is None


def test_page_info_roundtrip() -> None:
    page = FDFPage()
    info = FDFPageInfo()
    page.set_page_info(info)
    out = page.get_page_info()
    assert out is not None
    assert out.get_cos_object() is info.get_cos_object()


def test_page_info_none_clears() -> None:
    page = FDFPage()
    page.set_page_info(FDFPageInfo())
    page.set_page_info(None)
    assert page.get_page_info() is None
