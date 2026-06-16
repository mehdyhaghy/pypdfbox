import java.io.PrintStream;
import java.util.Base64;
import java.util.TreeSet;
import org.apache.fontbox.pfb.PfbParser;
import org.apache.fontbox.type1.Type1Font;

/**
 * Live oracle probe for the Type 1 PFB/PFA *segment* + eexec-boundary parse
 * surface — the IBM-style 0x80 record framing in {@link PfbParser} and the
 * downstream {@link Type1Font#createWithPFB(byte[])} /
 * {@link Type1Font#createWithSegments(byte[], byte[])} construction paths.
 *
 * This complements {@code Type1PfbDirectProbe} (which dumps the parsed surface
 * of genuine .pfb fixtures) and {@code Type1CharStringFuzzProbe} (wave 1546,
 * which fuzzed the charstring interpreter): here we feed ~30 deliberately
 * malformed / edge-case PFB byte streams and project, for each, whether
 * PfbParser threw (and the exception type + message), and if it parsed, the
 * three segment lengths and the re-parsed font name / #charstrings / #subrs.
 *
 * Each case is supplied on the command line as a Base64-encoded byte blob so
 * arbitrary (incl. high / NUL) bytes survive the shell. The driver test
 * (test_type1_pfb_segment_fuzz_wave1561.py) builds the same blobs and compares.
 *
 * Usage: java -cp pdfbox-app.jar:build Type1PfbSegmentFuzzProbe &lt;base64&gt;
 *
 * Canonical output (UTF-8):
 *   PFB &lt;OK|ERR&gt; ...           PfbParser(byte[]) result
 *     OK  -> "PFB OK len0 len1 len2"
 *     ERR -> "PFB ERR &lt;exceptionSimpleName&gt; &lt;message&gt;"
 *   FONT &lt;OK|ERR&gt; ...          Type1Font.createWithPFB(byte[]) result
 *     OK  -> "FONT OK &lt;name&gt; &lt;nGlyphs&gt; &lt;nSubrs&gt;"
 *     ERR -> "FONT ERR &lt;exceptionSimpleName&gt;"
 */
public final class Type1PfbSegmentFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] data = Base64.getDecoder().decode(args[0]);

        try {
            PfbParser parser = new PfbParser(data);
            int[] lengths = parser.getLengths();
            out.println("PFB OK " + lengths[0] + " " + lengths[1] + " " + lengths[2]);
        } catch (Throwable t) {
            out.println("PFB ERR " + t.getClass().getSimpleName() + " " + msg(t));
        }

        try {
            Type1Font font = Type1Font.createWithPFB(data);
            TreeSet<String> names = new TreeSet<String>(font.getCharStringsDict().keySet());
            out.println("FONT OK " + font.getName() + " " + names.size()
                    + " " + font.getSubrsArray().size());
        } catch (Throwable t) {
            out.println("FONT ERR " + t.getClass().getSimpleName());
        }
    }

    private static String msg(Throwable t) {
        String m = t.getMessage();
        return m == null ? "" : m.replace('\n', ' ').replace('\r', ' ');
    }
}
