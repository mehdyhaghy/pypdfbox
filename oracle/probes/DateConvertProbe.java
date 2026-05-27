import java.io.PrintStream;
import java.util.Calendar;
import java.util.GregorianCalendar;
import java.util.SimpleTimeZone;
import java.util.TimeZone;
import org.apache.pdfbox.util.DateConverter;

/**
 * Live oracle probe for {@code org.apache.pdfbox.util.DateConverter}.
 *
 * Two modes:
 *
 *   java ... DateConvertProbe parse <datestring>
 *       Drives DateConverter.toCalendar(String). Emits either
 *       "PARSE_FAIL" (toCalendar threw an IOException — unparseable input)
 *       or "<epochMillis> <offsetMillis>" where offsetMillis is the
 *       calendar's total (ZONE_OFFSET + DST_OFFSET) at that instant. The
 *       epoch-millis pins the absolute instant; the offset pins how PDFBox
 *       chose to display the wall-clock + zone. A null return (whitespace /
 *       "D:" only) emits "NULL".
 *
 *   java ... DateConvertProbe format <epochMillis> <offsetMinutes>
 *       Builds a GregorianCalendar at the given instant in a fixed-offset
 *       SimpleTimeZone (offsetMinutes east of UTC, no DST) and emits
 *       DateConverter.toString(Calendar) — the canonical
 *       "D:yyyyMMddHHmmss(+|-)HH'mm'" PDF date string. "null" calendar emits
 *       "NULL".
 *
 * Output is a single UTF-8 line, no extra framing beyond println.
 */
public final class DateConvertProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("parse".equals(mode)) {
            String input = args.length > 1 ? args[1] : null;
            // DateConverter.toCalendar(String) does not throw a checked
            // exception in PDFBox 3.0.7 — it returns null for input it cannot
            // parse. So "unparseable" is observed as NULL, not an exception.
            Calendar c = DateConverter.toCalendar(input);
            if (c == null) {
                out.print("NULL");
            } else {
                long epoch = c.getTimeInMillis();
                int off = c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET);
                out.print(epoch + " " + off);
            }
        } else if ("format".equals(mode)) {
            long epochMillis = Long.parseLong(args[1]);
            int offsetMinutes = Integer.parseInt(args[2]);
            TimeZone tz = new SimpleTimeZone(offsetMinutes * 60 * 1000, "FIXED");
            GregorianCalendar cal = new GregorianCalendar(tz);
            cal.setTimeInMillis(epochMillis);
            String s = DateConverter.toString(cal);
            out.print(s == null ? "NULL" : s);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }
}
