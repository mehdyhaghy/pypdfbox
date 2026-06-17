import java.io.File;
import java.util.ArrayList;
import java.util.List;
import org.apache.fontbox.ttf.TrueTypeCollection;
import org.apache.fontbox.ttf.TrueTypeFont;

/**
 * Live oracle probe for the TrueTypeCollection (.ttc) parse + per-font lookup
 * contract under malformed / edge input (wave 1552 differential TTC fuzz).
 *
 * Complements {@code TrueTypeCollectionFuzzProbe} (wave 1530, which fingerprints
 * only the header parse + name enumeration). This probe goes deeper into the
 * PER-FONT projection that wave 1530 left out:
 *
 *   * the GLYPH COUNT of each enumerated font (shared-table behaviour: every
 *     font in a multi-font TTC still resolves its own maxp.numGlyphs),
 *   * a getFontByName lookup for a name we KNOW is present (vs. wave 1530's
 *     missing-name only),
 *   * getFontByName's returned font glyph count, proving the by-name path
 *     yields a fully-parsed font, not just a header.
 *
 * {@code getFontAtIndex} is private upstream, so index access is fingerprinted
 * indirectly through {@code processAllFonts}, which visits fonts in offset-array
 * order — i.e. index 0 is the first {@code visited=...} line.
 *
 * Output (stable projection, never raw bytes):
 *
 *   ok=true
 *   numFonts=<count visited by processAllFonts, or "error" if it threw>
 *   visited=<name>:<numGlyphs> (one per font, comma-joined; "null"/"err" guards)
 *   byName[<probeName>]=<numGlyphs of the matched font, "null" if not found,
 *                        "error" on throw>
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from the {@link TrueTypeCollection} constructor (header parse).
 *
 * Usage:
 *   java -cp ... TtcFuzzProbe collection.ttc [probeName]
 */
public final class TtcFuzzProbe
{
    public static void main(String[] args) throws Exception
    {
        File file = new File(args[0]);
        String probeName = args.length > 1 ? args[1] : "__nope__";

        TrueTypeCollection ttc;
        try
        {
            ttc = new TrueTypeCollection(file);
        }
        catch (Throwable t)
        {
            System.out.print("ok=false\n");
            return;
        }

        StringBuilder sb = new StringBuilder();
        try
        {
            sb.append("ok=true\n");

            final List<String> visited = new ArrayList<>();
            String countLine;
            try
            {
                ttc.processAllFonts(font ->
                {
                    visited.add(describe(font));
                });
                countLine = Integer.toString(visited.size());
            }
            catch (Throwable t)
            {
                countLine = "error";
            }
            sb.append("numFonts=").append(countLine).append('\n');
            sb.append("visited=").append(String.join(",", visited)).append('\n');
            sb.append("byName[").append(probeName).append("]=")
              .append(byName(ttc, probeName)).append('\n');
        }
        finally
        {
            try
            {
                ttc.close();
            }
            catch (Throwable ignore)
            {
                // best-effort close
            }
        }
        System.out.print(sb);
    }

    /** "<name>:<numGlyphs>" with per-field guards so one bad font is visible. */
    private static String describe(TrueTypeFont font)
    {
        String name;
        try
        {
            String n = font.getName();
            name = n == null ? "null" : n;
        }
        catch (Throwable t)
        {
            name = "nameerr";
        }
        String glyphs;
        try
        {
            glyphs = Integer.toString(font.getNumberOfGlyphs());
        }
        catch (Throwable t)
        {
            glyphs = "glyphserr";
        }
        return name + ":" + glyphs;
    }

    /** numGlyphs of the by-name match, "null" if absent, "error" on throw. */
    private static String byName(TrueTypeCollection ttc, String probeName)
    {
        try
        {
            TrueTypeFont f = ttc.getFontByName(probeName);
            if (f == null)
            {
                return "null";
            }
            return Integer.toString(f.getNumberOfGlyphs());
        }
        catch (Throwable t)
        {
            return "error";
        }
    }
}
