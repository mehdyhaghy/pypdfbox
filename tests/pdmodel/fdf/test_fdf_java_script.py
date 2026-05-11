from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSStream, COSString
from pypdfbox.pdmodel.fdf import FDFJavaScript


def test_get_cos_object_initializes_empty_dict() -> None:
    js = FDFJavaScript()
    assert isinstance(js.get_cos_object(), COSDictionary)


def test_set_get_before() -> None:
    js = FDFJavaScript()
    js.set_before("app.alert('hi')")
    assert js.get_before() == "app.alert('hi')"


def test_set_before_none_clears() -> None:
    js = FDFJavaScript()
    js.set_before("payload")
    js.set_before(None)
    assert js.get_before() is None


def test_get_before_from_stream() -> None:
    dictionary = COSDictionary()
    stream = COSStream()
    stream.set_raw_data(b"after();")
    dictionary.set_item("Before", stream)
    js = FDFJavaScript(dictionary)
    assert js.get_before() == "after();"


def test_set_get_after() -> None:
    js = FDFJavaScript()
    js.set_after("done();")
    assert js.get_after() == "done();"


def test_after_unknown_type_returns_none() -> None:
    dictionary = COSDictionary()
    dictionary.set_string("After", "x")
    js = FDFJavaScript(dictionary)
    assert js.get_after() == "x"


def test_get_doc_when_absent() -> None:
    js = FDFJavaScript()
    assert js.get_doc() is None


def test_set_get_doc_roundtrip() -> None:
    js = FDFJavaScript()
    action_a = COSDictionary()
    action_a.set_name("S", "JavaScript")
    js.set_doc({"alpha": action_a})
    out = js.get_doc()
    assert out is not None
    assert "alpha" in out
    assert out["alpha"] is action_a


def test_set_doc_none_clears() -> None:
    js = FDFJavaScript()
    js.set_doc({"a": COSDictionary()})
    js.set_doc(None)
    assert js.get_doc() is None


def test_existing_dictionary_preserved() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("Before", COSString("hi"))
    js = FDFJavaScript(dictionary)
    assert js.get_cos_object() is dictionary
