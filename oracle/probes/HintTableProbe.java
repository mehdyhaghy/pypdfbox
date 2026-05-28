import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe for the linearization HINT TABLE surface.
 *
 * Apache PDFBox 3.0.7 does not ship a hint-stream decoder — it parses the
 * trailing xref, surfaces the linearization parameter dictionary via
 * {@link COSDocument#getLinearizedDictionary()}, and stops there. The hint
 * stream body is never interpreted (no public accessor for the page-offset /
 * shared-object / thumbnail tables). The PDFBox jar bundled with this repo
 * confirms this by absence: ``jar tf pdfbox-app-3.0.7.jar | grep -i hint``
 * matches only ``ContentHints.class`` from the bouncycastle dependency.
 *
 * So this probe captures the subset PDFBox **does** expose — the
 * linearization parameter dictionary's keys ``/L``, ``/H``, ``/O``, ``/E``,
 * ``/N``, ``/T``, and the ``/Linearized`` version. pypdfbox decodes the hint
 * table internals via its own decoder and we verify byte-range / page-count
 * consistency against these values, plus cross-check against qpdf's
 * ``--show-linearization`` output on the Python side.
 *
 * Usage:
 *   java -cp <cp> HintTableProbe linearized.pdf
 *
 * Output (UTF-8, LF-terminated, sorted-key dict-emit pattern):
 *   linearized=<true|false>
 *   pages=<n>                     # PDDocument.getNumberOfPages()
 *   linversion=<float|absent>
 *   L=<int|absent>                # /L (total file length)
 *   H_count=<int|absent>          # number of entries in /H (2 or 4)
 *   H_0=<int|absent>              # /H[0] primary hint offset
 *   H_1=<int|absent>              # /H[1] primary hint length
 *   H_2=<int|absent>              # /H[2] overflow / shared sub-table off
 *   H_3=<int|absent>              # /H[3] overflow length
 *   O=<int|absent>                # /O first page object number
 *   E=<int|absent>                # /E byte offset of first page end
 *   N=<int|absent>                # /N total page count
 *   T=<int|absent>                # /T offset of first xref
 *
 * On any throw the sole line is PARSE_FAIL.
 */
public final class HintTableProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.print("PARSE_FAIL\n");
            return;
        }
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            COSDocument cos = doc.getDocument();
            COSDictionary lin = findLinearizedDict(cos);
            sb.append("linearized=").append(lin != null).append('\n');
            sb.append("pages=").append(doc.getNumberOfPages()).append('\n');
            if (lin != null) {
                sb.append("linversion=")
                  .append(Float.toString(lin.getFloat("Linearized")))
                  .append('\n');
                sb.append("L=").append(intOrAbsent(lin, "L")).append('\n');
                COSBase hBase = lin.getDictionaryObject(COSName.getPDFName("H"));
                if (hBase instanceof COSArray) {
                    COSArray h = (COSArray) hBase;
                    int n = h.size();
                    sb.append("H_count=").append(n).append('\n');
                    for (int i = 0; i < 4; i++) {
                        if (i < n) {
                            COSBase v = h.getObject(i);
                            if (v instanceof COSNumber) {
                                sb.append("H_").append(i).append('=')
                                  .append(((COSNumber) v).intValue()).append('\n');
                            } else {
                                sb.append("H_").append(i).append("=absent\n");
                            }
                        } else {
                            sb.append("H_").append(i).append("=absent\n");
                        }
                    }
                } else {
                    sb.append("H_count=absent\n");
                    sb.append("H_0=absent\n");
                    sb.append("H_1=absent\n");
                    sb.append("H_2=absent\n");
                    sb.append("H_3=absent\n");
                }
                sb.append("O=").append(intOrAbsent(lin, "O")).append('\n');
                sb.append("E=").append(intOrAbsent(lin, "E")).append('\n');
                sb.append("N=").append(intOrAbsent(lin, "N")).append('\n');
                sb.append("T=").append(intOrAbsent(lin, "T")).append('\n');
            } else {
                sb.append("linversion=absent\n");
                sb.append("L=absent\n");
                sb.append("H_count=absent\n");
                sb.append("H_0=absent\n");
                sb.append("H_1=absent\n");
                sb.append("H_2=absent\n");
                sb.append("H_3=absent\n");
                sb.append("O=absent\n");
                sb.append("E=absent\n");
                sb.append("N=absent\n");
                sb.append("T=absent\n");
            }
        } catch (Throwable t) {
            out.print("PARSE_FAIL\n");
            return;
        }
        out.print(sb);
    }

    private static COSDictionary findLinearizedDict(COSDocument cos) {
        COSDictionary d = cos.getLinearizedDictionary();
        if (d == null) {
            return null;
        }
        COSBase v = d.getDictionaryObject(COSName.getPDFName("Linearized"));
        if (v != null && d.getFloat("Linearized") != 0f) {
            return d;
        }
        return null;
    }

    private static String intOrAbsent(COSDictionary d, String key) {
        COSBase v = d.getDictionaryObject(COSName.getPDFName(key));
        if (v == null) {
            return "absent";
        }
        return Integer.toString(d.getInt(key));
    }
}
