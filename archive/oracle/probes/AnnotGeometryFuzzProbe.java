import java.io.File;
import java.io.PrintStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquare;

/**
 * Differential fuzz probe for the GEOMETRY ACCESSORS of the markup annotations,
 * Apache PDFBox 3.0.7 (wave 1561, agent A).
 *
 * <p>Complements the appearance-handler fuzz of wave 1544 (which drives the
 * /AP stream GENERATORS) and the type-accessor fuzz of wave 1554 (scalar
 * accessors of the OTHER subtypes). NONE of those project the raw geometry
 * arrays a hostile producer can stuff into these dicts:</p>
 * <ul>
 *   <li>Square/Circle: getRectDifferences (/RD four/short/long/negative/
 *       non-numeric/non-array) -&gt; float[]; getInteriorColor (/IC arity
 *       0/1/3/4/non-array) -&gt; PDColor.</li>
 *   <li>Polygon: getVertices (/Vertices odd/empty/non-numeric/non-array)
 *       -&gt; float[]; getInteriorColor.</li>
 *   <li>Polyline: getVertices; getStartPointEndingStyle / getEndPointEndingStyle
 *       (/LE valid/unknown/string/short).</li>
 *   <li>Ink: getInkList (/InkList empty/flat/nested/non-array/mixed) -&gt;
 *       float[][].</li>
 *   <li>Line: getLine (/L short/long/non-numeric/non-array); getInteriorColor.</li>
 * </ul>
 *
 * <p>File-based, identical-bytes-on-disk (same harness as the wave-1554
 * sibling AnnotationTypeAccessorFuzzProbe): the pypdfbox test builds a
 * deterministic corpus of annotation dictionaries, embeds them as entries of a
 * non-standard {@code /FuzzAnnots} COSArray hung off the document catalog and
 * saves ONE {@code corpus.pdf} plus a {@code manifest.txt} (one case name per
 * line, in array order). This probe loads that pdf, walks the array, feeds each
 * raw COSDictionary to {@code PDAnnotation.createAnnotation} and projects one
 * stable framed line per case. Both libraries read the same bytes.</p>
 *
 * <p>Output grammar (one line per case, manifest order):</p>
 * <pre>
 *   CASE &lt;name&gt; &lt;per-type geometry projection | ERR:&lt;Exc&gt;&gt;
 * </pre>
 */
public final class AnnotGeometryFuzzProbe {

    static PrintStream out;

    private AnnotGeometryFuzzProbe() {
    }

    // Round half-even to 3 decimals; strip trailing zeros / dot; normalise -0.
    static String canon(double value) {
        BigDecimal bd = new BigDecimal(Double.toString(value))
                .setScale(3, RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0") || s.isEmpty()) {
            s = "0";
        }
        return s;
    }

    /** float[] -> "null" | "[]" | "[a b c]". */
    static String floats(float[] a) {
        if (a == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(canon(a[i]));
        }
        return sb.append(']').toString();
    }

    /** float[][] -> "[[..] [..]]"; never null (upstream returns float[0][0]). */
    static String floats2(float[][] a) {
        if (a == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(floats(a[i]));
        }
        return sb.append(']').toString();
    }

    /**
     * PDColor projection: "null" when getInteriorColor returns null; otherwise
     * "C&lt;ncomponents&gt;&lt;floats&gt;" — PDColor is non-null for ANY /IC
     * COSArray (arity 0/2/5 give a null colourspace but a non-null PDColor).
     */
    static String color(PDColor c) {
        if (c == null) {
            return "null";
        }
        return "C" + floats(c.getComponents());
    }

    static String accProj(PDAnnotation a) {
        try {
            if (a instanceof PDAnnotationSquare || a instanceof PDAnnotationCircle) {
                float[] rd;
                PDColor ic;
                if (a instanceof PDAnnotationSquare sq) {
                    rd = sq.getRectDifferences();
                    ic = sq.getInteriorColor();
                } else {
                    PDAnnotationCircle ci = (PDAnnotationCircle) a;
                    rd = ci.getRectDifferences();
                    ic = ci.getInteriorColor();
                }
                return "rd=" + floats(rd) + " ic=" + color(ic);
            }
            if (a instanceof PDAnnotationPolygon p) {
                // /IC omitted: pypdfbox polygon exposes a lite 3-tuple accessor
                // that diverges from PDColor (None for arity 1/4); that
                // divergence is pinned in the test's self-contained block, not
                // compared here. Vertices are byte-comparable.
                return "v=" + floats(p.getVertices());
            }
            if (a instanceof PDAnnotationPolyline pl) {
                return "v=" + floats(pl.getVertices())
                        + " le=" + pl.getStartPointEndingStyle()
                        + "," + pl.getEndPointEndingStyle();
            }
            if (a instanceof PDAnnotationInk ink) {
                return "ink=" + floats2(ink.getInkList());
            }
            if (a instanceof PDAnnotationLine ln) {
                return "l=" + floats(ln.getLine())
                        + " le=" + ln.getStartPointEndingStyle()
                        + "," + ln.getEndPointEndingStyle()
                        + " ic=" + color(ln.getInteriorColor());
            }
            return "n/a";
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static void runCase(COSDictionary d, String name) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try {
            PDAnnotation a = PDAnnotation.createAnnotation(d);
            sb.append(accProj(a));
        } catch (Exception e) {
            sb.append("ERR:").append(e.getClass().getSimpleName());
        }
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File pdf = new File(dir, "corpus.pdf");
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        String[] cleaned =
                Arrays.stream(names).map(String::trim).filter(s -> !s.isEmpty())
                        .toArray(String[]::new);
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSBase fz =
                    catalog.getDictionaryObject(COSName.getPDFName("FuzzAnnots"));
            COSArray arr = (COSArray) fz;
            for (int i = 0; i < cleaned.length; i++) {
                COSBase entry = arr.getObject(i);
                COSDictionary d = entry instanceof COSDictionary
                        ? (COSDictionary) entry
                        : null;
                runCase(d, cleaned[i]);
            }
        }
    }
}
