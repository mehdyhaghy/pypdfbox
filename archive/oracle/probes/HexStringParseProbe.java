import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/**
 * Live oracle probe for hex-string {@code < ... >} parsing leniency in Apache
 * PDFBox's {@code BaseParser.parseCOSHexString()} + {@code COSString.parseHex()}.
 *
 * Reads a raw operand byte snippet (NOT a full PDF), tokenizes it through the
 * shared {@link PDFStreamParser}, and emits the decoded byte payload of the
 * FIRST {@link COSString} token as hex (LF-terminated). This isolates the hex
 * branch across the edge cases that real-world malformed PDFs lean on:
 *
 *   - odd-length hex runs (implicit trailing {@code 0} pad per ISO 32000-1
 *     §7.3.4.3),
 *   - embedded whitespace / newlines / tabs between hex digits (skipped),
 *   - a stray non-hex character mid-string (PDFBox drops a dangling half-pair,
 *     then skips to the closing {@code >}).
 *
 * Output per run:
 *   {@code str(<hex-of-decoded-bytes>)}   on success, or
 *   {@code error}                          if no COSString / parse failure.
 *
 * argv[0] = path to the raw snippet file.
 */
public final class HexStringParseProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] data = Files.readAllBytes(Paths.get(args[0]));
        try {
            PDFStreamParser parser = new PDFStreamParser(data);
            Object token;
            while ((token = parser.parseNextToken()) != null) {
                if (token instanceof COSString) {
                    out.print("str(" + hex(((COSString) token).getBytes()) + ")\n");
                    return;
                }
                if (!(token instanceof COSBase)) {
                    // operator etc. — keep scanning for the string token
                    continue;
                }
            }
            out.print("error\n");
        } catch (Exception e) {
            out.print("error\n");
        }
    }

    private static String hex(byte[] data) {
        StringBuilder sb = new StringBuilder();
        for (byte b : data) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16));
            sb.append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
