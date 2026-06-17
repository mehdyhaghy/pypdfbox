import java.awt.geom.Point2D;
import java.io.ByteArrayInputStream;
import java.io.PrintStream;
import java.util.LinkedHashMap;
import java.util.Map;
import org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.image.PDImage;
import org.apache.pdfbox.pdmodel.graphics.image.PDInlineImage;

/**
 * Live oracle probe (wave 1537): drive Apache PDFBox's graphics-level
 * {@code BeginInlineImage} OPERATOR-PROCESSOR — the {@code BI} dispatch that
 * builds a {@link PDInlineImage} from the parser-collated operator and forwards
 * it to {@code PDFGraphicsStreamEngine.drawImage} — over a battery of malformed
 * inline-image content streams, and project the observable result.
 *
 * <p>This complements {@code InlineImageFuzzProbe} (parser tokenisation only)
 * and {@code InlineImageDictProbe} / {@code InlineImageKeyResolveProbe} (dict +
 * key resolution) by exercising the OPERATOR's draw-dispatch guards: upstream
 * {@code BeginInlineImage.process} short-circuits (no draw) when the image data
 * is null/empty, when {@code image.isEmpty()}, and when the image is not a
 * stencil while colour operators are suppressed — otherwise it builds the
 * {@link PDInlineImage} and calls {@code drawImage}. The fuzz angle is therefore
 * "did a draw happen, with what assembled W/H/BPC/stencil/colour-space, or did a
 * throw escape the build?".
 *
 * <p>The probe wraps each case's content stream in a real {@code PDPage} and
 * calls {@code engine.processPage(page)} so the {@code BI} operator runs inside
 * the genuine {@code processStreamOperators} context (colour-operator flag set
 * true), exactly as a renderer drives it — rather than poking the operator in
 * isolation, which would leave the colour flag false and suppress every
 * non-stencil draw.
 *
 * <p>Output (UTF-8) is one block per case argument:
 * <pre>
 *   draws=&lt;n&gt; err=&lt;none|throw&gt;
 *   img w=&lt;W&gt; h=&lt;H&gt; bpc=&lt;BPC&gt; stencil=&lt;bool&gt; cs=&lt;name|throw|-&gt; empty=&lt;bool&gt;
 * </pre>
 * one {@code img} line per drawImage call. Exception CLASS names differ across
 * the port, so only the throw-vs-not fact is projected ({@code err=throw}).
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> InlineImageOperatorFuzzProbe <case>}
 */
public final class InlineImageOperatorFuzzProbe {

    /** Named fuzz cases — identical content-stream text to the pytest side. */
    static final Map<String, String> CASES = new LinkedHashMap<>();

    static {
        // A tiny 2x2 RGB raster: 2*2*3 = 12 bytes of payload (uncompressed).
        String rgb12 = "abcdefghijkl";
        CASES.put("rgb_2x2", "BI /W 2 /H 2 /BPC 8 /CS /RGB ID " + rgb12 + " EI");
        CASES.put("gray_2x2", "BI /W 2 /H 2 /BPC 8 /CS /G ID abcd EI");
        CASES.put("long_keys",
                "BI /Width 2 /Height 2 /BitsPerComponent 8 /ColorSpace /DeviceRGB ID "
                        + rgb12 + " EI");
        CASES.put("stencil", "BI /W 2 /H 2 /IM true ID ab EI");
        CASES.put("no_width", "BI /H 2 /BPC 8 /CS /G ID abcd EI");
        CASES.put("no_height", "BI /W 2 /BPC 8 /CS /G ID abcd EI");
        CASES.put("no_bpc", "BI /W 2 /H 2 /CS /G ID abcd EI");
        CASES.put("no_cs", "BI /W 2 /H 2 /BPC 8 ID abcd EI");
        CASES.put("empty_dict", "BI ID abcd EI");
        CASES.put("empty_data", "BI /W 2 /H 2 /BPC 8 /CS /G ID  EI");
        // ID immediately followed by EOL+EI -> zero-byte payload: upstream's
        // BeginInlineImage short-circuits (data.length == 0 -> no draw).
        CASES.put("zero_byte_data", "BI /W 1 /H 1 /BPC 8 /CS /G ID\nEI");
        CASES.put("zero_dim", "BI /W 0 /H 0 /BPC 8 /CS /G ID abcd EI");
        CASES.put("unknown_cs", "BI /W 2 /H 2 /BPC 8 /CS /Bogus ID abcd EI");
        CASES.put("cmyk", "BI /W 1 /H 1 /BPC 8 /CS /CMYK ID abcd EI");
        CASES.put("indexed",
                "BI /W 2 /H 2 /BPC 8 /CS [/I /RGB 1 <000000ffffff>] ID abcd EI");
        CASES.put("ei_no_bi", "EI");
        CASES.put("two_images",
                "BI /W 1 /H 1 /BPC 8 /CS /G ID a EI BI /W 1 /H 1 /BPC 8 /CS /RGB ID abc EI");
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String key = args[0];
        String content = CASES.get(key);
        if (content == null) {
            out.print("err=nocase\n");
            return;
        }
        byte[] bytes = content.getBytes("ISO-8859-1");

        StringBuilder sb = new StringBuilder();
        boolean threw = false;
        RecordingEngine engine;
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);
            PDStream stream = new PDStream(doc, new ByteArrayInputStream(bytes),
                    (COSName) null);
            page.setContents(stream);
            engine = new RecordingEngine(page);
            try {
                engine.processPage(page);
            } catch (Throwable t) {
                threw = true;
            }
        }
        sb.append("draws=").append(engine.images.size())
          .append(" err=").append(threw ? "throw" : "none").append('\n');
        for (PDImage img : engine.images) {
            sb.append("img w=").append(img.getWidth())
              .append(" h=").append(img.getHeight())
              .append(" bpc=").append(img.getBitsPerComponent())
              .append(" stencil=").append(img.isStencil())
              .append(" cs=").append(csName(img))
              .append(" empty=").append(img.isEmpty())
              .append('\n');
        }
        out.print(sb);
    }

    private static String csName(PDImage img) {
        try {
            return img.getColorSpace().getName();
        } catch (Throwable t) {
            return "throw";
        }
    }

    /** Minimal PDFGraphicsStreamEngine that records every drawImage call. */
    static final class RecordingEngine extends PDFGraphicsStreamEngine {
        final java.util.List<PDImage> images = new java.util.ArrayList<>();

        RecordingEngine(PDPage page) {
            super(page);
        }

        @Override
        public void drawImage(PDImage pdImage) {
            images.add(pdImage);
        }

        @Override
        public void appendRectangle(Point2D p0, Point2D p1, Point2D p2, Point2D p3) {
        }

        @Override
        public void clip(int windingRule) {
        }

        @Override
        public void moveTo(float x, float y) {
        }

        @Override
        public void lineTo(float x, float y) {
        }

        @Override
        public void curveTo(float x1, float y1, float x2, float y2, float x3, float y3) {
        }

        @Override
        public Point2D getCurrentPoint() {
            return new Point2D.Float(0, 0);
        }

        @Override
        public void closePath() {
        }

        @Override
        public void endPath() {
        }

        @Override
        public void strokePath() {
        }

        @Override
        public void fillPath(int windingRule) {
        }

        @Override
        public void fillAndStrokePath(int windingRule) {
        }

        @Override
        public void shadingFill(COSName shadingName) {
        }
    }
}
