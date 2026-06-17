import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.DrawObject;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.state.Concatenate;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.contentstream.operator.state.SetGraphicsStateParameters;
import org.apache.pdfbox.contentstream.operator.state.SetMatrix;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage;

/**
 * Live oracle probe: decode every inline image (BI/ID/EI) on a page with
 * Apache PDFBox and emit a canonical, tolerance-comparable fingerprint per
 * image so pypdfbox's PDInlineImage decode can be compared against it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> InlineImgProbe input.pdf pageIndex
 * Output (UTF-8, to stdout), one block per inline image, in stream order:
 *   line 1: "<width> <height> <bpc> <colorSpaceName>"
 *   line 2: 256 space-separated integers (0..255) — a 16x16 grid of average
 *           luminance per cell of the decoded raster (getImage()), row-major.
 *
 * Pixel-exact parity across Java2D vs Pillow is impossible, so the raster
 * fingerprint is a coarse 16x16 downsampled grayscale grid that survives
 * codec / rounding differences while still catching gross divergences
 * (blank raster, wrong dimensions, garbled bytes, wrong colour space).
 */
public final class InlineImgProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int pageIndex = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(pageIndex);
            final List<String> blocks = new ArrayList<>();
            ProbeEngine engine = new ProbeEngine();
            // Register only the state operators the inline-image path needs so
            // PDFStreamEngine.processPage can run; the BI operator is built-in.
            engine.addOperator(new Concatenate(engine));
            engine.addOperator(new DrawObject(engine));
            engine.addOperator(new SetGraphicsStateParameters(engine));
            engine.addOperator(new Save(engine));
            engine.addOperator(new Restore(engine));
            engine.addOperator(new SetMatrix(engine));
            engine.addOperator(new InlineCollector(engine, blocks));
            engine.processPage(page);

            for (String b : blocks) {
                out.print(b);
            }
        }
    }

    /** Concrete PDFStreamEngine — we only need operator dispatch + resources. */
    static final class ProbeEngine extends PDFStreamEngine {
    }

    /** Collects + fingerprints each inline image as its BI operator is run. */
    static final class InlineCollector
            extends org.apache.pdfbox.contentstream.operator.OperatorProcessor {
        private final List<String> blocks;

        InlineCollector(PDFStreamEngine context, List<String> blocks) {
            super(context);
            this.blocks = blocks;
        }

        @Override
        public String getName() {
            return org.apache.pdfbox.contentstream.operator.OperatorName.BEGIN_INLINE_IMAGE;
        }

        @Override
        public void process(Operator operator, List<COSBase> operands) throws java.io.IOException {
            COSName imageName = COSName.getPDFName("inline");
            PDInlineImage image = new PDInlineImage(
                    operator.getImageParameters(),
                    operator.getImageData(),
                    getContext().getResources());
            blocks.add(fingerprint(image));
        }
    }

    static String fingerprint(PDInlineImage image) throws java.io.IOException {
        int width = image.getWidth();
        int height = image.getHeight();
        int bpc = image.getBitsPerComponent();
        String cs;
        try {
            cs = image.getColorSpace().getName();
        } catch (Exception e) {
            cs = "?";
        }
        StringBuilder sb = new StringBuilder();
        sb.append(width).append(' ').append(height).append(' ')
                .append(bpc).append(' ').append(cs).append('\n');

        BufferedImage img = image.getImage();
        long[] sum = new long[GRID * GRID];
        long[] cnt = new long[GRID * GRID];
        int w = img.getWidth();
        int h = img.getHeight();
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
        for (int i = 0; i < GRID * GRID; i++) {
            if (i > 0) {
                sb.append(' ');
            }
            long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
            sb.append(avg);
        }
        sb.append('\n');
        return sb.toString();
    }
}
