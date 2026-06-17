import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.PostScriptTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe for the TrueType {@code post} table *header* surface — the
 * scalar fields parsed before the optional format-2.0 glyph-name array. The
 * sibling {@code PostTableProbe} already pins the glyph-name accessors
 * ({@code getFormatType} / {@code getName} / {@code nameToGID}); this probe pins
 * the remaining {@link PostScriptTable} header getters that drive font metrics
 * (italic slant, underline placement, fixed-pitch flag, Type42/Type1 VM hints):
 *
 *   - {@link PostScriptTable#getItalicAngle()}        — 16.16 fixed, degrees CCW
 *   - {@link PostScriptTable#getUnderlinePosition()}  — FUnits (signed short)
 *   - {@link PostScriptTable#getUnderlineThickness()} — FUnits (signed short)
 *   - {@link PostScriptTable#getIsFixedPitch()}       — 0 = proportional, !=0 = monospace
 *   - {@link PostScriptTable#getMinMemType42()} / getMaxMemType42()
 *   - {@link PostScriptTable#getMinMemType1()}  / getMaxMemType1()
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PostHeaderProbe <font.ttf>
 *
 * Output: UTF-8, tab-delimited, deterministic line order. One KEY\tVALUE line
 * per field; floats rendered via Float.toString so the integer-valued ones read
 * as "0.0" / "-12.0" exactly as Python's str(float) does.
 */
public final class PostHeaderProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String path = args[0];

        TrueTypeFont ttf = null;
        try {
            ttf = new TTFParser().parse(new RandomAccessReadBufferedFile(new File(path)));
            PostScriptTable post = ttf.getPostScript();
            out.printf("FORMAT\t%s%n", Float.toString(post.getFormatType()));
            out.printf("ITALICANGLE\t%s%n", Float.toString(post.getItalicAngle()));
            out.printf("UNDERLINEPOSITION\t%d%n", post.getUnderlinePosition());
            out.printf("UNDERLINETHICKNESS\t%d%n", post.getUnderlineThickness());
            out.printf("ISFIXEDPITCH\t%d%n", post.getIsFixedPitch());
            out.printf("MINMEMTYPE42\t%d%n", post.getMinMemType42());
            out.printf("MAXMEMTYPE42\t%d%n", post.getMaxMemType42());
            out.printf("MINMEMTYPE1\t%d%n", post.getMinMemType1());
            out.printf("MAXMEMTYPE1\t%d%n", post.getMaxMemType1());
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
    }
}
