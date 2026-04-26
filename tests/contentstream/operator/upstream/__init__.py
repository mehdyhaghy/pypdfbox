# Upstream PDFBox 3.0.x has no per-operator test classes under
# ``pdfbox/src/test/java/org/apache/pdfbox/contentstream/operator/``.
# The text operators are exercised indirectly through PDFTextStripper
# integration tests (text/) and rendering parity tests (rendering/),
# both of which require font + rendering infrastructure that lands in
# pypdfbox clusters #7/#9. Once those clusters ship we will revisit
# here and port the relevant integration tests.
