import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/** Differential malformed literal-string escape probe (wave 1518). */
public final class CosStringLiteralEscapeFuzzProbe {
    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xf, 16));
            sb.append(Character.forDigit(b & 0xf, 16));
        }
        return sb.toString();
    }

    private static void run(String name, byte[] syntax) {
        PDFStreamParser parser = new PDFStreamParser(syntax);
        try {
            Object token = parser.parseNextToken();
            if (token instanceof COSString) {
                System.out.println("CASE " + name + " bytes="
                        + hex(((COSString) token).getBytes()));
            } else {
                System.out.println("CASE " + name + " type="
                        + (token == null ? "null" : token.getClass().getSimpleName()));
            }
        } catch (Exception e) {
            System.out.println("CASE " + name + " ERR:" + e.getClass().getSimpleName());
        } finally {
            try {
                parser.close();
            } catch (Exception ignored) {
                // best-effort close
            }
        }
    }

    public static void main(String[] args) throws Exception {
        run("empty", "()".getBytes("ISO-8859-1"));
        run("named", "(a\\nb\\rc\\td\\be\\ff\\(g\\)h\\\\i)".getBytes("ISO-8859-1"));
        run("unknown", "(a\\zb)".getBytes("ISO-8859-1"));
        run("octal_one", "(\\7)".getBytes("ISO-8859-1"));
        run("octal_two", "(\\77)".getBytes("ISO-8859-1"));
        run("octal_three", "(\\377)".getBytes("ISO-8859-1"));
        run("octal_overflow", "(\\777)".getBytes("ISO-8859-1"));
        run("octal_stops_at_8", "(\\128)".getBytes("ISO-8859-1"));
        run("nested", "(a(b(c)d)e)".getBytes("ISO-8859-1"));
        run("escaped_close", "(a\\)b)".getBytes("ISO-8859-1"));
        run("line_lf", "(a\\\nb)".getBytes("ISO-8859-1"));
        run("line_cr", "(a\\\rb)".getBytes("ISO-8859-1"));
        run("line_crlf", "(a\\\r\nb)".getBytes("ISO-8859-1"));
        run("bare_eols", "(a\rb\r\nc\nd)".getBytes("ISO-8859-1"));
        run("backslash_eof", "(abc\\".getBytes("ISO-8859-1"));
        run("unterminated", "(abc".getBytes("ISO-8859-1"));
        run("nul_byte", new byte[] {'(', 'a', 0, 'b', ')'});
    }
}
