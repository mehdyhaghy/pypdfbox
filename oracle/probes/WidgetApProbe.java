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
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceEntry;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceStream;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe for the WIDGET + LINK annotation appearance &
 * appearance-state machinery — the facts the markup-annotation probes
 * (AnnotApAppearanceProbe = wave 1429 form-XObject container shape;
 * AnnotAppearGenProbe / AnnotAppear2Probe = generated content-stream operator
 * sequences) did NOT capture:
 *
 *   * widget /AS appearance-state value;
 *   * the /AP /N sub-dictionary STATE KEYS (single-stream vs state-keyed
 *     PDAppearanceEntry — isSubDictionary);
 *   * /MK appearance characteristics: /BG background, /BC border colour
 *     (canonical float components), /CA caption, /R rotation;
 *   * the /D (down) appearance presence + its sub-dictionary state keys;
 *   * the on-state appearance-stream /BBox;
 *   * link: /H highlight mode, /BS border style + width, /A action subtype.
 *
 * READ-ONLY probe: the fixture is built once by pypdfbox and saved, then read
 * by BOTH implementations so the build itself is part of the differential
 * surface. Per annotation (in page /Annots order) emit canonical lines:
 *
 *   ANNOT <subtype>
 *   --- widget ---
 *   AS <state-name|none>
 *   NKIND <stream|subdict|none>
 *   NKEYS <sorted space-joined state keys|->          (subdict only)
 *   DKIND <stream|subdict|none>
 *   DKEYS <sorted space-joined state keys|->          (subdict only)
 *   MKBG <space-joined canon floats|none>
 *   MKBC <space-joined canon floats|none>
 *   MKCA <caption|none>
 *   MKR <int>
 *   ONBBOX <x0>,<y0>,<x1>,<y1>|none                   (the /AS-selected stream)
 *   --- link ---
 *   H <highlight-mode>
 *   BSSTYLE <style-name>
 *   BSWIDTH <canon float>
 *   ASUBTYPE <action /S name|none>
 *   END
 */
public final class WidgetApProbe {
    public static void main(String[] args) throws Exception {
        File file = new File(args[1]);
        // arg[0] is always "read"; the fixture is built by pypdfbox.
        read(file);
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

    private static void emit(StringBuilder sb, PDAnnotation annot) {
        String subtype = annot.getSubtype();
        sb.append("ANNOT ").append(subtype == null ? "?" : subtype).append('\n');
        if (annot instanceof PDAnnotationWidget) {
            emitWidget(sb, (PDAnnotationWidget) annot);
        } else if (annot instanceof PDAnnotationLink) {
            emitLink(sb, (PDAnnotationLink) annot);
        }
        sb.append("END\n");
    }

    private static void emitWidget(StringBuilder sb, PDAnnotationWidget w) {
        COSName asName = w.getAppearanceState();
        sb.append("AS ").append(asName == null ? "none" : asName.getName()).append('\n');

        PDAppearanceDictionary ap = w.getAppearance();
        PDAppearanceEntry normal = ap == null ? null : ap.getNormalAppearance();
        PDAppearanceEntry down = ap == null ? null : ap.getDownAppearance();

        sb.append("NKIND ").append(kind(normal)).append('\n');
        sb.append("NKEYS ").append(subKeys(normal)).append('\n');
        // DPRESENT: explicit /AP /D key (no /N fallback) — the "down dropped"
        // signal. DKIND/DKEYS use getDownAppearance() which falls back to /N
        // per spec, so they describe the RESOLVED entry.
        COSBase apBase = w.getCOSObject().getDictionaryObject(COSName.AP);
        boolean dPresent = apBase instanceof COSDictionary
                && ((COSDictionary) apBase).containsKey(COSName.D);
        sb.append("DPRESENT ").append(dPresent ? "1" : "0").append('\n');
        sb.append("DKIND ").append(kind(down)).append('\n');
        sb.append("DKEYS ").append(subKeys(down)).append('\n');

        PDAppearanceCharacteristicsDictionary mk = w.getAppearanceCharacteristics();
        sb.append("MKBG ").append(mk == null ? "none" : colorArray(mk.getBackground())).append('\n');
        sb.append("MKBC ").append(mk == null ? "none" : colorArray(mk.getBorderColour())).append('\n');
        sb.append("MKCA ").append(mk == null || mk.getNormalCaption() == null
                ? "none" : mk.getNormalCaption()).append('\n');
        sb.append("MKR ").append(mk == null ? 0 : mk.getRotation()).append('\n');

        // BBox of the /AS-selected on-state stream.
        sb.append("ONBBOX ").append(onBBox(w, normal)).append('\n');
    }

    private static void emitLink(StringBuilder sb, PDAnnotationLink link) {
        sb.append("H ").append(link.getHighlightMode()).append('\n');
        PDBorderStyleDictionary bs = link.getBorderStyle();
        if (bs == null) {
            sb.append("BSSTYLE none\n");
            sb.append("BSWIDTH none\n");
        } else {
            sb.append("BSSTYLE ").append(bs.getStyle()).append('\n');
            sb.append("BSWIDTH ").append(canonFloat(bs.getWidth())).append('\n');
        }
        COSBase action = link.getCOSObject().getDictionaryObject(COSName.A);
        if (action instanceof COSDictionary) {
            COSBase s = ((COSDictionary) action).getDictionaryObject(COSName.S);
            sb.append("ASUBTYPE ").append(s instanceof COSName
                    ? ((COSName) s).getName() : "none").append('\n');
        } else {
            sb.append("ASUBTYPE none\n");
        }
    }

    private static String kind(PDAppearanceEntry entry) {
        if (entry == null) {
            return "none";
        }
        return entry.isSubDictionary() ? "subdict" : "stream";
    }

    private static String subKeys(PDAppearanceEntry entry) {
        if (entry == null || !entry.isSubDictionary()) {
            return "-";
        }
        List<String> keys = new ArrayList<>();
        for (COSName k : entry.getSubDictionary().keySet()) {
            keys.add(k.getName());
        }
        Collections.sort(keys);
        return keys.isEmpty() ? "-" : String.join(" ", keys);
    }

    private static String onBBox(PDAnnotationWidget w, PDAppearanceEntry normal) {
        if (normal == null) {
            return "none";
        }
        PDAppearanceStream stream;
        if (normal.isSubDictionary()) {
            COSName state = w.getAppearanceState();
            if (state == null) {
                return "none";
            }
            stream = normal.getSubDictionary().get(state);
        } else {
            stream = normal.getAppearanceStream();
        }
        if (stream == null) {
            return "none";
        }
        PDRectangle bbox = stream.getBBox();
        if (bbox == null) {
            return "none";
        }
        return canonFloat(bbox.getLowerLeftX()) + ","
                + canonFloat(bbox.getLowerLeftY()) + ","
                + canonFloat(bbox.getUpperRightX()) + ","
                + canonFloat(bbox.getUpperRightY());
    }

    /** Space-joined canonical-float components of a /BC or /BG colour array. */
    private static String colorArray(org.apache.pdfbox.pdmodel.graphics.color.PDColor color) {
        if (color == null) {
            return "none";
        }
        COSArray arr = color.toCOSArray();
        List<String> comps = new ArrayList<>();
        for (int i = 0; i < arr.size(); i++) {
            COSBase b = arr.getObject(i);
            if (b instanceof COSNumber) {
                comps.add(canonFloat(((COSNumber) b).floatValue()));
            }
        }
        return comps.isEmpty() ? "none" : String.join(" ", comps);
    }

    /** Locale-independent canonical float: half-even to 3 decimals, strip zeros. */
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
}
