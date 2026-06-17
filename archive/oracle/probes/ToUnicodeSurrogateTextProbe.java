import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the END-TO-END text-extraction path over a Type0 font
 * whose {@code /ToUnicode} CMap maps codes to MULTI-CHARACTER and
 * SURROGATE-PAIR (astral, &gt; U+FFFF) destinations.
 *
 * The companion {@code ToUnicodeSurrogateTextProbe} sibling probe
 * ({@link ToUnicodeSurrogateProbe}) drives {@code CMap.toUnicode(byte[])} in
 * isolation; this one drives the full {@code PDFTextStripper} so the
 * {@code PDType0Font.toUnicode} -&gt; stripper-assembly chain is exercised on a
 * genuine multi-byte content stream. PDFBox assembles the UTF-16BE bfchar
 * destinations (including surrogate pairs spanning two 16-bit units, and
 * multi-char strings) into the extracted text.
 *
 * Usage: java -cp ... ToUnicodeSurrogateTextProbe &lt;pdf&gt;
 *
 * Output (UTF-8):
 *   CODEPOINTS:&lt;space-separated U+XXXX tokens, one per Unicode code point&gt;
 *   TEXT:&lt;extracted text, backslash/newline escaped&gt;
 *
 * Code points are taken via {@code String.codePointAt} so an astral
 * destination collapses to a single {@code U+1XXXX} token — matching how
 * Python iterates its decoded {@code str}.
 */
public final class ToUnicodeSurrogateTextProbe {
    private static String esc(String s) {
        return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            String text = stripper.getText(doc);

            StringBuilder cps = new StringBuilder();
            int i = 0;
            while (i < text.length()) {
                int cp = text.codePointAt(i);
                if (cps.length() > 0) {
                    cps.append(' ');
                }
                cps.append(String.format("U+%04X", cp));
                i += Character.charCount(cp);
            }
            out.print("CODEPOINTS:" + cps + "\n");
            out.print("TEXT:" + esc(text) + "\n");
        }
    }
}
