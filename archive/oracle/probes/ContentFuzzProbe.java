import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for differential CONTENT-STREAM operator fuzz (wave 1504).
 *
 * The companion test (tests/contentstream/oracle/test_content_fuzz_oracle.py)
 * builds a single-page template PDF whose /Contents stream is a *malformed*
 * content stream (missing/extra/wrong-typed operands, unbalanced q/Q and
 * BT/ET, unknown operators, corrupt inline images, Do/gs of missing
 * resources, division-shaped edge values, mid-operator truncation). The PDF
 * file bytes are built identically on both sides and written to one temp file
 * that is handed to BOTH this probe and pypdfbox, so the input is guaranteed
 * byte-identical.
 *
 * Projection (compared, NOT byte offsets):
 *
 *   ok=true
 *   text=<repr of PDFTextStripper.getText, control chars escaped>
 *
 * or, on any throw out of load + getText (the exception *class* names differ
 * between Java and Python, so only the ok=false fact is compared, not the
 * class — a crash-vs-skip divergence still surfaces as ok=false vs ok=true):
 *
 *   ok=false
 *
 * A content-stream interpreter that is correctly lenient swallows the
 * malformed operator (MissingOperandException / unsupportedOperator) and
 * still extracts the surrounding valid text; a buggy one either crashes
 * (ok=false where Java is ok=true) or drops valid text.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ContentFuzzProbe input.pdf
 */
public final class ContentFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String text;
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            text = new PDFTextStripper().getText(doc);
        } catch (Throwable t) {
            out.print("ok=false\n");
            return;
        }
        out.print("ok=true\ntext=" + escape(text) + "\n");
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '\\') {
                b.append("\\\\");
            } else if (c == '\n') {
                b.append("\\n");
            } else if (c == '\r') {
                b.append("\\r");
            } else if (c == '\t') {
                b.append("\\t");
            } else if (c < 0x20 || c == 0x7f) {
                b.append(String.format("\\x%02x", (int) c));
            } else {
                b.append(c);
            }
        }
        return b.toString();
    }
}
