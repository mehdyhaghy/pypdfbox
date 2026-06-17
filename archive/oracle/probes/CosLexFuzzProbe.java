import java.io.PrintStream;
import java.util.Calendar;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;

/**
 * COS lexical-layer differential parse-fuzz probe (pypdfbox parity wave 1510).
 *
 * Targets the date-parsing entry point of the COS dictionary layer:
 * {@code COSDictionary.getDate(COSName)}. In PDFBox 3.0.7 that method
 * delegates straight to
 * {@code org.apache.pdfbox.util.DateConverter.toCalendar(COSString)}
 * (confirmed by bytecode disassembly), so this probe pins the FULL leniency
 * of the production date parser as it is actually reached from the COS layer —
 * not the isolated DateConverter (already covered by {@code DateConvertProbe}).
 *
 * The pypdfbox sibling
 * ({@code tests/cos/oracle/test_cos_lex_fuzz_wave1510.py}) builds the
 * identical {@code COSDictionary} with a {@code COSString} value under
 * {@code /D} and calls {@code COSDictionary.get_date("D")}, comparing the same
 * projection. Before wave 1510 pypdfbox's {@code getDate} used a private regex
 * parser that diverged from {@code DateConverter} on GMT/UTC-prefixed, ISO
 * 8601, named-month, and "Z + explicit offset" shapes; this probe is the pin
 * that proves the delegation fix is byte-faithful.
 *
 * Usage:
 *   java CosLexFuzzProbe &lt;date-string-hex&gt;
 *
 * The date string is passed as hex of its raw (Latin-1 / byte) form so that
 * embedded NULs, control bytes, and quote characters survive the shell.
 *
 * Projection (single UTF-8 line):
 *   NULL                       getDate returned null (absent / not a COSString
 *                              / unparseable date)
 *   &lt;epochMillis&gt; &lt;offsetMillis&gt;  parsed instant + displayed zone offset
 */
public final class CosLexFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] raw = hexToBytes(args[0]);
        // COSString.<init>(byte[]) keeps the bytes verbatim; getString()
        // reverses them to the same String the parser saw — exactly the path
        // a date read from a parsed PDF takes.
        COSString value = new COSString(raw);
        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.getPDFName("D"), value);

        Calendar c = dict.getDate(COSName.getPDFName("D"));
        if (c == null) {
            out.print("NULL");
        } else {
            long epoch = c.getTimeInMillis();
            int off = c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET);
            out.print(epoch + " " + off);
        }
    }

    private static byte[] hexToBytes(String hex) {
        int n = hex.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++) {
            out[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return out;
    }
}
