import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe for differential mutation-fuzz of the lenient load path.
 *
 * Apache PDFBox's {@code Loader.loadPDF} is lenient by default: garbled
 * {@code startxref} pointers, wrong subsection offsets, corrupt {@code /Length},
 * swapped {@code obj}/{@code endobj} tokens, broken object streams, etc. all
 * trigger brute-force recovery (rescan body for {@code N G obj}, rebuild xref +
 * trailer). This probe captures the recovered FACTS so pypdfbox can be held to
 * the same outcome (not byte offsets):
 *
 *   ok=<true|false>
 *   pages=<n>                            (only when ok)
 *   root=<present|absent>                (trailer /Root resolves to a dict)
 *   media=<llx lly urx ury|none>         (first page MediaBox, canonical floats)
 *
 * On any throw the sole line is {@code ok=false}.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> MutationFuzzProbe input.pdf
 */
public final class MutationFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pages = doc.getNumberOfPages();
            COSDocument cos = doc.getDocument();
            COSDictionary trailer = cos.getTrailer();
            boolean root = false;
            if (trailer != null) {
                COSBase r = trailer.getDictionaryObject(COSName.ROOT);
                root = r instanceof COSDictionary;
            }
            String media = "none";
            if (pages > 0) {
                PDPage page = doc.getPage(0);
                media = box(page.getMediaBox());
            }
            sb.append("ok=true\n");
            sb.append("pages=").append(pages).append('\n');
            sb.append("root=").append(root ? "present" : "absent").append('\n');
            sb.append("media=").append(media).append('\n');
        } catch (Throwable t) {
            out.print("ok=false\n");
            return;
        }
        out.print(sb);
    }

    private static String box(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + " " + fmt(r.getLowerLeftY()) + " "
             + fmt(r.getUpperRightX()) + " " + fmt(r.getUpperRightY());
    }

    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        String s = String.format(Locale.ROOT, "%.4f", v);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') {
            end--;
        }
        if (end > 0 && s.charAt(end - 1) == '.') {
            end--;
        }
        return s.substring(0, end);
    }
}
