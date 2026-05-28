import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;

/**
 * Live oracle probe: emit Apache PDFBox's view of a PDF's effective version,
 * exercising the PDF 32000-1 §7.5.2 catalog ``/Version`` override semantics.
 *
 * Per the spec, the document catalog may carry a ``/Version`` name entry that
 * overrides the file-header ``%PDF-1.X`` declaration *when it is later*.
 * PDFBox's PDDocument.getVersion() reflects this with a literal
 * ``max(catalogVersion, headerVersion)`` resolution; if the catalog's
 * ``/Version`` is older than (or equal to) the header the header wins —
 * versions never roll backwards.
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; CatalogVersionProbe input.pdf
 *
 * Output (UTF-8, stdout, line-oriented, no framing):
 *   resolved=&lt;float, formatted "%.1f"&gt;
 *   header=&lt;float, formatted "%.1f"&gt;
 *   catalog=&lt;name-string-or-NULL&gt;
 *
 * The ``resolved`` line is the headline ``PDDocument.getVersion()`` value —
 * what end-user tooling actually reads. ``header`` is the raw
 * ``COSDocument.getVersion()`` (what the parser pulled from ``%PDF-1.X``).
 * ``catalog`` is the raw ``PDDocumentCatalog.getVersion()`` (the optional
 * /Version name, NULL when absent). Together the three lines pinpoint
 * exactly which side of the max() determined the resolved value.
 */
public final class CatalogVersionProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            COSDocument cosDoc = doc.getDocument();

            out.println(String.format("resolved=%.1f", doc.getVersion()));
            out.println(String.format("header=%.1f", cosDoc.getVersion()));
            out.println("catalog=" + nz(cat.getVersion()));
        }
    }
}
