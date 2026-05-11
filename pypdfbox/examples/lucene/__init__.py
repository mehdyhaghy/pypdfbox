"""Port of ``org.apache.pdfbox.examples.lucene``.

The upstream demo populates an Apache Lucene index with extracted PDF
text. Lucene has no canonical Python equivalent (``pylucene`` is a JNI
shim and ``whoosh`` is unmaintained), so the ports keep the public
method surface for parity but raise ``NotImplementedError`` from
``main()``. Users wanting to wire pypdfbox to a search index can supply
their own backend by extending these classes.
"""

from pypdfbox.examples.lucene.index_pdf_files import IndexPDFFiles
from pypdfbox.examples.lucene.lucene_pdf_document import LucenePDFDocument

__all__ = [
    "IndexPDFFiles",
    "LucenePDFDocument",
]
