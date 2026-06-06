import java.io.PrintStream;
import java.util.Calendar;
import java.util.GregorianCalendar;
import java.util.SimpleTimeZone;
import java.util.TimeZone;
import org.apache.xmpbox.DateConverter;

/**
 * Live oracle probe for {@code org.apache.xmpbox.DateConverter} — the xmpbox
 * date helper, which is a SEPARATE class from {@code org.apache.pdfbox.util.DateConverter}
 * (owned by {@link DateConvertProbe}). xmpbox's variant has a stricter
 * {@code toCalendar(String)} (no PDF {@code D:} form, NPE on empty input) and a
 * distinct {@code toISO8601(Calendar[, boolean])} formatter that always emits a
 * colon-separated {@code ±HH:MM} zone offset.
 *
 * Two modes:
 *
 *   java ... XmpDateConverterProbe iso <epochMillis> <offsetMinutes>
 *       Builds a GregorianCalendar at the instant in a fixed-offset SimpleTimeZone
 *       (offsetMinutes east of UTC, no DST) and emits two tab-separated tokens:
 *       toISO8601(cal) and toISO8601(cal, true) — the second prints milliseconds.
 *
 *   java ... XmpDateConverterProbe parse <datestring>
 *       Drives DateConverter.toCalendar(String). Emits "<epochMillis>\t<offsetMillis>"
 *       on success, "ERR\t<ExceptionSimpleName>" on any throwable (xmpbox throws
 *       IOException for unparseable input and NullPointerException for "").
 *
 * Output is a single UTF-8 line per invocation, no extra framing.
 */
public final class XmpDateConverterProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("iso".equals(mode)) {
            long epochMillis = Long.parseLong(args[1]);
            int offsetMinutes = Integer.parseInt(args[2]);
            TimeZone tz = new SimpleTimeZone(offsetMinutes * 60 * 1000, "FIXED");
            GregorianCalendar cal = new GregorianCalendar(tz);
            cal.setTimeInMillis(epochMillis);
            out.print(DateConverter.toISO8601(cal) + "\t" + DateConverter.toISO8601(cal, true));
        } else if ("parse".equals(mode)) {
            String input = args.length > 1 ? args[1] : "";
            try {
                Calendar c = DateConverter.toCalendar(input);
                long epoch = c.getTimeInMillis();
                int off = c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET);
                out.print(epoch + "\t" + off);
            } catch (Throwable t) {
                out.print("ERR\t" + t.getClass().getSimpleName());
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }
}
