import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for the RENDER-TIME image-XObject painting path
 * (PageDrawer.drawImage): /ImageMask stencil fill, color-key /Mask,
 * /SMask soft-mask compositing, /Decode inversion, 1-bit vs 8-bit
 * bit-depth and /Interpolate. It renders one page of a caller-supplied
 * fixture and emits COARSE painted-region facts rather than a pixel-exact
 * raster, because Java2D and Pillow disagree on anti-aliasing / sampling.
 *
 * <p>The coarse facts are robust to AA / sub-pixel drift but still pin the
 * things a masking bug actually breaks: which region paints (the painted
 * bbox + the non-white pixel-count bucket) and the gross colour identity
 * of the painted region (a quantised centre-of-mass colour sample). A
 * masked region that wrongly paints (or a painted region that wrongly
 * masks) shifts the bucket and the bbox; an un-inverted /Decode image or a
 * stencil filled with the wrong colour shifts the colour sample.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; ImagePaintFuzzProbe input.pdf pageIndex
 *
 * <p>Output (UTF-8, to stdout), one line, space-separated:
 *   {@code <w> <h> <bucket> <bx0> <by0> <bx1> <by1> <qr> <qg> <qb>}
 * where:
 *   w,h            rendered pixel dimensions (exact — a mismatch is a bug);
 *   bucket         non-white pixel count quantised to a coarse bucket
 *                  (count * 16 / totalPixels, 0..16) so AA fringe pixels
 *                  don't tip the bucket;
 *   bx0,by0,bx1,by1 painted bbox in 16ths of the page (the tightest box
 *                  enclosing every non-white pixel, each edge floor/ceil
 *                  to a 16th) — -1,-1,-1,-1 when nothing painted;
 *   qr,qg,qb       the average colour of all non-white pixels, quantised to
 *                  one of 6 levels per channel (0,51,102,153,204,255), so a
 *                  red stencil vs an inverted-blue image is unmistakable but
 *                  AA blending of edges is absorbed; 255,255,255 when blank.
 *
 * <p>"Non-white" is luma &lt; 250 to drop the page's white backdrop while
 * keeping any painted pixel (even pale ones) in the count.
 */
public final class ImagePaintFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(page, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();

            long count = 0;
            long sumR = 0;
            long sumG = 0;
            long sumB = 0;
            int minX = w;
            int minY = h;
            int maxX = -1;
            int maxY = -1;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    int luma = (int) Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                    if (luma < 250) {
                        count++;
                        sumR += r;
                        sumG += g;
                        sumB += b;
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

            long totalPixels = (long) w * h;
            int bucket = totalPixels > 0
                    ? (int) (count * 16 / totalPixels)
                    : 0;

            int bx0;
            int by0;
            int bx1;
            int by1;
            int qr;
            int qg;
            int qb;
            if (count == 0) {
                bx0 = -1;
                by0 = -1;
                bx1 = -1;
                by1 = -1;
                qr = 255;
                qg = 255;
                qb = 255;
            } else {
                bx0 = minX * 16 / w;
                by0 = minY * 16 / h;
                bx1 = (maxX * 16 + w - 1) / w; // ceil-ish
                by1 = (maxY * 16 + h - 1) / h;
                qr = quantize((int) (sumR / count));
                qg = quantize((int) (sumG / count));
                qb = quantize((int) (sumB / count));
            }

            out.println(w + " " + h + " " + bucket + " "
                    + bx0 + " " + by0 + " " + bx1 + " " + by1 + " "
                    + qr + " " + qg + " " + qb);
        }
    }

    /** Snap a 0..255 channel to one of 6 evenly-spaced levels. */
    private static int quantize(int v) {
        int level = (int) Math.round(v / 255.0 * 5.0);
        if (level < 0) {
            level = 0;
        }
        if (level > 5) {
            level = 5;
        }
        return level * 51;
    }
}
