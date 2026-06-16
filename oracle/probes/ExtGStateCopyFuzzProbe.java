import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDLineDashPattern;
import org.apache.pdfbox.pdmodel.graphics.blend.BlendMode;
import org.apache.pdfbox.pdmodel.graphics.state.PDExtendedGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.PDGraphicsState;
import org.apache.pdfbox.pdmodel.graphics.state.PDSoftMask;
import org.apache.pdfbox.pdmodel.graphics.state.RenderingIntent;

/**
 * Differential fuzz probe for
 * {@link PDExtendedGraphicsState#copyIntoGraphicsState(PDGraphicsState)} over a
 * MALFORMED {@code /ExtGState} parameter dictionary, Apache PDFBox 3.0.7
 * (wave 1541, agent D).
 *
 * <p>Distinct from the accessor-leniency probe {@code ExtGStateFuzzProbe}
 * (wave 1514, which reads each typed getter in isolation) and from the
 * hand-picked {@code GraphicsStateApplyEdgeProbe} (6 modes): this probe
 * exercises the FULL spec-default-substitution matrix of
 * {@code copyIntoGraphicsState}. For each case it constructs a fresh
 * {@link PDGraphicsState} (so every slot starts at its constructor default),
 * optionally SEEDS one slot with a non-default value, applies the mutated
 * ExtGState, then projects the WHOLE resulting graphics state. This catches
 * three behaviours the prior probes do not co-test:
 * <ul>
 *   <li>spec-default push for a present-but-malformed numeric entry — upstream
 *       {@code defaultIfNull}: /LW→1, /ML→10, /OPM→0, /FL→1, /SM→0, /CA→1,
 *       /ca→1 (overwriting any seeded value);</li>
 *   <li>null-overwrite for /D, /RI, /TR, /TR2 (a malformed entry CLEARS a
 *       seeded value rather than leaving it intact);</li>
 *   <li>which slots are LEFT UNTOUCHED when the corresponding key is absent
 *       (the seeded value survives).</li>
 * </ul>
 *
 * <p>Usage: {@code java -cp <jar>:<build> ExtGStateCopyFuzzProbe <mode>}. Each
 * mode prints one framed line; the pypdfbox sibling
 * (tests/pdmodel/graphics/state/oracle/test_extgstate_copy_fuzz_wave1541.py)
 * builds the identical ExtGState dict + seed and asserts line-for-line parity.
 *
 * <p>Projection grammar (one line per mode)::
 * <pre>
 *   MODE &lt;name&gt; lw=&lt;f&gt; lc=&lt;int&gt; lj=&lt;int&gt; ml=&lt;f&gt; ca=&lt;f&gt; cana=&lt;f&gt; \
 *       bm=&lt;name&gt; ais=&lt;0|1&gt; tk=&lt;0|1&gt; sa=&lt;0|1&gt; op=&lt;0|1&gt; opns=&lt;0|1&gt; \
 *       opm=&lt;int&gt; fl=&lt;f&gt; sm=&lt;f&gt; ri=&lt;enum|null&gt; dash=&lt;proj&gt; \
 *       smask=&lt;kind&gt; tr=&lt;marker&gt;
 * </pre>
 */
public final class ExtGStateCopyFuzzProbe {

    static PrintStream out;

    static String fmt(double v) {
        if (Double.isNaN(v)) {
            return "nan";
        }
        if (v == Math.rint(v) && !Double.isInfinite(v)) {
            return Long.toString((long) v);
        }
        if (Double.isInfinite(v)) {
            return v > 0 ? "inf" : "-inf";
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

    static COSDictionary base() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("ExtGState"));
        return d;
    }

    static COSArray nums(float... vals) {
        COSArray a = new COSArray();
        for (float v : vals) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase it : items) {
            a.add(it);
        }
        return a;
    }

    static String dash(PDLineDashPattern p) {
        if (p == null) {
            return "null";
        }
        StringBuilder sb = new StringBuilder("[");
        float[] a = p.getDashArray();
        for (int i = 0; i < a.length; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(fmt(a[i]));
        }
        sb.append("]p").append(fmt(p.getPhase()));
        return sb.toString();
    }

    static String bm(BlendMode b) {
        if (b == null) {
            return "null";
        }
        COSName cn = b.getCOSName();
        return cn == null ? "null" : cn.getName();
    }

    static String ri(RenderingIntent r) {
        return r == null ? "null" : r.name();
    }

    static String smask(PDSoftMask sm) {
        if (sm == null) {
            return "null";
        }
        COSName st = sm.getSubType();
        return "dict:" + (st == null ? "null" : st.getName());
    }

    static String project(PDGraphicsState gs) {
        StringBuilder sb = new StringBuilder();
        sb.append("lw=").append(fmt(gs.getLineWidth()));
        sb.append(" lc=").append(gs.getLineCap());
        sb.append(" lj=").append(gs.getLineJoin());
        sb.append(" ml=").append(fmt(gs.getMiterLimit()));
        sb.append(" ca=").append(fmt(gs.getAlphaConstant()));
        sb.append(" cana=").append(fmt(gs.getNonStrokeAlphaConstant()));
        sb.append(" bm=").append(bm(gs.getBlendMode()));
        sb.append(" ais=").append(gs.isAlphaSource() ? "1" : "0");
        sb.append(" tk=").append(gs.getTextState().getKnockoutFlag() ? "1" : "0");
        sb.append(" sa=").append(gs.isStrokeAdjustment() ? "1" : "0");
        sb.append(" op=").append(gs.isOverprint() ? "1" : "0");
        sb.append(" opns=").append(gs.isNonStrokingOverprint() ? "1" : "0");
        sb.append(" opm=").append(gs.getOverprintMode());
        sb.append(" fl=").append(fmt(gs.getFlatness()));
        sb.append(" sm=").append(fmt(gs.getSmoothness()));
        sb.append(" ri=").append(ri(gs.getRenderingIntent()));
        sb.append(" dash=").append(dash(gs.getLineDashPattern()));
        sb.append(" smask=").append(smask(gs.getSoftMask()));
        sb.append(" tr=").append(marker(gs.getTransfer()));
        return sb.toString();
    }

    static String marker(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSName) {
            return "name:" + ((COSName) b).getName();
        }
        if (b instanceof COSArray && ((COSArray) b).size() > 0) {
            COSBase first = ((COSArray) b).getObject(0);
            if (first instanceof COSName) {
                return "arr:" + ((COSName) first).getName();
            }
            return "arr" + ((COSArray) b).size();
        }
        return b.getClass().getSimpleName();
    }

    static COSDictionary smaskDict(String subtype) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.getPDFName("Mask"));
        if (subtype != null) {
            d.setItem(COSName.getPDFName("S"), COSName.getPDFName(subtype));
        }
        return d;
    }

    static PDGraphicsState run(String mode) throws Exception {
        PDGraphicsState gs = new PDGraphicsState(new PDRectangle());
        COSDictionary d = base();

        switch (mode) {
            case "empty":
                break;

            // --- /LW spec-default push on malformed; absent leaves seed -----
            case "lw_malformed_pushes_default":
                gs.setLineWidth(42);
                d.setItem(COSName.getPDFName("LW"), COSName.getPDFName("x"));
                break;
            case "lw_huge":
                d.setItem(COSName.getPDFName("LW"), new COSFloat(1.0e9f));
                break;
            case "lw_negative":
                d.setItem(COSName.getPDFName("LW"), new COSFloat(-5));
                break;
            case "lw_absent_seed_survives":
                gs.setLineWidth(42);
                break;

            // --- /ML default 10 on malformed --------------------------------
            case "ml_malformed_pushes_default":
                gs.setMiterLimit(99);
                d.setItem(COSName.getPDFName("ML"), COSBoolean.TRUE);
                break;
            case "ml_negative":
                d.setItem(COSName.getPDFName("ML"), new COSFloat(-3));
                break;

            // --- /LC /LJ sentinel -1 pushed verbatim ------------------------
            case "lc_malformed_pushes_sentinel":
                gs.setLineCap(2);
                d.setItem(COSName.getPDFName("LC"), COSName.getPDFName("Round"));
                break;
            case "lj_value":
                d.setItem(COSName.getPDFName("LJ"), COSInteger.get(2));
                break;

            // --- /CA /ca default 1 on malformed -----------------------------
            case "ca_malformed_pushes_default":
                gs.setAlphaConstant(0.1);
                d.setItem(COSName.getPDFName("CA"), COSName.getPDFName("x"));
                break;
            case "ca_value":
                d.setItem(COSName.getPDFName("CA"), new COSFloat(0.5f));
                break;
            case "cana_out_of_range":
                d.setItem(COSName.getPDFName("ca"), new COSFloat(1.7f));
                break;
            case "cana_malformed_pushes_default":
                gs.setNonStrokeAlphaConstant(0.2);
                d.setItem(COSName.getPDFName("ca"), new COSString("0.5"));
                break;

            // --- /OPM default 0 on malformed --------------------------------
            case "opm_malformed_pushes_default":
                gs.setOverprintMode(7);
                d.setItem(COSName.getPDFName("OPM"), COSName.getPDFName("x"));
                break;
            case "opm_value":
                d.setItem(COSName.getPDFName("OPM"), COSInteger.get(1));
                break;

            // --- /FL default 1, /SM default 0 on malformed ------------------
            case "fl_malformed_pushes_default":
                gs.setFlatness(8);
                d.setItem(COSName.getPDFName("FL"), COSName.getPDFName("x"));
                break;
            case "sm_malformed_pushes_default":
                gs.setSmoothness(0.9);
                d.setItem(COSName.getPDFName("SM"), COSBoolean.FALSE);
                break;

            // --- /BM blend mode ---------------------------------------------
            case "bm_known":
                d.setItem(COSName.getPDFName("BM"), COSName.getPDFName("Multiply"));
                break;
            case "bm_unknown_to_normal":
                d.setItem(COSName.getPDFName("BM"), COSName.getPDFName("Frobnicate"));
                break;
            case "bm_array_first_known":
                d.setItem(COSName.getPDFName("BM"),
                        arr(COSName.getPDFName("Nope"), COSName.getPDFName("Screen")));
                break;
            case "bm_string_to_normal":
                d.setItem(COSName.getPDFName("BM"), new COSString("Multiply"));
                break;

            // --- /RI null-overwrite + typed copy ----------------------------
            case "ri_known":
                d.setItem(COSName.getPDFName("RI"), COSName.getPDFName("Perceptual"));
                break;
            case "ri_string_resolves":
                d.setItem(COSName.getPDFName("RI"), new COSString("Saturation"));
                break;
            case "ri_unknown_to_relative":
                d.setItem(COSName.getPDFName("RI"), COSName.getPDFName("Frobnicate"));
                break;
            case "ri_malformed_overwrites_seed":
                gs.setRenderingIntent(RenderingIntent.SATURATION);
                d.setItem(COSName.getPDFName("RI"), COSInteger.get(5));
                break;
            case "ri_absent_seed_survives":
                gs.setRenderingIntent(RenderingIntent.PERCEPTUAL);
                break;

            // --- /D dash null-overwrite -------------------------------------
            case "dash_well_formed":
                d.setItem(COSName.getPDFName("D"), arr(nums(3, 2), COSInteger.get(1)));
                break;
            case "dash_malformed_overwrites_seed":
                gs.setLineDashPattern(new PDLineDashPattern(nums(7, 7), 9));
                d.setItem(COSName.getPDFName("D"), arr(COSInteger.get(1)));
                break;
            case "dash_empty_array":
                d.setItem(COSName.getPDFName("D"), arr(nums(), COSInteger.get(0)));
                break;

            // --- /TR /TR2 null-overwrite + precedence -----------------------
            case "tr2_wins_over_tr":
                d.setItem(COSName.getPDFName("TR"),
                        arr(COSName.getPDFName("TRm"), COSName.getPDFName("TRm"),
                                COSName.getPDFName("TRm"), COSName.getPDFName("TRm")));
                d.setItem(COSName.getPDFName("TR2"),
                        arr(COSName.getPDFName("TR2m"), COSName.getPDFName("TR2m"),
                                COSName.getPDFName("TR2m"), COSName.getPDFName("TR2m")));
                break;
            case "tr_malformed_overwrites_seed":
                gs.setTransfer(COSName.getPDFName("seeded"));
                d.setItem(COSName.getPDFName("TR"),
                        arr(COSName.getPDFName("a"), COSName.getPDFName("b"),
                                COSName.getPDFName("c")));
                break;
            case "tr_identity_name":
                d.setItem(COSName.getPDFName("TR"), COSName.getPDFName("Identity"));
                break;

            // --- /SMask -----------------------------------------------------
            case "smask_none_name":
                d.setItem(COSName.getPDFName("SMask"), COSName.getPDFName("None"));
                break;
            case "smask_dict":
                d.setItem(COSName.getPDFName("SMask"), smaskDict("Luminosity"));
                break;

            // --- booleans ---------------------------------------------------
            case "ais_true":
                d.setItem(COSName.getPDFName("AIS"), COSBoolean.TRUE);
                break;
            case "tk_false":
                d.setItem(COSName.getPDFName("TK"), COSBoolean.FALSE);
                break;
            case "sa_true":
                d.setItem(COSName.getPDFName("SA"), COSBoolean.TRUE);
                break;
            case "op_true":
                d.setItem(COSName.getPDFName("OP"), COSBoolean.TRUE);
                break;
            case "opns_fallback_to_op":
                d.setItem(COSName.getPDFName("OP"), COSBoolean.TRUE);
                break;
            default:
                throw new IllegalArgumentException("unknown mode: " + mode);
        }
        new PDExtendedGraphicsState(d).copyIntoGraphicsState(gs);
        return gs;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        for (String mode : args) {
            StringBuilder sb = new StringBuilder("MODE ").append(mode).append(' ');
            try {
                sb.append(project(run(mode)));
            } catch (Exception e) {
                sb.append("ERR:").append(e.getClass().getSimpleName());
            }
            out.println(sb.toString());
        }
    }
}
