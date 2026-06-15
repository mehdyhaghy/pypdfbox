import java.io.PrintStream;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/**
 * Live oracle probe for the COSName byte->String round-trip via the parser's
 * name-decode path. Feeds raw PDF name-token syntax bytes (e.g. {@code /A#C3#A9}
 * or {@code /AB} with raw high bytes) through {@code PDFStreamParser}, which
 * dispatches to {@code BaseParser.parseCOSName()} (the {@code #XX} hex decode +
 * the UTF-8 / Windows-1252 alternative-charset fallback for the decoded byte
 * buffer), then projects the resulting {@code COSName.getName()}.
 *
 * Output (UTF-8, one line, no trailing newline):
 *   NAME:<utf8HexOfGetName>   token decoded to a COSName; hex of getName()
 *                             re-encoded as UTF-8
 *   OTHER:<simpleName>        any other COS type
 *   NULL                      parseNextToken returned null
 */
public final class CosNameHexEscapeFuzzProbe {

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
        if (tok instanceof COSName) {
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
