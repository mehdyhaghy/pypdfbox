# Upstream PDFBox 3.0.x has no ``contentstream/`` test directory under
# ``pdfbox/src/test/java/org/apache/pdfbox/``. PDFStreamEngine and the
# operator dispatch path are covered indirectly through integration
# tests in ``text/`` (PDFTextStripperTest) and ``rendering/``
# (TestPDFToImage). Those depend on font + rendering machinery that
# arrives in pypdfbox clusters #7 and #9; we will port the relevant
# integration tests when those clusters land.
