import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;

/**
 * Live oracle probe: Apache PDFBox PDFunctionType2/Type3 eval edge cases.
 *
 * Angles (wave 1483):
 *  - Type2 missing /N (getFloat default -1 => x^-1), N=0, negative base with
 *    fractional N (Math.pow NaN), C0/C1 length mismatch (min sizing), x outside
 *    [0,1] but inside Domain (no input clip).
 *  - Type3 single subfunction (no /Bounds), input exactly AT a bound, input at
 *    domain edges, reversed /Encode [1 0], zero-width subdomain (repeated bound
 *    => divide-by-zero in interpolate), nested Type3-in-Type3.
 *
 * Line grammar:  FUNC <name> <in0,...> -> <out0> <out1> ...
 * Each float rendered with %.6f (or NaN/Infinity literal from Float.toString).
 */
public final class FunctionType23EdgeProbe {

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

    static COSDictionary type2(float[] c0, float[] c1, Float n, float[] domain, float[] range) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(domain));
        if (c0 != null) {
            d.setItem(COSName.C0, floats(c0));
        }
        if (c1 != null) {
            d.setItem(COSName.C1, floats(c1));
        }
        if (n != null) {
            d.setItem(COSName.N, new COSFloat(n));
        }
        if (range != null) {
            d.setItem(COSName.RANGE, floats(range));
        }
        return d;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---- Type2: missing /N => getFloat default -1 => x^-1 ----
        PDFunction t2noN = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, null, new float[] {0, 1}, null));
        for (float x : new float[] {0.25f, 0.5f, 1f, 2f}) {
            emit("T2noN", t2noN, new float[] {x});
        }

        // ---- Type2: N=0 => x^0 = 1 (and 0^0) ----
        PDFunction t2n0 = PDFunction.create(
            type2(new float[] {2}, new float[] {5}, 0f, new float[] {0, 1}, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T2n0", t2n0, new float[] {x});
        }

        // ---- Type2: negative base, fractional N => Math.pow NaN ----
        PDFunction t2negfrac = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, 0.5f, new float[] {-2, 2}, null));
        for (float x : new float[] {-1f, -0.5f, 0.5f}) {
            emit("T2negfrac", t2negfrac, new float[] {x});
        }

        // ---- Type2: negative base, integer-valued float N=2 (Math.pow defined) ----
        PDFunction t2negint = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, 2f, new float[] {-2, 2}, null));
        for (float x : new float[] {-1f, -0.5f, 1.5f}) {
            emit("T2negint", t2negint, new float[] {x});
        }

        // ---- Type2: negative base, odd integer N=3 ----
        PDFunction t2negodd = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, 3f, new float[] {-2, 2}, null));
        for (float x : new float[] {-1f, -0.5f}) {
            emit("T2negodd", t2negodd, new float[] {x});
        }

        // ---- Type2: C0 longer than C1 => result sized by min ----
        PDFunction t2mismatch = PDFunction.create(
            type2(new float[] {0, 0.1f, 0.2f}, new float[] {1, 0.9f}, 1f,
                  new float[] {0, 1}, null));
        emit("T2mismatch", t2mismatch, new float[] {0.5f});

        // ---- Type2: missing C0/C1 entirely => defaults [0]/[1] ----
        PDFunction t2nocoeff = PDFunction.create(
            type2(null, null, 1f, new float[] {0, 1}, null));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T2nocoeff", t2nocoeff, new float[] {x});
        }

        // ---- Type2: x outside [0,1] but inside Domain [-2,2], N=1 (no input clip) ----
        PDFunction t2outside = PDFunction.create(
            type2(new float[] {0}, new float[] {10}, 1f, new float[] {-2, 2}, null));
        for (float x : new float[] {-2f, -1f, 1.5f, 2f}) {
            emit("T2outside", t2outside, new float[] {x});
        }

        // ============ Type3 ============

        // ---- single subfunction, no /Bounds, Encode maps [0,1]->[0,1] ----
        COSArray f1 = new COSArray();
        f1.add(type2(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}, null));
        COSDictionary t3single = new COSDictionary();
        t3single.setInt(COSName.FUNCTION_TYPE, 3);
        t3single.setItem(COSName.DOMAIN, floats(0, 1));
        t3single.setItem(COSName.FUNCTIONS, f1);
        t3single.setItem(COSName.BOUNDS, new COSArray());
        t3single.setItem(COSName.ENCODE, floats(0, 1));
        PDFunction t3s = PDFunction.create(t3single);
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T3single", t3s, new float[] {x});
        }

        // ---- single subfunction, reversed Encode [1 0] ----
        COSDictionary t3rev = new COSDictionary();
        t3rev.setInt(COSName.FUNCTION_TYPE, 3);
        t3rev.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray fr = new COSArray();
        fr.add(type2(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}, null));
        t3rev.setItem(COSName.FUNCTIONS, fr);
        t3rev.setItem(COSName.BOUNDS, new COSArray());
        t3rev.setItem(COSName.ENCODE, floats(1, 0));
        PDFunction t3r = PDFunction.create(t3rev);
        for (float x : new float[] {0f, 0.25f, 1f}) {
            emit("T3rev", t3r, new float[] {x});
        }

        // ---- input exactly AT the bound (strict < vs Float.compare upper edge) ----
        // two children, bound 0.5. child0 = identity-ish (C0=0,C1=1), child1 = (C0=10,C1=20)
        COSArray fb = new COSArray();
        fb.add(type2(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}, null));
        fb.add(type2(new float[] {10}, new float[] {20}, 1f, new float[] {0, 1}, null));
        COSDictionary t3bound = new COSDictionary();
        t3bound.setInt(COSName.FUNCTION_TYPE, 3);
        t3bound.setItem(COSName.DOMAIN, floats(0, 1));
        t3bound.setItem(COSName.FUNCTIONS, fb);
        t3bound.setItem(COSName.BOUNDS, floats(0.5f));
        t3bound.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        PDFunction t3b = PDFunction.create(t3bound);
        for (float x : new float[] {0f, 0.49999f, 0.5f, 0.50001f, 1f}) {
            emit("T3bound", t3b, new float[] {x});
        }

        // ---- domain edges with domain [0.2, 0.8] (input clip to domain) ----
        COSArray fd = new COSArray();
        fd.add(type2(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}, null));
        fd.add(type2(new float[] {1}, new float[] {2}, 1f, new float[] {0, 1}, null));
        COSDictionary t3dom = new COSDictionary();
        t3dom.setInt(COSName.FUNCTION_TYPE, 3);
        t3dom.setItem(COSName.DOMAIN, floats(0.2f, 0.8f));
        t3dom.setItem(COSName.FUNCTIONS, fd);
        t3dom.setItem(COSName.BOUNDS, floats(0.5f));
        t3dom.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        PDFunction t3dm = PDFunction.create(t3dom);
        for (float x : new float[] {0f, 0.2f, 0.5f, 0.8f, 1f}) {
            emit("T3dom", t3dm, new float[] {x});
        }

        // ---- zero-width subdomain: bound repeated at domain edge => divide-by-zero ----
        // domain [0,1], bound at 0.0 (== domain.min) => first subdomain has width 0.
        COSArray fz = new COSArray();
        fz.add(type2(new float[] {3}, new float[] {7}, 1f, new float[] {0, 1}, null));
        fz.add(type2(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}, null));
        COSDictionary t3zero = new COSDictionary();
        t3zero.setInt(COSName.FUNCTION_TYPE, 3);
        t3zero.setItem(COSName.DOMAIN, floats(0, 1));
        t3zero.setItem(COSName.FUNCTIONS, fz);
        t3zero.setItem(COSName.BOUNDS, floats(0f));
        t3zero.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        PDFunction t3z = PDFunction.create(t3zero);
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emit("T3zerolo", t3z, new float[] {x});
        }

        // ---- repeated bounds [0.5, 0.5] => middle subdomain width 0 ----
        COSArray fr2 = new COSArray();
        fr2.add(type2(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}, null));
        fr2.add(type2(new float[] {5}, new float[] {6}, 1f, new float[] {0, 1}, null));
        fr2.add(type2(new float[] {2}, new float[] {3}, 1f, new float[] {0, 1}, null));
        COSDictionary t3rep = new COSDictionary();
        t3rep.setInt(COSName.FUNCTION_TYPE, 3);
        t3rep.setItem(COSName.DOMAIN, floats(0, 1));
        t3rep.setItem(COSName.FUNCTIONS, fr2);
        t3rep.setItem(COSName.BOUNDS, floats(0.5f, 0.5f));
        t3rep.setItem(COSName.ENCODE, floats(0, 1, 0, 1, 0, 1));
        PDFunction t3rp = PDFunction.create(t3rep);
        for (float x : new float[] {0.25f, 0.5f, 0.75f}) {
            emit("T3rep", t3rp, new float[] {x});
        }

        // ---- nested Type3-in-Type3 ----
        // inner: 2 children bound 0.5 over [0,1]
        COSArray innerF = new COSArray();
        innerF.add(type2(new float[] {0}, new float[] {1}, 1f, new float[] {0, 1}, null));
        innerF.add(type2(new float[] {1}, new float[] {0}, 1f, new float[] {0, 1}, null));
        COSDictionary inner = new COSDictionary();
        inner.setInt(COSName.FUNCTION_TYPE, 3);
        inner.setItem(COSName.DOMAIN, floats(0, 1));
        inner.setItem(COSName.FUNCTIONS, innerF);
        inner.setItem(COSName.BOUNDS, floats(0.5f));
        inner.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        // outer: child0 = a type2, child1 = the inner type3, bound 0.5 over [0,1]
        COSArray outerF = new COSArray();
        outerF.add(type2(new float[] {2}, new float[] {3}, 1f, new float[] {0, 1}, null));
        outerF.add(inner);
        COSDictionary outer = new COSDictionary();
        outer.setInt(COSName.FUNCTION_TYPE, 3);
        outer.setItem(COSName.DOMAIN, floats(0, 1));
        outer.setItem(COSName.FUNCTIONS, outerF);
        outer.setItem(COSName.BOUNDS, floats(0.5f));
        outer.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        PDFunction t3nest = PDFunction.create(outer);
        for (float x : new float[] {0.25f, 0.5f, 0.6f, 0.75f, 0.9f, 1f}) {
            emit("T3nest", t3nest, new float[] {x});
        }
    }
}
