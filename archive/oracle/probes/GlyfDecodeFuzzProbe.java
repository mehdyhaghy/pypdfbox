import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.GlyphData;
import org.apache.fontbox.ttf.GlyphDescription;
import org.apache.fontbox.ttf.GlyphTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe for the {@code glyf} table GLYPH-DECODE path of FontBox
 * under byte-level malformed input (wave 1525 differential glyf fuzz).
 *
 * Where {@code CompositeGlyphProbe} fingerprints a WELL-FORMED composite
 * outline, this probe targets the DECODE of HOSTILE glyf byte streams: a single
 * glyph's on-disk bytes are overwritten in place (same length, so the
 * {@code loca} offsets and every downstream table stay valid) with malformed
 * simple- / composite-glyph content, then the glyph is decoded and its OUTCOME
 * projected — never the raw bytes.
 *
 * The fuzz lives in {@code GlyfSimpleDescript} / {@code GlyfCompositeDescript} /
 * {@code GlyfCompositeComp}: simple-glyph flag REPEAT runs, X/Y coordinate
 * deltas truncated mid-stream, non-monotonic {@code endPtsOfContours},
 * {@code instructionLength} overflow, negative {@code numberOfContours} other
 * than -1, huge contour counts; composite {@code MORE_COMPONENTS} with data
 * ending, out-of-range / self / cyclic component glyph indices, deeply nested
 * composites, ARG words vs bytes, scale / 2x2 transform bytes truncated.
 *
 * The font is parsed RAW via {@link TTFParser} (not through a PDF) from a file
 * the Python companion writes (a permissively-licensed bundled font with one
 * spliced glyph). For each requested gid it emits a single stable line:
 *
 *   GLYPH \t gid \t decode_ok \t numberOfContours \t contourCount \t pointCount \t bbox
 *
 * where {@code decode_ok} is {@code true} when the description resolved without
 * throwing (then the resolved contour/point counts + bbox follow) or
 * {@code false} (then all four trailing fields are {@code ERR}). A {@code null}
 * GlyphData (zero-length entry) emits {@code GLYPH \t gid \t null}.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GlyfDecodeFuzzProbe font.ttf gid[,gid...]
 */
public final class GlyfDecodeFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File fontFile = new File(args[0]);
        int[] gids = parseGids(args[1]);
        TrueTypeFont ttf;
        try {
            ttf = new TTFParser().parse(new RandomAccessReadBufferedFile(fontFile));
        } catch (Throwable t) {
            // A parse-time throw (the malformed glyph killed the whole parse,
            // e.g. eager glyf/loca validation) collapses to a single line so
            // the Python side can mirror it without per-gid detail.
            out.print("PARSE\tfalse\n");
            return;
        }
        try {
            GlyphTable glyf = ttf.getGlyph();
            for (int gid : gids) {
                emitGlyph(out, glyf, gid);
            }
        } finally {
            ttf.close();
        }
    }

    private static void emitGlyph(PrintStream out, GlyphTable glyf, int gid) {
        GlyphData gd;
        try {
            gd = glyf.getGlyph(gid);
        } catch (Throwable t) {
            out.printf("GLYPH\t%d\tget_err\n", gid);
            return;
        }
        if (gd == null) {
            out.printf("GLYPH\t%d\tnull\n", gid);
            return;
        }
        try {
            int numberOfContours = gd.getNumberOfContours();
            GlyphDescription desc = gd.getDescription();
            desc.resolve();
            int contours = desc.getContourCount();
            int points = desc.getPointCount();
            out.printf("GLYPH\t%d\ttrue\t%d\t%d\t%d\t%d %d %d %d%n",
                    gid, numberOfContours, contours, points,
                    gd.getXMinimum(), gd.getYMinimum(),
                    gd.getXMaximum(), gd.getYMaximum());
        } catch (Throwable t) {
            out.printf("GLYPH\t%d\tfalse\tERR\tERR\tERR\tERR%n", gid);
        }
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
