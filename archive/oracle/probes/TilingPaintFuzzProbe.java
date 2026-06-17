import java.awt.geom.AffineTransform;
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
 * Live oracle probe: differential-fuzz RENDER-TIME tiling-pattern paint in
 * Apache PDFBox 3.0.7. For each named case the probe synthesises a small page
 * whose inner box is filled with a tiling pattern, renders it at 72 DPI, and
 * emits a COARSE fingerprint that is robust to anti-aliasing and sub-pixel
 * tile-phase differences between the two engines:
 *
 *   line 1: "<width> <height>"
 *   line 2: "<paintedBucket> <minX> <minY> <maxX> <maxY>"
 *           paintedBucket = round(painted-pixel-count / total * 100) i.e.
 *           the percentage of page pixels that are NOT the white background,
 *           rounded to an int (0..100). minX/minY/maxX/maxY = the painted
 *           bounding box in device pixels (-1 -1 -1 -1 when nothing painted).
 *   line 3: N sampled colours "r,g,b" space-separated, sampled at fixed
 *           device points (see SAMPLES) — the tile colour at known spots.
 *
 * Cases (see build()):
 *   colored        PaintType 1, seamless 20pt cell with a red square motif.
 *   colored_blue   PaintType 1, seamless 20pt cell with a blue square motif.
 *   uncolored_red  PaintType 2, motif is a shape only; scn tint = red.
 *   uncolored_blue PaintType 2, same cell; scn tint = blue.
 *   spaced         PaintType 1, XStep/YStep (40) > BBox (20): gaps appear.
 *   seamless       PaintType 1, XStep/YStep == BBox (20): no gaps.
 *   matrix_scale   PaintType 1, /Matrix scales the pattern 2x.
 *   matrix_xlate   PaintType 1, /Matrix translates the lattice by (10,10).
 *   zero_xstep     degenerate: /XStep 0 → PDFBox falls back to /BBox width.
 *   green_square   PaintType 1, cell draws a green square (distinct colour).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TilingPaintFuzzProbe <case>
 */
public final class TilingPaintFuzzProbe {
    private static final float PAGE = 120.0f;
    private static final float BBOX = 20.0f;

    // Fixed device-space sample points (x, y) inside the fill region. The fill
    // box is the inner 100x100 at page (10,10); at 72 DPI device == user with a
    // y-flip (device_y = 120 - user_y). Points chosen to land on cell interiors
    // for the seamless/colored cases.
    private static final int[][] SAMPLES = {
        {15, 105}, // user (15,15)  — bottom-left cell interior
        {35, 85},  // user (35,35)
        {55, 65},  // user (55,55)
        {75, 45},  // user (75,75)
    };

    static PDDocument build(String which) throws Exception {
        PDDocument doc = new PDDocument();
        PDPage page = new PDPage(new PDRectangle(0, 0, PAGE, PAGE));
        doc.addPage(page);

        PDTilingPattern pattern = new PDTilingPattern();
        pattern.setTilingType(PDTilingPattern.TILING_CONSTANT_SPACING);
        pattern.setBBox(new PDRectangle(0, 0, BBOX, BBOX));
        pattern.setXStep(BBOX);
        pattern.setYStep(BBOX);

        boolean uncolored = which.startsWith("uncolored");
        String motif;
        if (uncolored) {
            pattern.setPaintType(PDTilingPattern.PAINT_UNCOLORED);
            motif = "2 2 16 16 re f\n";
        } else {
            pattern.setPaintType(PDTilingPattern.PAINT_COLORED);
            String rg = "1 0 0 rg"; // red default
            if ("colored_blue".equals(which)) {
                rg = "0 0 1 rg";
            } else if ("green_square".equals(which)) {
                rg = "0 1 0 rg";
            }
            motif = rg + " 2 2 16 16 re f\n";
        }

        if ("spaced".equals(which)) {
            pattern.setXStep(40.0f);
            pattern.setYStep(40.0f);
        }
        if ("zero_xstep".equals(which)) {
            pattern.setXStep(0.0f);
        }
        if ("matrix_scale".equals(which)) {
            pattern.setMatrix(AffineTransform.getScaleInstance(2.0, 2.0));
        }
        if ("matrix_xlate".equals(which)) {
            pattern.setMatrix(AffineTransform.getTranslateInstance(10.0, 10.0));
        }

        org.apache.pdfbox.cos.COSStream patternStream =
            (org.apache.pdfbox.cos.COSStream) pattern.getCOSObject();
        OutputStream cs = patternStream.createOutputStream();
        cs.write(motif.getBytes("US-ASCII"));
        cs.close();

        PDResources resources = new PDResources();
        page.setResources(resources);
        resources.put(COSName.getPDFName("P0"), pattern);

        ByteArrayOutputStream content = new ByteArrayOutputStream();
        if (uncolored) {
            COSArray patternCs = new COSArray();
            patternCs.add(COSName.PATTERN);
            patternCs.add(COSName.DEVICERGB);
            org.apache.pdfbox.cos.COSDictionary csDict =
                new org.apache.pdfbox.cos.COSDictionary();
            csDict.setItem(COSName.getPDFName("PCS"), patternCs);
            resources.getCOSObject().setItem(COSName.COLORSPACE, csDict);
            String tint = "uncolored_blue".equals(which) ? "0 0 1" : "1 0 0";
            content.write(("/PCS cs " + tint
                + " /P0 scn 10 10 100 100 re f\n").getBytes("US-ASCII"));
        } else {
            content.write(
                "/Pattern cs /P0 scn 10 10 100 100 re f\n".getBytes("US-ASCII"));
        }

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
        String which = args.length > 0 ? args[0] : "colored";

        try (PDDocument doc = build(which)) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(0, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);

            long painted = 0;
            int minX = Integer.MAX_VALUE;
            int minY = Integer.MAX_VALUE;
            int maxX = -1;
            int maxY = -1;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    // "Painted" = clearly not the white page background.
                    if (r < 240 || g < 240 || b < 240) {
                        painted++;
                        if (x < minX) {
                            minX = x;
                        }
                        if (y < minY) {
                            minY = y;
                        }
                        if (x > maxX) {
                            maxX = x;
                        }
                        if (y > maxY) {
                            maxY = y;
                        }
                    }
                }
            }
            long total = (long) w * h;
            int bucket = (int) Math.round(100.0 * painted / total);
            if (maxX < 0) {
                out.println(bucket + " -1 -1 -1 -1");
            } else {
                out.println(bucket + " " + minX + " " + minY + " "
                    + maxX + " " + maxY);
            }

            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < SAMPLES.length; i++) {
                int sx = Math.min(w - 1, SAMPLES[i][0]);
                int sy = Math.min(h - 1, SAMPLES[i][1]);
                int rgb = img.getRGB(sx, sy);
                if (i > 0) {
                    sb.append(' ');
                }
                sb.append((rgb >> 16) & 0xFF).append(',')
                    .append((rgb >> 8) & 0xFF).append(',')
                    .append(rgb & 0xFF);
            }
            out.println(sb.toString());
        }
    }
}
