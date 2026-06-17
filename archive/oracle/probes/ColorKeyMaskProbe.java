import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe: emit the ARGB result of the FIRST image XObject's
 * {@code PDImageXObject.getImage()} on page 0, as a coarse downsampled RGBA
 * grid. This is the direct surface for color-key {@code /Mask} parity
 * (PDF 32000-1 §8.9.6.4) on a NON-RGB image (DeviceGray / DeviceCMYK /
 * Indexed): {@code getImage()} composites the color-keyed samples as fully
 * transparent (alpha 0) pixels, so a renderer that keys the wrong components
 * (e.g. comparing the converted sRGB pixels rather than the raw native samples)
 * leaves the wrong cells opaque.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ColorKeyMaskProbe input.pdf
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — getImage() pixel dimensions
 *   line 2: GRID*GRID*4 comma-separated ints (0..255) — an 8x8 grid of
 *           average (R,G,B,A) per cell, row-major, each cell's four channels
 *           consecutive: r0,g0,b0,a0, r1,g1,b1,a1, ...
 *
 * Averaging alpha per cell keeps the comparison tolerance-friendly (PIL vs
 * Java2D sample rounding) while still pinning which cells are keyed
 * transparent (alpha ~0) vs opaque (alpha 255).
 */
public final class ColorKeyMaskProbe {
    private static final int GRID = 8;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);
            PDResources resources = page.getResources();
            PDImageXObject image = null;
            for (COSName name : resources.getXObjectNames()) {
                PDXObject xobj = resources.getXObject(name);
                if (xobj instanceof PDImageXObject) {
                    image = (PDImageXObject) xobj;
                    break;
                }
            }
            if (image == null) {
                out.println("0 0");
                out.println("");
                return;
            }
            BufferedImage img = image.getImage();
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);

            long[] sr = new long[GRID * GRID];
            long[] sg = new long[GRID * GRID];
            long[] sb = new long[GRID * GRID];
            long[] sa = new long[GRID * GRID];
            long[] cnt = new long[GRID * GRID];
            boolean hasAlpha = img.getColorModel().hasAlpha();
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
                    int argb = img.getRGB(x, y);
                    int a = hasAlpha ? ((argb >> 24) & 0xFF) : 255;
                    int idx = cy * GRID + cx;
                    sr[idx] += (argb >> 16) & 0xFF;
                    sg[idx] += (argb >> 8) & 0xFF;
                    sb[idx] += argb & 0xFF;
                    sa[idx] += a;
                    cnt[idx] += 1;
                }
            }
            StringBuilder sb2 = new StringBuilder();
            for (int i = 0; i < GRID * GRID; i++) {
                long c = cnt[i] > 0 ? cnt[i] : 1;
                appendCell(sb2, Math.round((double) sr[i] / c));
                appendCell(sb2, Math.round((double) sg[i] / c));
                appendCell(sb2, Math.round((double) sb[i] / c));
                appendCell(sb2, Math.round((double) sa[i] / c));
            }
            out.println(sb2.toString());
        }
    }

    private static void appendCell(StringBuilder sb, long value) {
        if (sb.length() > 0) {
            sb.append(',');
        }
        sb.append(value);
    }
}
