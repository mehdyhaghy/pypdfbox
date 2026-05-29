import java.awt.Color;
import java.awt.image.BufferedImage;
import java.io.File;
import java.io.IOException;
import java.io.PrintStream;
import java.util.HashSet;
import java.util.Set;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.PDFGraphicsStreamEngine;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImage;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.util.Matrix;
import org.apache.pdfbox.util.Vector;

/**
 * Live oracle probe for the {@code org.apache.pdfbox.tools.ExtractImages} tool
 * surface: the per-page graphics-engine walk that {@code ImageGraphicsEngine}
 * performs to collect the images a page actually <em>draws</em>, the de-dup of
 * a repeated image by its COS object identity, and the per-image identity
 * (output name, dimensions, bits-per-component, colorspace, file suffix).
 *
 * <p>Unlike a raw {@code PDResources.getXObjectNames()} walk, the tool only
 * extracts images reached through {@code Do} operators (so an unreferenced
 * resource is skipped), counts them in draw order, and the de-dup set means a
 * single physical image drawn N times is extracted once.
 *
 * <p>The probe first builds a deterministic two-page fixture so both engines
 * compare on identical bytes:
 * <ul>
 *   <li>page 0 draws image A (4x3 RGB), then image B (2x2 RGB), then image A
 *       again — de-dup must collapse the third draw,</li>
 *   <li>page 1 draws image B again (a separate physical XObject) once.</li>
 * </ul>
 *
 * <p>It then runs an {@code ImageGraphicsEngine} clone over each page and emits,
 * UTF-8 to stdout, one line per extracted image:
 * <pre>
 *   page &lt;p&gt; img &lt;name&gt; w &lt;w&gt; h &lt;h&gt; bpc &lt;bpc&gt; cs &lt;cs&gt; suffix &lt;sx&gt;
 * </pre>
 * followed by a {@code total &lt;n&gt;} trailer. {@code name} mirrors the tool's
 * {@code prefix-counter} numbering (counter starts at 1, never resets across
 * pages); the de-dup set is shared across the whole document.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; ExtractImagesToolProbe out.pdf
 */
public final class ExtractImagesToolProbe {

    static PrintStream out;

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File tmp = new File(args[0]);
        build(tmp);

        try (PDDocument doc = Loader.loadPDF(tmp)) {
            Counter ctr = new Counter();
            Set<COSBase> seen = new HashSet<>();
            for (int p = 0; p < doc.getNumberOfPages(); p++) {
                PDPage page = doc.getPage(p);
                Engine engine = new Engine(page, p, ctr, seen);
                engine.processPage(page);
            }
            out.println("total " + (ctr.value - 1));
        }
    }

    /** Shared image-output counter (mirrors ExtractImages.imageCounter). */
    static final class Counter {
        int value = 1;
    }

    /** A deterministic w-by-h RGB image with a fixed gradient pattern. */
    static BufferedImage fixedImage(int w, int h, int seed) {
        BufferedImage bi = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int r = (x * 50 + seed) & 0xFF;
                int g = (y * 70 + seed) & 0xFF;
                int b = (seed * 13) & 0xFF;
                bi.setRGB(x, y, new Color(r, g, b).getRGB());
            }
        }
        return bi;
    }

    static void build(File tmp) throws IOException {
        try (PDDocument doc = new PDDocument()) {
            PDImageXObject imgA = LosslessFactory.createFromImage(doc, fixedImage(4, 3, 1));
            PDImageXObject imgB = LosslessFactory.createFromImage(doc, fixedImage(2, 2, 2));

            PDPage page0 = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page0);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page0)) {
                cs.drawImage(imgA, new Matrix(40, 0, 0, 30, 10, 10));
                cs.drawImage(imgB, new Matrix(20, 0, 0, 20, 100, 100));
                // Draw A again: de-dup must collapse this.
                cs.drawImage(imgA, new Matrix(40, 0, 0, 30, 10, 200));
            }

            // Second physical image B' on page 1 (distinct XObject).
            PDImageXObject imgB2 = LosslessFactory.createFromImage(doc, fixedImage(2, 2, 2));
            PDPage page1 = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page1);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page1)) {
                cs.drawImage(imgB2, new Matrix(20, 0, 0, 20, 50, 50));
            }
            doc.save(tmp);
        }
    }

    /** A trimmed clone of {@code ExtractImages.ImageGraphicsEngine}. */
    static final class Engine extends PDFGraphicsStreamEngine {
        private final int pageIndex;
        private final Counter counter;
        private final Set<COSBase> seen;

        Engine(PDPage page, int pageIndex, Counter counter, Set<COSBase> seen) {
            super(page);
            this.pageIndex = pageIndex;
            this.counter = counter;
            this.seen = seen;
        }

        @Override
        public void drawImage(PDImage pdImage) throws IOException {
            if (pdImage instanceof PDImageXObject) {
                PDImageXObject xobj = (PDImageXObject) pdImage;
                if (seen.contains(xobj.getCOSObject())) {
                    return;
                }
                seen.add(xobj.getCOSObject());
            }
            String name = "img-" + counter.value;
            counter.value++;
            emit(name, pdImage);
        }

        private void emit(String name, PDImage pdImage) throws IOException {
            int w = pdImage.getWidth();
            int h = pdImage.getHeight();
            int bpc = pdImage.getBitsPerComponent();
            PDColorSpace colorSpace = pdImage.getColorSpace();
            String cs = colorSpace != null ? colorSpace.getName() : "null";
            String suffix = pdImage.getSuffix();
            if (suffix == null) {
                suffix = "png";
            }
            if (suffix.equals("jb2")) {
                suffix = "png";
            } else if (suffix.equals("jpx")) {
                suffix = "jp2";
            }
            out.println("page " + pageIndex + " img " + name
                    + " w " + w + " h " + h + " bpc " + bpc
                    + " cs " + cs + " suffix " + suffix);
        }

        // --- empty overrides (mirror the tool's "Empty:" stubs) -------------
        @Override
        public void appendRectangle(java.awt.geom.Point2D p0, java.awt.geom.Point2D p1,
                java.awt.geom.Point2D p2, java.awt.geom.Point2D p3) { }

        @Override
        public void clip(int windingRule) { }

        @Override
        public void moveTo(float x, float y) { }

        @Override
        public void lineTo(float x, float y) { }

        @Override
        public void curveTo(float x1, float y1, float x2, float y2, float x3, float y3) { }

        @Override
        public java.awt.geom.Point2D getCurrentPoint() {
            return new java.awt.geom.Point2D.Float(0, 0);
        }

        @Override
        public void closePath() { }

        @Override
        public void endPath() { }

        @Override
        public void strokePath() { }

        @Override
        public void fillPath(int windingRule) { }

        @Override
        public void fillAndStrokePath(int windingRule) { }

        @Override
        public void shadingFill(org.apache.pdfbox.cos.COSName shadingName) { }

        @Override
        public void showFontGlyph(Matrix textRenderingMatrix,
                org.apache.pdfbox.pdmodel.font.PDFont font, int code, Vector displacement) { }
    }
}
