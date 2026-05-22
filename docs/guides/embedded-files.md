# Embedded files

Pypdfbox ports the file-attachment surface under
[`pypdfbox.pdmodel.common.filespecification`](../api/pdmodel.md):
`PDFileSpecification`, `PDComplexFileSpecification`, and
`PDEmbeddedFile`. Attachments are addressed through the document
catalog's `/Names /EmbeddedFiles` name tree.

## Iterate embedded files

```python
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary

with PDDocument.load("input.pdf") as doc:
    names = PDDocumentNameDictionary(doc.get_document_catalog())
    ef_tree = names.get_embedded_files()
    if ef_tree is None:
        print("No embedded files.")
    else:
        # The name tree may have leaf names directly or a /Kids subtree;
        # walk both forms.
        def walk(node):
            entries = node.get_names() or {}
            yield from entries.items()
            for kid in node.get_kids() or []:
                yield from walk(kid)

        for filename, file_spec in walk(ef_tree):
            print(filename, "→", file_spec.get_file() or file_spec.get_file_unicode())
            print("  description:", file_spec.get_file_description())
            print("  AFRelationship:", file_spec.get_af_relationship())
```

The same name-tree walk is exposed in
[`pypdfbox/examples/pdmodel/extract_embedded_files.py`](https://github.com/Mehdy-haghy/pypdfbox/blob/main/pypdfbox/examples/pdmodel/extract_embedded_files.py)
including a path-traversal guard before writing each file out.

## Add an embedded file

```python
import datetime as dt
import io
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import (
    PDEmbeddedFile,
)
from pypdfbox.pdmodel.pd_document_name_dictionary import PDDocumentNameDictionary
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
from pypdfbox.pdmodel.page_mode import PageMode

with PDDocument.load("input.pdf") as doc:
    payload = b"Hello from an embedded file"

    # The embedded stream — payload + metadata (MIME type, size, ...).
    ef = PDEmbeddedFile(doc, io.BytesIO(payload))
    ef.set_subtype("text/plain")
    ef.set_size(len(payload))
    ef.set_creation_date(dt.datetime.now(dt.timezone.utc))

    # The file specification — name + description + the embedded stream.
    fs = PDComplexFileSpecification()
    fs.set_file("notes.txt")
    fs.set_file_unicode("notes.txt")
    fs.set_embedded_file(ef)
    fs.set_embedded_file_unicode(ef)
    fs.set_file_description("Reviewer notes")

    # Install into the catalog's /Names /EmbeddedFiles tree.
    leaf = PDEmbeddedFilesNameTreeNode()
    leaf.set_names({"notes.txt": fs})
    root = PDEmbeddedFilesNameTreeNode()
    root.set_kids([leaf])

    names = PDDocumentNameDictionary(doc.get_document_catalog())
    names.set_embedded_files(root)
    doc.get_document_catalog().set_names(names)

    # Optional: ask viewers to open the attachments panel.
    doc.get_document_catalog().set_page_mode(PageMode.USE_ATTACHMENTS)

    doc.save("with-attachment.pdf")
```

Setting both `set_file` / `set_file_unicode` and `set_embedded_file`
/ `set_embedded_file_unicode` keeps platform-specific viewers
working — older Windows-only readers fall back to the non-unicode
form.

## Extract embedded files

```python
from pathlib import Path

with PDDocument.load("with-attachment.pdf") as doc:
    names = PDDocumentNameDictionary(doc.get_document_catalog())
    ef_tree = names.get_embedded_files()
    out_dir = Path("attachments")
    out_dir.mkdir(exist_ok=True)

    def emit(node):
        for filename, fs in (node.get_names() or {}).items():
            ef = fs.get_embedded_file_unicode() or fs.get_embedded_file()
            if ef is None:
                continue
            (out_dir / filename).write_bytes(ef.to_byte_array())
        for kid in node.get_kids() or []:
            emit(kid)

    if ef_tree is not None:
        emit(ef_tree)
```

A second source of embedded files is per-page `FileAttachment`
annotations (PDF 32000-1 §12.5.6.15). The
`extract_files_from_page` helper in
`pypdfbox.examples.pdmodel.extract_embedded_files` shows how to find
them — iterate `page.get_annotations()` and skip anything that is
not a `PDAnnotationFileAttachment`.

## PDF/A-3 attachment relationships

PDF/A-3 requires every embedded file to carry an `/AFRelationship`
entry that explains how the attachment relates to the visible
content. The supported names are: `Source`, `Data`, `Alternative`,
`Supplement`, and `Unspecified` — they correspond to the spec's
Table 408. Pypdfbox exposes them through:

```python
fs.set_af_relationship("Source")
print(fs.get_af_relationship())            # "Source"
print(PDComplexFileSpecification.is_standard_af_relationship("Data"))   # True
```

PDF/A-3 also requires every attachment to be referenced from a
parent's `/AF` array — typically the document catalog or a page
dictionary:

```python
from pypdfbox.cos import COSArray

af_array = COSArray()
af_array.add(fs.get_cos_object())
doc.get_document_catalog().get_cos_object().set_item("AF", af_array)
```

Pypdfbox does not validate PDF/A conformance itself (see the
[support](../support.md) page and `CLAUDE.md` for why). The
`/AFRelationship` setter is just the data plumbing — verifying that
your output is actually PDF/A-3-compliant is left to a
permissively-licensed external validator of your choice.

## See also

- [Examples: `embedded_files.py`](https://github.com/Mehdy-haghy/pypdfbox/blob/main/pypdfbox/examples/pdmodel/embedded_files.py)
- [Examples: `extract_embedded_files.py`](https://github.com/Mehdy-haghy/pypdfbox/blob/main/pypdfbox/examples/pdmodel/extract_embedded_files.py)
- [API reference: `pypdfbox.pdmodel`](../api/pdmodel.md)
- [Documentation index](../index.md)
