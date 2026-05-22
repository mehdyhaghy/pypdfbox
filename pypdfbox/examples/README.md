# pypdfbox.examples

Direct port of `org.apache.pdfbox.examples` —
the `examples/src/main/java/org/apache/pdfbox/examples/*` tree
upstream ships as runnable sample code. Each subdirectory here
mirrors the matching upstream package, and each file is a
near-line-for-line translation of the Java source. They are not
production tools; they are read-along examples for callers who
want to learn the API surface by running real code.

These are reference scripts, not library modules. Every file has
either a `main()` entry point or a `if __name__ == "__main__":`
runner block that takes CLI args mirroring the upstream Java
sample's `args[]` contract — so a snippet pasted into a PDFBox
docs page translates one-for-one.

## Layout

```
pypdfbox/examples/
  ant/           # Ant-task helpers
  interactive/   # AcroForm widgets
    form/        # form-field examples
  lucene/        # Apache Lucene full-text indexing of PDFs
  pdmodel/       # PDF document-model examples (the bulk of the tree)
  printing/      # Java2D printing pipeline samples
  rendering/     # Custom rendering / page-drawer hooks
  signature/     # PKCS#7 / PAdES signing pipelines
    cert/        # certificate-verification helpers
    validation/  # PAdES-LTV / DSS / VRI builders
  util/          # Stand-alone command-line utilities
```

## Categories

### `pdmodel/`

The largest cluster — examples that exercise the high-level
document model. Cover document creation
(`create_blank_pdf.py`, `hello_world.py`, `hello_world_ttf.py`,
`hello_world_type1.py`), bookmarks
(`create_bookmarks.py`, `print_bookmarks.py`,
`go_to_second_bookmark_on_open.py`), font embedding
(`embedded_fonts.py`, `embedded_multiple_fonts.py`,
`embedded_vertical_fonts.py`, `extract_ttf_fonts.py`), images
(`add_image_to_pdf.py`, `rubber_stamp.py`,
`rubber_stamp_with_image.py`), metadata
(`add_metadata_from_doc_info.py`,
`print_document_meta_data.py`, `extract_metadata.py`), page
manipulation (`add_message_to_each_page.py`,
`remove_first_page.py`, `superimpose_page.py`,
`create_landscape_pdf.py`, `create_page_labels.py`),
annotations / links (`add_annotations.py`, `print_urls.py`,
`replace_urls.py`), colour / patterns / shadings
(`create_patterns_pdf.py`, `create_gradient_shading_pdf.py`,
`create_separation_color_box.py`, `show_color_boxes.py`),
JavaScript actions (`add_javascript.py`), text positioning
(`show_text_with_positioning.py`, `using_text_matrix.py`),
embedded files (`embedded_files.py`,
`extract_embedded_files.py`), portfolios
(`create_portable_collection.py`), tagged PDF
(`create_pdfa.py`), and the Bengali Unicode demo
(`bengali_pdf_generation_hello_world.py`).

### `interactive/form/`

AcroForm field examples — every widget type plus the field-lock,
field-trigger, and field-removal helpers. `create_simple_form.py`,
`create_simple_form_with_embedded_font.py`,
`create_check_box.py`, `create_push_button.py`,
`create_radio_buttons.py`, `create_multi_widgets_form.py`,
`fill_form_field.py`, `set_field.py`, `print_fields.py`,
`field_remover.py`, `field_triggers.py`,
`add_border_to_field.py`, `update_field_on_document_open.py`,
`determine_text_fits_field.py`.

### `signature/`

PKCS#7 / PAdES signing examples — the same shape as upstream's
`signature/` examples. Cover the basic detached PKCS#7 sign
(`create_signature.py`, `create_signature_base.py`), visible
signature widgets (`create_visible_signature.py`,
`create_visible_signature2.py`), document-level timestamps
(`create_embedded_time_stamp.py`, `create_signed_time_stamp.py`,
`validation_time_stamp.py`), an empty signature form
(`create_empty_signature_form.py`), signature inspection
(`show_signature.py`), the helper utilities
(`cms_processable_input_stream.py`, `sig_utils.py`,
`tsa_client.py`), and the LTV / DSS / VRI revocation-info
pipeline (`validation/add_validation_information.py`,
`validation/cert_information_collector.py`,
`validation/cert_information_helper.py`,
`validation/cert_signature_information.py`). The `cert/`
sibling holds the certificate-verifier shells
(`certificate_verifier.py`, `crl_verifier.py`, `ocsp_helper.py`,
`sha1_digest_calculator.py`, `revocation_collector.py`,
`certificate_verification_result.py`,
`revoked_certificate_exception.py`).

### `rendering/`

Hooks against `PDFRenderer` — `custom_page_drawer.py`
demonstrates a subclassed page drawer that intercepts the
content-stream operator stream, and
`custom_graphics_stream_engine.py` shows the lower-level
`GraphicsStreamEngine` walk (no rasterisation, just operator
tracing).

### `printing/`

Java2D printing pipeline ports —
`printing.py` is the basic print sample, and the three
`opaque_*` modules port upstream's opaque-print-job helpers
(`opaque_draw_object.py`, `opaque_pdf_renderer.py`,
`opaque_set_graphics_state_parameters.py`). On the Python side
these route through `PDFRenderer` + the host OS spooler.

### `util/`

Standalone command-line utilities. Watermarking
(`add_watermark_text.py`), text-layout debugging
(`draw_print_text_locations.py`,
`print_text_locations.py`, `print_image_locations.py`,
`print_text_colors.py`), area-bounded text extraction
(`extract_text_by_area.py`, `extract_text_simple.py`),
booklet splitting (`split_booklet.py`), text removal
(`remove_all_text.py`), a CLI merger
(`pdf_merger_example.py`), the
`pdf_highlighter.py` keyword-highlight tool, and the
`connected_input_stream.py` helper.

### `lucene/`

Apache Lucene full-text indexing examples
(`index_pdf_files.py`, `lucene_pdf_document.py`).
Lucene is not a runtime dependency of pypdfbox — these
illustrate the integration pattern; downstream users wire in
their own search engine.

### `ant/`

Ant-task wrapper port (`pdf_to_text_task.py`). Apache Ant is a
Java build tool; the Python translation exists for parity with
the upstream tree, but isn't used in practice on the Python
side. Read it as documentation of the upstream invocation
shape.

## Running an example

Each script is meant to be run directly. With pypdfbox installed
(or with the repo on `PYTHONPATH`):

```sh
python -m pypdfbox.examples.pdmodel.hello_world out.pdf
python -m pypdfbox.examples.util.extract_text_simple in.pdf out.txt
```

Args mirror the upstream Java sample's `args[]`. If you're
unsure, the file's docstring usually mentions the expected
positional arguments.

## Parity note

These examples are not in the public API surface. They are not
versioned, not exposed through `pypdfbox/__init__.py`, and not
covered by the same parity SLA as the rest of the package.
Treat them as snippets — copy out what you need into your own
code. Tests for the example scripts live under
`tests/examples/`, but they exercise basic smoke-runnability
rather than enforcing API stability.

Provenance for every ported example file is tracked in the
top-level `PROVENANCE.md` against its upstream
`examples/src/main/java/org/apache/pdfbox/examples/...` path.
