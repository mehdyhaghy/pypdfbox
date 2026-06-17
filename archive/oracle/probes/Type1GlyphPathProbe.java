import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.FileInputStream;
import java.io.PrintStream;
import java.util.TreeSet;
import org.apache.fontbox.type1.Type1Font;

/**
 * Live oracle probe: emit Apache FontBox's program-native Type 1 glyph OUTLINE
 * straight from a standalone PFB program (NOT from a PDF, NOT from a raster).
 *
 * Companion to {@code GlyphPathProbe} (which covers TrueType / CFF glyph paths
 * reached through a PDF) and to the {@code rendering/oracle} Type 1 tests
 * (which cover the rasterised glyph). This probe isolates the FontBox Type 1
 * charstring interpreter itself: {@code Type1Font.createWithPFB(bytes)} then
 * {@code Type1Font.getPath(glyphName)} -> {@link java.awt.geom.GeneralPath}.
 * That exercises {@code hsbw} / {@code sbw}, {@code rmoveto} / {@code rlineto}
 * / {@code rrcurveto} / {@code closepath}, the {@code seac} accent composite,
 * and the flex / hint-replacement {@code OtherSubrs} machinery.
 *
 * The path is fingerprinted in a COORDINATE-TOLERANT but STRUCTURALLY-STRICT
 * way (identical strategy to {@code GlyphPathProbe}), because exact control
 * coordinates can differ by sub-unit rounding between AWT's GeneralPath and
 * fontTools:
 *   - the control-point bounding box (4 ints: minX minY maxX maxY, rounded via
 *     Math.round on Rectangle2D from getBounds2D),
 *   - the number of path segments,
 *   - the segment-type sequence (M/L/Q/C/Z) read from the PathIterator.
 *
 * A GeneralPath's PathIterator yields SEG_MOVETO=M, SEG_LINETO=L,
 * SEG_QUADTO=Q, SEG_CUBICTO=C, SEG_CLOSE=Z. Type 1 charstrings only ever emit
 * cubics, so Q never appears.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type1GlyphPathProbe font.pfb
 *
 * Output (UTF-8, stdout), deterministic line order (glyph name ascending):
 *   NAME &lt;type1FontName&gt;
 *   PATH &lt;glyphName&gt; &lt;minX&gt; &lt;minY&gt; &lt;maxX&gt; &lt;maxY&gt; &lt;nseg&gt; &lt;typeSeq&gt;
 * For an empty (no-outline) glyph the bbox is "0 0 0 0", nseg "0", typeSeq ""
 * (empty). A glyph whose path lookup throws is emitted as bbox
 * "ERR ERR ERR ERR", nseg "ERR", typeSeq "ERR".
 */
public final class Type1GlyphPathProbe {
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
            emit(out, t1, name);
        }
    }

    private static void emit(PrintStream out, Type1Font t1, String name) {
        GeneralPath path;
        try {
            path = t1.getPath(name);
        } catch (Exception e) {
            out.println("PATH " + name + " ERR ERR ERR ERR ERR ERR");
            return;
        }
        StringBuilder seq = new StringBuilder();
        int nseg = 0;
        PathIterator it = path.getPathIterator(null);
        double[] coords = new double[6];
        while (!it.isDone()) {
            int type = it.currentSegment(coords);
            switch (type) {
                case PathIterator.SEG_MOVETO:
                    seq.append('M');
                    break;
                case PathIterator.SEG_LINETO:
                    seq.append('L');
                    break;
                case PathIterator.SEG_QUADTO:
                    seq.append('Q');
                    break;
                case PathIterator.SEG_CUBICTO:
                    seq.append('C');
                    break;
                case PathIterator.SEG_CLOSE:
                    seq.append('Z');
                    break;
                default:
                    seq.append('?');
                    break;
            }
            nseg++;
            it.next();
        }
        long minX;
        long minY;
        long maxX;
        long maxY;
        if (nseg == 0) {
            minX = 0;
            minY = 0;
            maxX = 0;
            maxY = 0;
        } else {
            Rectangle2D b = path.getBounds2D();
            minX = Math.round(b.getMinX());
            minY = Math.round(b.getMinY());
            maxX = Math.round(b.getMaxX());
            maxY = Math.round(b.getMaxY());
        }
        out.println(
            "PATH " + name + " " + minX + " " + minY + " " + maxX + " " + maxY
            + " " + nseg + " " + seq.toString());
    }
}
