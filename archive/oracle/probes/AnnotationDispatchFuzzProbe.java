import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationFreeText;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationInk;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLine;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationTextMarkup;

/**
 * Differential fuzz probe for {@code PDAnnotation.createAnnotation(COSBase)}
 * dispatch + per-subtype geometry-accessor leniency, Apache PDFBox 3.0.7
 * (wave 1515, agent A).
 *
 * <p>Complements the existing well-formed annotation oracle suite
 * ({@code AnnotFactoryProbe} — which only covers a handful of subtypes with a
 * well-formed /Subtype, plus the heavy appearance-stream probes pinned in waves
 * 1508/1509). None of those exercise the MALFORMED CONSTRUCTION + GEOMETRY
 * subset this probe targets:</p>
 * <ul>
 *   <li>/Subtype missing / unknown / mistyped (a COSString instead of a
 *       COSName) / lowercase / empty -&gt; which concrete class
 *       createAnnotation returns (typed subclass vs the generic
 *       PDAnnotationUnknown fallback).</li>
 *   <li>/Rect missing / wrong-arity (2, 3, 5 elements) / non-numeric element /
 *       inverted (urx&lt;llx).</li>
 *   <li>per-subtype geometry through the typed accessor:
 *       /QuadPoints (text-markup &amp; Link), /L (Line), /Vertices
 *       (Polygon/PolyLine), /InkList (Ink, array-of-arrays), /CL callout +
 *       /RD rectangle-differences (FreeText) — each fuzzed with wrong arity,
 *       non-numeric members, wrong COS type, and nested-array shape errors.</li>
 *   <li>/C color array arity (0/1/3/4/5/non-numeric), /CA constant alpha
 *       (real/int/string/missing), /F flags (int/real/string/missing).</li>
 * </ul>
 *
 * <p>Driven file-based, identical-bytes-on-disk: the pypdfbox sibling
 * ({@code tests/pdmodel/interactive/annotation/oracle/test_annotation_dispatch_fuzz_wave1515.py})
 * builds the deterministic corpus of annotation dictionaries, embeds them as
 * entries of a non-standard {@code /FuzzAnnots} COSArray hung off the document
 * catalog, and saves ONE {@code corpus.pdf} plus a {@code manifest.txt} (one
 * case name per line, in array order). This probe loads that single pdf, walks
 * the array, feeds each raw COSDictionary to
 * {@code PDAnnotation.createAnnotation} and projects a stable framed line. Both
 * sides read the exact same bytes on disk, so the dispatch + geometry contract
 * is directly comparable.</p>
 *
 * <p>Output grammar (one line per case, manifest order):</p>
 * <pre>
 *   CASE &lt;name&gt; class=&lt;simpleName|ERR:&lt;Exc&gt;&gt; rect=&lt;x,y,w,h|null|ERR:&lt;Exc&gt;&gt; geom=&lt;subtype-proj|ERR:&lt;Exc&gt;&gt; color=&lt;arrN|null&gt; ca=&lt;val|null&gt; flags=&lt;int&gt;
 * </pre>
 *
 * <p>class  = createAnnotation's runtime class simple name (or
 * ERR:&lt;ExcSimpleName&gt; if dispatch threw).<br>
 * rect  = getRectangle() rendered "llx,lly,width,height" with %s of the
 * float, or "null" when getRectangle() returns null, or ERR.<br>
 * geom  = a per-subtype geometry projection via the typed accessor (see
 * projectGeom); "n/a" for subtypes with no fuzzed geometry; ERR on throw.<br>
 * color = "arr&lt;n&gt;" for a /C COSArray of size n, else "null".<br>
 * ca    = getConstantAlpha-equivalent raw /CA number rendered with %s, or
 * "null" when absent / non-numeric.<br>
 * flags = getAnnotationFlags() (defaults 0).</p>
 *
 * <p>Floats are rendered with {@code fmt} (Float.toString of the value) so the
 * two libraries' float-formatting is directly diffable; the pypdfbox sibling
 * mirrors Java Float.toString via a matching helper.</p>
 */
public final class AnnotationDispatchFuzzProbe {

    static PrintStream out;

    /** Java Float.toString, so the sibling can mirror it exactly. */
    static String fmt(float f) {
        return Float.toString(f);
    }

    static String fmtArr(float[] a) {
        if (a == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(fmt(a[i]));
        }
        return sb.append(']').toString();
    }

    static String rectProj(PDAnnotation a) {
        try {
            PDRectangle r = a.getRectangle();
            if (r == null) {
                return "null";
            }
            return fmt(r.getLowerLeftX()) + "," + fmt(r.getLowerLeftY()) + ","
                    + fmt(r.getWidth()) + "," + fmt(r.getHeight());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    /** Per-subtype geometry projection through the typed accessor. */
    static String geomProj(PDAnnotation a) {
        try {
            if (a instanceof PDAnnotationLine) {
                return "L=" + fmtArr(((PDAnnotationLine) a).getLine());
            }
            if (a instanceof PDAnnotationTextMarkup) {
                return "QP=" + fmtArr(((PDAnnotationTextMarkup) a).getQuadPoints());
            }
            if (a instanceof PDAnnotationPolygon) {
                return "V=" + fmtArr(((PDAnnotationPolygon) a).getVertices());
            }
            if (a instanceof PDAnnotationPolyline) {
                return "V=" + fmtArr(((PDAnnotationPolyline) a).getVertices());
            }
            if (a instanceof PDAnnotationInk) {
                float[][] paths = ((PDAnnotationInk) a).getInkList();
                if (paths == null) {
                    return "INK=null";
                }
                StringBuilder sb = new StringBuilder("INK=[");
                for (int i = 0; i < paths.length; i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append(fmtArr(paths[i]));
                }
                return sb.append(']').toString();
            }
            if (a instanceof PDAnnotationFreeText) {
                PDAnnotationFreeText ft = (PDAnnotationFreeText) a;
                return "CL=" + fmtArr(ft.getCallout()) + " RD="
                        + rdProj(ft);
            }
            return "n/a";
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String rdProj(PDAnnotationFreeText m) {
        try {
            PDRectangle r = m.getRectDifference();
            if (r == null) {
                return "null";
            }
            return fmt(r.getLowerLeftX()) + "," + fmt(r.getLowerLeftY()) + ","
                    + fmt(r.getWidth()) + "," + fmt(r.getHeight());
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String colorProj(PDAnnotation a) {
        COSBase c = a.getCOSObject()
                .getDictionaryObject(COSName.getPDFName("C"));
        if (c instanceof COSArray) {
            return "arr" + ((COSArray) c).size();
        }
        return "null";
    }

    static String caProj(PDAnnotation a) {
        COSBase ca = a.getCOSObject()
                .getDictionaryObject(COSName.getPDFName("CA"));
        if (ca instanceof COSNumber) {
            return fmt(((COSNumber) ca).floatValue());
        }
        return "null";
    }

    static void runCase(COSDictionary d, String name) {
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try {
            PDAnnotation a = PDAnnotation.createAnnotation(d);
            sb.append("class=").append(a.getClass().getSimpleName());
            sb.append(" rect=").append(rectProj(a));
            sb.append(" geom=").append(geomProj(a));
            sb.append(" color=").append(colorProj(a));
            sb.append(" ca=").append(caProj(a));
            sb.append(" flags=").append(a.getAnnotationFlags());
        } catch (Exception e) {
            sb.append("class=ERR:").append(e.getClass().getSimpleName());
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
