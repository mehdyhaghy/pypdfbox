"""Port of ``org.apache.pdfbox.examples.ant``.

Apache Ant is Java-only — there is no canonical Python equivalent. The
class is preserved for parity so the public surface lines up with
upstream PDFBox; ``execute()`` raises ``NotImplementedError``.
"""

from pypdfbox.examples.ant.pdf_to_text_task import PDFToTextTask

__all__ = ["PDFToTextTask"]
