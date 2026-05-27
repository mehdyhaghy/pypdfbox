import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfwriter.COSWriter;

/**
 * Live oracle probe: emit the EXACT serialized bytes Apache PDFBox's
 * {@code COSWriter} produces when escaping {@code COSName} and {@code COSString}
 * values. This is the string/name ESCAPING facet, distinct from the per-type
 * {@code writePDF} self-write surface (CosWriteSelfProbe) and the one-spec
 * scalar probe (WriteScalarProbe): it runs a fixed internal battery so the
 * whole escape table round-trips in a single JVM start, and it focuses on the
 * high-value escaping decisions:
 *
 *   - COSName  : the {@code #XX} escape table -- which bytes pass through the
 *                printable allowlist (A-Z a-z 0-9 $ * + - . ; @ _) and which
 *                become {@code #XX} (whitespace, the delimiters ()<>[]{}/%,
 *                {@code #} itself, control bytes, and every byte >= 0x7F).
 *   - COSString: literal {@code (...)} vs hex {@code <...>} selection (hex when
 *                any byte >= 0x80 or a CR/LF EOL byte is present), balanced and
 *                unbalanced paren handling (PDFBox escapes EVERY paren with a
 *                backslash regardless of balance), backslash escaping, the raw
 *                emission of other control bytes (tab/backspace/formfeed) inside
 *                literal form, a UTF-16BE BOM string, the empty string, and the
 *                forced-hex form.
 *
 * Names are constructed from raw bytes via {@code new String(bytes, ISO_8859_1)}
 * so a single byte maps to a single code point; {@code COSName.getName()} then
 * UTF-8 re-encodes, which is exactly what {@code writePDF} escapes. The Python
 * side mirrors this by decoding the same hex with latin-1 before
 * {@code COSName.get_pdf_name}.
 *
 * Output: one {@code <label> <inputHex>: <outputHex>} line per case. Source is
 * ASCII-only so the platform-default encoding javac assumes cannot mangle a
 * literal.
 *
 * Usage: java -cp <jar>:<build> CosEscapeProbe
 */
public final class CosEscapeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // ---- COSName escape table: every byte 0x00..0xFF as a single-byte name.
        // Drives the full printable-allowlist vs #XX decision in one pass.
        for (int b = 0; b <= 0xFF; b++) {
            byte[] raw = new byte[] {(byte) b};
            String nm = new String(raw, StandardCharsets.ISO_8859_1);
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            COSName.getPDFName(nm).writePDF(baos);
            out.print("name " + toHex(raw) + ": " + toHex(baos.toByteArray()) + "\n");
        }

        // ---- COSName multi-byte / structural cases (the marquee escapes).
        emitName(out, "");                         // empty name -> just '/'
        emitName(out, "Type");                     // all pass-through
        emitName(out, "A B");                      // space -> #20
        emitName(out, "A#B");                      // hash itself -> #23
        emitName(out, "Name(1)");                  // parens -> #28 #29
        emitName(out, "Slash/Sub");                // slash -> #2F
        emitName(out, "Pct%X");                    // percent -> #25
        emitName(out, "br[a]ce{s}");               // bracket/brace delimiters
        emitName(out, "lt<gt>");                    // angle delimiters
        emitName(out, "Plus+Minus-Under_At@Star*Dollar$Semi;Dot."); // pass-through set
        emitNameRaw(out, hex("c3a9"));              // e-acute UTF-8 -> #C3#A9
        emitNameRaw(out, hex("e28094"));            // em dash UTF-8 -> #E2#80#94
        emitNameRaw(out, hex("7a00656e64"));        // embedded NUL -> #00

        // ---- COSString escaping battery (literal vs hex, parens, controls).
        emitStr(out, hex(""), false);                  // empty -> ()
        emitStr(out, hex("48656c6c6f"), false);        // "Hello" plain literal
        emitStr(out, hex("2829"), false);              // "()" both escaped
        emitStr(out, hex("612862296329"), false);      // "a(b)c)" balanced+trailing
        emitStr(out, hex("28616263"), false);          // "(abc" unbalanced open
        emitStr(out, hex("61296229"), false);          // "a)b)" unbalanced close
        emitStr(out, hex("5c"), false);                // backslash -> \\
        emitStr(out, hex("612862295c63"), false);      // "a(b)\c" mixed escapes
        emitStr(out, hex("09"), false);                // tab -> raw 0x09 in literal
        emitStr(out, hex("08"), false);                // backspace -> raw 0x08
        emitStr(out, hex("0c"), false);                // formfeed -> raw 0x0c
        emitStr(out, hex("0d"), false);                // CR -> forces hex
        emitStr(out, hex("0a"), false);                // LF -> forces hex
        emitStr(out, hex("0d0a"), false);              // CRLF -> forces hex
        emitStr(out, hex("00010203"), false);          // low control bytes literal
        emitStr(out, hex("ff"), false);                // high byte -> forces hex
        emitStr(out, hex("414243e9"), false);          // ASCII then high -> hex
        emitStr(out, hex("7f"), false);                // DEL -> raw in literal (0x7f<0x80)
        // UTF-16BE BOM string: FEFF + UTF-16BE of "hello" with an e-acute.
        emitStr(out, hex("feff006800e9006c006c006f"), false);
        // Forced-hex form on otherwise-literal payloads.
        emitStr(out, hex("48656c6c6f"), true);         // "Hello" forced hex
        emitStr(out, hex("2829"), true);               // "()" forced hex
        emitStr(out, hex(""), true);                   // empty forced hex
    }

    private static void emitName(PrintStream out, String s) throws Exception {
        emitNameRaw(out, s.getBytes(StandardCharsets.UTF_8));
    }

    private static void emitNameRaw(PrintStream out, byte[] raw) throws Exception {
        String nm = new String(raw, StandardCharsets.ISO_8859_1);
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSName.getPDFName(nm).writePDF(baos);
        out.print("namem " + toHex(raw) + ": " + toHex(baos.toByteArray()) + "\n");
    }

    private static void emitStr(PrintStream out, byte[] raw, boolean forceHex)
            throws Exception {
        COSString s = new COSString(raw);
        if (forceHex) {
            s.setForceHexForm(true);
        }
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter.writeString(s, baos);
        String tag = forceHex ? "strhex" : "strlit";
        out.print(tag + " " + toHex(raw) + ": " + toHex(baos.toByteArray()) + "\n");
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
        StringBuilder sb = new StringBuilder();
        for (byte x : b) {
            sb.append(String.format("%02x", x & 0xff));
        }
        return sb.toString();
    }
}
