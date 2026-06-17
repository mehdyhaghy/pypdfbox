import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PageLayout;
import org.apache.pdfbox.pdmodel.PageMode;

/**
 * Live oracle probe: emit Apache PDFBox's view of the catalog /PageMode and
 * /PageLayout enum name for a single PDF.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CatalogPageEnumProbe input.pdf
 *
 * Apache PDFBox bakes the PDF 32000-1 §7.7.3.3 Table 28 spec default into
 * getPageMode() (UseNone) and getPageLayout() (SinglePage) — both getters are
 * non-null. We emit the stringValue() of each so the Python side can assert the
 * full six-member enum matrix (PageMode: UseNone / UseOutlines / UseThumbs /
 * FullScreen / UseOC / UseAttachments; PageLayout: SinglePage / OneColumn /
 * TwoColumnLeft / TwoColumnRight / TwoPageLeft / TwoPageRight) round-trips
 * byte-for-byte through a pypdfbox-built file.
 *
 * Output (UTF-8, stdout, two lines):
 *   pageMode=<PageMode.stringValue()>
 *   pageLayout=<PageLayout.stringValue()>
 */
public final class CatalogPageEnumProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            PageMode mode = cat.getPageMode();
            PageLayout layout = cat.getPageLayout();
            out.println("pageMode=" + mode.stringValue());
            out.println("pageLayout=" + layout.stringValue());
        }
    }
}
