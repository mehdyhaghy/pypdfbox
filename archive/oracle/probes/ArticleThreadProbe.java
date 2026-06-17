import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThread;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDThreadBead;

/**
 * Live oracle probe for ARTICLE THREADS / BEADS.
 *
 * Surface: PDDocumentCatalog.getThreads() -> per-thread PDThread, walking each
 * thread's /I info dict (its /Title) + /F first bead, then the circular bead
 * linked-list via /N next, emitting each bead's /P page index + /R rectangle.
 *
 * read mode only (pypdfbox authors the PDF; this probe re-reads it):
 *
 *   java ... ArticleThreadProbe read out.pdf
 *
 * Emits, per thread (in /Threads array order):
 *
 *   THREAD <thread index>
 *   TITLE <info /Title>                 (or "TITLE none")
 *   BEAD <page index> <llx>,<lly>,<urx>,<ury>   (per bead, in /N order)
 *   ...
 *   ENDTHREAD
 *
 * Page index comes from doc.getPages().indexOf(bead.getPage()); rect from
 * PDThreadBead.getRectangle() reduced to its four corners. The /N walk is
 * identity-guarded against the first bead so the circular list terminates.
 */
public final class ArticleThreadProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("read".equals(mode)) {
            read(file);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static String num(float v) {
        return v == (int) v ? Integer.toString((int) v) : Float.toString(v);
    }

    private static String rectOf(PDRectangle r) {
        if (r == null) {
            return "none";
        }
        return num(r.getLowerLeftX()) + "," + num(r.getLowerLeftY()) + ","
                + num(r.getUpperRightX()) + "," + num(r.getUpperRightY());
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            List<PDThread> threads = catalog.getThreads();
            int ti = 0;
            for (PDThread thread : threads) {
                sb.append("THREAD ").append(ti).append('\n');
                PDDocumentInformation info = thread.getThreadInfo();
                String title = info == null ? null : info.getTitle();
                sb.append("TITLE ").append(title == null ? "none" : title).append('\n');

                PDThreadBead first = thread.getFirstBead();
                if (first != null) {
                    PDThreadBead bead = first;
                    do {
                        PDPage page = bead.getPage();
                        int pageIndex = page == null ? -1 : doc.getPages().indexOf(page);
                        sb.append("BEAD ").append(pageIndex).append(' ')
                                .append(rectOf(bead.getRectangle())).append('\n');
                        bead = bead.getNextBead();
                    } while (bead != null && bead.getCOSObject() != first.getCOSObject());
                }
                sb.append("ENDTHREAD\n");
                ti++;
            }
        }
        out.print(sb);
    }
}
