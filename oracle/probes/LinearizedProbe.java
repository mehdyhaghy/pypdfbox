import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for linearized-PDF (PDF 32000-1 Annex F) parsing +
 * save-round-trip behaviour.
 *
 * Apache PDFBox 3.0.x READS linearized PDFs (the trailing xref still wins —
 * the linearization parameter dictionary is the first indirect object and is
 * advisory) but does NOT WRITE them: {@code doc.save()} emits an ordinary,
 * non-linearized file. This probe captures both facts so pypdfbox can be held
 * to the same outcome.
 *
 * Usage:
 *   java -cp <cp> LinearizedProbe read  in.pdf
 *   java -cp <cp> LinearizedProbe save  in.pdf out.pdf
 *
 * "read" output (UTF-8, LF-terminated):
 *   pages=<n>
 *   linearized=<true|false>      # a /Linearized dict present in the raw COS
 *   linversion=<float|absent>    # value of /Linearized on that dict
 *   N=<int|absent>               # /N from the linearization dict
 *   O=<int|absent>               # /O from the linearization dict
 *   text=<escaped PDFTextStripper text, \n -> \\n, \r -> \\r>
 *
 * "save" output:
 *   out_linearized=<true|false>  # does the re-saved file still carry /Linearized?
 *   out_pages=<n>                # page count of the reloaded re-saved file
 *
 * On any throw the sole line is PARSE_FAIL.
 */
public final class LinearizedProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("read".equals(mode)) {
            read(out, args[1]);
        } else if ("save".equals(mode)) {
            save(out, args[1], args[2]);
        } else {
            out.print("PARSE_FAIL\n");
        }
    }

    private static void read(PrintStream out, String path) {
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(new File(path))) {
            int pages = doc.getNumberOfPages();
            COSDictionary lin = findLinearizedDict(doc.getDocument());
            sb.append("pages=").append(pages).append('\n');
            sb.append("linearized=").append(lin != null).append('\n');
            if (lin != null) {
                COSBase v = lin.getDictionaryObject(
                        COSName.getPDFName("Linearized"));
                sb.append("linversion=")
                  .append(v == null ? "absent"
                          : Float.toString(lin.getFloat("Linearized")))
                  .append('\n');
                sb.append("N=").append(intOrAbsent(lin, "N")).append('\n');
                sb.append("O=").append(intOrAbsent(lin, "O")).append('\n');
            } else {
                sb.append("linversion=absent\n");
                sb.append("N=absent\n");
                sb.append("O=absent\n");
            }
            String text = new PDFTextStripper().getText(doc);
            sb.append("text=").append(escape(text)).append('\n');
        } catch (Throwable t) {
            out.print("PARSE_FAIL\n");
            return;
        }
        out.print(sb);
    }

    private static void save(PrintStream out, String inPath, String outPath) {
        try {
            try (PDDocument doc = Loader.loadPDF(new File(inPath))) {
                doc.save(new File(outPath));
            }
            boolean stillLin;
            int outPages;
            try (PDDocument re = Loader.loadPDF(new File(outPath))) {
                stillLin = findLinearizedDict(re.getDocument()) != null;
                outPages = re.getNumberOfPages();
            }
            StringBuilder sb = new StringBuilder();
            sb.append("out_linearized=").append(stillLin).append('\n');
            sb.append("out_pages=").append(outPages).append('\n');
            out.print(sb);
        } catch (Throwable t) {
            out.print("PARSE_FAIL\n");
        }
    }

    /**
     * Resolve the linearization parameter dictionary the same way pypdfbox's
     * COSDocument.get_linearized_dictionary does. Upstream
     * COSDocument.getLinearizedDictionary returns the first xref-ordered dict
     * carrying a /Linearized key (bare-presence check); pypdfbox tightens that
     * to require a truthy numeric value (documented divergence). We mirror the
     * truthy-value filter here so the oracle and pypdfbox agree on the marker
     * semantics rather than the byte-for-byte upstream rule.
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
