"""Wave 1399 — close residual partial branches on ``security_handler``.

Targets the 7 partial-arrow + 1 missing-line entries left after wave 1396:

* 517->521 — ``stream_type = get_item("Type")`` returns ``None`` (legacy
  duck path on a /Type-less stream).
* 525->528 — ``not self._decrypt_metadata and name == "Metadata"`` skip
  branch fires (decrypt_metadata=False on a Metadata stream).
* 537->exit — ``get_raw_bytes`` returns a non-bytes value (skip the
  set_raw_bytes write).
* 549->557 — ``get_item("CF")`` raises (caught broad-except), is_signature
  detection still runs.
* 568->577 — duck-typed dict with non-COSArray /ByteRange short-circuits
  the signature detection.
* 581->595 — dictionary-like with no ``entry_set`` / ``items`` skips the
  loop entirely.
* 608 — ``_decrypt_array`` array with no ``set`` setter uses
  ``arr[i] = replaced`` fallback.
"""
from __future__ import annotations

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_name import COSName
from pypdfbox.cos.cos_string import COSString
from pypdfbox.pdmodel.encryption.security_handler import SecurityHandler

# ---------- minimal concrete handler ----------


class _ConcreteHandler(SecurityHandler):
    def prepare_for_decryption(self, encryption, document_id, decryption_material):  # noqa: ARG002
        return None

    def prepare_document(self, document):  # noqa: ARG002
        return None

    def _decrypt(self, data: bytes, _obj_num: int, _gen_num: int) -> bytes:
        # Pass-through so the rest of the decrypt walk completes.
        return data


def _handler() -> _ConcreteHandler:
    h = _ConcreteHandler()
    h.set_encryption_key(b"\x00" * 16)
    h.set_aes(False)
    h.set_revision(4)
    h.set_key_length(128)
    return h


# ---------- 517->521 — legacy duck-typed stream returns None /Type ----------


def test_decrypt_stream_in_place_get_item_returns_none_keeps_decrypting() -> None:
    """A stream whose ``get_item("Type")`` returns ``None`` (no /Type at all)
    falls through to the body-decrypt step. Closes the False arm of the
    ``stream_type is not None`` check at line 521."""
    handler = _handler()

    captured: dict[str, bytes] = {}

    class _LegacyStreamNoType:
        # Only get_item, no get_cos_name — so the elif arm fires.
        def get_item(self, _key: str) -> object | None:
            return None

        def get_raw_bytes(self) -> bytes:
            return b"plain-body"

        def set_raw_bytes(self, data: bytes) -> None:
            captured["body"] = data

    handler.decrypt_stream_in_place(_LegacyStreamNoType(), 11, 0)
    # Body decrypt actually ran (set_raw_bytes was reached).
    assert captured["body"] == b"plain-body"


# ---------- 517->521 — stream lacks BOTH get_cos_name and get_item ----------


def test_decrypt_stream_in_place_no_type_accessors_skips_type_probe() -> None:
    """A stream object that exposes neither ``get_cos_name`` nor
    ``get_item`` makes ``stream_type`` stay ``None`` — the type-probe
    block at 515-518 is bypassed entirely. Closes the False arm of
    the ``elif callable(get_item)`` guard at L517."""
    handler = _handler()

    write_calls: list[bytes] = []

    class _StreamNoTypeAccessors:
        # No get_cos_name and no get_item — get_raw_bytes only.
        def get_raw_bytes(self) -> bytes:
            return b"body-content"

        def set_raw_bytes(self, data: bytes) -> None:
            write_calls.append(data)

    handler.decrypt_stream_in_place(_StreamNoTypeAccessors(), 21, 0)
    # Body decrypt still ran — confirms the False-arm at L517 fell through.
    assert write_calls == [b"body-content"]


# ---------- 525->528 — decrypt_metadata=False skips /Metadata stream --------


def test_decrypt_stream_in_place_skips_metadata_when_decrypt_metadata_disabled() -> None:
    """When ``decrypt_metadata`` is False and the stream's /Type is
    ``Metadata``, the helper returns without touching the body bytes.
    Closes the True arm of the metadata-skip guard at line 525."""
    handler = _handler()
    handler.set_decrypt_metadata(False)

    write_calls: list[bytes] = []

    class _LegacyMetadataStream:
        # Duck-typed: exposes get_cos_name (modern accessor) + the body
        # getters/setters that decrypt_stream_in_place reaches for.
        def get_cos_name(self, _key) -> object:
            return COSName.get_pdf_name("Metadata")

        def get_raw_bytes(self) -> bytes:
            return b"<rdf:RDF/>"

        def set_raw_bytes(self, data: bytes) -> None:
            write_calls.append(data)

    handler.decrypt_stream_in_place(_LegacyMetadataStream(), 12, 0)
    # set_raw_bytes was NOT called — function returned early.
    assert write_calls == []


def test_decrypt_stream_in_place_typed_non_metadata_stream_still_decrypts() -> None:
    """A stream whose /Type is something other than ``XRef`` or
    ``Metadata`` (e.g. ``Image``) passes through the type-probe block
    AND falls through the L525 metadata guard to the body decrypt.
    Closes the False arm of the L525 guard (arc 525→528 — skip the
    early return)."""
    handler = _handler()
    handler.set_decrypt_metadata(True)  # default, but explicit

    write_calls: list[bytes] = []

    class _ImageStream:
        # /Type=Image — neither XRef nor Metadata, so the L525
        # short-circuit is False and we fall through to body decrypt.
        def get_cos_name(self, _key) -> object:
            return COSName.get_pdf_name("Image")

        def get_raw_bytes(self) -> bytes:
            return b"jpeg-bytes"

        def set_raw_bytes(self, data: bytes) -> None:
            write_calls.append(data)

    handler.decrypt_stream_in_place(_ImageStream(), 22, 0)
    # Body decrypt ran — confirms the False arm of L525 was taken.
    assert write_calls == [b"jpeg-bytes"]


# ---------- 537->exit — get_raw_bytes returns non-bytes value ---------------


def test_decrypt_stream_in_place_skips_when_raw_bytes_not_bytes() -> None:
    """A stream whose ``get_raw_bytes()`` returns a non-bytes value (e.g.
    a file handle) is left untouched. Closes the False arm of the
    ``isinstance(raw, (bytes, bytearray, memoryview))`` guard at L537."""
    handler = _handler()

    write_calls: list[bytes] = []

    class _StreamWithFileLikeRaw:
        def get_item(self, _key: str) -> object | None:
            return None

        def get_raw_bytes(self) -> object:
            # Simulate a legacy stream that returns a stream-like object.
            return object()

        def set_raw_bytes(self, data: bytes) -> None:
            write_calls.append(data)

    handler.decrypt_stream_in_place(_StreamWithFileLikeRaw(), 13, 0)
    # set_raw_bytes must NOT have been called.
    assert write_calls == []


# ---------- 549->557 — get_item("CF") raises, is_signature detect still runs


def test_decrypt_dictionary_get_item_cf_raises_continues_decrypt() -> None:
    """A dictionary whose ``get_item("CF")`` raises is treated as if CF
    is absent; the rest of the decrypt path still runs. Closes the
    broad-except path on the /CF probe."""
    handler = _handler()

    calls: list[str] = []

    class _DictRaisingOnCF:
        def get_item(self, key: str) -> object | None:
            calls.append(key)
            if key == "CF":
                raise RuntimeError("CF lookup boom")
            return None

        def entry_set(self) -> list[object]:
            return []

    # Must not raise — broad-except in the CF probe swallows the error.
    out = handler._decrypt_dictionary(_DictRaisingOnCF(), 14, 0)
    assert out is not None
    # Confirm CF probe was attempted.
    assert "CF" in calls


# ---------- 549->557 — dictionary lacks callable get_item -------------------


def test_decrypt_dictionary_no_get_item_method_skips_cf_probe() -> None:
    """A dictionary-like object that does NOT expose a callable
    ``get_item`` skips the /CF probe block at 549-555 and continues to
    the signature-detection step. Closes the False arm of the L549
    ``callable(get_item)`` guard."""
    handler = _handler()

    class _DictNoGetItem:
        # No get_item at all — getattr returns None → callable() False.
        def entry_set(self) -> list[tuple[object, object]]:
            return [("Key", COSString(b"value"))]

    sentinel = _DictNoGetItem()
    out = handler._decrypt_dictionary(sentinel, 18, 0)
    assert out is sentinel


# ---------- 568->577 — duck-typed dict, /ByteRange is not COSArray ----------


def test_decrypt_dictionary_byterange_not_cos_array_skips_signature_path() -> None:
    """A duck-typed dictionary with /Contents as COSString but /ByteRange
    as something other than COSArray is NOT detected as a signature dict.
    Closes the False arm at line 571 (``isinstance(byterange, COSArray)``)."""
    handler = _handler()

    class _DictNonSigByteRange:
        def get_item(self, key: str) -> object | None:
            if key == "Contents":
                return COSString(b"")
            if key == "ByteRange":
                # Not a COSArray — e.g. a stray COSString.
                return COSString(b"oops")
            return None

        def entry_set(self) -> list[object]:
            # Empty walk — we just need the signature-detection branch
            # to fall through without raising.
            return []

    handler._decrypt_dictionary(_DictNonSigByteRange(), 15, 0)


# ---------- 581->595 — entries is None (no entry_set / items) ---------------


def test_decrypt_dictionary_no_entries_method_returns_dict_unchanged() -> None:
    """A dict-like object with neither ``entry_set`` nor ``items`` skips
    the iteration loop and is returned unchanged. Closes the False arm
    of the ``callable(entries)`` guard at line 581."""
    handler = _handler()

    class _DictNoIter:
        # Only get_item; no entry_set / items.
        def get_item(self, _key: str) -> object | None:
            return None

    sentinel = _DictNoIter()
    out = handler._decrypt_dictionary(sentinel, 16, 0)
    assert out is sentinel


# ---------- 608 — _decrypt_array without callable ``set`` uses __setitem__ --


def test_decrypt_array_uses_setter_when_replacement_object_returned() -> None:
    """When :meth:`decrypt` returns a *different* object than the input
    (subclass override), ``_decrypt_array`` invokes the array's ``.set``
    setter. Closes line 608 (the True arm of the ``callable(setter)``
    guard inside the ``replaced is not elem`` branch). The base
    ``decrypt`` always preserves identity, so we override it here to
    surface the replacement path."""

    class _ReplacingHandler(_ConcreteHandler):
        # Force a replacement so ``replaced is not elem`` becomes True.
        def decrypt(self, obj: object, _obj_num: int, _gen_num: int) -> object:
            return COSString(b"replaced")

    handler = _ReplacingHandler()
    handler.set_encryption_key(b"\x00" * 16)
    handler.set_aes(False)
    handler.set_revision(4)
    handler.set_key_length(128)

    inside = COSString(b"original")
    arr = COSArray([inside])
    out = handler._decrypt_array(arr, 17, 0)
    assert out is arr
    # The setter path replaced the entry in-place.
    replaced = arr.get_object(0)
    assert replaced is not inside
    assert isinstance(replaced, COSString)
    assert replaced.get_bytes() == b"replaced"


def test_decrypt_array_without_setter_falls_back_to_setitem() -> None:
    """An array-like without a callable ``.set`` method uses index
    assignment (``arr[i] = replaced``). Exercises the else arm of the
    ``callable(setter)`` guard at line 609-610."""

    class _ReplacingHandler(_ConcreteHandler):
        def decrypt(self, obj: object, _obj_num: int, _gen_num: int) -> object:
            return COSString(b"swap")

    handler = _ReplacingHandler()
    handler.set_encryption_key(b"\x00" * 16)
    handler.set_aes(False)
    handler.set_revision(4)
    handler.set_key_length(128)

    setitem_calls: list[tuple[int, object]] = []

    class _ArrayNoSetter:
        # Non-callable .set attribute → getattr returns it but callable()
        # is False, so the helper falls back to __setitem__.
        set: int = 0  # type: ignore[assignment]

        def __init__(self) -> None:
            self._backing: list[object] = [COSString(b"a"), COSString(b"b")]

        def __len__(self) -> int:
            return len(self._backing)

        def __getitem__(self, i: int) -> object:
            return self._backing[i]

        def __setitem__(self, i: int, value: object) -> None:
            setitem_calls.append((i, value))
            self._backing[i] = value

    wrapped = _ArrayNoSetter()
    out = handler._decrypt_array(wrapped, 18, 0)
    assert out is wrapped
    # __setitem__ was used for the replacement, not .set (which is
    # non-callable on this object).
    assert len(setitem_calls) == 2
