import java.awt.image.BufferedImage;
import java.io.File;
import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: build a 100x100 page carrying one axial (Type 2)
 * shading whose ``/ColorSpace`` is NOT a Device space — either a
 * Separation (tint transform -> alternate DeviceRGB) or an Indexed
 * palette — save it, render it through Apache PDFBox, and emit the
 * render fingerprint.
 *
 * The shading's ``/Function`` produces the colour-space *input*
 * (a 1-component tint for Separation, a 1-component index for Indexed),
 * which the colour space then converts to RGB. This is exactly the path
 * a Device-RGB-only renderer gets wrong: it would treat the function
 * output as already-RGB instead of running it through the tint
 * transform / palette lookup.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> NonDeviceShadingProbe \
 *            <label> <outPdfPath>
 *   label = separation_axial | indexed_axial
 *
 * Output (UTF-8, stdout):
 *   line 1: "<width> <height>"      — rendered image pixel dimensions
 *   line 2: 256 space-separated ints — 16x16 average-luminance grid,
 *           row-major (identical fingerprint to RenderProbe.java).
 *
 * The probe writes the *same* PDF bytes the Python differential test
 * loads, so the two engines render a byte-identical fixture; any grid
 * divergence is a rendering-pipeline difference, not a writer one.
 */
public final class NonDeviceShadingProbe {
    private static final int GRID = 16;
    private static final float PAGE = 100.0f;

    static COSArray floats(float... vals) {
        COSArray a = new COSArray();
        for (float v : vals) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    // Type 2 exponential interpolation function dictionary.
    static COSStream type2(float[] c0, float[] c1, float n,
                           float[] domain, float[] range) throws Exception {
        // A stream (rather than a bare dict) keeps the builder uniform
        // with the Type 0 sampled function below; PDFunction.create
        // dispatches on /FunctionType either way.
        COSStream d = new COSStream();
        d.setInt(COSName.FUNCTION_TYPE, 2);
        d.setItem(COSName.DOMAIN, floats(domain));
        d.setItem(COSName.C0, floats(c0));
        d.setItem(COSName.C1, floats(c1));
        d.setItem(COSName.N, new COSFloat(n));
        if (range != null) {
            d.setItem(COSName.RANGE, floats(range));
        }
        try (OutputStream os = d.createOutputStream()) {
            os.write(new byte[0]);
        }
        return d;
    }

    // Type 0 sampled function: 1-in, 1-out.
    static COSStream type0(byte[] samples, int size, int bps,
                           float[] domain, float[] range) throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 0);
        s.setItem(COSName.DOMAIN, floats(domain));
        s.setItem(COSName.RANGE, floats(range));
        COSArray sizeArr = new COSArray();
        sizeArr.add(COSInteger.get(size));
        s.setItem(COSName.SIZE, sizeArr);
        s.setInt(COSName.BITS_PER_SAMPLE, bps);
        try (OutputStream os = s.createOutputStream()) {
            os.write(samples);
        }
        return s;
    }

    // [/Separation <name> /DeviceRGB <tintTransform>]
    static COSArray separationCS() throws Exception {
        COSArray cs = new COSArray();
        cs.add(COSName.SEPARATION);
        cs.add(COSName.getPDFName("MyTint"));
        cs.add(COSName.DEVICERGB);
        // tint 0 -> (0,0,1) blue, tint 1 -> (1,1,0) yellow.
        cs.add(type2(new float[] {0, 0, 1}, new float[] {1, 1, 0}, 1.0f,
                     new float[] {0, 1}, new float[] {0, 1, 0, 1, 0, 1}));
        return cs;
    }

    // [/Indexed /DeviceRGB hival <lookup>]
    static COSArray indexedCS() {
        COSArray cs = new COSArray();
        cs.add(COSName.INDEXED);
        cs.add(COSName.DEVICERGB);
        cs.add(COSInteger.get(3));
        // 4 palette entries: red, green, blue, white.
        byte[] palette = new byte[] {
            (byte) 255, 0, 0,
            0, (byte) 255, 0,
            0, 0, (byte) 255,
            (byte) 255, (byte) 255, (byte) 255
        };
        cs.add(new COSString(palette));
        return cs;
    }

    static COSStream buildShading(String label) throws Exception {
        COSStream sh = new COSStream();
        sh.setInt(COSName.SHADING_TYPE, 2);
        sh.setItem(COSName.COORDS, floats(10, 0, 90, 0));
        sh.setItem(COSName.DOMAIN, floats(0, 1));
        COSArray extend = new COSArray();
        extend.add(org.apache.pdfbox.cos.COSBoolean.TRUE);
        extend.add(org.apache.pdfbox.cos.COSBoolean.TRUE);
        sh.setItem(COSName.EXTEND, extend);
        if (label.equals("separation_axial")) {
            sh.setItem(COSName.COLORSPACE, separationCS());
            // Tint ramp 0 -> 1 across the axis.
            sh.setItem(COSName.FUNCTION,
                type2(new float[] {0}, new float[] {1}, 1.0f,
                      new float[] {0, 1}, new float[] {0, 1}));
        } else if (label.equals("indexed_axial")) {
            sh.setItem(COSName.COLORSPACE, indexedCS());
            // Index ramp 0 -> 3 across the axis (Type 0 sampled, 2-bit
            // would clip; use 8-bit range scaled to [0,3]).
            byte[] samples = new byte[] {(byte) 0, (byte) 255};
            sh.setItem(COSName.FUNCTION,
                type0(samples, 2, 8, new float[] {0, 1},
                      new float[] {0, 3}));
        } else {
            throw new IllegalArgumentException("unknown label: " + label);
        }
        return sh;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String label = args[0];
        File outFile = new File(args[1]);

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(PAGE, PAGE));
            doc.addPage(page);
            PDResources res = new PDResources();
            COSStream sh = buildShading(label);
            res.getCOSObject().setItem(COSName.SHADING,
                shadingDict("Sh0", sh));
            page.setResources(res);
            COSStream contents = new COSStream();
            try (OutputStream os = contents.createOutputStream()) {
                os.write("0 0 100 100 re W n /Sh0 sh\n".getBytes("US-ASCII"));
            }
            page.getCOSObject().setItem(COSName.CONTENTS, contents);
            doc.save(outFile);
        }

        try (PDDocument doc =
                org.apache.pdfbox.Loader.loadPDF(outFile)) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(0, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);

            long[] sum = new long[GRID * GRID];
            long[] cnt = new long[GRID * GRID];
            for (int y = 0; y < h; y++) {
                int cy = (int) ((long) y * GRID / h);
                if (cy >= GRID) {
                    cy = GRID - 1;
                }
                for (int x = 0; x < w; x++) {
                    int cx = (int) ((long) x * GRID / w);
                    if (cx >= GRID) {
                        cx = GRID - 1;
                    }
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    int lum = (int) Math.round(
                        0.299 * r + 0.587 * g + 0.114 * b);
                    int idx = cy * GRID + cx;
                    sum[idx] += lum;
                    cnt[idx] += 1;
                }
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < GRID * GRID; i++) {
                if (i > 0) {
                    sb.append(' ');
                }
                long avg = cnt[i] > 0
                    ? Math.round((double) sum[i] / cnt[i]) : 255;
                sb.append(avg);
            }
            out.println(sb.toString());
        }
    }

    static org.apache.pdfbox.cos.COSDictionary shadingDict(
            String name, COSStream sh) {
        org.apache.pdfbox.cos.COSDictionary d =
            new org.apache.pdfbox.cos.COSDictionary();
        d.setItem(COSName.getPDFName(name), sh);
        return d;
    }
}
