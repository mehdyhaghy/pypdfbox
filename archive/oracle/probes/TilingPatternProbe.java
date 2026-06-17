import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDTilingPattern;

/**
 * Live oracle probe: emit a CANONICAL, deterministic listing of every TILING
 * pattern (/PatternType 1) reachable from each page's /Resources /Pattern
 * subdictionary, as Apache PDFBox parses it through PDTilingPattern.
 *
 * For each tiling pattern, one block reports the typed accessor surface this
 * parity surface owns:
 *
 *   PATTERNTYPE getPatternType()      (always 1 for a tiling pattern)
 *   PAINTTYPE   getPaintType()
 *   TILINGTYPE  getTilingType()
 *   BBOX        getBBox()  -> llx,lly,urx,ury  (or "none")
 *   XSTEP       getXStep()
 *   YSTEP       getYStep()
 *   MATRIX      getMatrix().getValues() flattened a,b,c,d,e,f
 *
 * Blocks are sorted by the pattern's resource name so output is independent
 * of dictionary iteration order.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TilingPatternProbe <pdf>
 * Output (UTF-8, LF-terminated). One block per tiling pattern:
 *
 *   PATTERN <name>
 *   PATTERNTYPE <int>
 *   PAINTTYPE <int>
 *   TILINGTYPE <int>
 *   BBOX <llx>,<lly>,<urx>,<ury>      (or BBOX none)
 *   XSTEP <canonFloat>
 *   YSTEP <canonFloat>
 *   MATRIX <a>,<b>,<c>,<d>,<e>,<f>
 *   END
 */
public final class TilingPatternProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            List<String> blocks = new ArrayList<>();
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res == null) {
                    continue;
                }
                for (COSName name : res.getPatternNames()) {
                    PDAbstractPattern pattern = res.getPattern(name);
                    if (pattern instanceof PDTilingPattern) {
                        blocks.add(block(name.getName(),
                                (PDTilingPattern) pattern));
                    }
                }
            }
            Collections.sort(blocks);
            StringBuilder sb = new StringBuilder();
            for (String b : blocks) {
                sb.append(b);
            }
            out.print(sb);
        }
    }

    private static String block(String name, PDTilingPattern p) {
        StringBuilder b = new StringBuilder();
        b.append("PATTERN ").append(name).append('\n');
        b.append("PATTERNTYPE ").append(p.getPatternType()).append('\n');
        b.append("PAINTTYPE ").append(p.getPaintType()).append('\n');
        b.append("TILINGTYPE ").append(p.getTilingType()).append('\n');
        b.append("BBOX ").append(bbox(p)).append('\n');
        b.append("XSTEP ").append(canonFloat(p.getXStep())).append('\n');
        b.append("YSTEP ").append(canonFloat(p.getYStep())).append('\n');
        b.append("MATRIX ").append(matrix(p)).append('\n');
        b.append("END\n");
        return b.toString();
    }

    private static String bbox(PDTilingPattern p) {
        PDRectangle r = p.getBBox();
        if (r == null) {
            return "none";
        }
        return canonFloat(r.getLowerLeftX()) + "," + canonFloat(r.getLowerLeftY())
                + "," + canonFloat(r.getUpperRightX()) + ","
                + canonFloat(r.getUpperRightY());
    }

    private static String matrix(PDTilingPattern p) {
        float[][] v = p.getMatrix().getValues();
        // getValues() returns a 3x3 row-major matrix; the affine entries are
        // [0][0]=a [0][1]=b [1][0]=c [1][1]=d [2][0]=e [2][1]=f.
        StringBuilder sb = new StringBuilder();
        sb.append(canonFloat(v[0][0])).append(',');
        sb.append(canonFloat(v[0][1])).append(',');
        sb.append(canonFloat(v[1][0])).append(',');
        sb.append(canonFloat(v[1][1])).append(',');
        sb.append(canonFloat(v[2][0])).append(',');
        sb.append(canonFloat(v[2][1]));
        return sb.toString();
    }

    /** Round half-even to 3 decimals, strip trailing zeros/dot, normalise -0. */
    private static String canonFloat(double value) {
        java.math.BigDecimal bd = new java.math.BigDecimal(value)
                .setScale(3, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if ("-0".equals(s) || s.isEmpty()) {
            s = "0";
        }
        return s;
    }
}
