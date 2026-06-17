import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit the exact ARGB of one or more pixels from a page
 * rendered by Apache PDFBox at 72 DPI.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PixelSampleProbe input.pdf pageIndex x0,y0 x1,y1 ...
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   one line per requested coordinate: "<r> <g> <b>" (each 0..255)
 *
 * Unlike RenderProbe's 16x16 luminance fingerprint, this reports the exact
 * per-channel colour at a point, so a per-channel blend-mode formula error
 * (which a grey-luminance average can mask) is caught directly.
 */
public final class PixelSampleProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(page, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);
            for (int i = 2; i < args.length; i++) {
                String[] xy = args[i].split(",");
                int x = Integer.parseInt(xy[0].trim());
                int y = Integer.parseInt(xy[1].trim());
                int rgb = img.getRGB(x, y);
                int r = (rgb >> 16) & 0xFF;
                int g = (rgb >> 8) & 0xFF;
                int b = rgb & 0xFF;
                out.println(r + " " + g + " " + b);
            }
        }
    }
}
