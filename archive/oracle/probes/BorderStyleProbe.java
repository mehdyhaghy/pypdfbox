import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationSquareCircle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderEffectDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe: emit a CANONICAL, deterministic listing of every
 * annotation's BORDER STYLING surface as Apache PDFBox parses it:
 *
 *   - /BS border style dictionary: getWidth() / getStyle() / getDashStyle()
 *     dash array (the typed PDBorderStyleDictionary accessors, read off the
 *     annotation COS dict so the probe is uniform across every subtype).
 *   - legacy /Border array [hradius vradius width [dash]] read raw off the
 *     COS dictionary, INCLUDING the absent-array default which Adobe / PDFBox
 *     synthesise differently from the typed wrapper. This probe emits the raw
 *     array verbatim (or "none" when absent) so pypdfbox's get_border() default
 *     synthesis can be checked against the spec/Adobe default.
 *   - /BE border effect dictionary: getStyle() / getIntensity() via the typed
 *     PDBorderEffectDictionary (square/circle subtypes), with absent -> "none".
 *   - /RD rectangle differences: getRectDifferences() float[] (square/circle),
 *     with absent -> empty.
 *
 * read <pdf> — load and print one block per annotation, blocks sorted by a
 * canonical key so order is independent of /Annots array order.
 *
 * Output (UTF-8, LF-terminated). One block per annotation:
 *
 *   ANNOT <subtype>
 *   KEY <sortkey>
 *   BS none                                          (when /BS absent)
 *   BS w=<canonFloat> s=<style> dash=<a,b,..|none>   (when present)
 *   BORDER none                                      (when /Border absent)
 *   BORDER <v0>,<v1>,<v2>[,dash:<d0>,..]             (when present, raw)
 *   BE none                                          (when /BE absent)
 *   BE s=<style> i=<canonFloat>                      (when present)
 *   RD none                                          (when /RD absent)
 *   RD <v0>,<v1>,<v2>,<v3>                           (when present)
 *   END
 */
public final class BorderStyleProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length >= 2 && "read".equals(args[0])) {
            read(out, args[1]);
            return;
        }
        read(out, args[0]);
    }

    private static void read(PrintStream out, String path) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(path))) {
            StringBuilder sb = new StringBuilder();
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                List<String> blocks = new ArrayList<>();
                for (PDAnnotation annot : page.getAnnotations()) {
                    blocks.add(block(pageIndex, annot));
                }
                Collections.sort(blocks);
                for (String b : blocks) {
                    sb.append(b);
                }
                pageIndex++;
            }
            out.print(sb);
        }
    }

    private static String block(int pageIndex, PDAnnotation annot) {
        String subtype = annot.getSubtype();
        if (subtype == null) {
            subtype = "?";
        }
        String key = "p" + pageIndex + " " + subtype + " " + rect(annot);

        StringBuilder b = new StringBuilder();
        b.append("ANNOT ").append(subtype).append('\n');
        b.append("KEY ").append(key).append('\n');
        b.append(bsLine(annot)).append('\n');
        b.append(borderLine(annot)).append('\n');
        b.append(beLine(annot)).append('\n');
        b.append(rdLine(annot)).append('\n');
        b.append("END\n");
        return b.toString();
    }

    private static String rect(PDAnnotation annot) {
        PDRectangle r = annot.getRectangle();
        if (r == null) {
            return "none";
        }
        return canonFloat(r.getLowerLeftX()) + "," + canonFloat(r.getLowerLeftY())
                + "," + canonFloat(r.getUpperRightX()) + ","
                + canonFloat(r.getUpperRightY());
    }

    private static String bsLine(PDAnnotation annot) {
        COSDictionary bsDict = annot.getCOSObject().getCOSDictionary(COSName.BS);
        if (bsDict == null) {
            return "BS none";
        }
        PDBorderStyleDictionary bs = new PDBorderStyleDictionary(bsDict);
        StringBuilder sb = new StringBuilder();
        sb.append("BS w=").append(canonFloat(bs.getWidth()));
        sb.append(" s=").append(bs.getStyle());
        PDLineDashPattern dash = bs.getDashStyle();
        if (dash == null) {
            sb.append(" dash=none");
        } else {
            float[] arr = dash.getDashArray();
            if (arr == null || arr.length == 0) {
                sb.append(" dash=none");
            } else {
                sb.append(" dash=");
                for (int i = 0; i < arr.length; i++) {
                    if (i > 0) {
                        sb.append(',');
                    }
                    sb.append(canonFloat(arr[i]));
                }
            }
        }
        return sb.toString();
    }

    /**
     * Legacy /Border read raw off the COS dict. PDFBox does NOT synthesise a
     * default for the bare /Border array on PDAnnotation (only the typed
     * wrappers do), so the probe emits the raw array verbatim. pypdfbox's
     * get_border() default-synthesis ([0 0 1] when absent) is checked
     * separately by the test against this raw view.
     */
    private static String borderLine(PDAnnotation annot) {
        COSBase base = annot.getCOSObject().getDictionaryObject(COSName.BORDER);
        if (!(base instanceof COSArray)) {
            return "BORDER none";
        }
        COSArray arr = (COSArray) base;
        StringBuilder sb = new StringBuilder("BORDER ");
        for (int i = 0; i < arr.size(); i++) {
            COSBase e = arr.getObject(i);
            if (i > 0) {
                sb.append(',');
            }
            if (e instanceof COSArray) {
                COSArray d = (COSArray) e;
                sb.append("dash:");
                for (int j = 0; j < d.size(); j++) {
                    if (j > 0) {
                        sb.append(';');
                    }
                    COSBase de = d.getObject(j);
                    sb.append(de instanceof COSNumber
                            ? canonFloat(((COSNumber) de).floatValue()) : "?");
                }
            } else if (e instanceof COSNumber) {
                sb.append(canonFloat(((COSNumber) e).floatValue()));
            } else {
                sb.append('?');
            }
        }
        return sb.toString();
    }

    private static String beLine(PDAnnotation annot) {
        COSDictionary beDict = annot.getCOSObject().getCOSDictionary(COSName.BE);
        if (beDict == null) {
            return "BE none";
        }
        PDBorderEffectDictionary be = new PDBorderEffectDictionary(beDict);
        return "BE s=" + be.getStyle() + " i=" + canonFloat(be.getIntensity());
    }

    private static String rdLine(PDAnnotation annot) {
        if (!(annot instanceof PDAnnotationSquareCircle)) {
            // /RD is a square/circle (and free-text/caret) accessor; for other
            // subtypes read it raw off the COS dict so the probe is uniform.
            COSBase base = annot.getCOSObject().getDictionaryObject(COSName.RD);
            if (!(base instanceof COSArray)) {
                return "RD none";
            }
            float[] arr = ((COSArray) base).toFloatArray();
            return "RD " + floats(arr);
        }
        PDAnnotationSquareCircle sc = (PDAnnotationSquareCircle) annot;
        float[] arr = sc.getRectDifferences();
        if (arr == null || arr.length == 0) {
            return "RD none";
        }
        return "RD " + floats(arr);
    }

    private static String floats(float[] arr) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < arr.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(canonFloat(arr[i]));
        }
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
