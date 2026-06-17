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
 * Live oracle probe for the linearization PARAMETER DICTIONARY values
 * (PDF 32000-1 Annex F, Table F.1). Complements {@code LinearizedProbe}
 * (which covers /N, /O, version, page count + save round-trip) by emitting the
 * remaining file-geometry parameters pypdfbox exposes:
 *
 *   /L  total file length in bytes
 *   /T  byte offset of the first (trailing) xref entry
 *   /E  byte offset of the end of the first page
 *   /H  primary hint stream offset + length (and optional overflow pair)
 *
 * These are the linearization params a viewer uses to stream the first page;
 * they exercise the full integer/array decode path of the parameter dict, not
 * just the /Linearized marker. pypdfbox must read the SAME values PDFBox does.
 *
 * Usage:
 *   java -cp <cp> LinearizationParamsProbe in.pdf
 *
 * Output (UTF-8, LF-terminated):
 *   linearized=<true|false>
 *   L=<int|absent>
 *   T=<int|absent>
 *   E=<int|absent>
 *   H=<int,int[,int,int]|absent>     # /H array entries, comma-joined
 *   pages=<n>                        # PDDocument page count (cross-check vs /N)
 *
 * On any throw the sole line is PARSE_FAIL.
 */
public final class LinearizationParamsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            COSDocument cos = doc.getDocument();
            COSDictionary lin = findLinearizedDict(cos);
            sb.append("linearized=").append(lin != null).append('\n');
            if (lin != null) {
                sb.append("L=").append(intOrAbsent(lin, "L")).append('\n');
                sb.append("T=").append(intOrAbsent(lin, "T")).append('\n');
                sb.append("E=").append(intOrAbsent(lin, "E")).append('\n');
                sb.append("H=").append(hintOrAbsent(lin)).append('\n');
            } else {
                sb.append("L=absent\n");
                sb.append("T=absent\n");
                sb.append("E=absent\n");
                sb.append("H=absent\n");
            }
            sb.append("pages=").append(doc.getNumberOfPages()).append('\n');
        } catch (Throwable t) {
            out.print("PARSE_FAIL\n");
            return;
        }
        out.print(sb);
    }

    /**
     * Resolve the linearization parameter dictionary the same way pypdfbox's
     * COSDocument.get_linearized_dictionary does: upstream
     * getLinearizedDictionary uses a bare-presence /Linearized check; pypdfbox
     * tightens that to a truthy numeric value (documented divergence). Mirror
     * the truthy filter so oracle and pypdfbox agree on marker semantics.
     */
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

    private static String hintOrAbsent(COSDictionary d) {
        COSBase v = d.getDictionaryObject(COSName.getPDFName("H"));
        if (!(v instanceof COSArray)) {
            return "absent";
        }
        COSArray arr = (COSArray) v;
        int n = arr.size();
        if (n != 2 && n != 4) {
            return "absent";
        }
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < n; i++) {
            COSBase e = arr.getObject(i);
            if (!(e instanceof COSNumber)) {
                return "absent";
            }
            if (i > 0) {
                b.append(',');
            }
            b.append(((COSNumber) e).intValue());
        }
        return b.toString();
    }
}
