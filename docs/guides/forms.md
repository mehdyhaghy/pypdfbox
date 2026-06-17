# AcroForms

Pypdfbox mirrors the upstream
[`pypdfbox.pdmodel.interactive.form`](../api/pdmodel.md) package
class-for-class: `PDAcroForm`, `PDField`, `PDTextField`, `PDCheckBox`,
`PDRadioButton`, `PDChoice`, `PDPushButton`, and `PDSignatureField`.

## Load a PDF with a form

```python
from pypdfbox.pdmodel import PDDocument

with PDDocument.load("form.pdf") as doc:
    catalog = doc.get_document_catalog()
    acro_form = catalog.get_acro_form()
    if acro_form is None or acro_form.is_empty():
        print("No AcroForm in this document.")
```

`get_acro_form()` returns `None` when the catalog has no `/AcroForm`.
Use `get_acro_form_or_create()` to create one on demand.

## Iterate fields and read values

```python
with PDDocument.load("form.pdf") as doc:
    acro_form = doc.get_document_catalog().get_acro_form()
    for field in acro_form.get_field_iterator():
        print(
            f"{field.get_fully_qualified_name()!r} "
            f"({type(field).__name__}) = {field.get_value_as_string()!r}"
        )
```

`get_field_iterator()` walks the field tree (including non-terminal
parents); `get_fields()` returns only the top-level entries. The
field tree is a forest rooted at the AcroForm's `/Fields` array.

## Set field values

Each subclass mirrors the upstream type's `set_value` semantics:

```python
from pypdfbox.pdmodel.interactive.form import (
    PDCheckBox,
    PDChoice,
    PDRadioButton,
    PDSignatureField,
    PDTextField,
)

with PDDocument.load("form.pdf") as doc:
    acro_form = doc.get_document_catalog().get_acro_form()

    name = acro_form.get_field("Customer.Name")
    if isinstance(name, PDTextField):
        name.set_value("Ada Lovelace", regenerate_appearance=True)

    subscribe = acro_form.get_field("Subscribe")
    if isinstance(subscribe, PDCheckBox):
        subscribe.check()                # convenience
        # or: subscribe.set_value("Yes", regenerate_appearance=True)

    plan = acro_form.get_field("Plan")
    if isinstance(plan, PDRadioButton):
        plan.set_value("Annual")          # value must be an on-state name

    country = acro_form.get_field("Country")
    if isinstance(country, PDChoice):
        country.set_value("Brazil")       # str or list[str] for multi-select

    sig = acro_form.get_field("ApplicantSignature")
    if isinstance(sig, PDSignatureField):
        # PDSignatureField.set_value takes a PDSignature object — see
        # the signing guide.
        pass

    doc.save("filled.pdf")
```

`set_value` accepts `regenerate_appearance=True` to rebuild each
widget's `/AP /N` normal appearance. Leave it `False` if you plan to
flatten or re-render externally and don't want the lite appearance
generator touching the object graph.

## Field-name path navigation

Fields use dot-delimited fully-qualified names. `get_field` accepts
the full path:

```python
acro_form.get_field("Address.City")           # nested terminal field
acro_form.get_field("Address")                # non-terminal parent
acro_form.get_field("Address.City.Region")    # arbitrary depth
```

Names that don't resolve return `None`. The first lookup builds a
cache; subsequent lookups are O(1).

## Flatten the form

`flatten()` walks every widget, paints its current appearance into
the host page's content stream, and removes the field from the form.
After flattening every field, the catalog's `/AcroForm` entry is
dropped:

```python
with PDDocument.load("form.pdf") as doc:
    acro_form = doc.get_document_catalog().get_acro_form()
    acro_form.flatten(refresh_appearances=True)
    doc.save("flat.pdf")
```

To flatten only a subset, pass a list of fields:

```python
field = acro_form.get_field("Signature")
acro_form.flatten(fields=[field])
```

The `refresh_appearances=True` flag regenerates each widget's
appearance via the lite `PDAppearanceGenerator` before painting — use
it when the source PDF was filled with `/V` but never built an `/AP`.

## Rich-text values in text fields

A supported XHTML subset is recognised for the `/RV`
rich-text-value entry on text fields with the rich-text flag. The
supported tag set is: `<p>`, `<span>`, `<br>`, `<b>`, `<strong>`,
`<i>`, `<em>`, `<u>`, `<sub>`, `<sup>`, and `<font color=... face=...
size=...>`. All other tags are ignored; unknown attributes are
ignored.

```python
text = acro_form.get_field("Bio")
text.set_value("Hello <b>world</b>", regenerate_appearance=True)
text.set_rich_text_value(
    "<p>This is <b>bold</b> with <font color='#ff8800'>color</font>.</p>"
)
```

The plain `/V` stays in sync — viewers that do not honour `/RV` see
the unformatted text.

## Default-appearance font resolution

`/DA` strings reference a font by resource name (e.g.
`/Helv 12 Tf 0 g`). Pypdfbox follows upstream's three-tier
resolution order when generating field appearances:

1. The form's default resources (`/AcroForm /DR /Font`).
2. The widget's existing normal appearance resources (`/AP /N /Resources /Font`).
3. The host page's resources (`/Resources /Font`).

When the source PDF authors `/DA /OldFont 12 Tf` but only the page
carries `/OldFont`, the generator now finds the font instead of
falling back to a standard-14 default.

## Push-button appearance variants

Push-button widgets carry up to three appearance dictionaries: `/N`
(normal), `/R` (rollover), and `/D` (down/pressed). All three are
serialised when generating push-button appearances:

```python
from pypdfbox.pdmodel.interactive.form import PDPushButton

btn = acro_form.get_field("Submit")
if isinstance(btn, PDPushButton):
    btn.set_caption("Submit", regenerate_appearance=True)
    btn.set_caption_rollover("Submit →", regenerate_appearance=True)
    btn.set_caption_down("Submitting...", regenerate_appearance=True)
```

The exact setter names depend on whether the widget is configured
for caption-only, icon-only, or icon+caption — consult
`PDAppearanceCharacteristicsDictionary` for the full surface.

## See also

- [API reference: `pypdfbox.pdmodel.interactive.form`](../api/pdmodel.md)
- [Examples: `pypdfbox/examples/interactive/form/`](https://github.com/Mehdy-haghy/pypdfbox/tree/main/pypdfbox/examples/interactive/form)
- [Signing guide](signing.md) for `PDSignatureField.set_value`
- [Documentation index](../index.md)
