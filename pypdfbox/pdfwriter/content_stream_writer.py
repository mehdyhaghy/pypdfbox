from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, BinaryIO

from pypdfbox.contentstream import Operator, OperatorName
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.io import RandomAccessWrite

# The PDFStreamParser ships its own ``Operator`` value type alongside the
# canonical ``pypdfbox.contentstream.operator.Operator``. Until the parser
# is rewired to emit the canonical class, the writer must accept both so
# that ``parse() -> write_tokens()`` round-trips work — see
# CHANGES.md for the deviation note.
from pypdfbox.pdfparser.pdf_stream_parser import Operator as _ParserOperator

from .cos_writer import (
    ARRAY_CLOSE,
    ARRAY_OPEN,
    DICT_CLOSE,
    DICT_OPEN,
    COSWriter,
    _is_printable_name_byte,
)

# Public byte constants — mirror upstream ``ContentStreamWriter.SPACE`` /
# ``ContentStreamWriter.EOL``. PDF content streams use bare LF (0x0A) as
# the line separator (ISO 32000-1 §7.2.3).
SPACE: bytes = b" "
EOL: bytes = b"\n"


class ContentStreamWriter:
    """
    Serialize a list of content-stream tokens (operands + operators) back
    into PDF content-stream bytes.

    Mirrors ``org.apache.pdfbox.pdfwriter.ContentStreamWriter``. Used by
    consumers that have parsed a content stream via
    :class:`~pypdfbox.pdfparser.pdf_stream_parser.PDFStreamParser`,
    optionally mutated the token list, and want to emit the result.

    Tokens may be either:
      - any ``COSBase`` operand (number, name, string, array, dict, null,
        bool); or
      - an :class:`~pypdfbox.contentstream.operator.Operator` (the parser
        currently emits its own ``Operator`` value type — both are accepted
        for round-trip convenience).

    Inline images are emitted as a special ``BI ... ID ... EI`` block,
    with the image-parameter dictionary printed inline (no surrounding
    ``<<>>``) and the raw image bytes copied verbatim between ``ID`` and
    ``EI``.
    """

    SPACE: bytes = SPACE
    EOL: bytes = EOL

    def __init__(self, output: BinaryIO | RandomAccessWrite) -> None:
        """``output`` must be a writable binary stream (anything exposing
        ``write(bytes) -> int``, e.g. ``io.BytesIO`` or a file opened in
        ``"wb"`` mode).

        ``RandomAccessWrite`` is also accepted for parity with the rest of
        the writer cluster.
        """
        self._output = output

    # ---------- public API (snake_case from upstream camelCase) ----------

    def write_token(self, token: COSBase | Operator | _ParserOperator) -> None:
        """Emit a single operand or operator token."""
        self._write_object(token)

    def writeToken(self, token: COSBase | Operator | _ParserOperator) -> None:  # noqa: N802
        """Java-style alias for :meth:`write_token`."""
        self.write_token(token)

    def write_tokens(self, *tokens: Any) -> None:
        """Emit a sequence of tokens.

        Supports both the upstream ``writeTokens(Object... tokens)`` and
        ``writeTokens(List<?> tokens)`` overloads:

        - ``writer.write_tokens(t1, t2, t3)`` — varargs form (terminates
          with a single ``\\n`` to match upstream).
        - ``writer.write_tokens([t1, t2, t3])`` — list form (no trailing
          newline; matches upstream's ``writeTokens(List<?>)``).

        Any non-token iterable (list, tuple, generator, custom iterable)
        passed as the *only* positional argument is treated as the
        ``List<?>`` overload. Token types (``COSBase``, ``Operator``) and
        bytes-like operands are excluded from the iterable detection so
        that ``write_tokens(some_cos_array)`` keeps the varargs semantics
        even though ``COSArray`` is itself iterable.
        """
        # Disambiguate: a single iterable argument that isn't itself a
        # COSBase / Operator behaves like the ``List<?>`` overload (no
        # trailing newline). Anything else is the varargs overload.
        if len(tokens) == 1 and self._is_list_overload(tokens[0]):
            for token in tokens[0]:
                self._write_object(token)
            return
        for token in tokens:
            self._write_object(token)
        self._write(EOL)

    def writeTokens(self, *tokens: Any) -> None:  # noqa: N802
        """Java-style alias for :meth:`write_tokens`."""
        self.write_tokens(*tokens)

    @staticmethod
    def _is_list_overload(arg: Any) -> bool:
        """Return ``True`` if ``arg`` should trigger the ``List<?>``
        overload of :meth:`write_tokens` (no trailing newline).

        Lists and tuples always qualify. Other iterables (generators,
        deques, custom iterables) qualify too, *except* for token /
        bytes-like types that need to be passed through to the varargs
        arm and dispatched as a single token.
        """
        if isinstance(arg, (list, tuple)):
            return True
        if isinstance(
            arg,
            (COSBase, Operator, _ParserOperator, bytes, bytearray, memoryview, str),
        ):
            return False
        # Iterators and generic iterables (e.g. ``deque``, ``map``,
        # generator expressions) — pypdfbox extension over upstream's
        # ``List<?>`` (see CHANGES.md).
        return isinstance(arg, (Iterable, Iterator))

    # ---------- dispatch ----------

    def _write_object(self, o: Any) -> None:
        if isinstance(o, (Operator, _ParserOperator)):
            self._write_operator(o)
        elif isinstance(o, COSBase):
            self._write_cos(o)
        else:
            raise OSError(f"Error:Unknown type in content stream:{o}")

    # ---------- operators ----------

    def _write_operator(self, op: Operator | _ParserOperator) -> None:
        name = op.get_name()
        if name == OperatorName.BEGIN_INLINE_IMAGE:
            self._write(OperatorName.BEGIN_INLINE_IMAGE.encode("iso-8859-1"))
            self._write(EOL)
            params = op.get_image_parameters()
            if params is None:
                params = COSDictionary()
            for key in params.key_set():
                value = params.get_dictionary_object(key)
                if value is None:
                    # Defensive: a malformed hand-built dict can contain
                    # a value-less key. Skip the whole entry rather than
                    # emitting a dangling inline-image parameter.
                    continue
                self._write_name(key)
                self._write(SPACE)
                # ``writeObject(value)`` upstream — value is a COSBase.
                self._write_cos(value)
                self._write(EOL)
            self._write(
                OperatorName.BEGIN_INLINE_IMAGE_DATA.encode("iso-8859-1")
            )
            self._write(EOL)
            data = op.get_image_data()
            if data:
                self._write(data)
            self._write(EOL)
            self._write(OperatorName.END_INLINE_IMAGE.encode("iso-8859-1"))
            self._write(EOL)
        else:
            self._write(name.encode("iso-8859-1"))
            self._write(EOL)

    # ---------- COSBase serializers ----------
    #
    # These mirror upstream's ``writeObject(COSBase)`` switch. We reuse
    # ``COSWriter`` static helpers for string + float formatting (so the
    # bytes produced here are byte-identical to those a full COSWriter
    # save would produce) but inline the integer / boolean / null /
    # name / array / dict paths because they don't require any of
    # COSWriter's indirect-object bookkeeping.

    def _write_cos(self, o: COSBase) -> None:
        if isinstance(o, COSString):
            self._write_string(o)
            self._write(SPACE)
        elif isinstance(o, COSFloat):
            self._write(COSWriter.format_float_value(o))
            self._write(SPACE)
        elif isinstance(o, COSInteger):
            self._write(str(o.value).encode("ascii"))
            self._write(SPACE)
        elif isinstance(o, COSBoolean):
            self._write(b"true" if o.get_value() else b"false")
            self._write(SPACE)
        elif isinstance(o, COSName):
            self._write_name(o)
            self._write(SPACE)
        elif isinstance(o, COSArray):
            self._write(ARRAY_OPEN)
            for i in range(o.size()):
                item = o.get(i)
                if item is None:
                    self._write_cos(COSNull.NULL)
                else:
                    self._write_cos(item)
            self._write(ARRAY_CLOSE)
            self._write(SPACE)
        elif isinstance(o, COSDictionary):
            self._write(DICT_OPEN)
            for key, value in o.entry_set():
                if value is None:
                    continue
                self._write_cos(key)
                self._write_cos(value)
            self._write(DICT_CLOSE)
            self._write(SPACE)
        elif isinstance(o, COSNull):
            self._write(b"null")
            self._write(SPACE)
        else:
            raise OSError(f"Error:Unknown type in content stream:{o}")

    # ---------- low-level emit helpers ----------

    def _write_name(self, name: COSName) -> None:
        """Inline of ``COSName.writePDF`` — emit ``/`` then the name with
        any non-printable byte ``#xx``-escaped (ISO 32000-1 §7.3.5).
        Mirrors :func:`pypdfbox.pdfwriter.cos_writer._is_printable_name_byte`."""
        self._write(b"/")
        for b in name.get_bytes():
            if _is_printable_name_byte(b):
                self._write(bytes((b,)))
            else:
                self._write(b"#")
                self._write(f"{b:02X}".encode("ascii"))

    def _write_string(self, s: COSString) -> None:
        """Reuse :meth:`COSWriter.write_string`, which expects something
        with a ``write(bytes)`` method. ``self._output`` already satisfies
        that contract directly."""
        # ``COSWriter.write_string`` takes a ``COSStandardOutputStream``,
        # but in practice it only invokes ``write(bytes)`` and
        # ``write_byte(int)``. Our raw output stream lacks ``write_byte``,
        # so we wrap it with a tiny shim.
        COSWriter.write_string(s, _ByteWriterShim(self._output))

    def _write(self, data: bytes) -> None:
        # The output may be a plain BinaryIO or a RandomAccessWrite-like
        # sink exposing only ``write_bytes``. Sniff lazily to preserve the
        # duck-typed surface accepted by earlier writer tests.
        if isinstance(self._output, RandomAccessWrite):
            self._output.write_bytes(data)
            return
        write = getattr(self._output, "write", None)
        if callable(write):
            write(data)
            return
        write_bytes = getattr(self._output, "write_bytes", None)
        if callable(write_bytes):
            write_bytes(data)
            return
        raise TypeError("ContentStreamWriter output must expose write or write_bytes")


class _ByteWriterShim:
    """Adapter exposing the small subset of ``COSStandardOutputStream`` that
    :meth:`COSWriter.write_string` needs (``write(bytes)`` plus
    ``write_byte(int)``) over an arbitrary writable binary stream."""

    __slots__ = ("_out",)

    def __init__(self, out: Any) -> None:
        self._out = out

    def write(self, data: bytes) -> None:
        if isinstance(self._out, RandomAccessWrite):
            self._out.write_bytes(data)
            return
        write = getattr(self._out, "write", None)
        if callable(write):
            write(data)
            return
        write_bytes = getattr(self._out, "write_bytes", None)
        if callable(write_bytes):
            write_bytes(data)
            return
        raise TypeError("ContentStreamWriter output must expose write or write_bytes")

    def write_byte(self, b: int) -> None:
        self.write(bytes((b,)))
