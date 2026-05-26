import java.io.PrintStream;
import java.util.Calendar;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.util.DateConverter;

/**
 * Live oracle probe for COSString text-string decoding + PDF date parsing.
 *
 * Usage:
 *   java ... CosStrTextDateProbe str  <hexbytes>   # COSString.parseHex(hex).getString()
 *   java ... CosStrTextDateProbe date <datestring> # DateConverter.toCalendar(str)
 *
 * Output (UTF-8, single line, no trailing newline framing beyond println):
 *
 *   str  mode: space-separated lowercase hex of each Unicode *code point* of
 *        getString() (NOT UTF-16 chars — surrogate pairs are folded into the
 *        single supplementary code point so the Python side, whose str holds
 *        code points natively, compares equal). Empty string emits "".
 *
 *   date mode: normalised ISO-8601 "yyyy-MM-ddTHH:mm:ss(+|-)HH:mm", or the
 *        literal "NULL" when toCalendar returns null (unparseable). The TZ
 *        suffix is the calendar's total (zone+dst) offset reduced exactly as
 *        Java's Calendar.ZONE_OFFSET reports it.
 */
public final class CosStrTextDateProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("str".equals(mode)) {
            COSString cs = COSString.parseHex(args[1]);
            out.print(codePointHex(cs.getString()));
        } else if ("date".equals(mode)) {
            Calendar c = DateConverter.toCalendar(args[1]);
            out.print(iso(c));
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    /** Space-separated lowercase hex of each Unicode code point. */
    private static String codePointHex(String s) {
        StringBuilder sb = new StringBuilder();
        int i = 0;
        boolean first = true;
        while (i < s.length()) {
            int cp = s.codePointAt(i);
            if (!first) {
                sb.append(' ');
            }
            first = false;
            sb.append(Integer.toHexString(cp));
            i += Character.charCount(cp);
        }
        return sb.toString();
    }

    private static String iso(Calendar c) {
        if (c == null) {
            return "NULL";
        }
        int off = c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET);
        int totalMin = off / 60000;
        String sign = totalMin < 0 ? "-" : "+";
        int absMin = Math.abs(totalMin);
        return String.format(
                "%04d-%02d-%02dT%02d:%02d:%02d%s%02d:%02d",
                c.get(Calendar.YEAR),
                c.get(Calendar.MONTH) + 1,
                c.get(Calendar.DAY_OF_MONTH),
                c.get(Calendar.HOUR_OF_DAY),
                c.get(Calendar.MINUTE),
                c.get(Calendar.SECOND),
                sign,
                absMin / 60,
                absMin % 60);
    }
}
