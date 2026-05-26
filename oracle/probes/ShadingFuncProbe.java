import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.function.PDFunction;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType2;
import org.apache.pdfbox.pdmodel.graphics.shading.PDShadingType3;

/**
 * Live oracle probe: emit Apache PDFBox's PDF-function evaluation and
 * axial/radial shading color-function samples as canonical text lines.
 *
 * A fixed battery of functions and shadings is hard-coded so the Python
 * differential test only has to reproduce the matching pypdfbox objects
 * and the same input points. No argv needed.
 *
 * Line grammar (must match the Python harness in the differential test):
 *
 *   FUNC <name> <in0,in1,...> -> <out0> <out1> ...
 *   SHADING <name> t=<t> -> <c0> <c1> ...
 *
 * Each float is rendered with %.6f so the comparison is locale-independent
 * and stable across the two float renderers.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ShadingFuncProbe
 */
public final class ShadingFuncProbe {

    static PrintStream out;

    static String fmt(float v) {
        return String.format(java.util.Locale.ROOT, "%.6f", v);
    }

    static String fmtIn(float[] in) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < in.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(fmt(in[i]));
        }
        return sb.toString();
    }

    static void emitFunc(String name, PDFunction fn, float[] in) throws Exception {
        float[] outv = fn.eval(in);
        StringBuilder sb = new StringBuilder();
        sb.append("FUNC ").append(name).append(' ').append(fmtIn(in)).append(" ->");
        for (float v : outv) {
            sb.append(' ').append(fmt(v));
        }
        out.println(sb.toString());
    }

    static void emitShading(String name, float[] color, float t) {
        StringBuilder sb = new StringBuilder();
        sb.append("SHADING ").append(name).append(" t=").append(fmt(t)).append(" ->");
        for (float v : color) {
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

    static COSArray ints(int... vals) {
        COSArray a = new COSArray();
        for (int v : vals) {
            a.add(COSInteger.get(v));
        }
        return a;
    }

    // ---------- function builders ----------

    static COSDictionary type2(float[] c0, float[] c1, float n, float[] domain, float[] range) {
        COSDictionary d = new COSDictionary();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(domain));
        if (c0 != null) {
            d.setItem(COSName.C0, floats(c0));
        }
        if (c1 != null) {
            d.setItem(COSName.C1, floats(c1));
        }
        d.setItem(COSName.N, new COSFloat(n));
        if (range != null) {
            d.setItem(COSName.RANGE, floats(range));
        }
        return d;
    }

    static COSStream type4(String ps, float[] domain, float[] range) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.RANGE, floats(range));
        java.io.OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static COSStream type0(byte[] samples, int[] size, int bps, float[] domain, float[] range,
                           int[] encode, float[] decode, int order) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 0);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.RANGE, floats(range));
        s.setItem(COSName.SIZE, ints(size));
        s.setInt(COSName.BITS_PER_SAMPLE, bps);
        if (encode != null) {
            s.setItem(COSName.ENCODE, ints(encode));
        }
        if (decode != null) {
            s.setItem(COSName.DECODE, floats(decode));
        }
        if (order > 0) {
            s.setInt(COSName.getPDFName("Order"), order);
        }
        java.io.OutputStream os = s.createOutputStream();
        os.write(samples);
        os.close();
        return s;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ============ Type 2 (exponential interpolation) ============
        // 3-component linear ramp red->blue, N=1.
        PDFunction t2lin = PDFunction.create(
            type2(new float[] {1, 0, 0}, new float[] {0, 0, 1}, 1.0f,
                  new float[] {0, 1}, null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitFunc("T2lin", t2lin, new float[] {x});
        }
        // N=2 (quadratic) single component.
        PDFunction t2quad = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, 2.0f, new float[] {0, 1}, null));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitFunc("T2quad", t2quad, new float[] {x});
        }
        // N=0.5 (sqrt-ish), domain [0,1], 2 components.
        PDFunction t2sqrt = PDFunction.create(
            type2(new float[] {0, 1}, new float[] {1, 0}, 0.5f, new float[] {0, 1}, null));
        for (float x : new float[] {0.1f, 0.5f, 0.9f}) {
            emitFunc("T2sqrt", t2sqrt, new float[] {x});
        }
        // C0/C1 defaults (absent) -> [0] / [1]; N=1.
        PDFunction t2def = PDFunction.create(
            type2(null, null, 1.0f, new float[] {0, 1}, null));
        for (float x : new float[] {0f, 0.3f, 1f}) {
            emitFunc("T2def", t2def, new float[] {x});
        }
        // Range clamping: C0=-0.5 C1=1.5 with /Range [0 1].
        PDFunction t2clamp = PDFunction.create(
            type2(new float[] {-0.5f}, new float[] {1.5f}, 1.0f,
                  new float[] {0, 1}, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitFunc("T2clamp", t2clamp, new float[] {x});
        }
        // Domain clamping: input out of [0.2, 0.8] gets clipped.
        PDFunction t2dom = PDFunction.create(
            type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0.2f, 0.8f}, null));
        for (float x : new float[] {0f, 0.2f, 0.5f, 0.8f, 1f}) {
            emitFunc("T2dom", t2dom, new float[] {x});
        }

        // ============ Type 3 (stitching) ============
        // Two Type 2 children, bound at 0.5, encode [0 1 0 1].
        COSArray funcs = new COSArray();
        funcs.add(type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0, 1}, null));
        funcs.add(type2(new float[] {1}, new float[] {0}, 1.0f, new float[] {0, 1}, null));
        COSDictionary t3d = new COSDictionary();
        t3d.setInt(COSName.FUNCTION_TYPE, 3);
        t3d.setItem(COSName.DOMAIN, floats(0, 1));
        t3d.setItem(COSName.FUNCTIONS, funcs);
        t3d.setItem(COSName.BOUNDS, floats(0.5f));
        t3d.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        PDFunction t3 = PDFunction.create(t3d);
        for (float x : new float[] {0f, 0.25f, 0.49f, 0.5f, 0.51f, 0.75f, 1f}) {
            emitFunc("T3stitch", t3, new float[] {x});
        }

        // Three children, bounds [0.3 0.7], encode reversed in the middle.
        COSArray funcs3 = new COSArray();
        funcs3.add(type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0, 1}, null));
        funcs3.add(type2(new float[] {1}, new float[] {0}, 1.0f, new float[] {0, 1}, null));
        funcs3.add(type2(new float[] {0}, new float[] {1}, 2.0f, new float[] {0, 1}, null));
        COSDictionary t3b = new COSDictionary();
        t3b.setInt(COSName.FUNCTION_TYPE, 3);
        t3b.setItem(COSName.DOMAIN, floats(0, 1));
        t3b.setItem(COSName.FUNCTIONS, funcs3);
        t3b.setItem(COSName.BOUNDS, floats(0.3f, 0.7f));
        t3b.setItem(COSName.ENCODE, floats(0, 1, 0, 1, 0, 1));
        PDFunction t3three = PDFunction.create(t3b);
        for (float x : new float[] {0f, 0.15f, 0.3f, 0.5f, 0.7f, 0.85f, 1f}) {
            emitFunc("T3three", t3three, new float[] {x});
        }

        // ============ Type 0 (sampled) ============
        // 1-in, 1-out, 8-bit, 3 samples [0, 128, 255], domain/range [0,1].
        byte[] s1 = new byte[] {(byte) 0, (byte) 128, (byte) 255};
        PDFunction t0lin = PDFunction.create(
            type0(s1, new int[] {3}, 8, new float[] {0, 1}, new float[] {0, 1},
                  null, null, 0));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitFunc("T0lin", t0lin, new float[] {x});
        }
        // 1-in, 3-out, 8-bit, 2 samples: [(255,0,0),(0,0,255)] red->blue.
        byte[] s2 = new byte[] {
            (byte) 255, (byte) 0, (byte) 0,
            (byte) 0, (byte) 0, (byte) 255
        };
        PDFunction t0rgb = PDFunction.create(
            type0(s2, new int[] {2}, 8, new float[] {0, 1},
                  new float[] {0, 1, 0, 1, 0, 1}, null, null, 0));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitFunc("T0rgb", t0rgb, new float[] {x});
        }
        // 2-in, 1-out, 8-bit, 2x2 grid: corners 0,85,170,255 (row-major,
        // first dim fastest): index = x0 + x1*2.
        byte[] s3 = new byte[] {(byte) 0, (byte) 85, (byte) 170, (byte) 255};
        PDFunction t0grid = PDFunction.create(
            type0(s3, new int[] {2, 2}, 8, new float[] {0, 1, 0, 1},
                  new float[] {0, 1}, null, null, 0));
        for (float[] in : new float[][] {
                {0, 0}, {1, 0}, {0, 1}, {1, 1}, {0.5f, 0.5f}, {0.25f, 0.75f}}) {
            emitFunc("T0grid", t0grid, in);
        }
        // 4-bit width, 1-in 1-out, 4 samples [0,5,10,15], range [0,1].
        byte[] s4 = new byte[] {(byte) 0x05, (byte) 0xAF};  // 0,5,10,15
        PDFunction t0n4 = PDFunction.create(
            type0(s4, new int[] {4}, 4, new float[] {0, 1}, new float[] {0, 1},
                  null, null, 0));
        for (float x : new float[] {0f, 0.33f, 0.66f, 1f}) {
            emitFunc("T0n4", t0n4, new float[] {x});
        }
        // 16-bit width, 1-in 1-out, 2 samples [0, 65535], range [0,1].
        byte[] s5 = new byte[] {(byte) 0x00, (byte) 0x00, (byte) 0xFF, (byte) 0xFF};
        PDFunction t0n16 = PDFunction.create(
            type0(s5, new int[] {2}, 16, new float[] {0, 1}, new float[] {0, 1},
                  null, null, 0));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emitFunc("T0n16", t0n16, new float[] {x});
        }

        // ============ Type 4 (PostScript calculator) ============
        PDFunction t4sub = PDFunction.create(type4("{ 1 exch sub }",
            new float[] {0, 1}, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitFunc("T4sub", t4sub, new float[] {x});
        }
        // square then clamp.
        PDFunction t4sq = PDFunction.create(type4("{ dup mul }",
            new float[] {0, 1}, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitFunc("T4sq", t4sq, new float[] {x});
        }
        // 1-in 3-out: t -> (t, 1-t, 0.5).
        PDFunction t4rgb = PDFunction.create(type4(
            "{ dup 1 exch sub 0.5 }",
            new float[] {0, 1}, new float[] {0, 1, 0, 1, 0, 1}));
        for (float x : new float[] {0f, 0.5f, 1f}) {
            emitFunc("T4rgb", t4rgb, new float[] {x});
        }
        // conditional: t < 0.5 ? 0 : 1.
        PDFunction t4cond = PDFunction.create(type4(
            "{ 0.5 lt { 0 } { 1 } ifelse }",
            new float[] {0, 1}, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.49f, 0.5f, 0.51f, 1f}) {
            emitFunc("T4cond", t4cond, new float[] {x});
        }
        // arithmetic mix: sqrt, sin (degrees), abs, neg.
        PDFunction t4math = PDFunction.create(type4(
            "{ 360 mul sin abs }",
            new float[] {0, 1}, new float[] {0, 1}));
        for (float x : new float[] {0f, 0.125f, 0.25f, 0.5f, 0.75f}) {
            emitFunc("T4math", t4math, new float[] {x});
        }
        // 2-in 1-out: average.
        PDFunction t4avg = PDFunction.create(type4(
            "{ add 2 div }",
            new float[] {0, 1, 0, 1}, new float[] {0, 1}));
        for (float[] in : new float[][] {{0, 0}, {1, 0}, {0.2f, 0.8f}, {1, 1}}) {
            emitFunc("T4avg", t4avg, in);
        }

        // ============ Axial (Type 2) shading color function ============
        // /Function = Type2 red->blue, eval at t=0..1.
        PDShadingType2 ax = new PDShadingType2(new COSDictionary());
        ax.setCoords(floats(0, 0, 100, 0));
        ax.setColorSpace(
            org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB.INSTANCE);
        ax.getCOSObject().setItem(COSName.FUNCTION,
            type2(new float[] {1, 0, 0}, new float[] {0, 0, 1}, 1.0f,
                  new float[] {0, 1}, null));
        for (float t : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitShading("AxialRGB", ax.evalFunction(t), t);
        }

        // Axial with a stitching (Type 3) function driving the color.
        PDShadingType2 ax2 = new PDShadingType2(new COSDictionary());
        ax2.setCoords(floats(0, 0, 100, 0));
        ax2.setColorSpace(
            org.apache.pdfbox.pdmodel.graphics.color.PDDeviceGray.INSTANCE);
        COSArray sfuncs = new COSArray();
        sfuncs.add(type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0, 1}, null));
        sfuncs.add(type2(new float[] {1}, new float[] {0}, 1.0f, new float[] {0, 1}, null));
        COSDictionary sdict = new COSDictionary();
        sdict.setInt(COSName.FUNCTION_TYPE, 3);
        sdict.setItem(COSName.DOMAIN, floats(0, 1));
        sdict.setItem(COSName.FUNCTIONS, sfuncs);
        sdict.setItem(COSName.BOUNDS, floats(0.5f));
        sdict.setItem(COSName.ENCODE, floats(0, 1, 0, 1));
        ax2.getCOSObject().setItem(COSName.FUNCTION, sdict);
        for (float t : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitShading("AxialStitch", ax2.evalFunction(t), t);
        }

        // ============ Radial (Type 3) shading color function ============
        PDShadingType3 rad = new PDShadingType3(new COSDictionary());
        rad.setCoords(floats(0, 0, 0, 0, 0, 100));
        rad.setColorSpace(
            org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB.INSTANCE);
        rad.getCOSObject().setItem(COSName.FUNCTION,
            type2(new float[] {0, 1, 0}, new float[] {1, 1, 0}, 1.0f,
                  new float[] {0, 1}, null));
        for (float t : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitShading("RadialRGB", rad.evalFunction(t), t);
        }

        // Radial with per-component function array (3 single-out Type 2s).
        PDShadingType3 rad2 = new PDShadingType3(new COSDictionary());
        rad2.setCoords(floats(0, 0, 0, 0, 0, 100));
        rad2.setColorSpace(
            org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB.INSTANCE);
        COSArray perComp = new COSArray();
        perComp.add(type2(new float[] {0}, new float[] {1}, 1.0f, new float[] {0, 1}, null));
        perComp.add(type2(new float[] {1}, new float[] {0.5f}, 1.0f, new float[] {0, 1}, null));
        perComp.add(type2(new float[] {0.2f}, new float[] {0.8f}, 2.0f, new float[] {0, 1}, null));
        rad2.getCOSObject().setItem(COSName.FUNCTION, perComp);
        for (float t : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitShading("RadialPerComp", rad2.evalFunction(t), t);
        }

        // Radial color clamp: Type 2 with C1 out of [0,1] -> evalFunction clamps.
        PDShadingType3 rad3 = new PDShadingType3(new COSDictionary());
        rad3.setCoords(floats(0, 0, 0, 0, 0, 100));
        rad3.setColorSpace(
            org.apache.pdfbox.pdmodel.graphics.color.PDDeviceGray.INSTANCE);
        rad3.getCOSObject().setItem(COSName.FUNCTION,
            type2(new float[] {-0.5f}, new float[] {1.5f}, 1.0f, new float[] {0, 1}, null));
        for (float t : new float[] {0f, 0.25f, 0.5f, 0.75f, 1f}) {
            emitShading("RadialClamp", rad3.evalFunction(t), t);
        }
    }
}
