import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: Apache PDFBox PDFunctionType2 (exponential interpolation)
 * eval fuzz (wave 1536). Dedicated to the Type 2 exponential evaluator —
 * complements FunctionType23EdgeProbe with deeper malformed-coefficient,
 * malformed /N, /Domain, and /Range angles.
 *
 * Angles:
 *  - /N: missing (getFloat default -1 => x^-1), 0, 1, negative even/odd, huge,
 *    fractional.
 *  - x=0 with negative /N (Math.pow(0,neg) => Infinity; Python ValueError).
 *  - /C0 or /C1: missing (constructor materialises [0]/[1]), present-but-empty
 *    (constructor still materialises [0]/[1]), different lengths (min sizing).
 *  - /Domain: missing, wrong length, reversed; input outside domain (eval does
 *    NOT clip the input to /Domain in Type 2).
 *  - /Range clipping of each output component.
 *  - x at 0 and 1, and large positive x with fractional N.
 *
 * Line grammar:  FUNC <name> <in0,...> -> <out0> <out1> ...
 * Each float rendered with %.6f (or NaN/Infinity literal).
 */
public final class FunctionType2FuzzProbe {

    static PrintStream out;

    static String fmt(float v) {
        if (Float.isNaN(v)) {
            return "NaN";
        }
        if (Float.isInfinite(v)) {
            return v > 0 ? "Infinity" : "-Infinity";
        }
        return String.format(java.util.Locale.ROOT, "%.6f", v);
    }

    static String fmtIn(float[] in) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < in.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(Double.toString((double) in[i]));
        }
        return sb.toString();
    }

    static void emit(String name, PDFunction fn, float[] in) throws Exception {
        float[] outv = fn.eval(in);
        StringBuilder sb = new StringBuilder();
        sb.append("FUNC ").append(name).append(' ').append(fmtIn(in)).append(" ->");
        for (float v : outv) {
            sb.append(' ').append(fmt(v));
        }
        out.println(sb.toString());
    }

    static COSArray floats(float... vals) {
        COSArray a = new COSArray();
        for (float v : vals) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    static COSDictionary base(float[] domain) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        if (domain != null) {
            d.setItem(COSName.DOMAIN, floats(domain));
        }
        return d;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- /N values: 1, 2, huge, fractional, negative-even ----
        PDFunction n1 = PDFunction.create(buildc(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("N1", n1, new float[] {x});
        }
        PDFunction nhuge = PDFunction.create(buildc(new float[] {0}, new float[] {1}, 1000f, new float[] {0, 1}));
        for (float x : new float[] {0.5f, 0.9f, 1f}) {
            emit("Nhuge", nhuge, new float[] {x});
        }
        PDFunction nfrac = PDFunction.create(buildc(new float[] {0}, new float[] {1}, 0.5f, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.25f, 1f}) {
            emit("Nfrac", nfrac, new float[] {x});
        }
        PDFunction nnegeven = PDFunction.create(buildc(new float[] {0}, new float[] {1}, -2f, new float[] {0.001f, 4}));
        for (float x : new float[] {0.5f, 2f, 4f}) {
            emit("Nnegeven", nnegeven, new float[] {x});
        }

        // ---- x=0 with negative /N => Math.pow(0,neg) = Infinity ----
        PDFunction nnegzero = PDFunction.create(buildc(new float[] {0}, new float[] {1}, -1f, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("Nnegzero", nnegzero, new float[] {x});
        }
        PDFunction nneg2zero = PDFunction.create(buildc(new float[] {0}, new float[] {1}, -2f, new float[] {0, 1}));
        emit("Nneg2zero", nneg2zero, new float[] {0f});

        // ---- /C0 present but EMPTY => constructor materialises [0] ----
        COSDictionary c0empty = base(new float[] {0, 1});
        c0empty.setItem(COSName.C0, new COSArray());
        c0empty.setItem(COSName.C1, floats(5));
        c0empty.setItem(COSName.N, new COSFloat(1f));
        PDFunction fc0empty = PDFunction.create(c0empty);
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("C0empty", fc0empty, new float[] {x});
        }

        // ---- /C1 present but EMPTY => constructor materialises [1] ----
        COSDictionary c1empty = base(new float[] {0, 1});
        c1empty.setItem(COSName.C0, floats(3));
        c1empty.setItem(COSName.C1, new COSArray());
        c1empty.setItem(COSName.N, new COSFloat(1f));
        PDFunction fc1empty = PDFunction.create(c1empty);
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("C1empty", fc1empty, new float[] {x});
        }

        // ---- both /C0 and /C1 EMPTY => [0] / [1] ----
        COSDictionary bothempty = base(new float[] {0, 1});
        bothempty.setItem(COSName.C0, new COSArray());
        bothempty.setItem(COSName.C1, new COSArray());
        bothempty.setItem(COSName.N, new COSFloat(1f));
        PDFunction fbothempty = PDFunction.create(bothempty);
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("BothEmpty", fbothempty, new float[] {x});
        }

        // ---- C0 longer than C1 (3 vs 1) => min sizing = 1 ----
        PDFunction c0long = PDFunction.create(
            buildc(new float[] {1, 2, 3}, new float[] {9}, 1f, new float[] {0, 1}));
        emit("C0long", c0long, new float[] {0.5f});

        // ---- C1 longer than C0 (1 vs 3) => min sizing = 1 ----
        PDFunction c1long = PDFunction.create(
            buildc(new float[] {1}, new float[] {7, 8, 9}, 1f, new float[] {0, 1}));
        emit("C1long", c1long, new float[] {0.5f});

        // ---- multi-component matched C0/C1 (per-component interpolation) ----
        PDFunction multi = PDFunction.create(
            buildc(new float[] {0, 1, 2}, new float[] {10, 5, -2}, 2f, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("Multi", multi, new float[] {x});
        }

        // ---- /Domain MISSING entirely ----
        COSDictionary nodomain = new COSDictionary();
        nodomain.setInt(COSName.FUNCTION_TYPE, 2);
        nodomain.setItem(COSName.C0, floats(0));
        nodomain.setItem(COSName.C1, floats(1));
        nodomain.setItem(COSName.N, new COSFloat(1f));
        PDFunction fnodomain = PDFunction.create(nodomain);
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("NoDomain", fnodomain, new float[] {x});
        }

        // ---- input OUTSIDE /Domain [0.2,0.8] (eval does NOT clip input) ----
        PDFunction domclip = PDFunction.create(
            buildc(new float[] {0}, new float[] {10}, 1f, new float[] {0.2f, 0.8f}));
        for (float x : new float[] {0f, 0.2f, 0.8f, 1f}) {
            emit("DomClip", domclip, new float[] {x});
        }

        // ---- reversed /Domain [1,0] ----
        PDFunction domrev = PDFunction.create(
            buildc(new float[] {0}, new float[] {4}, 1f, new float[] {1, 0}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("DomRev", domrev, new float[] {x});
        }

        // ---- /Range clipping each output component ----
        COSDictionary withrange = base(new float[] {0, 1});
        withrange.setItem(COSName.C0, floats(0, 0));
        withrange.setItem(COSName.C1, floats(100, -100));
        withrange.setItem(COSName.N, new COSFloat(1f));
        withrange.setItem(COSName.RANGE, floats(0, 10, -10, 0));
        PDFunction frange = PDFunction.create(withrange);
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("Range", frange, new float[] {x});
        }

        // ---- negative base, fractional N => NaN (Math.pow) ----
        PDFunction negbase = PDFunction.create(
            buildc(new float[] {0}, new float[] {1}, 0.5f, new float[] {-4, 4}));
        for (float x : new float[] {-1f, -4f}) {
            emit("NegBase", negbase, new float[] {x});
        }
    }

    static COSDictionary buildc(float[] c0, float[] c1, Float n, float[] domain) {
        COSDictionary d = base(domain);
        if (c0 != null) {
            d.setItem(COSName.C0, floats(c0));
        }
        if (c1 != null) {
            d.setItem(COSName.C1, floats(c1));
        }
        if (n != null) {
            d.setItem(COSName.N, new COSFloat(n));
        }
        return d;
    }
}
