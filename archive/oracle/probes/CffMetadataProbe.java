import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.Map;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;

/**
 * Live oracle probe for CFF Top DICT metadata-string operators
 * ({@code /version}, {@code /Notice}, {@code /Copyright},
 * {@code /FullName}, {@code /FamilyName}, {@code /Weight}).
 *
 * <p>Each operator carries a SID; per Adobe Technote #5176 §10 the SID
 * must resolve via the predefined Standard Strings table (SIDs 0..390)
 * for any value matching an entry in that table, and via the per-font
 * STRING INDEX for everything else. The two paths are the
 * differential-test target — confusing them surfaces as a wrong
 * resolved string (either garbage or the wrong String-INDEX entry).
 *
 * <pre>
 *   java -cp ... CffMetadataProbe &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   NAME \t &lt;CFFFont.getName()&gt;
 *   META \t &lt;key&gt; \t &lt;value or "<null>" when absent&gt;
 *       For each of: version, Notice, Copyright, FullName, FamilyName, Weight.
 *
 * Never mutates input; the parser holds no external resources, so no
 * try-with-resources is required (the underlying bytes are read via
 * {@link java.nio.file.Files#readAllBytes} which closes immediately).
 */
public final class CffMetadataProbe {

    private static final String[] METADATA_KEYS = {
            "version", "Notice", "Copyright", "FullName", "FamilyName", "Weight"
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 1) {
            out.println("usage: CffMetadataProbe <input.cff>");
            return;
        }
        byte[] data = java.nio.file.Files.readAllBytes(new File(args[0]).toPath());
        List<CFFFont> fonts = new CFFParser().parse(data, new CffByteSource(data));
        if (fonts.isEmpty()) {
            out.println("NAME\t<empty>");
            return;
        }
        CFFFont font = fonts.get(0);
        out.printf("NAME\t%s%n", String.valueOf(font.getName()));
        Map<String, Object> topDict = font.getTopDict();
        for (String key : METADATA_KEYS) {
            Object value = topDict.get(key);
            out.printf("META\t%s\t%s%n", key,
                    value == null ? "<null>" : String.valueOf(value));
        }
    }

    /** Minimal ByteSource backing the embedded CFF program. */
    private static final class CffByteSource implements CFFParser.ByteSource {
        private final byte[] bytes;

        CffByteSource(byte[] bytes) {
            this.bytes = bytes;
        }

        @Override
        public byte[] getBytes() {
            return bytes;
        }
    }
}
