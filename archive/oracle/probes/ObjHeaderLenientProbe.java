import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for object-header / endobj parser leniency.
 *
 * Apache PDFBox's {@code Loader.loadPDF} tolerates several common
 * malformations around the {@code N G obj ... endobj} envelope: extra
 * whitespace between the header and the object body, a {@code %}-comment
 * inserted inside an object, a missing {@code endobj} (next {@code N G obj}
 * marker arrives directly), and extra garbage bytes between {@code endobj}
 * and the next object. This probe captures the RECOVERED facts so pypdfbox
 * can be held to the same lenient outcome.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ObjHeaderLenientProbe input.pdf
 *
 * Output (UTF-8, LF-terminated). When PDFBox loads the file:
 *
 *   pages=&lt;n&gt;
 *   objects=&lt;COSDocument xref-table size&gt;
 *   root=&lt;present|absent&gt;
 *   info=&lt;present|absent&gt;
 *   text=&lt;repr of PDFTextStripper text with \n -&gt; \\n, \r -&gt; \\r&gt;
 *
 * When PDFBox throws anywhere in load/strip, the sole line is:
 *
 *   PARSE_FAIL
 */
public final class ObjHeaderLenientProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pages = doc.getNumberOfPages();
            COSDocument cos = doc.getDocument();
            int objects = cos.getXrefTable().size();
            COSDictionary trailer = cos.getTrailer();
            boolean root = trailer != null && trailer.getDictionaryObject(
                    COSName.ROOT) != null;
            boolean info = trailer != null && trailer.getDictionaryObject(
                    COSName.getPDFName("Info")) != null;
            String text = new PDFTextStripper().getText(doc);
            sb.append("pages=").append(pages).append('\n');
            sb.append("objects=").append(objects).append('\n');
            sb.append("root=").append(root ? "present" : "absent").append('\n');
            sb.append("info=").append(info ? "present" : "absent").append('\n');
            sb.append("text=").append(escape(text)).append('\n');
        } catch (Throwable t) {
            out.print("PARSE_FAIL\n");
            return;
        }
        out.print(sb);
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\n') {
                b.append("\\n");
            } else if (c == '\r') {
                b.append("\\r");
            } else if (c == '\\') {
                b.append("\\\\");
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }
}
