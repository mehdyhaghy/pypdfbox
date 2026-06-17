import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationHighlight;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;

/**
 * Live oracle probe for the HIGHLIGHT text-markup annotation's blend-mode +
 * alpha graphics state — the multiply-blend that makes a highlight visually
 * multiply over the underlying text (PDF 32000-1 §11.3.5, §11.6.4.4).
 *
 * Existing wave-1442/1455 coverage (TextMarkupProbe) fingerprints the highlight
 * /AP /N operator KEYWORD sequence and asserts two `gs` operators are present,
 * but never inspects what those two ExtGStates ACTUALLY contain. A highlight
 * whose ExtGState carried /BM /Normal (or no blend mode), or the wrong alpha
 * constant, would pass the operator-sequence test yet render wrong — it would
 * paint an opaque solid block over the text instead of a translucent multiply
 * wash. This probe closes that gap by resolving each `gs` operand to its
 * ExtGState resource and emitting its /BM, /CA, /ca and /AIS values.
 *
 * Two modes:
 *
 *   java ... HighlightBlendProbe write out.pdf
 *       Build a page with three highlights: a default-opacity yellow highlight,
 *       a /CA 0.5 half-opacity highlight, and a /CA 1 cyan highlight; call
 *       constructAppearances(doc) on each and save. PDFBox-AUTHORED reference.
 *
 *   java ... HighlightBlendProbe read out.pdf
 *       Re-open ANY highlight PDF and emit, per annotation in /Annots order:
 *
 *         ANNOT <subtype>
 *         CA <canonical float>                  (the /CA constant opacity, or "none")
 *         GS <ref-name> BM=<blend> CA=<f|none> ca=<f|none> AIS=<true|false|none>
 *             ... one GS line per ExtGState referenced by a `gs` operator ...
 *         END
 *
 *   The /BM blend mode and the /CA /ca alpha constants are the load-bearing
 *   values; they are emitted as canonical floats / names and compared exactly.
 *   This is independent of whether the fill lives inline or in a form XObject —
 *   we resolve the ExtGState resources reachable from the /AP /N stream's `gs`
 *   operators and (recursively) from any form XObject it `Do`-invokes.
 */
public final class HighlightBlendProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        File file = new File(args[1]);
        if ("write".equals(mode)) {
            write(file);
        } else {
            read(file);
        }
    }

    private static PDColor rgb(float r, float g, float b) {
        return new PDColor(new float[] {r, g, b}, PDDeviceRGB.INSTANCE);
    }

    private static void write(File file) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page);

            PDAnnotationHighlight h1 = new PDAnnotationHighlight();
            h1.setRectangle(new PDRectangle(50, 295, 200, 25));
            h1.setQuadPoints(new float[] {50, 315, 250, 315, 50, 300, 250, 300});
            h1.setColor(rgb(1, 1, 0));
            h1.constructAppearances(doc);
            page.getAnnotations().add(h1);

            PDAnnotationHighlight h2 = new PDAnnotationHighlight();
            h2.setRectangle(new PDRectangle(50, 245, 200, 25));
            h2.setQuadPoints(new float[] {50, 265, 250, 265, 50, 250, 250, 250});
            h2.setColor(rgb(1, 0, 0));
            h2.setConstantOpacity(0.5f);
            h2.constructAppearances(doc);
            page.getAnnotations().add(h2);

            PDAnnotationHighlight h3 = new PDAnnotationHighlight();
            h3.setRectangle(new PDRectangle(50, 195, 200, 25));
            h3.setQuadPoints(new float[] {50, 215, 250, 215, 50, 200, 250, 200});
            h3.setColor(rgb(0, 1, 1));
            h3.setConstantOpacity(1f);
            h3.constructAppearances(doc);
            page.getAnnotations().add(h3);

            doc.save(file);
        }
    }

    private static void read(File file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        try (PDDocument doc = Loader.loadPDF(file)) {
            for (PDPage page : doc.getPages()) {
                for (PDAnnotation annot : page.getAnnotations()) {
                    emit(sb, annot);
                }
            }
        }
        out.print(sb);
    }

    private static void emit(StringBuilder sb, PDAnnotation annot) throws Exception {
        String subtype = annot.getSubtype();
        sb.append("ANNOT ").append(subtype == null ? "?" : subtype).append('\n');

        COSBase ca = annot.getCOSObject().getDictionaryObject(COSName.CA);
        if (ca instanceof COSNumber) {
            sb.append("CA ").append(canonFloat(((COSNumber) ca).floatValue())).append('\n');
        } else {
            sb.append("CA none\n");
        }

        PDAppearanceStream stream = normalStream(annot);
        if (stream != null) {
            collectGraphicsStates(sb, stream.getResources(), stream, 0);
        }
        sb.append("END\n");
    }

    /**
     * Walk a content stream's tokens; for every `gs` operator resolve its
     * operand name to an ExtGState in the supplied resources and emit a GS
     * line. Recurse into form XObjects invoked by `Do` so that PDFBox's
     * transparency-group form (which carries the Multiply ExtGState) and
     * pypdfbox's inline-ExtGState emission both surface the same blend facts.
     */
    private static void collectGraphicsStates(
            StringBuilder sb, PDResources resources, Object streamSource, int depth)
            throws Exception {
        if (resources == null || depth > 4) {
            return;
        }
        PDFStreamParser parser;
        if (streamSource instanceof PDAppearanceStream) {
            parser = new PDFStreamParser((PDAppearanceStream) streamSource);
        } else {
            parser = new PDFStreamParser(
                    (org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject) streamSource);
        }
        List<Object> tokens = parser.parse();
        List<COSBase> operands = new ArrayList<>();
        for (Object tok : tokens) {
            if (tok instanceof COSBase) {
                operands.add((COSBase) tok);
            } else if (tok instanceof Operator) {
                String name = ((Operator) tok).getName();
                if ("gs".equals(name) && !operands.isEmpty()
                        && operands.get(operands.size() - 1) instanceof COSName) {
                    COSName gsName = (COSName) operands.get(operands.size() - 1);
                    PDExtendedGraphicsState gs = resources.getExtGState(gsName);
                    emitGs(sb, gsName.getName(), gs);
                } else if ("Do".equals(name) && !operands.isEmpty()
                        && operands.get(operands.size() - 1) instanceof COSName) {
                    COSName xName = (COSName) operands.get(operands.size() - 1);
                    org.apache.pdfbox.pdmodel.graphics.PDXObject xobj =
                            resources.getXObject(xName);
                    if (xobj instanceof org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject) {
                        org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject form =
                                (org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject) xobj;
                        collectGraphicsStates(sb, form.getResources(), form, depth + 1);
                    }
                }
                operands.clear();
            }
        }
    }

    private static void emitGs(StringBuilder sb, String name, PDExtendedGraphicsState gs) {
        sb.append("GS ").append(name);
        if (gs == null) {
            sb.append(" BM=none CA=none ca=none AIS=none\n");
            return;
        }
        COSDictionary d = gs.getCOSObject();
        sb.append(" BM=").append(blendName(d.getDictionaryObject(COSName.BM)));
        sb.append(" CA=").append(numOrNone(d.getDictionaryObject(COSName.CA)));
        sb.append(" ca=").append(numOrNone(d.getDictionaryObject(COSName.getPDFName("ca"))));
        COSBase ais = d.getDictionaryObject(COSName.getPDFName("AIS"));
        if (ais instanceof COSBoolean) {
            sb.append(" AIS=").append(((COSBoolean) ais).getValue());
        } else {
            sb.append(" AIS=none");
        }
        sb.append('\n');
    }

    private static String blendName(COSBase bm) {
        if (bm instanceof COSName) {
            return ((COSName) bm).getName();
        }
        if (bm instanceof org.apache.pdfbox.cos.COSArray) {
            org.apache.pdfbox.cos.COSArray arr = (org.apache.pdfbox.cos.COSArray) bm;
            if (arr.size() > 0 && arr.getObject(0) instanceof COSName) {
                return ((COSName) arr.getObject(0)).getName();
            }
        }
        return "none";
    }

    private static String numOrNone(COSBase b) {
        if (b instanceof COSNumber) {
            return canonFloat(((COSNumber) b).floatValue());
        }
        return "none";
    }

    static String canonFloat(float f) {
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(3, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
            s = "0";
        }
        return s;
    }

    private static PDAppearanceStream normalStream(PDAnnotation annot) {
        PDAppearanceDictionary ap = annot.getAppearance();
        if (ap == null) {
            return null;
        }
        PDAppearanceEntry normal = ap.getNormalAppearance();
        if (normal == null || normal.isSubDictionary()) {
            return null;
        }
        return normal.getAppearanceStream();
    }
}
