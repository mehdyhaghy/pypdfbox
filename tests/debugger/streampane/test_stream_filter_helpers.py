"""Hand-written tests for the promoted filter-list helpers on
:class:`pypdfbox.debugger.streampane.stream.Stream`.

Covers the methods that were upstream-private in Java but exposed under
their snake_case names for parity tooling:

* ``create_filter_list``
* ``get_filtered_label``
* ``get_partial_stream_command``
* ``get_stop_filter_list``
* ``is_image_stream``
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.debugger.streampane.stream import Stream


def _make_plain_stream() -> COSStream:
    cos = COSStream()
    cos.set_data(b"hello")
    return cos


def _make_chain_stream(filter_names: list[str]) -> COSStream:
    """Construct a stream whose ``/Filter`` array holds the given names.

    The body is intentionally a placeholder — these tests only exercise
    the label/list helpers, not the actual decode path.
    """
    cos = COSStream()
    chain = COSArray()
    for name in filter_names:
        chain.add(COSName.get_pdf_name(name))
    cos.set_data(b"unused")
    cos.set_item("Filter", chain)
    return cos


# ---------------------------------------------------------------------------
# create_filter_list
# ---------------------------------------------------------------------------


def test_create_filter_list_for_unfiltered_stream() -> None:
    """A stream with no ``/Filter`` chain yields just ``DECODED`` plus
    the (empty) ``Encoded ()`` raw label — no ``Keep`` partials."""
    cos = _make_plain_stream()
    stream = Stream(cos, is_thumb=False)
    labels = stream.create_filter_list(cos)
    keys = list(labels.keys())
    # No Image, no partials, just decoded + encoded raw.
    assert Stream.DECODED in keys
    assert Stream.IMAGE not in keys
    assert not any(k.startswith("Keep ") for k in keys)
    assert any(k.startswith("Encoded (") for k in keys)


def test_create_filter_list_for_two_filter_chain() -> None:
    """``/Filter [/ASCIIHexDecode /FlateDecode]`` produces ordered
    labels: ``Decoded``, one ``Keep ...`` partial (stop before
    ``FlateDecode``), then the ``Encoded (...)`` raw label."""
    cos = _make_chain_stream(["ASCIIHexDecode", "FlateDecode"])
    stream = Stream(cos, is_thumb=False)
    labels = stream.create_filter_list(cos)
    keys = list(labels.keys())
    assert keys[0] == Stream.DECODED
    # The middle entry is a Keep partial naming the trailing filter.
    keep_entries = [k for k in keys if k.startswith("Keep ")]
    assert len(keep_entries) == 1
    assert "FlateDecode" in keep_entries[0]
    # Encoded label is last.
    assert keys[-1].startswith("Encoded (")
    assert "ASCIIHexDecode" in keys[-1]
    assert "FlateDecode" in keys[-1]


def test_create_filter_list_for_image_prepends_image_label() -> None:
    cos = COSStream()
    cos.set_item("Type", COSName.get_pdf_name("XObject"))
    cos.set_item("Subtype", COSName.get_pdf_name("Image"))
    cos.set_data(b"img")
    stream = Stream(cos, is_thumb=False)
    labels = stream.create_filter_list(cos)
    assert list(labels.keys())[0] == Stream.IMAGE


# ---------------------------------------------------------------------------
# get_filtered_label
# ---------------------------------------------------------------------------


def test_get_filtered_label_unfiltered_stream() -> None:
    cos = _make_plain_stream()
    stream = Stream(cos, is_thumb=False)
    # No /Filter → empty parentheses.
    assert stream.get_filtered_label() == "Encoded ()"


def test_get_filtered_label_single_filter() -> None:
    cos = COSStream()
    cos.set_data(b"x", filters=[COSName.FLATE_DECODE])
    stream = Stream(cos, is_thumb=False)
    label = stream.get_filtered_label()
    assert label == "Encoded (FlateDecode)"


def test_get_filtered_label_chain_is_comma_separated() -> None:
    cos = _make_chain_stream(["ASCIIHexDecode", "FlateDecode"])
    stream = Stream(cos, is_thumb=False)
    assert stream.get_filtered_label() == "Encoded (ASCIIHexDecode, FlateDecode)"


# ---------------------------------------------------------------------------
# get_partial_stream_command
# ---------------------------------------------------------------------------


def test_get_partial_stream_command_two_filter_chain() -> None:
    """For a 2-filter chain, ``get_partial_stream_command(1)`` names
    only the tail filter."""
    cos = _make_chain_stream(["ASCIIHexDecode", "FlateDecode"])
    stream = Stream(cos, is_thumb=False)
    assert stream.get_partial_stream_command(1) == "Keep FlateDecode ..."


def test_get_partial_stream_command_three_filter_chain() -> None:
    """``get_partial_stream_command(1)`` for a 3-filter chain names the
    two trailing filters joined by ``" & "`` and terminated with
    ``" ..."``."""
    cos = _make_chain_stream(["ASCIIHexDecode", "FlateDecode", "DCTDecode"])
    stream = Stream(cos, is_thumb=False)
    cmd = stream.get_partial_stream_command(1)
    assert cmd == "Keep FlateDecode & DCTDecode ..."


# ---------------------------------------------------------------------------
# get_stop_filter_list
# ---------------------------------------------------------------------------


def test_get_stop_filter_list_returns_single_name_at_index() -> None:
    cos = _make_chain_stream(["ASCIIHexDecode", "FlateDecode"])
    stream = Stream(cos, is_thumb=False)
    assert stream.get_stop_filter_list(0) == ["ASCIIHexDecode"]
    assert stream.get_stop_filter_list(1) == ["FlateDecode"]


# ---------------------------------------------------------------------------
# is_image_stream
# ---------------------------------------------------------------------------


def test_is_image_stream_true_for_image_subtype() -> None:
    cos = COSStream()
    cos.set_item("Subtype", COSName.get_pdf_name("Image"))
    assert Stream.is_image_stream(cos, is_thumb=False) is True


def test_is_image_stream_false_when_no_subtype() -> None:
    cos = COSStream()
    assert Stream.is_image_stream(cos, is_thumb=False) is False


def test_is_image_stream_false_for_non_image_subtype() -> None:
    cos = COSStream()
    cos.set_item("Subtype", COSName.get_pdf_name("Form"))
    assert Stream.is_image_stream(cos, is_thumb=False) is False


def test_is_image_stream_true_when_thumb_even_without_subtype() -> None:
    cos = COSStream()
    assert Stream.is_image_stream(cos, is_thumb=True) is True
