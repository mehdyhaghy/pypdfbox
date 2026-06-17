import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.interactive.pagenavigation.PDTransition;

/**
 * Differential fuzz probe for malformed page-transition (``/Trans``)
 * dictionaries. Builds ~30 edge-case COSDictionary instances directly, wraps
 * each in Apache PDFBox's typed {@link PDTransition}, and emits one
 * ``case <name> <projection>`` line per case so the Python oracle test can
 * compare byte-for-byte.
 *
 * The projection string packs every typed accessor PDFBox exposes:
 *
 *   S=<style> D=<duration> Dm=<dim> M=<motion> Di=<dir> SS=<scale> B=<flag>
 *
 * Each accessor is wrapped so a thrown exception renders as ``ERR:<Simple>``
 * instead of aborting the probe — that lets us pin the defensive contract on
 * both sides honestly.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TransitionFuzzProbe
 */
public final class TransitionFuzzProbe {

    private static final COSName S = COSName.getPDFName("S");
    private static final COSName D = COSName.getPDFName("D");
    private static final COSName DM = COSName.getPDFName("Dm");
    private static final COSName M = COSName.getPDFName("M");
    private static final COSName DI = COSName.getPDFName("Di");
    private static final COSName SS = COSName.getPDFName("SS");
    private static final COSName B = COSName.getPDFName("B");

    private interface Accessor {
        String get();
    }

    private static String result(Accessor accessor) {
        try {
            return accessor.get();
        } catch (Throwable throwable) {
            return "ERR:" + throwable.getClass().getSimpleName();
        }
    }

    /** Canonical float rendering matching PageTransProbe. */
    private static String fmt(float v) {
        if (Float.isNaN(v)) {
            return "NaN";
        }
        if (Float.isInfinite(v)) {
            return v > 0 ? "Inf" : "-Inf";
        }
        if (v == Math.rint(v)) {
            return Long.toString((long) v);
        }
        String s = String.format(Locale.ROOT, "%.4f", v);
        int end = s.length();
        while (end > 0 && s.charAt(end - 1) == '0') {
            end--;
        }
        if (end > 0 && s.charAt(end - 1) == '.') {
            end--;
        }
        return s.substring(0, end);
    }

    /** Render ``/Di`` as PDFBox getDirection() returns a raw COSBase. */
    private static String direction(COSBase value) {
        if (value instanceof COSInteger) {
            return Long.toString(((COSInteger) value).longValue());
        }
        if (value instanceof COSName) {
            return ((COSName) value).getName();
        }
        if (value == null) {
            return "null";
        }
        return value.getClass().getSimpleName();
    }

    private static String project(PDTransition trans) {
        String style = result(() -> trans.getStyle());
        String dur = result(() -> fmt(trans.getDuration()));
        String dim = result(() -> trans.getDimension());
        String motion = result(() -> trans.getMotion());
        String dir = result(() -> direction(trans.getDirection()));
        String scale = result(() -> fmt(trans.getFlyScale()));
        String flag = result(() -> Boolean.toString(trans.isFlyAreaOpaque()));
        return "S=" + style + " D=" + dur + " Dm=" + dim + " M=" + motion
                + " Di=" + dir + " SS=" + scale + " B=" + flag;
    }

    private static COSDictionary base() {
        COSDictionary d = new COSDictionary();
        d.setName(COSName.TYPE, "Trans");
        return d;
    }

    private static void emit(StringBuilder sb, String name, COSDictionary d) {
        PDTransition trans = new PDTransition(d);
        sb.append("case ").append(name).append(' ').append(project(trans)).append('\n');
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        // Empty dictionary — every accessor falls back to its default.
        emit(sb, "empty", base());

        // /S style sweep: every spec style plus unknown + non-name shapes.
        String[] styles = {
            "Split", "Blinds", "Box", "Wipe", "Dissolve", "Glitter",
            "R", "Fly", "Push", "Cover", "Uncover", "Fade", "Bogus"
        };
        for (String style : styles) {
            COSDictionary d = base();
            d.setName(S, style);
            emit(sb, "style_" + style, d);
        }
        // /S as a non-name (string / integer / null) — defensive.
        COSDictionary sStr = base();
        sStr.setItem(S, new COSString("Wipe"));
        emit(sb, "style_string", sStr);
        COSDictionary sInt = base();
        sInt.setItem(S, COSInteger.get(5));
        emit(sb, "style_int", sInt);
        COSDictionary sNull = base();
        sNull.setItem(S, COSNull.NULL);
        emit(sb, "style_null", sNull);

        // /D duration edge cases.
        emit(sb, "dur_zero", durDict(COSInteger.get(0)));
        emit(sb, "dur_neg", durDict(new COSFloat(-2.5f)));
        emit(sb, "dur_huge", durDict(new COSFloat(1.0e9f)));
        emit(sb, "dur_frac", durDict(new COSFloat(0.25f)));
        emit(sb, "dur_int", durDict(COSInteger.get(3)));
        COSDictionary dName = base();
        dName.setName(D, "fast");
        emit(sb, "dur_name", dName);
        COSDictionary dStr = base();
        dStr.setItem(D, new COSString("3"));
        emit(sb, "dur_string", dStr);

        // /Dm dimension: H / V / garbage / string-shape (getNameAsString).
        emit(sb, "dim_h", dimDict("H"));
        emit(sb, "dim_v", dimDict("V"));
        emit(sb, "dim_bogus", dimDict("X"));
        COSDictionary dmStr = base();
        dmStr.setItem(DM, new COSString("V"));
        emit(sb, "dim_string", dmStr);

        // /M motion: I / O / garbage / string-shape (getNameAsString).
        emit(sb, "motion_i", motionDict("I"));
        emit(sb, "motion_o", motionDict("O"));
        emit(sb, "motion_bogus", motionDict("Q"));
        COSDictionary mStr = base();
        mStr.setItem(M, new COSString("O"));
        emit(sb, "motion_string", mStr);

        // /Di direction: integer degrees, /None name, garbage name, string.
        emit(sb, "dir_0", diDict(COSInteger.get(0)));
        emit(sb, "dir_90", diDict(COSInteger.get(90)));
        emit(sb, "dir_180", diDict(COSInteger.get(180)));
        emit(sb, "dir_270", diDict(COSInteger.get(270)));
        emit(sb, "dir_315", diDict(COSInteger.get(315)));
        emit(sb, "dir_999", diDict(COSInteger.get(999)));
        emit(sb, "dir_none", diDict(COSName.getPDFName("None")));
        emit(sb, "dir_badname", diDict(COSName.getPDFName("Left")));
        emit(sb, "dir_string", diDict(new COSString("90")));
        emit(sb, "dir_float", diDict(new COSFloat(90.0f)));

        // /SS fly scale edge cases.
        emit(sb, "ss_unit", ssDict(new COSFloat(1.0f)));
        emit(sb, "ss_half", ssDict(new COSFloat(0.5f)));
        emit(sb, "ss_neg", ssDict(new COSFloat(-1.0f)));
        COSDictionary ssName = base();
        ssName.setName(SS, "big");
        emit(sb, "ss_name", ssName);

        // /B opaque-background flag edge cases.
        COSDictionary bTrue = base();
        bTrue.setBoolean(B, true);
        emit(sb, "b_true", bTrue);
        COSDictionary bFalse = base();
        bFalse.setBoolean(B, false);
        emit(sb, "b_false", bFalse);
        COSDictionary bInt = base();
        bInt.setItem(B, COSInteger.ONE);
        emit(sb, "b_int", bInt);
        COSDictionary bName = base();
        bName.setName(B, "true");
        emit(sb, "b_name", bName);

        // A fully-populated Fly transition (the spec's headline combination).
        COSDictionary fly = base();
        fly.setName(S, "Fly");
        fly.setFloat(D, 2);
        fly.setName(DM, "V");
        fly.setName(M, "O");
        fly.setItem(DI, COSName.getPDFName("None"));
        fly.setFloat(SS, 0.7f);
        fly.setBoolean(B, true);
        emit(sb, "fly_full", fly);

        out.print(sb);
        out.flush();
    }

    private static COSDictionary durDict(COSBase value) {
        COSDictionary d = base();
        d.setItem(D, value);
        return d;
    }

    private static COSDictionary dimDict(String dim) {
        COSDictionary d = base();
        d.setName(DM, dim);
        return d;
    }

    private static COSDictionary motionDict(String motion) {
        COSDictionary d = base();
        d.setName(M, motion);
        return d;
    }

    private static COSDictionary diDict(COSBase value) {
        COSDictionary d = base();
        d.setItem(DI, value);
        return d;
    }

    private static COSDictionary ssDict(COSBase value) {
        COSDictionary d = base();
        d.setItem(SS, value);
        return d;
    }

    // Reference so unused-import checks pass for COSBoolean (true-flag path).
    static {
        assert COSBoolean.TRUE != null;
    }
}
