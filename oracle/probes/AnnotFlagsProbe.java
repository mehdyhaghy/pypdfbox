import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDBorderStyleDictionary;

/**
 * Live oracle probe: emit a CANONICAL, deterministic listing of every
 * annotation's COMMON properties as Apache PDFBox parses them — the /F flag
 * predicates, the /BS border style (width + style + dash array + phase) and
 * the /MK appearance characteristics (rotation + border/background colour
 * component counts + caption).
 *
 * Two modes:
 *
 *   read  input.pdf   — load a PDF and print one block per annotation.
 *   write out.pdf     — build a one-widget PDF whose annotation sets EVERY
 *                       /F flag bit, a /BS (width + dashed style + dash array)
 *                       and a /MK (rotation + 3-comp /BC + 4-comp /BG +
 *                       caption) so every flag/border/MK branch is exercised.
 *
 * Output (UTF-8, LF-terminated). One block per annotation, blocks sorted by a
 * canonical key so order is independent of /Annots array order:
 *
 *   ANNOT <subtype>
 *   KEY <sortkey>
 *   FLAGS inv=<0|1> hid=.. prt=.. nzm=.. nrt=.. nvw=.. ro=.. lck=.. tnv=.. lc=..
 *   BS none                                    (when /BS absent)
 *   BS w=<canonFloat> s=<style> dash=<a,b,..|none> phase=<int>   (when present)
 *   MK none                                    (when /MK absent)
 *   MK r=<int> bc=<count|-1> bg=<count|-1> ca=<caption|none>     (when present)
 *   END
 *
 * /BS and /MK are read directly off the annotation COS dictionary (so the
 * probe is uniform across every subtype, matching pypdfbox's per-subclass
 * surface), via the typed wrappers PDBorderStyleDictionary /
 * PDAppearanceCharacteristicsDictionary that pypdfbox mirrors.
 */
public final class AnnotFlagsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length >= 2 && "write".equals(args[0])) {
            write(args[1]);
            return;
        }
        if (args.length >= 2 && "read".equals(args[0])) {
            read(out, args[1]);
            return;
        }
        // Backwards-compatible: a single bare path argument means read.
        read(out, args[0]);
    }

    // ----------------------------------------------------------------- read

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
        // Canonical sort key: page, subtype, rounded rect, flag int. Sorting on
        // the rendered block string keeps order stable without /Annots order.
        String key = "p" + pageIndex + " " + subtype + " " + rect(annot)
                + " f" + annot.getAnnotationFlags();

        StringBuilder b = new StringBuilder();
        b.append("ANNOT ").append(subtype).append('\n');
        b.append("KEY ").append(key).append('\n');
        b.append("FLAGS")
                .append(" inv=").append(annot.isInvisible() ? 1 : 0)
                .append(" hid=").append(annot.isHidden() ? 1 : 0)
                .append(" prt=").append(annot.isPrinted() ? 1 : 0)
                .append(" nzm=").append(annot.isNoZoom() ? 1 : 0)
                .append(" nrt=").append(annot.isNoRotate() ? 1 : 0)
                .append(" nvw=").append(annot.isNoView() ? 1 : 0)
                .append(" ro=").append(annot.isReadOnly() ? 1 : 0)
                .append(" lck=").append(annot.isLocked() ? 1 : 0)
                .append(" tnv=").append(annot.isToggleNoView() ? 1 : 0)
                .append(" lc=").append(annot.isLockedContents() ? 1 : 0)
                .append('\n');
        b.append(borderLine(annot)).append('\n');
        b.append(mkLine(annot)).append('\n');
        b.append("END\n");
        return b.toString();
    }

    private static String rect(PDAnnotation annot) {
        PDRectangle r = annot.getRectangle();
        if (r == null) {
            return "none";
        }
        // Canonical floats (not Math.round) so the sort key never diverges
        // from Python on a half-rounding boundary (Math.round is half-up,
        // Python round() is banker's rounding).
        return canonFloat(r.getLowerLeftX()) + "," + canonFloat(r.getLowerLeftY())
                + "," + canonFloat(r.getUpperRightX()) + ","
                + canonFloat(r.getUpperRightY());
    }

    private static String borderLine(PDAnnotation annot) {
        COSDictionary bsDict = annot.getCOSObject()
                .getCOSDictionary(COSName.BS);
        if (bsDict == null) {
            return "BS none";
        }
        PDBorderStyleDictionary bs = new PDBorderStyleDictionary(bsDict);
        StringBuilder sb = new StringBuilder();
        sb.append("BS w=").append(canonFloat(bs.getWidth()));
        sb.append(" s=").append(bs.getStyle());
        PDLineDashPattern dash = bs.getDashStyle();
        if (dash == null) {
            sb.append(" dash=none phase=0");
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
            sb.append(" phase=").append(dash.getPhase());
        }
        return sb.toString();
    }

    private static String mkLine(PDAnnotation annot) {
        COSDictionary mkDict = annot.getCOSObject()
                .getCOSDictionary(COSName.MK);
        if (mkDict == null) {
            return "MK none";
        }
        PDAppearanceCharacteristicsDictionary mk =
                new PDAppearanceCharacteristicsDictionary(mkDict);
        int bc = mk.getBorderColour() != null
                ? mk.getBorderColour().getComponents().length : -1;
        int bg = mk.getBackground() != null
                ? mk.getBackground().getComponents().length : -1;
        String ca = mk.getNormalCaption();
        return "MK r=" + mk.getRotation() + " bc=" + bc + " bg=" + bg
                + " ca=" + (ca == null ? "none" : ca);
    }

    // --------------------------------------------------------------- write

    private static void write(String path) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(PDRectangle.LETTER);
            doc.addPage(page);

            COSDictionary annot = new COSDictionary();
            annot.setItem(COSName.TYPE, COSName.ANNOT);
            annot.setItem(COSName.SUBTYPE, COSName.WIDGET);

            COSArray rect = new COSArray();
            rect.add(new COSFloat(10));
            rect.add(new COSFloat(20));
            rect.add(new COSFloat(110));
            rect.add(new COSFloat(70));
            annot.setItem(COSName.RECT, rect);

            // Every /F bit set: bits 1..10 -> 0b1111111111 = 1023.
            annot.setInt(COSName.F, 1023);

            // /BS: width 3, dashed style, dash array [4 2] (no explicit phase
            // in the /D array form so phase defaults to 0).
            COSDictionary bs = new COSDictionary();
            bs.setItem(COSName.TYPE, COSName.getPDFName("Border"));
            bs.setInt(COSName.W, 3);
            bs.setItem(COSName.S, COSName.getPDFName("D"));
            COSArray dash = new COSArray();
            dash.add(COSInteger.get(4));
            dash.add(COSInteger.get(2));
            bs.setItem(COSName.D, dash);
            annot.setItem(COSName.BS, bs);

            // /MK: rotation 90, 3-comp /BC (RGB), 4-comp /BG (CMYK), caption.
            COSDictionary mk = new COSDictionary();
            mk.setInt(COSName.R, 90);
            COSArray bc = new COSArray();
            bc.add(new COSFloat(1));
            bc.add(new COSFloat(0));
            bc.add(new COSFloat(0));
            mk.setItem(COSName.BC, bc);
            COSArray bg = new COSArray();
            bg.add(new COSFloat(0));
            bg.add(new COSFloat(0));
            bg.add(new COSFloat(0));
            bg.add(new COSFloat(0.2f));
            mk.setItem(COSName.BG, bg);
            mk.setItem(COSName.CA, new COSString("Submit"));
            annot.setItem(COSName.MK, mk);

            COSArray annots = new COSArray();
            annots.add(annot);
            page.getCOSObject().setItem(COSName.ANNOTS, annots);

            doc.save(path);
        }
    }

    // ------------------------------------------------------------- helpers

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
