# pypdfbox.pdmodel.interactive — annotations, forms, actions, signatures

`pypdfbox.pdmodel.interactive` covers everything that makes a PDF
interactive: comment-style annotations, AcroForm fields, action dispatch,
the outline tree, and digital signatures. The package mirrors
`org.apache.pdfbox.pdmodel.interactive` exactly. There is no `__init__`
re-export at the top level — import from the relevant sub-package.

## Annotations (`pypdfbox.pdmodel.interactive.annotation`)

Every annotation type defined in PDF 32000 §12.5 has a class. Common base
classes hold shared behaviour: `PDAnnotation` is the root,
`PDAnnotationMarkup` adds `/T` (author) and `/Popup`, `PDAnnotationText`
inherits from `PDAnnotationMarkup`, etc.

| Class | PDF `/Subtype` |
| --- | --- |
| `PDAnnotation` | Abstract root. |
| `PDAnnotationMarkup` | Common base for text-markup-style annotations. |
| `PDAnnotationText` | `/Text` (sticky note). |
| `PDAnnotationLink` | `/Link`. |
| `PDAnnotationFreeText` | `/FreeText`. |
| `PDAnnotationLine` | `/Line`. |
| `PDAnnotationSquare` / `PDAnnotationCircle` / `PDAnnotationSquareCircle` | `/Square`, `/Circle`. |
| `PDAnnotationPolygon` / `PDAnnotationPolyline` | `/Polygon`, `/PolyLine`. |
| `PDAnnotationHighlight` / `PDAnnotationUnderline` / `PDAnnotationStrikeout` / `PDAnnotationSquiggly` / `PDAnnotationTextMarkup` | Text markup family. |
| `PDAnnotationCaret` | `/Caret`. |
| `PDAnnotationInk` | `/Ink`. |
| `PDAnnotationPopup` | `/Popup`. |
| `PDAnnotationFileAttachment` | `/FileAttachment`. |
| `PDAnnotationSound` | `/Sound`. |
| `PDAnnotationMovie` | `/Movie`. |
| `PDAnnotationScreen` | `/Screen`. |
| `PDAnnotationStamp` / `PDAnnotationRubberStamp` | `/Stamp`. |
| `PDAnnotationPrinterMark` | `/PrinterMark`. |
| `PDAnnotationTrapNet` | `/TrapNet`. |
| `PDAnnotationWatermark` | `/Watermark`. |
| `PDAnnotation3D` | `/3D`. |
| `PDAnnotationRedact` | `/Redact`. |
| `PDAnnotationWidget` | `/Widget` (forms). |
| `PDAnnotationUnknown` | Fallback wrapper for non-standard `/Subtype` values. |
| `AnnotationFilter` | Protocol to filter `PDPage.get_annotations()`. |

Appearance / border / icon helpers:

| Class | Purpose |
| --- | --- |
| `PDAppearanceDictionary` | `/AP` dictionary (normal / rollover / down). |
| `PDAppearanceEntry` | A single entry inside `/AP`. |
| `PDAppearanceStream` | A content-stream form X-object used as an appearance. |
| `PDAppearanceContentStream` | Helper to write appearance streams (subclass of `PDAbstractContentStream`). |
| `PDAppearanceCharacteristicsDictionary` | `/MK` dictionary (button caption + border color). |
| `PDBorderStyleDictionary` | `/BS` dictionary. |
| `PDBorderEffectDictionary` | `/BE` dictionary. |
| `PDIconFit` | `/IF` icon-fit options. |
| `PDInkList` | Polyline path for `/Ink` annotations. |
| `PDLineInfo` | `/LE`, `/LL`, `/LLE`, `/IT` for line annotations. |
| `PDPathInfo` | Path geometry for polygon/polyline annotations. |
| `PDVertices` | Vertex list for polygon/polyline annotations. |
| `PDMovie` / `PDMovieActivation` | Movie metadata. |
| `PDExternalDataDictionary` | `/ExData` for trap-net / 3D annotations. |

## Forms (`pypdfbox.pdmodel.interactive.form`)

| Class | Purpose |
| --- | --- |
| `PDAcroForm` | The `/AcroForm` dictionary. `get_fields`, `get_field(fully_qualified_name)`, `flatten`, `refresh_appearances`, `import_fdf`, `export_fdf`, `set_need_appearances`. |
| `PDFieldTree` | Iterate the (possibly nested) field hierarchy. |
| `PDFieldIterator` | Internal lazy iterator backing `PDFieldTree`. |
| `PDField` | Abstract field. `get_fully_qualified_name`, `get_partial_name`, `get_value`, `set_value`, `get_field_type`, `get_widgets`. |
| `PDTerminalField` | Abstract base for leaf fields. |
| `PDNonTerminalField` | Branch field (has `/Kids`). |
| `PDTextField` | `/Tx`. `set_value(str)`, `get_max_length`. |
| `PDChoice` | `/Ch` shared base. `set_options(list)`. |
| `PDListBox` | `/Ch` with multi-select. |
| `PDComboBox` | `/Ch` with edit. |
| `PDButton` | `/Btn` shared base. |
| `PDCheckBox` | `/Btn` non-radio non-pushbutton. |
| `PDRadioButton` | `/Btn` radio. |
| `PDPushButton` | `/Btn` pushbutton. |
| `PDSignatureField` | `/Sig` — wraps a `PDSignature`. |
| `PDVariableText` | Common base for `PDTextField`/`PDChoice` (`/DA` default appearance, `/Q` quadding, `/RV` rich value). |
| `PDFieldFactory` | Dispatch on `/FT` to instantiate the right `PDField` subtype. |
| `PDFieldStub` | Read-only placeholder for fields whose type is not yet supported. |
| `PDXFAResource` | Wraps `/XFA` data (legacy XFA-as-XML; rendering is out of scope). |
| `PDAppearanceGenerator` | Regenerates `/AP` streams from current field values + style. |
| `AppearanceGeneratorHelper` / `AppearanceStyle` / `PlainText` / `PlainTextFormatter` | Appearance generation plumbing. |
| `TextAlign` | `LEFT`, `CENTER`, `RIGHT`, `JUSTIFY`. |
| `ScriptingHandler` | Protocol for JavaScript dispatch — pluggable, default is a no-op. |
| `FieldUtils` / `KeyValue` / `Word` / `Line` / `Paragraph` / `Builder` | Layout primitives reused by the appearance generator. |

## Actions (`pypdfbox.pdmodel.interactive.action`)

`PDActionFactory.create_action(cos_dict)` dispatches on `/S` and returns
the correct subtype. Each action type is one class:

| Class | `/S` value |
| --- | --- |
| `PDActionGoTo` | `/GoTo` |
| `PDActionRemoteGoTo` | `/GoToR` |
| `PDActionEmbeddedGoTo` | `/GoToE` |
| `PDActionGoToDp` | `/GoToDp` |
| `PDActionGoTo3DView` | `/GoTo3DView` |
| `PDActionLaunch` | `/Launch` |
| `PDActionThread` | `/Thread` |
| `PDActionURI` | `/URI` |
| `PDActionSound` | `/Sound` |
| `PDActionMovie` | `/Movie` |
| `PDActionHide` | `/Hide` |
| `PDActionNamed` | `/Named` |
| `PDActionSubmitForm` | `/SubmitForm` |
| `PDActionResetForm` | `/ResetForm` |
| `PDActionImportData` | `/ImportData` |
| `PDActionSetOCGState` | `/SetOCGState` |
| `PDActionRendition` | `/Rendition` |
| `PDActionTransition` | `/Trans` |
| `PDActionJavaScript` | `/JavaScript` |
| `PDActionRichMediaExecute` | `/RichMediaExecute` |
| `PDActionUnknown` | Fallback. |

Trigger-point dictionaries:

| Class | Carries |
| --- | --- |
| `PDAdditionalActions` | Abstract base for `/AA` dictionaries. |
| `PDAnnotationAdditionalActions` | E/X/D/U/Fo/Bl on annotations. |
| `PDPageAdditionalActions` | O/C on pages. |
| `PDFormFieldAdditionalActions` | K/F/V/C on form fields. |
| `PDDocumentCatalogAdditionalActions` | WC/WS/DS/WP/DP on the catalog. |
| `PDURIDictionary` | `/URI` document-level dictionary. |
| `PDTargetDirectory` | `/T` target for embedded-go-to. |
| `PDWindowsLaunchParams` | `/Win` parameters for `Launch`. |
| `OpenMode` | `enum.Enum` open-action mode. |

## Outlines (`pypdfbox.pdmodel.interactive.documentnavigation.outline`)

| Class | Purpose |
| --- | --- |
| `PDOutlineNode` | Abstract node. `iter_children`, `add_first`, `add_last`. |
| `PDDocumentOutline` | The root outline (lives under `/Outlines`). |
| `PDOutlineItem` | A single bookmark entry. `get_title`, `set_title`, `get_destination`, `set_destination`, `get_action`. |

## Destinations (`pypdfbox.pdmodel.interactive.documentnavigation.destination`)

`PDDestination`, `PDPageDestination`, `PDPageFitDestination`,
`PDPageXYZDestination`, `PDPageFitHeightDestination`,
`PDPageFitWidthDestination`, `PDPageFitRectangleDestination`,
`PDPageFitBoundingBoxDestination`, `PDNamedDestination`.

## Digital signatures (`pypdfbox.pdmodel.interactive.digitalsignature`)

| Class | Purpose |
| --- | --- |
| `PDSignature` | The `/Sig` dictionary. `set_byte_range`, `set_contents`, `set_name`, `set_reason`, `set_location`, `set_sign_date`. |
| `PDSignatureLock` | Lock dictionary. |
| `PDSeedValue` / `PDSeedValueCertificate` / `PDSeedValueMDP` / `PDSeedValueTimeStamp` | `/SV` constraints. |
| `PDPropBuild` / `PDPropBuildDataDict` | `/Prop_Build` software-build metadata. |
| `PDDocumentSecurityStore` | `/DSS` LTV store (CRLs, OCSPs, certs). |
| `PDValidationInformation` | `/VRI` per-signature validation info. |
| `SignatureInterface` | Protocol — `sign(content_stream: io.IOBase) -> bytes`. The plug-in seam for PKCS#7 + timestamp providers. |
| `SignatureOptions` | Reservation-size + page index + form-field name configuration. `DEFAULT_SIGNATURE_SIZE` = 9472 bytes. |
| `SignatureValidationResult` | Result + per-check status enum. |
| `Pkcs7Signature` | Default `SignatureInterface` for PKCS#7 (CMS) signatures. |
| `TimestampedPkcs7Signature` | Adds an RFC 3161 timestamp via a configurable TSA URL. |
| `DocumentTimestampSigner` | Pure document-timestamp signer. |
| `SigningSupport` | Mid-level helpers (DSS construction, signed-attribute building, byte-range placement). |
| `COSFilterInputStream` | Helper input stream used during the signing digest computation. |
| `cms_helpers` functions | Lower-level cryptography helpers (built on `cryptography` and `pyhanko-certvalidator`). |
| `check_certificate_usage`, `check_responder_certificate_usage`, `check_time_stamp_certificate_usage`, `compute_byte_range`, `compute_signed_digest`, `extract_pkcs7_message_digest`, `get_last_relevant_signature`, `get_mdp_permission`, `set_mdp_permission` | Free functions. |

## Typical usage

```python
from pypdfbox import Loader
from pypdfbox.pdmodel.interactive.form import PDAcroForm

with Loader.load_pdf("form.pdf") as doc:
    form: PDAcroForm = doc.get_document_catalog().get_acro_form()
    form.get_field("Name").set_value("Ada Lovelace")
    form.flatten()
    doc.save("filled.pdf")
```

## See also

- [pdmodel.md](pdmodel.md) — `PDPage.get_annotations()` returns these
  classes.
- [contentstream.md](contentstream.md) — appearance streams write through
  the same operator surface.
- [guides/forms.md](../guides/forms.md), [guides/signing.md](../guides/signing.md).
