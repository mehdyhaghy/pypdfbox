import java.io.File;
import java.io.FileInputStream;
import java.io.PrintStream;
import java.util.TreeSet;
import org.apache.fontbox.type1.Type1Font;

/**
 * Live oracle probe: emit Apache FontBox's program-native Type 1 glyph
 * ADVANCE WIDTH straight from a standalone PFB program.
 *
 * Companion to {@code Type1GlyphPathProbe} (which fingerprints the glyph
 * OUTLINE). This probe isolates the width prologue of the Type 1 charstring
 * interpreter: {@code hsbw} (horizontal side-bearing + width) and {@code sbw}
 * (full side-bearing + width), including the {@code seac} accent composite,
 * whose advance width is taken from the COMPOSITE charstring's own
 * {@code hsbw} (NOT the base glyph's). We reach
 * {@code Type1Font.createWithPFB(bytes)} then {@code Type1Font.getWidth(name)}.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type1WidthProbe font.pfb
 *
 * Output (UTF-8, stdout), deterministic line order (glyph name ascending):
 *   NAME &lt;type1FontName&gt;
 *   WIDTH &lt;glyphName&gt; &lt;advanceWidth&gt;
 * where the advance width is rendered as a plain integer when integral and
 * otherwise as the default float string. A glyph whose width lookup throws is
 * emitted with width "ERR".
 */
public final class Type1WidthProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] pfb;
        try (FileInputStream in = new FileInputStream(new File(args[0]))) {
            pfb = in.readAllBytes();
        }
        Type1Font t1 = Type1Font.createWithPFB(pfb);
        out.println("NAME " + t1.getName());
        TreeSet<String> names = new TreeSet<String>(t1.getCharStringsDict().keySet());
        for (String name : names) {
            String w;
            try {
                w = canonNumber(t1.getWidth(name));
            } catch (Exception e) {
                w = "ERR";
            }
            out.println("WIDTH " + name + " " + w);
        }
    }

    private static String canonNumber(float value) {
        if (value == Math.rint(value) && !Float.isInfinite(value)) {
            return Long.toString((long) value);
        }
        return Float.toString(value);
    }
}
