import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfwriter.COSWriter;

/**
 * Live oracle probe: the EXACT bytes Apache PDFBox's {@code COSWriter.writeString}
 * emits for a {@code COSString}, focused on the *string write* surface alone
 * (literal {@code (...)} vs hex {@code <...>} selection and literal-form
 * escaping). This complements {@code CosEscapeProbe} (which spot-checks a fixed
 * battery shared with COSName escaping) by sweeping EVERY single byte
 * 0x00..0xFF as a one-byte string, so the per-byte literal/hex boundary (hex iff
 * byte >= 0x80 or byte is CR 0x0D / LF 0x0A; everything else literal, with
 * {@code ( ) \} backslash-escaped and all other control bytes emitted raw) is
 * pinned at the granularity a fixed battery skips (0x05, 0x10, 0x1F, 0x7F, 0x80,
 * 0x9F, ...).
 *
 * It also exercises:
 *   - multi-byte paren balance permutations (PDFBox escapes EVERY paren);
 *   - mixed literal payloads with embedded high/EOL bytes (forces hex);
 *   - the forced-hex override on otherwise-literal payloads;
 *   - the empty string.
 *
 * Output: one {@code <tag> <inputHex>: <outputHex>} line per case.
 * {@code single} = one-byte sweep, {@code multi} = multi-byte literal cases,
 * {@code forcehex} = forced-hex form. Source is ASCII-only.
 *
 * Usage: java -cp <jar>:<build> CosStringWriteProbe
 */
public final class CosStringWriteProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // Exhaustive single-byte sweep: pins the literal/hex boundary per byte.
        for (int b = 0; b <= 0xFF; b++) {
            emit(out, "single", new byte[] {(byte) b}, false);
        }

        // Multi-byte literal cases: paren balance + backslash permutations.
        emit(out, "multi", hex(""), false);                 // empty -> ()
        emit(out, "multi", hex("28"), false);               // "(" lone open
        emit(out, "multi", hex("29"), false);               // ")" lone close
        emit(out, "multi", hex("2829"), false);             // "()" balanced
        emit(out, "multi", hex("2928"), false);             // ")(" reversed
        emit(out, "multi", hex("282829"), false);            // "(()" nested-ish
        emit(out, "multi", hex("28282929"), false);          // "(())" balanced nested
        emit(out, "multi", hex("5c28"), false);              // "\(" backslash+open
        emit(out, "multi", hex("5c5c"), false);              // "\\" double backslash
        emit(out, "multi", hex("612862295c63"), false);       // "a(b)\c" mixed
        emit(out, "multi", hex("48656c6c6f20576f726c64"), false); // "Hello World"
        emit(out, "multi", hex("4142430d44"), false);         // "ABC\rD" -> hex (CR)
        emit(out, "multi", hex("4142430a44"), false);         // "ABC\nD" -> hex (LF)
        emit(out, "multi", hex("414243ff44"), false);         // "ABC\xffD" -> hex (high)
        emit(out, "multi", hex("00280a29ff"), false);         // NUL ( LF ) high -> hex
        emit(out, "multi", hex("090808"), false);             // tabs/backspace raw literal

        // Forced-hex override on payloads that would otherwise go literal.
        emit(out, "forcehex", hex(""), true);                // empty forced hex
        emit(out, "forcehex", hex("48656c6c6f"), true);      // "Hello" forced hex
        emit(out, "forcehex", hex("2829"), true);            // "()" forced hex
        emit(out, "forcehex", hex("0928"), true);            // tab+paren forced hex
    }

    private static void emit(PrintStream out, String tag, byte[] raw, boolean forceHex)
            throws Exception {
        COSString s = new COSString(raw);
        if (forceHex) {
            s.setForceHexForm(true);
        }
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        COSWriter.writeString(s, baos);
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
