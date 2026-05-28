import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.GlyphData;
import org.apache.fontbox.ttf.GlyphDescription;
import org.apache.fontbox.ttf.GlyphTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;

/**
 * Live oracle probe for the {@code glyf} COMPOSITE-GLYPH path of FontBox.
 *
 * A composite glyph (e.g. an accented letter such as Agrave / Eacute) is not
 * stored as its own outline; instead it references one or more component
 * sub-glyphs (the base letter + the diacritic) by index, each with an
 * {@code ARGS_ARE_XY_VALUES} offset and an optional component transform
 * ({@code WE_HAVE_A_SCALE} / {@code WE_HAVE_AN_X_AND_Y_SCALE} /
 * {@code WE_HAVE_A_TWO_BY_TWO}), chained by the {@code MORE_COMPONENTS} flag.
 * FontBox flattens that chain in {@code GlyfCompositeDescript}, applying each
 * component's 2x2 scale + translate to every borrowed point
 * ({@code getXCoordinate} / {@code getYCoordinate}). This probe fingerprints
 * the ASSEMBLED outline so the Python {@code GlyfCompositeDescript} /
 * {@code GlyfCompositeComp} transform math can be diffed against it.
 *
 * It loads a RAW bundled TrueType font directly via {@link TTFParser} (NOT
 * through a PDF), so the fixture is a deterministic, permissively-licensed
 * font that ships in this repo (DejaVuSans / Liberation). For a curated set of
 * composite GIDs it emits, per glyph, from
 * {@code ttf.getGlyph().getGlyph(gid)}:
 *
 *   GLYPH \t gid \t name \t numberOfContours \t pointCount \t bbox(xMin yMin xMax yMax)
 *   PT    \t gid \t i    \t x \t y \t onCurve(0|1)
 *
 * {@code numberOfContours} is the RESOLVED outline contour count (the
 * GlyphDescription's getContourCount(), which equals the number of
 * end-points), {@code pointCount} the resolved total. Each PT row is one
 * assembled point: its (x, y) are the post-transform coordinates the composite
 * descript reports, and {@code onCurve} is bit 0 ({@code ON_CURVE}) of the
 * point's flag byte. The point order is FontBox's flatten order (component by
 * component, in MORE_COMPONENTS chain order).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CompositeGlyphProbe font.ttf gid[,gid...]
 *
 * The Python companion (tests/fontbox/ttf/oracle/test_composite_glyph_oracle.py)
 * passes the same font path + GID list and asserts an exact match (coordinates
 * are integer font units; the composite transform uses Math.round so both sides
 * land on the same integer).
 */
public final class CompositeGlyphProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File fontFile = new File(args[0]);
        int[] gids = parseGids(args[1]);
        TrueTypeFont ttf = new TTFParser().parse(
                new org.apache.pdfbox.io.RandomAccessReadBufferedFile(fontFile));
        try {
            GlyphTable glyf = ttf.getGlyph();
            String[] names = glyphNames(ttf);
            for (int gid : gids) {
                emitGlyph(out, glyf, gid, names);
            }
        } finally {
            ttf.close();
        }
    }

    private static void emitGlyph(PrintStream out, GlyphTable glyf, int gid, String[] names)
            throws Exception {
        String name = (gid >= 0 && gid < names.length) ? names[gid] : "?";
        GlyphData gd = glyf.getGlyph(gid);
        if (gd == null) {
            out.printf("GLYPH\t%d\t%s\tNULL\tNULL\tNULL%n", gid, name);
            return;
        }
        GlyphDescription desc = gd.getDescription();
        // Resolve composite components against the parent glyf table so the
        // borrowed points + their transforms are materialised.
        desc.resolve();
        int contours = desc.getContourCount();
        int points = desc.getPointCount();
        out.printf("GLYPH\t%d\t%s\t%d\t%d\t%d %d %d %d%n",
                gid, name, contours, points,
                gd.getXMinimum(), gd.getYMinimum(),
                gd.getXMaximum(), gd.getYMaximum());
        for (int i = 0; i < points; i++) {
            int x = desc.getXCoordinate(i);
            int y = desc.getYCoordinate(i);
            // ON_CURVE is bit 0 of the glyf outline flag byte (GlyfDescript.ON_CURVE).
            int onCurve = (desc.getFlags(i) & 0x01) != 0 ? 1 : 0;
            out.printf("PT\t%d\t%d\t%d\t%d\t%d%n", gid, i, x, y, onCurve);
        }
    }

    /** glyph-name array indexed by GID (post table order). */
    private static String[] glyphNames(TrueTypeFont ttf) throws Exception {
        int n = ttf.getNumberOfGlyphs();
        String[] names = new String[n];
        org.apache.fontbox.ttf.PostScriptTable post = ttf.getPostScript();
        String[] glyphNames = post == null ? null : post.getGlyphNames();
        for (int i = 0; i < n; i++) {
            names[i] = (glyphNames != null && i < glyphNames.length)
                    ? String.valueOf(glyphNames[i]) : ("gid" + i);
        }
        return names;
    }

    private static int[] parseGids(String csv) {
        String[] parts = csv.split(",");
        int[] gids = new int[parts.length];
        for (int i = 0; i < parts.length; i++) {
            gids[i] = Integer.parseInt(parts[i].trim());
        }
        return gids;
    }
}
