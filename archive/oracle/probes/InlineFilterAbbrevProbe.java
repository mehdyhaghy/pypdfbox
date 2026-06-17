import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFStreamEngine;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.contentstream.operator.state.Concatenate;
import org.apache.pdfbox.contentstream.operator.state.Restore;
import org.apache.pdfbox.contentstream.operator.state.Save;
import org.apache.pdfbox.contentstream.operator.state.SetMatrix;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage;

/**
 * Live oracle probe: the inline-image FILTER-ABBREVIATION decode facet
 * (PDF 32000-1 §8.9.7 Table 93). For every inline image (BI/ID/EI) on a
 * page, emit:
 *
 *   line 1: the verbatim getFilters() names (space-separated, as stored —
 *           PDFBox does NOT expand /AHx -> ASCIIHexDecode in getFilters();
 *           the expansion happens in FilterFactory.getFilter()).
 *   line 2: "LEN <decodedByteLength> HEX <lowercase-hex-of-getData()>"
 *           — byte-exact decoded payload, the strongest parity signal for
 *           the lossless abbreviations (AHx / A85 / LZW / Fl / RL).
 *   line 3: 256 space-separated integers — a 16x16 downsampled luminance
 *           grid of getImage(), the tolerance signal for lossy/codec
 *           filters (DCT / CCF) where byte-exact decode is impossible.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> InlineFilterAbbrevProbe in.pdf pageIdx
 */
public final class InlineFilterAbbrevProbe {
    private static final int GRID = 16;
    private static final char[] HEX = "0123456789abcdef".toCharArray();

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int pageIndex = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(pageIndex);
            final List<String> blocks = new ArrayList<>();
            ProbeEngine engine = new ProbeEngine();
            engine.addOperator(new Concatenate(engine));
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

    static final class ProbeEngine extends PDFStreamEngine {
    }

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
        public void process(Operator operator, List<COSBase> operands)
                throws java.io.IOException {
            PDInlineImage image = new PDInlineImage(
                    operator.getImageParameters(),
                    operator.getImageData(),
                    getContext().getResources());
            blocks.add(fingerprint(image));
        }
    }

    static String hex(byte[] data) {
        char[] c = new char[data.length * 2];
        for (int i = 0; i < data.length; i++) {
            int v = data[i] & 0xFF;
            c[i * 2] = HEX[v >>> 4];
            c[i * 2 + 1] = HEX[v & 0x0F];
        }
        return new String(c);
    }

    static String fingerprint(PDInlineImage image) throws java.io.IOException {
        StringBuilder sb = new StringBuilder();

        // line 1 — verbatim filter names.
        List<String> filters = image.getFilters();
        for (int i = 0; i < filters.size(); i++) {
            if (i > 0) {
                sb.append(' ');
            }
            sb.append(filters.get(i));
        }
        if (filters.isEmpty()) {
            sb.append('-');
        }
        sb.append('\n');

        // line 2 — decoded byte length + hex.
        byte[] decoded = image.getData();
        sb.append("LEN ").append(decoded.length).append(" HEX ")
                .append(hex(decoded)).append('\n');

        // line 3 — 16x16 luminance grid of getImage().
        BufferedImage img;
        try {
            img = image.getImage();
        } catch (Exception e) {
            img = null;
        }
        if (img == null) {
            sb.append("NOIMAGE\n");
            return sb.toString();
        }
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
