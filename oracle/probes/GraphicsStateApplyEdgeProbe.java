import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState;

/**
 * Edge-case probe for PDExtendedGraphicsState.copyIntoGraphicsState. Each mode
 * pre-populates a PDGraphicsState with a NON-default dash pattern / transfer /
 * line width, then applies an ExtGState carrying a present-but-malformed entry,
 * and prints whether the pre-existing value was overwritten (with null) or left
 * intact.
 *
 * modes:
 *   malformed_d  -> ExtGState has /D present but malformed (size 1). Upstream
 *                   getLineDashPattern() returns null; does
 *                   setLineDashPattern(null) overwrite the seeded pattern?
 *   tr_tr2       -> ExtGState has both /TR and /TR2 (4-arrays of distinct
 *                   COSName markers). TR2 must win; print which transfer landed.
 *   tr_malformed -> ExtGState has /TR present but a 3-array (size != 4) so
 *                   getTransfer() returns null; does setTransfer(null) overwrite
 *                   the seeded transfer?
 *   wrong_lw     -> ExtGState has /LW present as a COSName (not a number) so
 *                   getLineWidth() returns null; defaultIfNull pushes 1.
 */
public final class GraphicsStateApplyEdgeProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];

        if ("malformed_d".equals(mode)) {
            PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
            float[] seed = {7.0f, 7.0f};
            gs.setLineDashPattern(new PDLineDashPattern(toArr(seed), 9));
            COSDictionary d = base();
            COSArray malformed = new COSArray();
            malformed.add(COSInteger.get(1)); // size 1, not 2
            d.setItem(COSName.getPDFName("D"), malformed);
            new PDExtendedGraphicsState(d).copyIntoGraphicsState(gs);
            out.println("dash=" + dash(gs.getLineDashPattern()));
        } else if ("tr_tr2".equals(mode)) {
            PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
            COSDictionary d = base();
            d.setItem(COSName.getPDFName("TR"), arr4("TRmark"));
            d.setItem(COSName.getPDFName("TR2"), arr4("TR2mark"));
            new PDExtendedGraphicsState(d).copyIntoGraphicsState(gs);
            out.println("transfer=" + marker(gs.getTransfer()));
        } else if ("tr_malformed".equals(mode)) {
            PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
            gs.setTransfer(COSName.getPDFName("seeded"));
            COSDictionary d = base();
            COSArray three = new COSArray();
            three.add(COSName.getPDFName("a"));
            three.add(COSName.getPDFName("b"));
            three.add(COSName.getPDFName("c"));
            d.setItem(COSName.getPDFName("TR"), three);
            new PDExtendedGraphicsState(d).copyIntoGraphicsState(gs);
            out.println("transfer=" + marker(gs.getTransfer()));
        } else if ("wrong_lw".equals(mode)) {
            PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
            gs.setLineWidth(42);
            COSDictionary d = base();
            d.setItem(COSName.getPDFName("LW"), COSName.getPDFName("notanumber"));
            new PDExtendedGraphicsState(d).copyIntoGraphicsState(gs);
            out.println("lineWidth=" + fmt(gs.getLineWidth()));
        } else if ("wrong_opm".equals(mode)) {
            // /OPM present but malformed (a COSName, not a number) -> getter
            // returns null; upstream pushes (overprintMode != null ? om : 0)
            // i.e. the spec default 0, overwriting a seeded non-zero value.
            PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
            gs.setOverprintMode(7);
            COSDictionary d = base();
            d.setItem(COSName.getPDFName("OPM"), COSName.getPDFName("notanumber"));
            new PDExtendedGraphicsState(d).copyIntoGraphicsState(gs);
            out.println("overprintMode=" + gs.getOverprintMode());
        } else if ("wrong_ri".equals(mode)) {
            // /RI present but malformed (a COSInteger, not a name/string) ->
            // getRenderingIntent() returns null; upstream setRenderingIntent(null)
            // overwrites a seeded intent.
            PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
            gs.setRenderingIntent(
                    org.apache.pdfbox.pdmodel.graphics.state.RenderingIntent.SATURATION);
            COSDictionary d = base();
            d.setItem(COSName.getPDFName("RI"), COSInteger.get(5));
            new PDExtendedGraphicsState(d).copyIntoGraphicsState(gs);
            out.println("renderingIntent="
                    + (gs.getRenderingIntent() == null ? "null"
                            : gs.getRenderingIntent().toString()));
        }
    }

    private static COSDictionary base() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        return d;
    }

    private static COSArray toArr(float[] f) {
        COSArray a = new COSArray();
        for (float v : f) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    private static COSArray arr4(String mark) {
        COSArray a = new COSArray();
        a.add(COSName.getPDFName(mark));
        a.add(COSName.getPDFName(mark));
        a.add(COSName.getPDFName(mark));
        a.add(COSName.getPDFName(mark));
        return a;
    }

    private static String marker(COSBase base) {
        if (base == null) {
            return "null";
        }
        if (base instanceof COSName) {
            return "name:" + ((COSName) base).getName();
        }
        if (base instanceof COSArray && ((COSArray) base).size() > 0) {
            COSBase first = ((COSArray) base).getObject(0);
            if (first instanceof COSName) {
                return "arr:" + ((COSName) first).getName();
            }
        }
        return base.toString();
    }

    private static String dash(PDLineDashPattern p) {
        if (p == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder("[");
        float[] arr = p.getDashArray();
        for (int i = 0; i < arr.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(fmt(arr[i]));
        }
        sb.append("] phase=").append(p.getPhase());
        return sb.toString();
    }

    private static String fmt(double v) {
        if (v == Math.rint(v) && !Double.isInfinite(v)) {
            return Long.toString((long) v);
        }
        String s = String.format(Locale.ROOT, "%.6f", v);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') {
            end--;
        }
        if (end > 0 && s.charAt(end - 1) == '.') {
            end--;
        }
        return s.substring(0, end);
    }
}
