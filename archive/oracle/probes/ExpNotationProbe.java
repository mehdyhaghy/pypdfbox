import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: exponential-notation real numbers in a content stream.
 *
 * PDF 32000-1 §7.3.3 defines real numbers as ``[+-]?(\d+|\d*\.\d+|\d+\.\d*)`` —
 * exponential notation (``1e3`` / ``1.5E-2``) is OUT OF SPEC, but real-world
 * PDF writers sometimes emit them. PDFBox's ``PDFStreamParser`` number branch
 * accepts only digits, ``.``, and ``-`` (double-negative + stray-dash quirks);
 * ``e``/``E`` is NOT consumed into the number token. The leftover ``e2``-style
 * suffix is read as an operator keyword. So a content stream with ``1.5e2 Tf``
 * tokenizes as ``[1.5(COSFloat), Tf(unknown-op), <next>]`` — PDFBox tolerates
 * it (no throw), but the operator chain becomes garbage downstream of the
 * exp-notation number.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ExpNotationProbe input.pdf
 *
 * Output (UTF-8, LF-terminated):
 *   pages=<n>
 *   text=<escaped-extracted-text>
 *   tokens.page<i>=<comma-joined-canonical-tokens>
 *
 * Emits ``PARSE_FAIL\n`` if Loader.loadPDF throws.
 *
 * Canonical token shapes:
 *   - COSInteger     -> i<n>
 *   - COSFloat       -> f<repr>   (Float.toString of the parsed value)
 *   - COSName        -> n<name>
 *   - COSString      -> s<text>
 *   - COSArray       -> a[<e0>,<e1>,...]   (each element canonicalised)
 *   - COSNull        -> null
 *   - Operator       -> op:<name>
 *   - <anything else> -> ?<class>
 */
public final class ExpNotationProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        PDDocument doc;
        try {
            doc = Loader.loadPDF(new File(args[0]));
        } catch (Throwable t) {
            out.print("PARSE_FAIL\n");
            return;
        }
        try {
            StringBuilder sb = new StringBuilder();
            int pageCount = doc.getNumberOfPages();
            sb.append("pages=").append(pageCount).append('\n');
            String text;
            try {
                text = new PDFTextStripper().getText(doc);
            } catch (Throwable t) {
                text = "<EXTRACT_FAIL>";
            }
            sb.append("text=").append(escape(text)).append('\n');
            int p = 0;
            for (PDPage page : doc.getPages()) {
                String toks;
                try {
                    PDFStreamParser parser = new PDFStreamParser(page);
                    List<Object> raw = parser.parse();
                    toks = canonTokens(raw);
                } catch (Throwable t) {
                    toks = "TOKEN_FAIL:" + t.getClass().getSimpleName();
                }
                sb.append("tokens.page").append(p).append('=').append(toks)
                  .append('\n');
                p++;
            }
            out.print(sb);
        } finally {
            doc.close();
        }
    }

    private static String canonTokens(List<Object> raw) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < raw.size(); i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(canon(raw.get(i)));
        }
        return sb.toString();
    }

    private static String canon(Object o) {
        if (o == null) {
            return "null";
        }
        if (o instanceof COSNull) {
            return "null";
        }
        if (o instanceof COSInteger) {
            return "i" + ((COSInteger) o).longValue();
        }
        if (o instanceof COSFloat) {
            return "f" + Float.toString(((COSFloat) o).floatValue());
        }
        if (o instanceof COSNumber) {
            return "f" + Float.toString(((COSNumber) o).floatValue());
        }
        if (o instanceof COSName) {
            return "n" + ((COSName) o).getName();
        }
        if (o instanceof COSString) {
            return "s" + ((COSString) o).getString();
        }
        if (o instanceof COSArray) {
            COSArray arr = (COSArray) o;
            StringBuilder a = new StringBuilder("a[");
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    a.append(',');
                }
                a.append(canon(arr.getObject(i)));
            }
            a.append(']');
            return a.toString();
        }
        if (o instanceof Operator) {
            return "op:" + ((Operator) o).getName();
        }
        if (o instanceof COSBase) {
            return "?" + o.getClass().getSimpleName();
        }
        return "?" + o.getClass().getSimpleName();
    }

    private static String escape(String s) {
        if (s == null) {
            return "null";
        }
        return s.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
