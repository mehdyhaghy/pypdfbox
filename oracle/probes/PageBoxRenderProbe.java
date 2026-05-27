import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for the page-boundary-box accessors AND the
 * crop-box / rotate render geometry, in one binary.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PageBoxRenderProbe read   <pdf> <page>
 *   java -cp <pdfbox-app.jar>:<build> PageBoxRenderProbe render <pdf> <page>
 *
 * "read" mode (one line, UTF-8 stdout):
 *   "media <4f> crop <4f> bleed <4f> trim <4f> art <4f> rot <i>"
 * exercising the public PDPage accessors so the default + clip + inheritable
 * logic runs exactly as upstream:
 *   - getMediaBox()  walks /Parent; US Letter when absent.
 *   - getCropBox()   /CropBox (inheritable) clipped to media, else media.
 *   - getBleedBox/getTrimBox/getArtBox  own entry clipped to media, else crop.
 *   - getRotation()  inheritable /Rotate normalised to {0,90,180,270}.
 *
 * "render" mode mirrors RenderProbe.java exactly — the rendered crop-box
 * raster fingerprint, at a fixed 72 DPI:
 *   line 1: "<width> <height>"  pixel dims (PDFRenderer sizes to the crop box,
 *           swapping w/h for 90/270 rotation).
 *   line 2: 256 space-separated 16x16 average Rec.601 luminance ints, row-major.
 */
public final class PageBoxRenderProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        File file = new File(args[1]);
        int pageIndex = Integer.parseInt(args[2]);
        try (PDDocument doc = Loader.loadPDF(file)) {
            PDPage page = doc.getPage(pageIndex);
            if ("read".equals(mode)) {
                StringBuilder sb = new StringBuilder();
                sb.append("media ").append(box(page.getMediaBox()))
                  .append(" crop ").append(box(page.getCropBox()))
                  .append(" bleed ").append(box(page.getBleedBox()))
                  .append(" trim ").append(box(page.getTrimBox()))
                  .append(" art ").append(box(page.getArtBox()))
                  .append(" rot ").append(page.getRotation());
                out.println(sb.toString());
            } else if ("render".equals(mode)) {
                PDFRenderer renderer = new PDFRenderer(doc);
                BufferedImage img = renderer.renderImageWithDPI(pageIndex, 72.0f);
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
            } else {
                throw new IllegalArgumentException("unknown mode: " + mode);
            }
        }
    }

    private static String box(PDRectangle r) {
        return fmt(r.getLowerLeftX()) + " " + fmt(r.getLowerLeftY()) + " "
             + fmt(r.getUpperRightX()) + " " + fmt(r.getUpperRightY());
    }

    /**
     * Canonical float rendering: integral values without a trailing ".0",
     * non-integral with up to 4 decimals and trailing zeros stripped.
     * Locale.ROOT keeps '.' as the decimal separator.
     */
    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
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
}
