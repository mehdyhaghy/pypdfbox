# pypdfbox.xmpbox — XMP metadata read/write

`xmpbox` ports Apache PDFBox's `xmpbox` subproject. It parses XMP metadata
packets (typically the `/Metadata` stream on the document catalog) into a
typed schema hierarchy, and serialises modified schemas back to bytes for
re-embedding. The DOM is built on `xml.etree.ElementTree` (stdlib only).
The package was added in cluster #1 with the parser + common schemas, and
later waves added the typed property hierarchy, structured types, and the
serialiser.

## Public surface

| Class / function | Purpose |
| --- | --- |
| `XMPMetadata` | The root of an XMP packet. Owns a list of `XMPSchema` instances + namespace registry. `create_and_add_*` methods for each shipped schema. `serialize(prefix=False, padding=2048)` returns bytes (via `XmpSerializer`). |
| `DomXmpParser` | Parses bytes (XMP packet) → `XMPMetadata`. `parse(packet_bytes) -> XMPMetadata`. |
| `XmpParsingException` | Raised by the parser. |
| `XMPSchema` | Base schema. Holds typed properties + array properties. Subclasses below override `get_preferred_prefix` and `get_namespace`. |
| `AdobePDFSchema` | `xmlns:pdf` — Producer, Keywords, PDFVersion. |
| `DublinCoreSchema` | `xmlns:dc` — title, creator, subject, language, rights, etc. |
| `PhotoshopSchema` | `xmlns:photoshop` — Headline, City, AuthorsPosition. |
| `PDFAExtensionSchema` | `xmlns:pdfaExtension` — schema descriptions for custom PDF/A properties. |
| `PDFAIdentificationSchema` | `xmlns:pdfaid` — `part`, `conformance`, `revision`. |
| `PDFUAIdentificationSchema` | `xmlns:pdfuaid` — `part`. |
| `XMPBasicSchema` | `xmlns:xmp` — CreateDate, ModifyDate, MetadataDate, CreatorTool. |
| `XMPBasicJobTicketSchema` | `xmlns:xmpBJ` — JobRef (uses `JobType`). |
| `XMPRightsManagementSchema` | `xmlns:xmpRights`. |
| `XMPMediaManagementSchema` | `xmlns:xmpMM` — InstanceID, DocumentID, ManageTo, History, DerivedFrom (uses `ResourceRefType`, `ResourceEventType`). |
| `XMPageTextSchema` | `xmlns:xmpTPg` — MaxPageSize, NPages, Colorants, Fonts, PlateNames. |
| `ExifSchema` | `xmlns:exif` — full EXIF block (uses `GPSCoordinateType`, `CFAPatternType`, `OECFType`). |
| `TiffSchema` | `xmlns:tiff` — TIFF camera metadata. |
| `BadFieldValueException` | Raised when setting a typed property to an out-of-range value (e.g. PDF/A `part` outside 1-4). |

## Property type hierarchy (`pypdfbox.xmpbox.type`)

| Type | Purpose |
| --- | --- |
| `AbstractField` | Parent of every typed and structured property. Owns the (`namespace`, `prefix`, `property_name`) triple. |
| `AbstractSimpleProperty` | Common base for scalar properties (Text, Integer, Real, Date, Boolean, URL, URI, GUID). |
| `AbstractStructuredType` | Common base for structured types (ResourceRef, Thumbnail, Job, OECF, CFAPattern). |
| `TextType`, `IntegerType`, `RealType`, `BooleanType`, `DateType`, `URIType`, `URLType`, `GUIDType`, `MIMEType`, `XPathType`, `RenditionClassType`, `LocaleType`, `LangAlt`, `ChoiceType`, `RationalType`, `VersionType`, `AgentNameType`, `ProperNameType`, `PartType` | Simple types. |
| `ArrayProperty` | Bag/Seq/Alt container. Carries a `Cardinality` enum (`BAG`, `SEQ`, `ALT`). |
| `ResourceRefType`, `ResourceEventType`, `ThumbnailType`, `JobType`, `OECFType`, `CFAPatternType`, `ColorantType`, `DimensionsType`, `FontType`, `LayerType`, `GPSCoordinateType` | Structured types. |
| `Cardinality` | `enum.Enum` — `BAG`, `SEQ`, `ALT`. |
| `Attribute` | XML attribute on an XMP property. |
| `TypeMapping` | Registry — `(namespace, prefix, property_name)` → type class. Looked up by the DOM parser. |
| `DateConverter` | RFC 3339 / W3CDTF date helper. |

## Typical usage

```python
from pypdfbox import Loader, PDDocument
from pypdfbox.xmpbox import DomXmpParser, XMPMetadata

# Read
with Loader.load_pdf("in.pdf") as doc:
    md_stream = doc.get_document_catalog().get_metadata()
    if md_stream is not None:
        xmp = DomXmpParser().parse(md_stream.export_xmp_metadata())
        dc = xmp.get_dublin_core_schema()
        print(dc.get_title())

# Write
xmp = XMPMetadata.create_xmp_metadata()
dc = xmp.create_and_add_dublin_core_schema()
dc.set_title("Hello")
dc.add_creator("Ada Lovelace")
packet = xmp.serialize()
```

## Schema dispatch

`DomXmpParser` walks the XMP DOM. For each property element it looks up
`(namespace, property_name)` in `TypeMapping`; matched properties are
instantiated as the right typed subclass. Unknown namespaces fall back to
a plain `XMPSchema` with raw `TextType` values — they round-trip but
without typed accessors.

## PDFBox divergence

- `XMPMetadata.createXMPMetadata()` → `XMPMetadata.create_xmp_metadata()`.
- `XmpSerializer.serialize(metadata, OutputStream, prefix)` → top-level
  `XMPMetadata.serialize(prefix=False, padding=2048) -> bytes`. Pass to
  a `COSStream.create_output_stream()` if embedding.
- Schemas expose plain attribute setters (`schema.set_title("…")`)
  alongside method-form accessors for source parity.

## See also

- [pdmodel.md](pdmodel.md) —
  `PDDocumentCatalog.get_metadata() / set_metadata(stream)`.
- [guides/metadata.md](../guides/metadata.md) — common XMP recipes.
- `pypdfbox/xmpbox/__init__.py` docstring — cluster-by-cluster shipping
  history.
