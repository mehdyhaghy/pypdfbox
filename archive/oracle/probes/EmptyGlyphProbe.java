import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.GlyphData;
import org.apache.fontbox.ttf.GlyphDescription;
import org.apache.fontbox.ttf.GlyphTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;

/**
 * Live oracle probe for the {@code glyf} EMPTY / ZERO-CONTOUR glyph path of
 * FontBox.
 *
 * A whitespace glyph (e.g. {@code space}) carries {@code numberOfContours == 0}
 * and a ZERO-LENGTH {@code loca} entry ({@code loca[gid] == loca[gid+1]}, i.e.
 * no glyf bytes at all). FontBox must still return a non-null
 * {@link GlyphData} for such a GID — see PDFBOX-5135, where composite-glyph
 * resolution could not tolerate a {@code null} here — with an EMPTY outline
 * (no path segments), a degenerate (0,0,0,0) bounding box, a resolved contour
 * count of 0, a point count of 0, and the glyph's real ADVANCE WIDTH from
 * {@code hmtx}. It must NOT throw.
 *
 * It loads a RAW bundled TrueType font directly via {@link TTFParser} (NOT
 * through a PDF), so the fixture is a deterministic, permissively-licensed font
 * that ships in this repo (DejaVuSans). For a curated set of empty GIDs it
 * emits, per glyph, from {@code ttf.getGlyph().getGlyph(gid)}:
 *
 *   GLYPH \t gid \t numberOfContours \t pointCount \t advanceWidth \t
 *         bbox(xMin yMin xMax yMax) \t nseg \t typeSeq \t nullFlag
 *
 * where:
 *   - numberOfContours is the resolved {@code GlyphDescription.getContourCount()}
 *   - pointCount is {@code GlyphDescription.getPointCount()}
 *   - advanceWidth is {@code ttf.getAdvanceWidth(gid)}
 *   - bbox is {@code gd.getXMinimum()}/.. (degenerate 0 0 0 0 for empties)
 *   - nseg / typeSeq fingerprint {@code gd.getPath()} (a GeneralPath); for an
 *     empty glyph nseg is 0 and typeSeq is "" (empty)
 *   - nullFlag is "NULL" when {@code getGlyph(gid)} returns null, else "OK".
 *
 * A GeneralPath's PathIterator yields SEG_MOVETO=M, SEG_LINETO=L,
 * SEG_QUADTO=Q, SEG_CUBICTO=C, SEG_CLOSE=Z.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> EmptyGlyphProbe font.ttf gid[,gid...]
 *
 * The Python companion (tests/fontbox/ttf/oracle/test_empty_glyph_oracle.py)
 * passes the same font path + GID list and asserts an exact match.
 */
public final class EmptyGlyphProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File fontFile = new File(args[0]);
        int[] gids = parseGids(args[1]);
        TrueTypeFont ttf = new TTFParser().parse(
                new org.apache.pdfbox.io.RandomAccessReadBufferedFile(fontFile));
        try {
            GlyphTable glyf = ttf.getGlyph();
            for (int gid : gids) {
                emitGlyph(out, ttf, glyf, gid);
            }
        } finally {
            ttf.close();
        }
    }

    private static void emitGlyph(PrintStream out, TrueTypeFont ttf, GlyphTable glyf, int gid)
            throws Exception {
        int advanceWidth = ttf.getAdvanceWidth(gid);
        GlyphData gd = glyf.getGlyph(gid);
        if (gd == null) {
            out.printf("GLYPH\t%d\tNULL\tNULL\t%d\tNULL\t0\t\tNULL%n", gid, advanceWidth);
            return;
        }
        GlyphDescription desc = gd.getDescription();
        desc.resolve();
        int contours = desc.getContourCount();
        int points = desc.getPointCount();
        GeneralPath path = gd.getPath();
        out.printf("GLYPH\t%d\t%d\t%d\t%d\t%d %d %d %d\t%s\tOK%n",
                gid, contours, points, advanceWidth,
                gd.getXMinimum(), gd.getYMinimum(),
                gd.getXMaximum(), gd.getYMaximum(),
                fingerprint(path));
    }

    /** Coordinate-tolerant, structure-strict fingerprint: "nseg\ttypeSeq". */
    private static String fingerprint(GeneralPath path) {
        StringBuilder types = new StringBuilder();
        int nseg = 0;
        double[] coords = new double[6];
        PathIterator it = path.getPathIterator(null);
        while (!it.isDone()) {
            switch (it.currentSegment(coords)) {
                case PathIterator.SEG_MOVETO: types.append('M'); break;
                case PathIterator.SEG_LINETO: types.append('L'); break;
                case PathIterator.SEG_QUADTO: types.append('Q'); break;
                case PathIterator.SEG_CUBICTO: types.append('C'); break;
                case PathIterator.SEG_CLOSE: types.append('Z'); break;
                default: types.append('?'); break;
            }
            nseg++;
            it.next();
        }
        return nseg + "\t" + types;
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
