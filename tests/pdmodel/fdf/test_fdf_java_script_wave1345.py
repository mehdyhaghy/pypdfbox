"""Wave 1345: residual coverage for ``FDFJavaScript``.

Targets the after-stream branch, the ``set_after(None)`` clear path and
the ``/Doc`` array fallback when the key half of a (key, value) pair is
not encoded as a ``COSString`` (upstream falls back to ``getName(i)``).
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString
from pypdfbox.pdmodel.fdf import FDFJavaScript


def test_get_after_from_stream() -> None:
    """``/After`` may be an indirect stream — decode it as text."""
    dictionary = COSDictionary()
    stream = COSStream()
    stream.set_raw_data(b"done();")
    dictionary.set_item("After", stream)
    js = FDFJavaScript(dictionary)
    assert js.get_after() == "done();"


def test_get_after_unknown_value_returns_none() -> None:
    """A non-string / non-stream ``/After`` (here a COSArray) yields None."""
    dictionary = COSDictionary()
    dictionary.set_item("After", COSArray())
    js = FDFJavaScript(dictionary)
    assert js.get_after() is None


def test_set_after_none_clears_entry() -> None:
    """``set_after(None)`` removes the ``/After`` key from the dictionary."""
    js = FDFJavaScript()
    js.set_after("alert(1)")
    assert js.get_after() == "alert(1)"
    js.set_after(None)
    assert js.get_after() is None
    assert not js.get_cos_object().contains_key("After")


def test_get_doc_uses_name_fallback_when_key_is_cos_name() -> None:
    """When the key in the ``/Doc`` array is a ``COSName`` rather than a
    ``COSString``, upstream falls back to ``array.get_name(i)`` to resolve
    the action name."""
    dictionary = COSDictionary()
    arr = COSArray()
    # Use a name-style key (COSName) so the get_name fallback path runs.
    arr.add(COSName.get_pdf_name("MyAction"))
    action = COSDictionary()
    action.set_name("S", "JavaScript")
    arr.add(action)
    dictionary.set_item("Doc", arr)
    js = FDFJavaScript(dictionary)
    doc = js.get_doc()
    assert doc is not None
    assert "MyAction" in doc
    assert doc["MyAction"] is action


def test_get_doc_skips_pair_when_value_not_dictionary() -> None:
    """A non-dictionary value (after a valid key) is silently skipped."""
    dictionary = COSDictionary()
    arr = COSArray()
    arr.add(COSString("noop"))
    arr.add(COSString("not-a-dict"))
    dictionary.set_item("Doc", arr)
    js = FDFJavaScript(dictionary)
    assert js.get_doc() == {}


def test_get_doc_odd_length_ignores_trailing_entry() -> None:
    """The pair iteration uses ``i + 1 < size``, so an odd-length array's
    trailing entry is silently dropped (matches upstream)."""
    dictionary = COSDictionary()
    arr = COSArray()
    arr.add(COSString("lonely"))  # odd: no companion
    dictionary.set_item("Doc", arr)
    js = FDFJavaScript(dictionary)
    assert js.get_doc() == {}


def test_get_doc_when_entry_is_not_array() -> None:
    """``/Doc`` set to a scalar value yields ``None``."""
    dictionary = COSDictionary()
    dictionary.set_string("Doc", "wrong-type")
    js = FDFJavaScript(dictionary)
    assert js.get_doc() is None
