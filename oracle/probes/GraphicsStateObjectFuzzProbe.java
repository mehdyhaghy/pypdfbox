import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.graphics.blend.BlendMode;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.PDTextState;
import org.apache.pdfbox.pdmodel.graphics.state.RenderingIntent;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe for the {@link PDGraphicsState} object's OWN behaviour —
 * constructor field defaults, {@code clone()} deep/shallow independence, and
 * setter storage of edge values. Distinct from GraphicsStateApplyProbe (which
 * drives PDExtendedGraphicsState.copyIntoGraphicsState INTO a state).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GraphicsStateObjectFuzzProbe <mode>
 *
 *   defaults  -> every field value on a fresh PDGraphicsState(new PDRectangle()).
 *   clone     -> mutate a clone's CTM / textMatrix / textState / dash / colour /
 *                clipping list, then report whether the ORIGINAL changed (shared
 *                vs independent per upstream clone semantics).
 *   setters   -> store edge values (negative line width, alpha out of [0,1], NaN,
 *                infinity, huge ints) verbatim and read them back.
 *
 * Output (UTF-8): one "key=value" line per projection, fixed order.
 */
public final class GraphicsStateObjectFuzzProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("defaults".equals(mode)) {
            defaults(out);
        } else if ("clone".equals(mode)) {
            cloneIndependence(out);
        } else if ("setters".equals(mode)) {
            setters(out);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void defaults(PrintStream out) {
        PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
        out.println("lineWidth=" + fmt(gs.getLineWidth()));
        out.println("lineCap=" + gs.getLineCap());
        out.println("lineJoin=" + gs.getLineJoin());
        out.println("miterLimit=" + fmt(gs.getMiterLimit()));
        out.println("strokeAdjustment=" + gs.isStrokeAdjustment());
        out.println("alphaConstant=" + fmt(gs.getAlphaConstant()));
        out.println("nonStrokeAlphaConstant=" + fmt(gs.getNonStrokeAlphaConstant()));
        out.println("alphaSource=" + gs.isAlphaSource());
        out.println("overprint=" + gs.isOverprint());
        out.println("nonStrokingOverprint=" + gs.isNonStrokingOverprint());
        out.println("overprintMode=" + gs.getOverprintMode());
        out.println("flatness=" + fmt(gs.getFlatness()));
        out.println("smoothness=" + fmt(gs.getSmoothness()));
        out.println("blendMode=" + blend(gs.getBlendMode()));
        out.println("renderingIntent=" + ri(gs.getRenderingIntent()));
        out.println("softMask=" + (gs.getSoftMask() == null ? "null" : "set"));
        out.println("transfer=" + (gs.getTransfer() == null ? "null" : "set"));
        out.println("textMatrix=" + (gs.getTextMatrix() == null ? "null" : matrix(gs.getTextMatrix())));
        out.println("textLineMatrix=" + (gs.getTextLineMatrix() == null ? "null" : matrix(gs.getTextLineMatrix())));
        out.println("ctm=" + matrix(gs.getCurrentTransformationMatrix()));
        out.println("strokingColor=" + color(gs.getStrokingColor()));
        out.println("nonStrokingColor=" + color(gs.getNonStrokingColor()));
        out.println("strokingColorSpace=" + cs(gs.getStrokingColorSpace()));
        out.println("nonStrokingColorSpace=" + cs(gs.getNonStrokingColorSpace()));
        out.println("dash=" + dash(gs.getLineDashPattern()));
        // text state defaults
        PDTextState ts = gs.getTextState();
        out.println("ts.characterSpacing=" + fmt(ts.getCharacterSpacing()));
        out.println("ts.wordSpacing=" + fmt(ts.getWordSpacing()));
        out.println("ts.horizontalScaling=" + fmt(ts.getHorizontalScaling()));
        out.println("ts.leading=" + fmt(ts.getLeading()));
        out.println("ts.fontSize=" + fmt(ts.getFontSize()));
        out.println("ts.rise=" + fmt(ts.getRise()));
        out.println("ts.renderingMode=" + ts.getRenderingMode());
        out.println("ts.knockout=" + ts.getKnockoutFlag());
        out.println("ts.font=" + (ts.getFont() == null ? "null" : "set"));
    }

    private static void cloneIndependence(PrintStream out) throws Exception {
        PDGraphicsState orig = new PDGraphicsState(new PDRectangle(0, 0, 100, 100));
        // seed text matrices so clone exercises the non-null branch
        orig.setTextMatrix(new Matrix());
        orig.setTextLineMatrix(new Matrix());
        PDGraphicsState clone = orig.clone();

        // CTM: deep-cloned -> mutating clone must NOT touch original.
        clone.getCurrentTransformationMatrix().setValue(0, 0, 9.0f);
        out.println("ctm_shared=" + (orig.getCurrentTransformationMatrix().getValue(0, 0) == 9.0f));

        // textMatrix: deep-cloned.
        clone.getTextMatrix().setValue(0, 0, 7.0f);
        out.println("textMatrix_shared=" + (orig.getTextMatrix().getValue(0, 0) == 7.0f));

        // textState: deep-cloned -> mutate clone's text state.
        clone.getTextState().setFontSize(42.0f);
        out.println("textState_shared=" + (orig.getTextState().getFontSize() == 42.0f));
        out.println("textState_sameRef=" + (orig.getTextState() == clone.getTextState()));

        // colours: SHARED (same reference per upstream clone).
        out.println("strokingColor_sameRef=" + (orig.getStrokingColor() == clone.getStrokingColor()));
        out.println("nonStrokingColor_sameRef=" + (orig.getNonStrokingColor() == clone.getNonStrokingColor()));

        // dash: SHARED (same reference).
        out.println("dash_sameRef=" + (orig.getLineDashPattern() == clone.getLineDashPattern()));

        // CTM reference identity (different objects).
        out.println("ctm_sameRef=" + (orig.getCurrentTransformationMatrix() == clone.getCurrentTransformationMatrix()));

        // clippingPaths: SHARED list (same reference) right after clone.
        out.println("clipping_sameRef=" + (orig.getCurrentClippingPaths() == clone.getCurrentClippingPaths()));

        // scalar field copied by value -> independent.
        clone.setLineWidth(5.0f);
        out.println("lineWidth_independent=" + (orig.getLineWidth() == 1.0f));
    }

    private static void setters(PrintStream out) {
        PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
        gs.setLineWidth(-3.5f);
        out.println("lineWidth_neg=" + fmt(gs.getLineWidth()));
        gs.setMiterLimit(-1.0f);
        out.println("miterLimit_neg=" + fmt(gs.getMiterLimit()));
        gs.setLineCap(99);
        out.println("lineCap_big=" + gs.getLineCap());
        gs.setLineJoin(-5);
        out.println("lineJoin_neg=" + gs.getLineJoin());
        gs.setAlphaConstant(2.5);
        out.println("alpha_over=" + fmt(gs.getAlphaConstant()));
        gs.setNonStrokeAlphaConstant(-0.5);
        out.println("nsAlpha_neg=" + fmt(gs.getNonStrokeAlphaConstant()));
        gs.setAlphaConstant(Double.NaN);
        out.println("alpha_nan=" + gs.getAlphaConstant());
        gs.setFlatness(Double.POSITIVE_INFINITY);
        out.println("flatness_inf=" + gs.getFlatness());
        gs.setSmoothness(-7.0);
        out.println("smoothness_neg=" + fmt(gs.getSmoothness()));
        gs.setOverprintMode(-2);
        out.println("opm_neg=" + gs.getOverprintMode());
        gs.setLineWidth(Float.NaN);
        out.println("lineWidth_nan=" + gs.getLineWidth());
        gs.setLineWidth(Float.POSITIVE_INFINITY);
        out.println("lineWidth_inf=" + gs.getLineWidth());
    }

    private static String matrix(Matrix m) {
        return m.toString();
    }

    private static String color(PDColor c) {
        if (c == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder("[");
        float[] comps = c.getComponents();
        for (int i = 0; i < comps.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(fmt(comps[i]));
        }
        sb.append("]");
        return sb.toString();
    }

    private static String cs(PDColorSpace c) {
        return c == null ? "null" : c.getName();
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
        if (Double.isNaN(v)) {
            return "NaN";
        }
        if (Double.isInfinite(v)) {
            return v > 0 ? "Infinity" : "-Infinity";
        }
        if (v == Math.rint(v)) {
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
