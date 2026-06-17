import java.nio.file.Files;
import java.util.List;
import org.apache.fontbox.cff.CFFCIDFont;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;

/**
 * Live oracle probe for the lenient CFF parse contract under malformed input
 * (wave 1507 differential font-parser fuzz; sibling of TtfParserFuzzProbe).
 *
 * Reads raw (possibly corrupt) bare-CFF bytes from a file, parses them with
 * Apache FontBox's {@link CFFParser} ({@code parse(byte[], ByteSource)} — the
 * entry point pypdfbox's {@code CFFParser().parse(bytes)} default maps to), and
 * prints a stable projection of the OUTCOME rather than raw bytes:
 *
 *   ok=true
 *   name=&lt;PostScript font name&gt;
 *   numGlyphs=&lt;int&gt;
 *   isCID=&lt;bool&gt;
 *   w0=&lt;advance width of gid 0&gt;
 *   wN=&lt;advance width of fixed probe gid&gt;
 *   nameN=&lt;glyph name (or CID) for probe gid&gt;
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from {@code CFFParser.parse}. The pypdfbox side reproduces this
 * fingerprint exactly so the parity assertion is a single string compare.
 *
 * Usage:
 *   java -cp ... CffParserFuzzProbe font.cff
 */
public final class CffParserFuzzProbe {
    /** Fixed probe gid used for the wN / nameN projection. */
    private static final int PROBE_GID = 1;

    public static void main(String[] args) throws Exception {
        byte[] bytes = Files.readAllBytes(new java.io.File(args[0]).toPath());

        StringBuilder sb = new StringBuilder();
        try {
            List<CFFFont> fonts = new CFFParser().parse(bytes, new ByteSource(bytes));
            CFFFont font = fonts.get(0);
            int numGlyphs = font.getNumCharStrings();
            boolean isCid = font instanceof CFFCIDFont;
            sb.append("ok=true\n");
            sb.append("name=").append(font.getName()).append('\n');
            sb.append("numGlyphs=").append(numGlyphs).append('\n');
            sb.append("isCID=").append(isCid).append('\n');
            sb.append("w0=").append(width(font, 0)).append('\n');
            sb.append("wN=").append(width(font, PROBE_GID)).append('\n');
            sb.append("nameN=").append(nameForGid(font, PROBE_GID)).append('\n');
        } catch (Throwable t) {
            System.out.print("ok=false\n");
            return;
        }
        System.out.print(sb);
    }

    private static String width(CFFFont font, int gid) {
        try {
            return formatWidth(font.getType2CharString(gid).getWidth());
        } catch (Throwable t) {
            return "-1";
        }
    }

    private static String formatWidth(float w) {
        // Render whole numbers without a trailing ".0" so the int-vs-float
        // representation matches the Python side's str(int) where possible.
        if (w == Math.rint(w) && !Float.isInfinite(w)) {
            return Long.toString((long) w);
        }
        return Float.toString(w);
    }

    private static String nameForGid(CFFFont font, int gid) {
        try {
            if (font instanceof CFFCIDFont) {
                return Integer.toString(font.getCharset().getCIDForGID(gid));
            }
            return font.getCharset().getNameForGID(gid);
        } catch (Throwable t) {
            return "-1";
        }
    }

    /** Minimal {@code CFFParser.ByteSource} so {@code CFFParser.parse} works. */
    private static final class ByteSource
            implements org.apache.fontbox.cff.CFFParser.ByteSource {
        private final byte[] bytes;

        ByteSource(byte[] bytes) {
            this.bytes = bytes;
        }

        @Override
        public byte[] getBytes() {
            return bytes;
        }
    }
}
