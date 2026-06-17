import java.io.File;
import java.util.ArrayList;
import java.util.List;
import org.apache.fontbox.ttf.TrueTypeCollection;
import org.apache.fontbox.ttf.TrueTypeFont;

/**
 * Live oracle probe for the TrueTypeCollection (.ttc) header-parse contract
 * under malformed input (wave 1530 differential TTC fuzz).
 *
 * Reads raw (possibly corrupt) TTC bytes from a file, constructs Apache
 * FontBox's {@link TrueTypeCollection}, and prints a stable projection of the
 * OUTCOME rather than raw bytes:
 *
 *   ok=true
 *   numFonts=<count seen by processAllFonts, or "error" if it threw>
 *   names=<comma-joined postscript names visited by processAllFonts>
 *   getByMissing=<true if getFontByName("__nope__") returned null, else value>
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from the {@link TrueTypeCollection} constructor (header parse).
 * Only the public API (constructor, processAllFonts, getFontByName, close) is
 * used — getFontAtIndex / numFonts are private upstream. The pypdfbox side
 * reproduces this fingerprint exactly so the parity assertion is a single
 * string compare.
 *
 * Usage:
 *   java -cp ... TrueTypeCollectionFuzzProbe collection.ttc
 */
public final class TrueTypeCollectionFuzzProbe
{
    public static void main(String[] args) throws Exception
    {
        File file = new File(args[0]);

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

            final List<String> names = new ArrayList<>();
            String countLine;
            try
            {
                ttc.processAllFonts(font ->
                {
                    String n = font.getName();
                    names.add(n == null ? "null" : n);
                });
                countLine = Integer.toString(names.size());
            }
            catch (Throwable t)
            {
                countLine = "error";
            }
            sb.append("numFonts=").append(countLine).append('\n');
            sb.append("names=").append(String.join(",", names)).append('\n');
            sb.append("getByMissing=").append(getByMissing(ttc)).append('\n');
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

    /** "true" iff getFontByName for a guaranteed-missing name returns null. */
    private static String getByMissing(TrueTypeCollection ttc)
    {
        try
        {
            TrueTypeFont f = ttc.getFontByName("__nope__");
            return Boolean.toString(f == null);
        }
        catch (Throwable t)
        {
            return "error";
        }
    }
}
