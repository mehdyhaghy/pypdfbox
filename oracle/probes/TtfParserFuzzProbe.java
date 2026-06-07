import java.io.File;
import java.nio.file.Files;
import org.apache.fontbox.ttf.CmapLookup;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the lenient TTF/OTF parse contract under malformed
 * input (wave 1506 differential font-parser fuzz).
 *
 * Reads raw (possibly corrupt) SFNT bytes from a file, parses them with
 * Apache FontBox's {@link TTFParser} in the requested leniency arm, and prints
 * a stable projection of the OUTCOME rather than raw bytes:
 *
 *   ok=true
 *   numGlyphs=<int>
 *   unitsPerEm=<int>
 *   tables=<comma-joined sorted table tags>
 *   adv0=<advance width of gid 0>
 *   advN=<advance width of a fixed probe gid>
 *   cmapA=<gid for U+0041, or -1 when no usable cmap>
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from {@code TTFParser.parse}. The pypdfbox side reproduces this
 * fingerprint exactly so the parity assertion is a single string compare.
 *
 * Usage:
 *   java -cp ... TtfParserFuzzProbe font.bin            # non-embedded (strict) arm
 *   java -cp ... TtfParserFuzzProbe font.bin embedded   # embedded (lenient) arm
 */
public final class TtfParserFuzzProbe
{
    /** Fixed probe gid used for the advN projection. */
    private static final int PROBE_GID = 3;

    public static void main(String[] args) throws Exception
    {
        File file = new File(args[0]);
        boolean embedded = args.length > 1 && "embedded".equals(args[1]);
        byte[] bytes = Files.readAllBytes(file.toPath());

        StringBuilder sb = new StringBuilder();
        try (TrueTypeFont font =
                new TTFParser(embedded).parse(new RandomAccessReadBuffer(bytes)))
        {
            sb.append("ok=true\n");
            sb.append("numGlyphs=").append(font.getNumberOfGlyphs()).append('\n');
            sb.append("unitsPerEm=").append(font.getUnitsPerEm()).append('\n');

            java.util.List<String> tags =
                    new java.util.ArrayList<>(font.getTableMap().keySet());
            java.util.Collections.sort(tags);
            // tags may carry trailing spaces (e.g. "cvt "); join verbatim.
            sb.append("tables=").append(String.join(",", tags)).append('\n');

            sb.append("adv0=").append(advance(font, 0)).append('\n');
            sb.append("advN=").append(advance(font, PROBE_GID)).append('\n');
            sb.append("cmapA=").append(cmapGid(font, 0x41)).append('\n');
        }
        catch (Throwable t)
        {
            System.out.print("ok=false\n");
            return;
        }
        System.out.print(sb);
    }

    private static int advance(TrueTypeFont font, int gid)
    {
        try
        {
            return font.getAdvanceWidth(gid);
        }
        catch (Throwable t)
        {
            return -1;
        }
    }

    private static int cmapGid(TrueTypeFont font, int codePoint)
    {
        try
        {
            CmapLookup cmap = font.getUnicodeCmapLookup(false);
            if (cmap == null)
            {
                return -1;
            }
            return cmap.getGlyphId(codePoint);
        }
        catch (Throwable t)
        {
            return -1;
        }
    }
}
