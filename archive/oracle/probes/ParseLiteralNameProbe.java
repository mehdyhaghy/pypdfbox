import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/**
 * Live oracle probe for the PDF token PARSE/DECODE direction of
 * {@code BaseParser} — distinct from the COSWriter ESCAPE direction covered by
 * CosEscapeProbe and from the {@code getString()} text-decode covered by
 * CosStrTextDateProbe. Here we feed raw PDF syntax bytes through Apache
 * PDFBox's {@code PDFStreamParser.parseNextToken()} (which dispatches to
 * {@code BaseParser.parseCOSString()} / {@code parseCOSName()}) and emit the
 * DECODED raw bytes the parser produced.
 *
 * This is the surface that decides:
 *   - literal string {@code (...)}: octal escapes ({@code \0 \12 \123 \053}),
 *     octal overflow wrap ({@code \400}), the named escapes
 *     ({@code \n \r \t \b \f \( \) \\}), unknown-escape drop-the-backslash,
 *     line continuation ({@code \<LF>}, {@code \<CR>}, {@code \<CRLF>}),
 *     bare EOL normalization (CR / CRLF / LF -> LF), and balanced nested
 *     parens kept as data.
 *   - name {@code /Foo}: {@code #XX} hex-escape decoding, a {@code #}
 *     followed by < 2 hex digits kept literally, and high bytes via #XX.
 *
 * Usage:
 *   java -cp ... ParseLiteralNameProbe &lt;syntaxHexBytes&gt;
 *
 * The single argument is the lower/upper-hex of the raw PDF syntax bytes for
 * ONE object (e.g. the bytes {@code (a\053b)} or {@code /A#42}). Output (UTF-8,
 * no trailing newline beyond the single line):
 *
 *   STR:&lt;decodedHex&gt;     parser returned a COSString; decodedHex is the
 *                             lower-hex of getBytes() (the decoded payload)
 *   NAME:&lt;decodedHex&gt;    parser returned a COSName; decodedHex is the
 *                             lower-hex of the raw decoded name bytes
 *                             (getName() re-encoded UTF-8 round-trips the
 *                             byte sequence the parser stored)
 *   OTHER:&lt;simpleName&gt;   any other COS type (defensive)
 *   NULL                      parseNextToken returned null
 */
public final class ParseLiteralNameProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] syntax = hex(args[0]);
        PDFStreamParser parser = new PDFStreamParser(syntax);
        Object tok = parser.parseNextToken();
        parser.close();
        out.print(render(tok));
    }

    private static String render(Object tok) {
        if (tok == null) {
            return "NULL";
        }
        if (tok instanceof COSString) {
            return "STR:" + toHex(((COSString) tok).getBytes());
        }
        if (tok instanceof COSName) {
            // getName() decodes the stored bytes (UTF-8, latin-1 fallback);
            // re-encoding as UTF-8 round-trips back to the raw byte sequence
            // the parser stored, which is what we want to compare.
            String name = ((COSName) tok).getName();
            return "NAME:" + toHex(name.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        if (tok instanceof COSBase) {
            return "OTHER:" + ((COSBase) tok).getClass().getSimpleName();
        }
        return "OTHER:" + tok.getClass().getSimpleName();
    }

    private static byte[] hex(String h) {
        int n = h.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(h.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }

    private static String toHex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
