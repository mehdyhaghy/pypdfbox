import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.graphics.blend.BlendMode;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.RenderingIntent;

/**
 * Live oracle probe: drive Apache PDFBox's
 * {@code PDExtendedGraphicsState.copyIntoGraphicsState(PDGraphicsState)} —
 * the merge performed by the {@code gs} content-stream operator — and emit
 * the resulting {@link PDGraphicsState} field values as JSON-ish key=value
 * lines.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GraphicsStateApplyProbe <full|empty>
 *
 *   full  -> an /ExtGState carrying every mergeable parameter
 *            (LW/LC/LJ/ML/D/RI/OP/op/OPM/FL/SM/SA/CA/ca/AIS/TK/BM)
 *            applied onto a default graphics state.
 *   empty -> only /Type, so copyIntoGraphicsState touches nothing and the
 *            graphics state keeps its constructor defaults.
 *
 * Output (UTF-8, to stdout): one "key=value" line per accessor, in a fixed
 * order. Floats render canonically; the blend mode prints its COSName; the
 * rendering intent prints its stringValue() or "null"; the text knockout
 * flag is read off the merged PDTextState.
 */
public final class GraphicsStateApplyProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        COSDictionary dict = "full".equals(mode) ? buildFull() : buildEmpty();
        PDExtendedGraphicsState egs = new PDExtendedGraphicsState(dict);

        PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
        egs.copyIntoGraphicsState(gs);

        out.println("lineWidth=" + fmt(gs.getLineWidth()));
        out.println("lineCap=" + gs.getLineCap());
        out.println("lineJoin=" + gs.getLineJoin());
        out.println("miterLimit=" + fmt(gs.getMiterLimit()));
        out.println("lineDashPattern=" + dash(gs.getLineDashPattern()));
        out.println("renderingIntent=" + ri(gs.getRenderingIntent()));
        out.println("overprint=" + gs.isOverprint());
        out.println("nonStrokingOverprint=" + gs.isNonStrokingOverprint());
        out.println("overprintMode=" + gs.getOverprintMode());
        out.println("flatness=" + fmt(gs.getFlatness()));
        out.println("smoothness=" + fmt(gs.getSmoothness()));
        out.println("strokeAdjustment=" + gs.isStrokeAdjustment());
        out.println("alphaConstant=" + fmt(gs.getAlphaConstant()));
        out.println("nonStrokeAlphaConstant=" + fmt(gs.getNonStrokeAlphaConstant()));
        out.println("alphaSource=" + gs.isAlphaSource());
        out.println("textKnockout=" + gs.getTextState().getKnockoutFlag());
        out.println("blendMode=" + blend(gs.getBlendMode()));
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
        d.setItem(COSName.getPDFName("RI"), COSName.getPDFName("Perceptual"));
        d.setItem(COSName.getPDFName("OP"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("op"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("OPM"), COSInteger.get(1));
        d.setItem(COSName.getPDFName("FL"), new COSFloat(0.5f));
        d.setItem(COSName.getPDFName("SM"), new COSFloat(0.125f));
        d.setItem(COSName.getPDFName("SA"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("CA"), new COSFloat(0.5f));
        d.setItem(COSName.getPDFName("ca"), new COSFloat(0.25f));
        d.setItem(COSName.getPDFName("AIS"), COSBoolean.TRUE);
        d.setItem(COSName.getPDFName("TK"), COSBoolean.FALSE);
        d.setItem(COSName.getPDFName("BM"), COSName.getPDFName("Multiply"));
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
        return b == null ? "null" : b.getCOSName().getName();
    }

    private static String ri(RenderingIntent r) {
        return r == null ? "null" : r.stringValue();
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
