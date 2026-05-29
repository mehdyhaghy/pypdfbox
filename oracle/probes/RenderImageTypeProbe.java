import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.ImageType;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit raster DIMENSIONS + pixel-format fingerprint for
 * one page rendered by Apache PDFBox across several DPI values and every
 * {@link ImageType} (RGB, ARGB, GRAY, BINARY).
 *
 * Pins two orthogonal facets of the {@code PDFRenderer.renderImageWithDPI}
 * surface:
 *   (1) DPI/scale -> raster dimensions: width = (int)(mediaBoxWidthPt/72*dpi),
 *       so the probe sweeps a fixed page across DPI values and reports the
 *       integer pixel dims PDFBox allocates (Java {@code (int)} cast == floor
 *       for the positive sizes here).
 *   (2) ImageType -> pixel format: PDFBox builds a {@code BufferedImage} of
 *       the matching {@code TYPE_*}; the probe reports the AWT type int and
 *       the raster's band count so a renderer that returns the wrong channel
 *       layout (e.g. RGB for a GRAY request) is caught.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> RenderImageTypeProbe input.pdf page
 * Output (UTF-8, to stdout), one line per (dpi, imageType) probe in a fixed
 * order:
 *   "<dpi> <typeName> <width> <height> <awtType> <numBands>: <256 comma grid>"
 * The grid is 256 comma-separated luminance ints (16x16, row-major) computed
 * with the same Rec.601 weights as RenderProbe so a probe swap won't drift
 * values. For GRAY/BINARY the per-pixel value IS the grayscale sample; for
 * ARGB getRGB returns the composited ARGB (white where transparent), matching
 * how Pillow's "L" conversion treats a flattened canvas.
 */
public final class RenderImageTypeProbe {
    private static final int GRID = 16;
    private static final float[] DPIS = {36.0f, 72.0f, 96.0f, 150.0f};
    private static final ImageType[] TYPES = {
        ImageType.RGB, ImageType.ARGB, ImageType.GRAY, ImageType.BINARY,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFRenderer renderer = new PDFRenderer(doc);
            for (float dpi : DPIS) {
                for (ImageType type : TYPES) {
                    BufferedImage img = renderer.renderImageWithDPI(page, dpi, type);
                    int w = img.getWidth();
                    int h = img.getHeight();
                    int awtType = img.getType();
                    int numBands = img.getRaster().getNumBands();
                    StringBuilder sb = new StringBuilder();
                    sb.append(dpi).append(' ').append(type.name()).append(' ')
                        .append(w).append(' ').append(h).append(' ')
                        .append(awtType).append(' ').append(numBands).append(": ");
                    sb.append(grid(img, w, h));
                    out.println(sb.toString());
                }
            }
        }
    }

    private static String grid(BufferedImage img, int w, int h) {
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
                sb.append(',');
            }
            long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
            sb.append(avg);
        }
        return sb.toString();
    }
}
