import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDTilingPattern;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: synthesise an *uncolored* tiling-pattern fill
 * (``/PaintType 2``, PDF 32000-1 §8.7.3.1 / §8.7.3.3) in Apache PDFBox
 * itself, render it, and emit the canonical render fingerprint.
 *
 * An uncolored tiling pattern's content stream carries NO colour operators:
 * the cell is a shape only (here a 16pt square inset in a 20pt /BBox cell).
 * The fill colour comes from the ``scn`` operands supplied when the pattern
 * is set, via a ``/Pattern`` colour space whose *underlying* colour space is
 * ``/DeviceRGB``. So the page content does ``/PCS cs r g b /P0 scn`` where
 * ``/PCS`` is the array colour space ``[/Pattern /DeviceRGB]``: the three
 * numbers are the tint the pattern paints with, and ``/P0`` selects the
 * uncolored tile.
 *
 * Because PDFBox builds *and* renders the fixture here, the probe is a tight
 * differential: any divergence in how the two engines (a) route the scn tint
 * through the underlying colour space and (b) paint an uncolored cell in that
 * tint shows up directly. The companion test passes two different scn colours
 * to prove the same pattern produces different rasters keyed on the tint.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> UncoloredTilingProbe <r> <g> <b>
 *   r g b = the scn tint components in [0,1] (DeviceRGB), e.g. "1 0 0".
 *
 * Output (UTF-8, to stdout), matching RenderProbe.java exactly:
 *   line 1: "<width> <height>"
 *   line 2: 256 space-separated 16x16 average-luminance cells, row-major.
 */
public final class UncoloredTilingProbe {
    private static final int GRID = 16;
    private static final float PAGE = 120.0f;
    private static final float BBOX = 20.0f;

    static PDDocument build(float r, float g, float b) throws Exception {
        PDDocument doc = new PDDocument();
        PDPage page = new PDPage(new PDRectangle(0, 0, PAGE, PAGE));
        doc.addPage(page);

        PDTilingPattern pattern = new PDTilingPattern();
        pattern.setPaintType(PDTilingPattern.PAINT_UNCOLORED);
        pattern.setTilingType(PDTilingPattern.TILING_CONSTANT_SPACING);
        pattern.setBBox(new PDRectangle(0, 0, BBOX, BBOX));
        pattern.setXStep(BBOX);
        pattern.setYStep(BBOX);
        // Uncolored cell motif: a 16pt square inset in the 20pt /BBox, with
        // NO colour operator — the fill colour is supplied by scn.
        org.apache.pdfbox.cos.COSStream patternStream =
            (org.apache.pdfbox.cos.COSStream) pattern.getCOSObject();
        OutputStream cs = patternStream.createOutputStream();
        cs.write("2 2 16 16 re f\n".getBytes("US-ASCII"));
        cs.close();

        PDResources resources = new PDResources();
        page.setResources(resources);
        resources.put(COSName.getPDFName("P0"), pattern);

        // Uncolored Pattern colour space: [ /Pattern /DeviceRGB ].
        COSArray patternCs = new COSArray();
        patternCs.add(COSName.PATTERN);
        patternCs.add(COSName.DEVICERGB);
        org.apache.pdfbox.cos.COSDictionary csDict =
            new org.apache.pdfbox.cos.COSDictionary();
        csDict.setItem(COSName.getPDFName("PCS"), patternCs);
        resources.getCOSObject().setItem(COSName.COLORSPACE, csDict);

        ByteArrayOutputStream content = new ByteArrayOutputStream();
        String op = "/PCS cs " + fmt(r) + " " + fmt(g) + " " + fmt(b)
            + " /P0 scn 10 10 100 100 re f\n";
        content.write(op.getBytes("US-ASCII"));

        org.apache.pdfbox.cos.COSStream stream =
            doc.getDocument().createCOSStream();
        OutputStream os = stream.createOutputStream();
        os.write(content.toByteArray());
        os.close();
        page.getCOSObject().setItem(COSName.CONTENTS, stream);

        return doc;
    }

    private static String fmt(float v) {
        if (v == Math.rint(v)) {
            return Integer.toString((int) v);
        }
        return Float.toString(v);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        float r = args.length > 0 ? Float.parseFloat(args[0]) : 1.0f;
        float g = args.length > 1 ? Float.parseFloat(args[1]) : 0.0f;
        float b = args.length > 2 ? Float.parseFloat(args[2]) : 0.0f;

        try (PDDocument doc = build(r, g, b)) {
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
                    int rr = (rgb >> 16) & 0xFF;
                    int gg = (rgb >> 8) & 0xFF;
                    int bb = rgb & 0xFF;
                    int lum = (int) Math.round(0.299 * rr + 0.587 * gg + 0.114 * bb);
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
                long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
                sb.append(avg);
            }
            out.println(sb.toString());
        }
    }
}
