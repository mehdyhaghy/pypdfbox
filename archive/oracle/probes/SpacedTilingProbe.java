import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.pattern.PDTilingPattern;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: synthesise a *spaced* tiling-pattern fill in Apache
 * PDFBox itself, render it, and emit the canonical render fingerprint.
 *
 * The defining feature exercised here is ``/XStep`` / ``/YStep`` LARGER than
 * the cell ``/BBox`` (PDF 32000-1 §8.7.3.1): the cell content fills only the
 * /BBox; the surplus between the cell and the next step is a gap where the
 * page background shows through. PDFBox renders the tile via a
 * ``TexturePaint`` over a step-sized anchor rectangle, so the gap pixels stay
 * transparent. This is the path ``test_spaced_tiling_oracle.py`` pins for
 * pypdfbox: the differential builds an equivalent PDF through the pypdfbox API
 * and asserts the two renders match within the render gate.
 *
 * Because PDFBox builds *and* renders the fixture here, the probe is a tighter
 * differential than a Python-built fixture rendered through RenderProbe: any
 * divergence in how the two engines lay out a spaced lattice (gap width, cell
 * footprint, lattice phase) shows up directly.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SpacedTilingProbe <case>
 *   case = "square" (XStep=YStep=40, BBox 20)  -> wide square gaps
 *        | "wide"   (XStep=50, YStep=25, BBox 20) -> asymmetric gaps
 *
 * Output (UTF-8, to stdout), matching RenderProbe.java exactly:
 *   line 1: "<width> <height>"
 *   line 2: 256 space-separated 16x16 average-luminance cells, row-major.
 */
public final class SpacedTilingProbe {
    private static final int GRID = 16;
    private static final float PAGE = 120.0f;

    static PDDocument build(String which) throws Exception {
        float xStep;
        float yStep;
        if ("wide".equals(which)) {
            xStep = 50.0f;
            yStep = 25.0f;
        } else {
            xStep = 40.0f;
            yStep = 40.0f;
        }

        PDDocument doc = new PDDocument();
        PDPage page = new PDPage(new PDRectangle(0, 0, PAGE, PAGE));
        doc.addPage(page);

        PDTilingPattern pattern = new PDTilingPattern();
        pattern.setPaintType(PDTilingPattern.PAINT_COLORED);
        pattern.setTilingType(PDTilingPattern.TILING_CONSTANT_SPACING);
        pattern.setBBox(new PDRectangle(0, 0, 20, 20));
        pattern.setXStep(xStep);
        pattern.setYStep(yStep);
        // Colored cell motif: a red square inset inside the 20pt /BBox. The
        // PDTilingPattern's COS object is itself the content stream.
        org.apache.pdfbox.cos.COSStream patternStream =
            (org.apache.pdfbox.cos.COSStream) pattern.getCOSObject();
        OutputStream cs = patternStream.createOutputStream();
        cs.write("1 0 0 rg 2 2 16 16 re f\n".getBytes("US-ASCII"));
        cs.close();

        PDResources resources = new PDResources();
        page.setResources(resources);
        resources.put(COSName.getPDFName("P0"), pattern);

        ByteArrayOutputStream content = new ByteArrayOutputStream();
        content.write("/Pattern cs /P0 scn 10 10 100 100 re f\n".getBytes("US-ASCII"));

        // Write the raw content stream directly (the operators above use a
        // Pattern colour space + scn, which the high-level builder cannot emit).
        org.apache.pdfbox.cos.COSStream stream =
            doc.getDocument().createCOSStream();
        OutputStream os = stream.createOutputStream();
        os.write(content.toByteArray());
        os.close();
        page.getCOSObject().setItem(COSName.CONTENTS, stream);

        return doc;
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String which = args.length > 0 ? args[0] : "square";

        try (PDDocument doc = build(which)) {
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
                    int lum = (int) Math.round(0.299 * r + 0.587 * g + 0.114 * b);
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
