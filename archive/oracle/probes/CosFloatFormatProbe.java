import java.io.ByteArrayOutputStream;
import java.io.PrintStream;

import org.apache.pdfbox.cos.COSFloat;

/**
 * Live oracle probe: drives Apache PDFBox 3.0.7
 * {@code org.apache.pdfbox.cos.COSFloat#writePDF(OutputStream)} for both the
 * direct-{@code float} constructor and the {@code COSFloat(String)} lexeme
 * constructor, so pypdfbox's {@code COSFloat.format_string} / {@code write_pdf}
 * can be diffed byte-for-byte against the real
 * {@code Float.toString} / {@code BigDecimal.stripTrailingZeros().toPlainString()}
 * pipeline (PDFBox 3.0.7).
 *
 * Usage:
 *   java -cp &lt;...&gt; CosFloatFormatProbe &lt;arg&gt; [&lt;arg&gt; ...]
 *
 * Each argument selects a construction path:
 *   - {@code s:&lt;lexeme&gt;}  -&gt; new COSFloat(&lt;lexeme&gt;)        (String ctor)
 *   - {@code &lt;double&gt;}     -&gt; new COSFloat((float) &lt;double&gt;) (float ctor)
 *
 * One line is emitted per argument, the writePDF bytes decoded as ISO-8859-1:
 *
 *   &lt;arg&gt;\t&lt;writePDF-output&gt;
 *
 * The leading argument echo keeps the diff self-describing; the Python side
 * splits on the first tab.
 */
public final class CosFloatFormatProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (String arg : args) {
            COSFloat f;
            if (arg.startsWith("s:")) {
                f = new COSFloat(arg.substring(2));
            } else {
                f = new COSFloat((float) Double.parseDouble(arg));
            }
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            f.writePDF(baos);
            out.println(arg + "\t" + baos.toString("ISO-8859-1"));
        }
    }

    private CosFloatFormatProbe() {}
}
