import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Locale;
import org.apache.fontbox.ttf.OTFParser;
import org.apache.fontbox.ttf.OpenTypeFont;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the renderer-facing GLYPH-ACCESS surface of a
 * CFF-flavoured ({@code OTTO}) {@link org.apache.fontbox.ttf.OpenTypeFont}.
 *
 * <p>Where {@code OtfCffLoadProbe} reaches into the embedded
 * {@code getCFF().getFont().getType2CharString(gid)} directly, this probe drives
 * the FontBox text/render API the way {@code PDType0Font} / {@code PDTrueTypeFont}
 * glyph lookup does:
 *
 * <ul>
 *   <li>{@link OpenTypeFont#getPath(String)} — the name-keyed override that
 *       routes through the CFF when the font is PostScript-flavoured;</li>
 *   <li>{@code TrueTypeFont.getWidth(String)} — the name-keyed advance, which
 *       upstream computes as {@code getAdvanceWidth(nameToGID(name))} with NO
 *       special-case for an unresolved (gid 0) name;</li>
 *   <li>{@code TrueTypeFont.hasGlyph(String)} — name resolves to a non-zero
 *       gid;</li>
 *   <li>{@link OpenTypeFont#getGlyph()} — must throw on a PostScript font (no
 *       {@code glyf} table).</li>
 * </ul>
 *
 * <pre>
 *   java -cp ... OtfCffGlyphAccessProbe read &lt;input.otf&gt;
 * </pre>
 *
 * Output (UTF-8, stdout), deterministic order:
 *
 *   GLYPHTABLE \t &lt;"THROWS" | "ok" | "null"&gt;
 *   ACCESS \t name \t hasGlyph \t width \t nseg \t typeSeq \t minX \t minY \t maxX \t maxY
 *
 * The ACCESS line drives {@code getPath(name)} + {@code getWidth(name)} +
 * {@code hasGlyph(name)} together — the exact trio a renderer touches per glyph.
 * The width is emitted as the rounded integer of the {@code float} return.
 * Path fingerprint is the same coordinate-tolerant / structurally-strict shape
 * as the sibling CFF probes. Reads the OTF byte file only; never mutates.
 */
public final class OtfCffGlyphAccessProbe {

    /**
     * Names probed. {@code uniXXXX} forms resolve through the cmap fallback in
     * {@code nameToGID} (the synthetic font ships a format-3.0 {@code post}
     * table, so PostScript names like "A" do not resolve — mirroring how a
     * real subset-embedded OTF/CFF font is keyed by Unicode). {@code uni0041}
     * is the drawn triangle, {@code uni0042} the curved glyph, {@code uni0020}
     * the blank space; {@code .notdef} and {@code bogusName} resolve to gid 0.
     */
    private static final String[] NAMES = {
        "uni0041", "uni0042", "uni0020", ".notdef", "bogusName",
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"read".equals(args[0])) {
            out.println("usage: OtfCffGlyphAccessProbe read <input.otf>");
            return;
        }
        byte[] data = Files.readAllBytes(Paths.get(args[1]));
        OpenTypeFont otf = new OTFParser().parse(new RandomAccessReadBuffer(data));

        // getGlyph() must reject a PostScript-flavoured OTF (no glyf table).
        String glyphTable;
        try {
            glyphTable = otf.getGlyph() == null ? "null" : "ok";
        } catch (UnsupportedOperationException e) {
            glyphTable = "THROWS";
        }
        out.printf(Locale.ROOT, "GLYPHTABLE\t%s%n", glyphTable);

        for (String name : NAMES) {
            emit(out, otf, name);
        }
    }

    private static void emit(PrintStream out, OpenTypeFont otf, String name) throws Exception {
        boolean hasGlyph = otf.hasGlyph(name);
        float width = otf.getWidth(name);
        GeneralPath path = otf.getPath(name);

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
        int minX;
        int minY;
        int maxX;
        int maxY;
        if (nseg == 0) {
            minX = 0;
            minY = 0;
            maxX = 0;
            maxY = 0;
        } else {
            Rectangle2D b = path.getBounds2D();
            minX = (int) Math.round(b.getMinX());
            minY = (int) Math.round(b.getMinY());
            maxX = (int) Math.round(b.getMaxX());
            maxY = (int) Math.round(b.getMaxY());
        }
        out.printf(Locale.ROOT, "ACCESS\t%s\t%b\t%d\t%d\t%s\t%d\t%d\t%d\t%d%n",
                name, hasGlyph, Math.round(width), nseg, types.toString(),
                minX, minY, maxX, maxY);
    }
}
