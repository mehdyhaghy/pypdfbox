# pypdfbox.contentstream — content-stream engine and operators

The content-stream layer turns the sequence of PDF operators that make up a
page (or a Type-3 glyph, or a form X-object, or an appearance stream) into
graphics-state callbacks. `PDFStreamEngine` is the dispatcher;
`PDFGraphicsStreamEngine` adds path-building and painting. Subclasses
(`PDFTextStripper`, `LegacyPDFStreamEngine`, `PageDrawer`,
`PDFMarkedContentExtractor`) override the parts they care about.

## Public surface

| Class / constant | Purpose |
| --- | --- |
| `PDFStreamEngine` | The base engine. Holds the graphics state stack, the current `PDResources` chain, and the operator dispatch table. Iterates a content-stream token stream and invokes `OperatorProcessor`s. `process_page(page)`, `process_children_stream(stream, page)`, `process_tiling_pattern(...)`, `process_type3_stream(...)`. Override `show_text_string`, `show_glyph`, `process_operator`, etc. to capture data. |
| `PDFGraphicsStreamEngine` | Adds path construction + path painting (`append_rectangle`, `move_to`, `line_to`, `curve_to`, `close_path`, `stroke_path`, `fill_path`, `clip(winding_rule)`). Constants `WIND_NON_ZERO`, `WIND_EVEN_ODD`. |
| `Operator` | One operator token. `op_name` plus optional inline-image dictionary + payload. |
| `OperatorName` | Sealed string constants: `BEGIN_TEXT` (`BT`), `END_TEXT` (`ET`), `SHOW_TEXT` (`Tj`), `SHOW_TEXT_LINE` (`'`), `MOVE_TO` (`m`), `LINE_TO` (`l`), `CURVE_TO` (`c`), `CLOSE_PATH` (`h`), `STROKE_PATH` (`S`), `FILL_PATH_NON_ZERO` (`f`), `FILL_PATH_EVEN_ODD` (`f*`), `BEGIN_INLINE_IMAGE` (`BI`), `DO` (`Do`), `BEGIN_MARKED_CONTENT_SEQ` (`BDC`), etc. Use these in lieu of hard-coded strings. |
| `OperatorProcessor` | Base class for the per-operator handlers. Override `process(operator, arguments)`. |
| `MissingOperandException` | Raised when an operator is invoked with too few operands on the stack. |
| `PDContentStream` | Protocol — `get_contents() -> InputStream`, `get_resources() -> PDResources`, `get_bbox()`. Implemented by `PDPage`, `PDFormXObject`, `PDType3CharProc`, `PDAppearanceStream`, `PDTilingPattern`. |

## Operator categories

`PDFStreamEngine` registers `OperatorProcessor` instances for every operator
in PDF 32000 §A.2. They divide into the following families:

| Family | Operators |
| --- | --- |
| Graphics state | `q`, `Q`, `cm`, `w`, `J`, `j`, `M`, `d`, `ri`, `i`, `gs` |
| Path construction | `m`, `l`, `c`, `v`, `y`, `h`, `re` |
| Path painting | `S`, `s`, `f`, `F`, `f*`, `B`, `B*`, `b`, `b*`, `n` |
| Clipping path | `W`, `W*` |
| Text object | `BT`, `ET` |
| Text state | `Tc`, `Tw`, `Tz`, `TL`, `Tf`, `Tr`, `Ts` |
| Text positioning | `Td`, `TD`, `Tm`, `T*` |
| Text showing | `Tj`, `TJ`, `'`, `"` |
| Color | `CS`, `cs`, `SC`, `SCN`, `sc`, `scn`, `G`, `g`, `RG`, `rg`, `K`, `k` |
| Shading | `sh` |
| Inline image | `BI`, `ID`, `EI` |
| XObject | `Do` |
| Marked content | `MP`, `DP`, `BMC`, `BDC`, `EMC` |
| Compatibility | `BX`, `EX` |
| Type-3 | `d0`, `d1` |

Every operator has a concrete `OperatorProcessor` subclass under
`pypdfbox.contentstream.operators.*` (e.g.
`pypdfbox.contentstream.operators.text.show_text.ShowText`). Custom engines
can override individual processors via `register_operator_processor`.

## Typical usage

```python
from pypdfbox import Loader
from pypdfbox.contentstream import PDFStreamEngine, OperatorName

class FontCounter(PDFStreamEngine):
    def __init__(self):
        super().__init__()
        self.fonts = set()

    def process_operator(self, operator, operands):
        if operator.op_name == OperatorName.SET_FONT_AND_SIZE:
            font_name = operands[0].name
            self.fonts.add(font_name)
        super().process_operator(operator, operands)

with Loader.load_pdf("in.pdf") as doc:
    engine = FontCounter()
    for page in doc.get_pages():
        engine.process_page(page)
    print(engine.fonts)
```

## Writing content streams

The writing side lives on `PDAbstractContentStream` (see
[pdmodel.md](pdmodel.md)) rather than this package — but the operator
constants from `OperatorName` are reused by both reader and writer for
consistency. `pypdfbox.pdfwriter.ContentStreamWriter` handles operand
formatting + spacing per upstream rules.

## PDFBox divergence

- `PDFStreamEngine.processOperator(op, args)` → `process_operator(op, operands)`.
- The Java `OperatorProcessor.process(Operator op, List<COSBase> args)` is
  `process(operator, arguments)`. `arguments` is a `list[COSBase]`.
- `WIND_NON_ZERO` / `WIND_EVEN_ODD` are integers (`0` / `1`) — same as
  `java.awt.geom.PathIterator`. Pass into `clip(rule)` /
  `fill_path(rule)`.
- `PDFGraphicsStreamEngine` uses tuples `(x, y)` for points instead of
  Java `Point2D`. Callers can use `pypdfbox.util.Vector` if they want a
  named-tuple-like object.

## See also

- [pdmodel.md](pdmodel.md) — `PDAbstractContentStream`,
  `PDPageContentStream`.
- [text.md](text.md) — `PDFTextStripper` is a `PDFStreamEngine` subclass.
- [rendering.md](rendering.md) — `PageDrawer` is the rasteriser-flavour
  engine.
- [guides/custom-engines.md](../guides/custom-engines.md) — building a
  bespoke content-stream consumer.
