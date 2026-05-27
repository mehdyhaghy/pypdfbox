import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.PostScriptTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe for the TrueType {@code post} table glyph-name surface.
 *
 * Loads a font program directly via FontBox ({@link TTFParser}) and exercises
 * the {@code post}-table glyph-name accessors that drive non-symbolic TrueType
 * encoding (code -> name -> gid) and glyph-name-based text extraction:
 *
 *   - {@link PostScriptTable#getFormatType()} — the post table format
 *     (1.0 = the standard Macintosh 258 names; 2.0 = a glyph-name index array
 *     plus the Mac 258 plus custom Pascal-string names; 3.0 = no names).
 *   - {@link PostScriptTable#getName(int)} — the glyph name for a gid. For
 *     format 2.0 this resolves Mac-standard indices (< 258) against the built-in
 *     258-name table and custom indices (>= 258) against the table's
 *     Pascal-string array.
 *   - {@link TrueTypeFont#nameToGID(String)} — the reverse lookup (glyph name
 *     -> gid) PDFBox uses when mapping an /Encoding name to a glyph.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PostTableProbe <font.ttf> <gid>... -- <name>...
 *
 * Everything before the literal {@code --} separator is a gid to resolve via
 * {@code getName}; everything after is a glyph name to resolve via
 * {@code nameToGID}.
 *
 * Output: UTF-8, tab-delimited, deterministic line order. Canonical lines:
 *   FORMAT   \t <formatType>          (e.g. 2.0)
 *   NUMGLYPHS\t <numberOfGlyphs>
 *   NAME     \t <gid> \t (<glyphName>|NULL)
 *   GID      \t <glyphName> \t <gid>
 */
public final class PostTableProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String path = args[0];

        // Split the remaining args at the literal "--" separator: gids before,
        // names after.
        int sep = -1;
        for (int i = 1; i < args.length; i++) {
            if ("--".equals(args[i])) {
                sep = i;
                break;
            }
        }
        int gidEnd = (sep == -1) ? args.length : sep;
        int nameStart = (sep == -1) ? args.length : sep + 1;

        TrueTypeFont ttf = null;
        try {
            ttf = new TTFParser().parse(new RandomAccessReadBufferedFile(new File(path)));
            PostScriptTable post = ttf.getPostScript();
            float format = (post == null) ? -1.0f : post.getFormatType();
            out.printf("FORMAT\t%s%n", formatFloat(format));
            out.printf("NUMGLYPHS\t%d%n", ttf.getNumberOfGlyphs());

            for (int i = 1; i < gidEnd; i++) {
                int gid = Integer.parseInt(args[i]);
                String name = (post == null) ? null : post.getName(gid);
                out.printf("NAME\t%d\t%s%n", gid, name == null ? "NULL" : name);
            }

            for (int i = nameStart; i < args.length; i++) {
                String name = args[i];
                int gid = ttf.nameToGID(name);
                out.printf("GID\t%s\t%d%n", name, gid);
            }
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
    }

    /** Render a post format the way PDFBox stores it (e.g. {@code 2.0}). */
    private static String formatFloat(float f) {
        // Java's default float -> String already yields "2.0", "1.0", "3.0".
        return Float.toString(f);
    }
}
