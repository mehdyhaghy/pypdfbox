import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDAbstractPattern;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDShadingPattern;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShading;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;

/**
 * Live oracle probe: emit a CANONICAL, deterministic listing of every SHADING
 * pattern (/PatternType 2) reachable from each page's /Resources /Pattern
 * subdictionary, as Apache PDFBox parses it through PDShadingPattern.
 *
 * For each shading pattern, one block reports the typed MODEL accessor surface
 * this parity surface owns:
 *
 *   PATTERNTYPE getPatternType()                (always 2 for a shading pattern)
 *   SHADINGTYPE getShading().getShadingType()   (or "none" when /Shading absent)
 *   EXTGSTATE   getExtendedGraphicsState() present? ("yes"/"no")
 *   MATRIX      getMatrix().getValues() flattened a,b,c,d,e,f
 *
 * Blocks are sorted by the pattern's resource name so output is independent of
 * dictionary iteration order.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ShadingPatternProbe <pdf>
 * Output (UTF-8, LF-terminated). One block per shading pattern:
 *
 *   PATTERN <name>
 *   PATTERNTYPE <int>
 *   SHADINGTYPE <int|none>
 *   EXTGSTATE <yes|no>
 *   MATRIX <a>,<b>,<c>,<d>,<e>,<f>
 *   END
 */
public final class ShadingPatternProbe {

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
                    if (pattern instanceof PDShadingPattern) {
                        blocks.add(block(name.getName(),
                                (PDShadingPattern) pattern));
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

    private static String block(String name, PDShadingPattern p)
            throws Exception {
        StringBuilder b = new StringBuilder();
        b.append("PATTERN ").append(name).append('\n');
        b.append("PATTERNTYPE ").append(p.getPatternType()).append('\n');
        PDShading shading = p.getShading();
        b.append("SHADINGTYPE ")
                .append(shading == null ? "none"
                        : Integer.toString(shading.getShadingType()))
                .append('\n');
        PDExtendedGraphicsState egs = p.getExtendedGraphicsState();
        b.append("EXTGSTATE ").append(egs == null ? "no" : "yes").append('\n');
        b.append("MATRIX ").append(matrix(p)).append('\n');
        b.append("END\n");
        return b.toString();
    }

    private static String matrix(PDShadingPattern p) {
        float[][] v = p.getMatrix().getValues();
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
