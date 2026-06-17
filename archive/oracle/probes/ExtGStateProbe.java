import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.graphics.blend.BlendMode;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.RenderingIntent;

/**
 * Live oracle probe: emit Apache PDFBox's PDExtendedGraphicsState parameter
 * accessor values for one of two in-memory /ExtGState dictionaries.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ExtGStateProbe <full|empty>
 *
 *   full  -> a dictionary with every parameter set to a known value
 *            (line width/cap/join/miter, dash, CA/ca, BM, RI, AIS, TK,
 *             OP/op/OPM, FL/SM/SA, Font[name,size]).
 *   empty -> a near-empty dictionary (only /Type) so every accessor returns
 *            its spec default / absent value.
 *
 * Output (UTF-8, to stdout): one "key=value" line per accessor, in a fixed
 * order. Floats are rendered canonically (see fmt); absent boxed values
 * print "null"; the blend mode prints its COSName ("Normal"/"Multiply"/...);
 * the rendering intent prints its stringValue() or "null".
 */
public final class ExtGStateProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        COSDictionary dict = "full".equals(mode) ? buildFull() : buildEmpty();
        PDExtendedGraphicsState gs = new PDExtendedGraphicsState(dict);

        out.println("lineWidth=" + fmtBoxed(gs.getLineWidth()));
        out.println("lineCapStyle=" + gs.getLineCapStyle());
        out.println("lineJoinStyle=" + gs.getLineJoinStyle());
        out.println("miterLimit=" + fmtBoxed(gs.getMiterLimit()));
        out.println("lineDashPattern=" + dash(gs.getLineDashPattern()));
        out.println("strokingAlphaConstant=" + fmtBoxed(gs.getStrokingAlphaConstant()));
        out.println("nonStrokingAlphaConstant=" + fmtBoxed(gs.getNonStrokingAlphaConstant()));
        out.println("blendMode=" + blend(gs.getBlendMode()));
        out.println("renderingIntent=" + ri(gs.getRenderingIntent()));
        out.println("alphaSourceFlag=" + gs.getAlphaSourceFlag());
        out.println("textKnockoutFlag=" + gs.getTextKnockoutFlag());
        out.println("strokingOverprintControl=" + gs.getStrokingOverprintControl());
        out.println("nonStrokingOverprintControl=" + gs.getNonStrokingOverprintControl());
        out.println("overprintMode=" + boxedInt(gs.getOverprintMode()));
        out.println("flatnessTolerance=" + fmtBoxed(gs.getFlatnessTolerance()));
        out.println("smoothnessTolerance=" + fmtBoxed(gs.getSmoothnessTolerance()));
        out.println("automaticStrokeAdjustment=" + gs.getAutomaticStrokeAdjustment());
    }

    private static COSDictionary buildEmpty() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        return d;
    }

    private static COSDictionary buildFull() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        d.setItem(COSName.getPDFName("LW"), new COSFloat(2.5f));
        d.setItem(COSName.getPDFName("LC"), COSInteger.get(1));
        d.setItem(COSName.getPDFName("LJ"), COSInteger.get(2));
        d.setItem(COSName.getPDFName("ML"), new COSFloat(4.0f));
        COSArray dash = new COSArray();
        COSArray dashArr = new COSArray();
        dashArr.add(new COSFloat(3.0f));
        dashArr.add(new COSFloat(2.0f));
        dash.add(dashArr);
        dash.add(COSInteger.get(1));
        d.setItem(COSName.getPDFName("D"), dash);
        d.setItem(COSName.getPDFName("CA"), new COSFloat(0.5f));
        d.setItem(COSName.getPDFName("ca"), new COSFloat(0.25f));
        d.setItem(COSName.getPDFName("BM"), COSName.getPDFName("Multiply"));
        d.setItem(COSName.getPDFName("RI"), COSName.getPDFName("Perceptual"));
        d.setItem(COSName.getPDFName("AIS"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("TK"), COSBoolean.FALSE);
        d.setItem(COSName.getPDFName("OP"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("op"), COSBoolean.FALSE);
        d.setItem(COSName.getPDFName("OPM"), COSInteger.get(1));
        d.setItem(COSName.getPDFName("FL"), new COSFloat(0.5f));
        d.setItem(COSName.getPDFName("SM"), new COSFloat(0.125f));
        d.setItem(COSName.getPDFName("SA"), COSBoolean.TRUE);
        COSArray font = new COSArray();
        font.add(COSName.getPDFName("F1"));
        font.add(new COSFloat(12.0f));
        d.setItem(COSName.getPDFName("Font"), font);
        return d;
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

    private static String blend(BlendMode b) {
        if (b == null) {
            return "null";
        }
        return b.getCOSName().getName();
    }

    private static String ri(RenderingIntent r) {
        return r == null ? "null" : r.stringValue();
    }

    private static String boxedInt(Integer i) {
        return i == null ? "null" : Integer.toString(i);
    }

    private static String fmtBoxed(Float v) {
        return v == null ? "null" : fmt(v);
    }

    /**
     * Canonical float rendering: integral values without a trailing ".0",
     * non-integral values with up to 6 decimals, trailing zeros stripped.
     */
    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
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
