import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.blend.BlendMode;

/**
 * Live oracle probe for blend-mode RESOLUTION + the SEPARABLE per-channel
 * blend functions (PDF 32000-1 §11.3.5).
 *
 * Existing wave coverage:
 *   - BlendAlphaProbe / HighlightBlendProbe fingerprint the RENDERED blend
 *     compositing + /ca alpha path of whole pages; they never call the
 *     pure BlendMode lookup or evaluate the per-channel blend functions in
 *     isolation.
 *   - TransparencyGroupCompositeProbe pins the group-composite raster.
 *
 * This probe owns the algebra that those rendering probes sit on top of:
 *
 *   1. RESOLVE — {@code BlendMode.getInstance(COSBase)} over a fuzz grid of
 *      /BM values: a plain COSName for each of the 16 standard modes, the
 *      Compatible alias (→ Normal), unknown names (→ Normal), a COSArray of
 *      names where "first recognised wins" (PDF 32000-1 §11.3.5 fallback
 *      chain), arrays that begin with an unknown name, an empty array, a
 *      null operand, a non-name/non-array operand (COSInteger / COSString),
 *      and a COSArray containing a non-name entry. Each resolved mode is
 *      projected by NAME plus its isSeparableBlendMode() flag.
 *
 *   2. EVALUATE — for every separable mode, evaluate
 *      {@code getBlendChannelFunction().blendChannel(src, backdrop)} over the
 *      Cartesian grid {0, 0.25, 0.5, 0.75, 1.0}^2 (25 pairs each), projecting
 *      each blended channel as a canonical float. Non-separable modes have a
 *      null channel function (getBlendChannelFunction() == null) — that null
 *      is projected too so the Python side pins the same "no scalar function"
 *      contract.
 *
 * Output (UTF-8, to stdout) — one line per case, leading two space-separated
 * tokens form the lookup key:
 *
 *   RESOLVE <case> name=<resolvedName> sep=<true|false>
 *   BLEND <Mode> <s>:<b>=<canonFloat> <s>:<b>=<canonFloat> ...   (25 pairs)
 *   CHANFN <Mode> present=<true|false>
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> BlendModeFuzzProbe
 */
public final class BlendModeFuzzProbe {
    private static final float[] GRID = {0.0f, 0.25f, 0.5f, 0.75f, 1.0f};

    private static final String[] SEPARABLE = {
        "Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten",
        "ColorDodge", "ColorBurn", "HardLight", "SoftLight",
        "Difference", "Exclusion"
    };

    private static final String[] NON_SEPARABLE = {
        "Hue", "Saturation", "Color", "Luminosity"
    };

    public static void main(String[] args) {
        PrintStream out = new PrintStream(System.out, true, java.nio.charset.StandardCharsets.UTF_8);
        StringBuilder sb = new StringBuilder();

        // --- 1. RESOLUTION cases ------------------------------------------
        // Plain names for all 16 standard modes.
        for (String n : SEPARABLE) {
            resolve(sb, "name_" + n, name(n));
        }
        for (String n : NON_SEPARABLE) {
            resolve(sb, "name_" + n, name(n));
        }
        // Compatible alias → Normal.
        resolve(sb, "name_Compatible", name("Compatible"));
        // Unknown names → Normal.
        resolve(sb, "name_Unknown", name("Bogus"));
        resolve(sb, "name_empty", name(""));
        resolve(sb, "name_lowercase", name("multiply"));
        // null operand → Normal.
        resolve(sb, "null", null);
        // Non-name, non-array operands → Normal.
        resolve(sb, "integer", COSInteger.get(3));
        resolve(sb, "string", new COSString("Multiply"));
        // Arrays — first recognised wins.
        resolve(sb, "arr_first_wins", arr(name("Darken"), name("Screen")));
        resolve(sb, "arr_unknown_then_known",
                arr(name("Bogus"), name("ColorBurn")));
        resolve(sb, "arr_two_unknown_then_known",
                arr(name("Foo"), name("Bar"), name("Hue")));
        resolve(sb, "arr_all_unknown", arr(name("Foo"), name("Bar")));
        resolve(sb, "arr_compatible_first",
                arr(name("Compatible"), name("Multiply")));
        resolve(sb, "arr_nonname_then_known",
                arr(COSInteger.get(1), name("Lighten")));
        resolve(sb, "arr_empty", new COSArray());
        resolve(sb, "arr_single", arr(name("SoftLight")));

        // --- 2. CHANNEL FUNCTION presence ---------------------------------
        for (String n : SEPARABLE) {
            chanfn(sb, n);
        }
        for (String n : NON_SEPARABLE) {
            chanfn(sb, n);
        }

        // --- 3. SEPARABLE BLEND EVALUATION over a 5x5 grid ----------------
        for (String n : SEPARABLE) {
            BlendMode mode = BlendMode.getInstance(name(n));
            BlendMode.BlendChannelFunction fn = mode.getBlendChannelFunction();
            sb.append("BLEND ").append(n);
            for (float s : GRID) {
                for (float b : GRID) {
                    float v = fn.blendChannel(s, b);
                    sb.append(' ')
                      .append(canonGrid(s)).append(':').append(canonGrid(b))
                      .append('=').append(canonFloat(v));
                }
            }
            sb.append('\n');
        }

        out.print(sb);
    }

    private static void resolve(StringBuilder sb, String label, COSBase bm) {
        BlendMode mode = BlendMode.getInstance(bm);
        sb.append("RESOLVE ").append(label)
          .append(" name=").append(mode.getCOSName().getName())
          .append(" sep=").append(mode.isSeparableBlendMode())
          .append('\n');
    }

    private static void chanfn(StringBuilder sb, String name) {
        BlendMode mode = BlendMode.getInstance(name(name));
        boolean present = mode.getBlendChannelFunction() != null;
        sb.append("CHANFN ").append(name)
          .append(" present=").append(present).append('\n');
    }

    private static COSName name(String n) {
        return COSName.getPDFName(n);
    }

    private static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase i : items) {
            a.add(i);
        }
        return a;
    }

    /** Canonical grid label (e.g. 0, 0.25, 0.5, 0.75, 1). */
    private static String canonGrid(float f) {
        return canonFloat(f);
    }

    /** HALF_EVEN to 4 decimals, trailing zeros stripped, "-0" → "0". */
    static String canonFloat(float f) {
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(4, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
            s = "0";
        }
        return s;
    }
}
