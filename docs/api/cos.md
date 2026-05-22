# pypdfbox.cos — COS object model

`pypdfbox.cos` is the in-memory representation of PDF's COS (Carousel Object
System) types — the low-level object graph that every higher layer (parser,
writer, pdmodel) reads and mutates. Every COS class derives from `COSBase`
and accepts an `ICOSVisitor` for serialisation (the writer uses this; you can
too for custom transforms). The package layout matches upstream
`org.apache.pdfbox.cos` exactly; class names are preserved verbatim.

## Public surface

| Class | Purpose |
| --- | --- |
| `COSBase` | Abstract root. `accept(visitor)`, lazy `direct_object`, `needs_to_be_updated` flag (for incremental save), `update_state` / `cos_object_key`. |
| `COSDictionary` | Mapping from `COSName` to `COSBase`. Insertion-ordered (matches PDFBox `LinkedHashMap`). Implements typed accessors. |
| `COSArray` | Ordered sequence of `COSBase`. Supports negative indices and slicing. |
| `COSStream` | `COSDictionary` plus a filtered byte payload. `create_input_stream()` / `create_output_stream(filters)` / `create_raw_input_stream()`. Lazy-decoded — the filter pipeline runs only when bytes are demanded. |
| `COSString` | PDF literal/hex string. `get_string()` returns decoded Python `str`; `get_bytes()` returns the underlying bytes. Encrypted-flag aware. |
| `COSName` | Interned name token. `COSName.get(name)` is the canonical constructor; equality is identity. |
| `COSInteger` | Boxed integer. `COSInteger.get(n)` caches `-256..256`. |
| `COSFloat` | Boxed float. Round-trips through PDFBox-compatible decimal formatting. |
| `COSNumber` | Common base for `COSInteger` + `COSFloat`. |
| `COSNull` | The singleton null token (`COSNull.NULL`). |
| `COSBoolean` | `COSBoolean.TRUE` / `COSBoolean.FALSE` singletons. |
| `COSObject` | Indirect reference (object number + generation). `get_object()` resolves through the parser; lazy. |
| `COSObjectKey` | `(object_number, generation)` value type. Hashable; used as the xref table key. |
| `COSDocument` | The owning root: holds the xref map, trailer, version, header line, encryption dict, stream-cache create function, scratch file. The parser produces this; the writer consumes it. |
| `COSDocumentState` | Lifecycle flag (parsing / parsed / encrypted / closed). |
| `COSIncrement` | Tracks objects added in the current incremental-save cycle. |
| `COSUpdateInfo` / `COSUpdateState` | Per-object dirty/update tracking for `save_incremental()`. |
| `COSInputStream` | Filter-decoding `io.RawIOBase` over a `COSStream`. |
| `COSOutputStream` | Filter-encoding `io.RawIOBase` over a `COSStream`. |
| `ICOSVisitor` | Protocol — `visit_from_array`, `visit_from_boolean`, `visit_from_dictionary`, `visit_from_document`, `visit_from_float`, `visit_from_integer`, `visit_from_name`, `visit_from_null`, `visit_from_stream`, `visit_from_string`, `visit_from_object`. Default implementation lives in the writer; you supply your own for analysis tools. |
| `ICOSParser` | Protocol — `parse_object_dynamically(key, requireExistingNotCompressedObj)`. The parser-side hook used by `COSObject` to resolve a lazy reference. |

## Typed-accessor surface on COSDictionary

These mirror the upstream typed accessors and are the only sanctioned way to
read fields without manually inspecting `COSBase` subclasses:

```python
d.get_name(key, default=None)           # COSName -> str | None
d.get_string(key, default=None)         # COSString -> str | None
d.get_int(key, default_value=-1)        # COSInteger -> int
d.get_long(key, default_value=-1)       # alias retained for source-parity reads
d.get_float(key, default_value=-1.0)    # COSNumber -> float
d.get_boolean(key, default=False)       # COSBoolean -> bool
d.get_date(key)                         # COSString (D:YYYYMMDD…) -> datetime
d.get_dictionary_object(key, expected_class=None)
d.get_cos_array(key)
d.get_cos_stream(key)
```

Mutators (`set_name`, `set_int`, `set_float`, `set_date`, `set_boolean`,
`set_string`, `set_item`, `set_cos_dictionary`) bypass boxing — pass raw
Python values and the dictionary wraps them in the right COSBase subtype.

## Typical usage

```python
from pypdfbox.cos import COSDictionary, COSName, COSArray, COSInteger

trailer = COSDictionary()
trailer.set_name(COSName.TYPE, "Catalog")
trailer.set_int(COSName.PAGE_COUNT, 4)
trailer.set_item(COSName.KIDS, COSArray([COSInteger.get(7), COSInteger.get(8)]))

# Visitor pattern (used by COSWriter):
class CountStrings:
    def __init__(self): self.n = 0
    def visit_from_string(self, s): self.n += 1
    # ...other visit_from_* methods...

visitor = CountStrings()
trailer.accept(visitor)
```

## PDFBox divergence

- All `getXxx` typed accessors become `get_xxx`. `setXxx` becomes `set_xxx`.
  No `camelCase` aliases.
- `COSName.getName()` → property `name`. `COSString.getString()` →
  `get_string()` (consistency over Python property convention so visitors
  composable with the writer).
- `COSObject` is callable via `get_object()` only — never via `__call__`.
  The Java `getObject()` plus `setObject(...)` pair is preserved.
- `COSDocument.getDocumentID()` returns `tuple[bytes, bytes]` (PDF
  `/ID` array) rather than the Java `byte[][]`.

## See also

- [pdfparser.md](pdfparser.md) — produces `COSDocument` from bytes.
- [pdfwriter.md](pdfwriter.md) — serialises `COSDocument` back out.
- [pdmodel.md](pdmodel.md) — the high-level PD* wrappers all hold a
  `COSDictionary` (or `COSStream`) as their single instance attribute.
- [guides/cos-low-level.md](../guides/cos-low-level.md) — when to drop down
  to COS and when to stay in pdmodel.
