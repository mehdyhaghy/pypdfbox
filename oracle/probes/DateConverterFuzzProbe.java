import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.Base64;
import java.util.Calendar;
import org.apache.pdfbox.util.DateConverter;

/**
 * Deep malformed-input fuzz probe for
 * {@code org.apache.pdfbox.util.DateConverter.toCalendar(String)} — the parser
 * that backs {@code COSDictionary.getDate} (wave 1522, agent C).
 *
 * <p>Complements the existing {@code DateConvertProbe} battery
 * (tests/xmpbox/oracle/test_date_convert_oracle.py) by driving a fresh corpus of
 * malformed {@code D:YYYYMMDDHHmmSSOHH'mm'} shapes the older battery does NOT
 * cover: missing/garbage {@code D:} prefix variants, deeply truncated strings,
 * out-of-range field combinations, malformed timezone offsets
 * ({@code +24'00'}, {@code -13'70'}, {@code +5}, missing-quote forms),
 * trailing junk, embedded non-digit chars, leap-second {@code 60}, odd
 * separators, very long strings, and lowercase/whitespace prefix noise.
 *
 * <p>Driven file-based to keep arbitrary bytes (control chars, whitespace,
 * apostrophes) out of argv. The pypdfbox sibling
 * (tests/util/oracle/test_date_converter_fuzz_wave1522.py) writes a
 * {@code corpus.txt} whose every line is the BASE64 of one UTF-8 input string
 * (base64 so whitespace / empty / control-char inputs survive line splitting).
 * Both sides decode the exact same bytes.
 *
 * <p>Line grammar (one per case, corpus order):
 *
 * <pre>
 *   &lt;NULL | epochMillis offsetMillis | ERR:ClassName&gt;
 * </pre>
 *
 * <p>{@code toCalendar(String)} returns null for unparseable / empty input in
 * PDFBox 3.0.7 (it does not throw). {@code offsetMillis} is
 * {@code ZONE_OFFSET + DST_OFFSET} — pins the displayed zone. Any unexpected
 * runtime exception is framed {@code ERR:ClassName} so a parser crash on a
 * fuzz input is observable rather than aborting the whole run.
 */
public final class DateConverterFuzzProbe {

    static String fingerprint(String input) {
        try {
            Calendar c = DateConverter.toCalendar(input);
            if (c == null) {
                return "NULL";
            }
            long epoch = c.getTimeInMillis();
            int off = c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET);
            return epoch + " " + off;
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String corpus =
                new String(Files.readAllBytes(new java.io.File(args[0]).toPath()),
                        StandardCharsets.UTF_8);
        Base64.Decoder dec = Base64.getDecoder();
        for (String line : corpus.split("\n", -1)) {
            String t = line.trim();
            if (t.isEmpty()) {
                continue;
            }
            String input = new String(dec.decode(t), StandardCharsets.UTF_8);
            out.println(fingerprint(input));
        }
    }
}
