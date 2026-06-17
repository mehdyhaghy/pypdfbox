import java.awt.Color;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.PrintStream;
import java.util.Arrays;
import javax.imageio.ImageIO;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.color.PDColor;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB;
import org.apache.pdfbox.pdmodel.graphics.form.PDFormXObject;
import org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.tools.ExtractImages;
import org.apache.pdfbox.util.Matrix;
import picocli.CommandLine;

/**
 * Differential-fuzz oracle probe for the {@code ExtractImages} CLI tool over a
 * battery of small, deterministically-built PDFs. Where
 * {@code ExtractImagesToolProbe} pins the graphics-engine walk on one fixture
 * and {@code ExtractImagesWrite2FileProbe} pins the {@code write2file} dispatch
 * on a four-image fixture, this probe sweeps many *scenario* PDFs and projects,
 * per scenario, the set of produced files (count + name + suffix + decoded
 * dimensions) so the tool's high-level extraction contract can be compared
 * end-to-end against pypdfbox.
 *
 * <p>Scenarios (each its own PDF, each run through the real CLI):
 * <ol>
 *   <li>{@code single_rgb} — one flate RGB image → one .png,</li>
 *   <li>{@code single_jpeg} — one DCT RGB image → one .jpg (passthrough),</li>
 *   <li>{@code multi} — three distinct images on one page,</li>
 *   <li>{@code dedup_same_page} — same XObject drawn twice on one page → 1,</li>
 *   <li>{@code dedup_cross_page} — same XObject drawn on two pages → 1,</li>
 *   <li>{@code no_images} — a page that draws no images → 0,</li>
 *   <li>{@code unreferenced} — image in resources but never Do'd → 0,</li>
 *   <li>{@code direct_jpeg} — DCT image with -useDirectJPEG → 1 .jpg,</li>
 *   <li>{@code indexed} — an Indexed-colorspace image → .png,</li>
 *   <li>{@code mask} — image with an explicit /Mask → .png (no passthrough),</li>
 *   <li>{@code stencil} — a 1-bit image-mask (ImageMask true) → .png,</li>
 *   <li>{@code nested_form} — image drawn inside a form XObject → 1,</li>
 *   <li>{@code multipage} — three pages, one distinct image each → 3,</li>
 *   <li>{@code gray} — a DeviceGray flate image → .png,</li>
 *   <li>{@code mixed} — jpeg + flate + dedup'd jpeg across two pages → 2.</li>
 * </ol>
 *
 * <p>Output: UTF-8 to stdout, per scenario a line
 * {@code scenario <name> count <n>} followed by {@code  file <name> <wxh>}
 * lines (files sorted by name; dim is {@code -} when the file can't be decoded
 * by ImageIO, e.g. a TIFF without a codec).
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> ExtractImagesToolFuzzProbe <workdir>}
 */
public final class ExtractImagesToolFuzzProbe {

    static PrintStream out;

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File work = new File(args[0]);
        work.mkdirs();

        scenario(work, "single_rgb", false, b -> {
            PDImageXObject img = LosslessFactory.createFromImage(b.doc, gradient(6, 4, 1));
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(img, new Matrix(60, 0, 0, 40, 10, 10));
            }
        });

        scenario(work, "single_jpeg", false, b -> {
            PDImageXObject img = JPEGFactory.createFromImage(b.doc, gradient(16, 12, 2));
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(img, new Matrix(160, 0, 0, 120, 10, 10));
            }
        });

        scenario(work, "multi", false, b -> {
            PDImageXObject a = LosslessFactory.createFromImage(b.doc, gradient(6, 4, 1));
            PDImageXObject c = JPEGFactory.createFromImage(b.doc, gradient(16, 12, 2));
            PDImageXObject d = LosslessFactory.createFromImage(b.doc, gradient(8, 8, 3));
            PDPage p = b.page(300, 300);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(a, new Matrix(60, 0, 0, 40, 10, 10));
                cs.drawImage(c, new Matrix(160, 0, 0, 120, 10, 150));
                cs.drawImage(d, new Matrix(80, 0, 0, 80, 200, 10));
            }
        });

        scenario(work, "dedup_same_page", false, b -> {
            PDImageXObject a = LosslessFactory.createFromImage(b.doc, gradient(6, 4, 1));
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(a, new Matrix(60, 0, 0, 40, 10, 10));
                cs.drawImage(a, new Matrix(60, 0, 0, 40, 10, 100));
            }
        });

        scenario(work, "dedup_cross_page", false, b -> {
            PDImageXObject a = LosslessFactory.createFromImage(b.doc, gradient(6, 4, 1));
            PDPage p0 = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p0)) {
                cs.drawImage(a, new Matrix(60, 0, 0, 40, 10, 10));
            }
            PDPage p1 = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p1)) {
                cs.drawImage(a, new Matrix(60, 0, 0, 40, 10, 10));
            }
        });

        scenario(work, "no_images", false, b -> {
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.setNonStrokingColor(new PDColor(new float[] {0.2f, 0.4f, 0.6f},
                        PDDeviceRGB.INSTANCE));
                cs.addRect(10, 10, 100, 100);
                cs.fill();
            }
        });

        scenario(work, "unreferenced", false, b -> {
            PDImageXObject a = LosslessFactory.createFromImage(b.doc, gradient(6, 4, 1));
            PDPage p = b.page(200, 200);
            // Put the image into resources but never emit a Do operator for it.
            PDResources res = new PDResources();
            res.add(a);
            p.setResources(res);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p,
                    PDPageContentStream.AppendMode.APPEND, false)) {
                cs.setNonStrokingColor(new PDColor(new float[] {0f}, PDDeviceGray.INSTANCE));
                cs.addRect(5, 5, 20, 20);
                cs.fill();
            }
        });

        scenario(work, "direct_jpeg", true, b -> {
            PDImageXObject img = JPEGFactory.createFromImage(b.doc, gradient(16, 12, 2));
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(img, new Matrix(160, 0, 0, 120, 10, 10));
            }
        });

        scenario(work, "indexed", false, b -> {
            PDImageXObject img = indexedImage(b.doc);
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(img, new Matrix(80, 0, 0, 80, 10, 10));
            }
        });

        scenario(work, "mask", false, b -> {
            PDImageXObject base = LosslessFactory.createFromImage(b.doc, gradient(8, 8, 5));
            // explicit stencil /Mask
            BufferedImage m = new BufferedImage(8, 8, BufferedImage.TYPE_BYTE_BINARY);
            for (int y = 0; y < 8; y++) {
                for (int x = 0; x < 8; x++) {
                    m.setRGB(x, y, ((x + y) % 2 == 0) ? 0xFFFFFF : 0x000000);
                }
            }
            PDImageXObject mask = LosslessFactory.createFromImage(b.doc, m);
            mask.getCOSObject().setBoolean(COSName.IMAGE_MASK, true);
            mask.getCOSObject().removeItem(COSName.COLORSPACE);
            base.getCOSObject().setItem(COSName.MASK, mask);
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(base, new Matrix(80, 0, 0, 80, 10, 10));
            }
        });

        scenario(work, "stencil", false, b -> {
            BufferedImage m = new BufferedImage(8, 8, BufferedImage.TYPE_BYTE_BINARY);
            for (int y = 0; y < 8; y++) {
                for (int x = 0; x < 8; x++) {
                    m.setRGB(x, y, ((x) % 2 == 0) ? 0xFFFFFF : 0x000000);
                }
            }
            PDImageXObject stencil = LosslessFactory.createFromImage(b.doc, m);
            stencil.getCOSObject().setBoolean(COSName.IMAGE_MASK, true);
            stencil.getCOSObject().removeItem(COSName.COLORSPACE);
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.setNonStrokingColor(new PDColor(new float[] {0.1f, 0.2f, 0.3f},
                        PDDeviceRGB.INSTANCE));
                cs.drawImage(stencil, new Matrix(80, 0, 0, 80, 10, 10));
            }
        });

        scenario(work, "nested_form", false, b -> {
            PDImageXObject a = LosslessFactory.createFromImage(b.doc, gradient(6, 4, 7));
            PDFormXObject form = new PDFormXObject(b.doc);
            form.setBBox(new PDRectangle(0, 0, 100, 100));
            PDResources formRes = new PDResources();
            COSName imgName = formRes.add(a);
            form.setResources(formRes);
            // Hand-write the form's content stream: scale CTM then Do the image.
            String formContent = "q 60 0 0 40 10 10 cm /" + imgName.getName() + " Do Q";
            try (java.io.OutputStream os = form.getContentStream().createOutputStream()) {
                os.write(formContent.getBytes("US-ASCII"));
            }
            PDPage p = b.page(200, 200);
            PDResources res = new PDResources();
            COSName formNm = res.add(form);
            p.setResources(res);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p,
                    PDPageContentStream.AppendMode.APPEND, false)) {
                cs.drawForm(form);
            }
        });

        scenario(work, "multipage", false, b -> {
            for (int i = 0; i < 3; i++) {
                PDImageXObject a = LosslessFactory.createFromImage(b.doc, gradient(6, 4, 10 + i));
                PDPage p = b.page(200, 200);
                try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                    cs.drawImage(a, new Matrix(60, 0, 0, 40, 10, 10));
                }
            }
        });

        scenario(work, "gray", false, b -> {
            BufferedImage g = new BufferedImage(8, 6, BufferedImage.TYPE_BYTE_GRAY);
            for (int y = 0; y < 6; y++) {
                for (int x = 0; x < 8; x++) {
                    int v = (x * 30 + y * 10) & 0xFF;
                    g.setRGB(x, y, new Color(v, v, v).getRGB());
                }
            }
            PDImageXObject img = LosslessFactory.createFromImage(b.doc, g);
            PDPage p = b.page(200, 200);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p)) {
                cs.drawImage(img, new Matrix(80, 0, 0, 60, 10, 10));
            }
        });

        scenario(work, "mixed", false, b -> {
            PDImageXObject jpeg = JPEGFactory.createFromImage(b.doc, gradient(16, 12, 2));
            PDImageXObject flate = LosslessFactory.createFromImage(b.doc, gradient(8, 6, 3));
            PDPage p0 = b.page(300, 300);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p0)) {
                cs.drawImage(jpeg, new Matrix(160, 0, 0, 120, 10, 10));
                cs.drawImage(flate, new Matrix(80, 0, 0, 60, 10, 150));
            }
            PDPage p1 = b.page(300, 300);
            try (PDPageContentStream cs = new PDPageContentStream(b.doc, p1)) {
                cs.drawImage(jpeg, new Matrix(160, 0, 0, 120, 10, 10));
            }
        });
    }

    interface Builder {
        void build(Ctx ctx) throws IOException;
    }

    static final class Ctx {
        final PDDocument doc;

        Ctx(PDDocument doc) {
            this.doc = doc;
        }

        PDPage page(float w, float h) {
            PDPage p = new PDPage(new PDRectangle(0, 0, w, h));
            doc.addPage(p);
            return p;
        }
    }

    static void scenario(File work, String name, boolean directJpeg, Builder builder)
            throws IOException {
        File pdf = new File(work, name + ".pdf");
        try (PDDocument doc = new PDDocument()) {
            builder.build(new Ctx(doc));
            doc.save(pdf);
        }

        File outDir = new File(work, name + "_out");
        outDir.mkdirs();
        String prefix = new File(outDir, "img").getAbsolutePath();

        PrintStream realOut = System.out;
        System.setOut(new PrintStream(new ByteArrayOutputStream()));
        try {
            if (directJpeg) {
                new CommandLine(new ExtractImages())
                        .execute("-i", pdf.getAbsolutePath(), "-prefix", prefix,
                                "-useDirectJPEG");
            } else {
                new CommandLine(new ExtractImages())
                        .execute("-i", pdf.getAbsolutePath(), "-prefix", prefix);
            }
        } finally {
            System.setOut(realOut);
        }

        File[] produced = outDir.listFiles();
        if (produced == null) {
            produced = new File[0];
        }
        Arrays.sort(produced, (x, y) -> x.getName().compareTo(y.getName()));
        out.println("scenario " + name + " count " + produced.length);
        for (File f : produced) {
            out.println("  file " + f.getName() + " " + dim(f));
        }
    }

    static String dim(File f) {
        try {
            BufferedImage bi = ImageIO.read(f);
            if (bi == null) {
                return "-";
            }
            return bi.getWidth() + "x" + bi.getHeight();
        } catch (IOException ex) {
            return "-";
        }
    }

    static PDImageXObject indexedImage(PDDocument doc) throws IOException {
        // 4-color palette indexed image, 8x8.
        byte[] palette = new byte[] {
            (byte) 0xFF, 0, 0,
            0, (byte) 0xFF, 0,
            0, 0, (byte) 0xFF,
            (byte) 0xFF, (byte) 0xFF, 0,
        };
        java.awt.image.IndexColorModel icm = new java.awt.image.IndexColorModel(
                2, 4, palette, 0, false);
        BufferedImage bi = new BufferedImage(8, 8, BufferedImage.TYPE_BYTE_INDEXED, icm);
        for (int y = 0; y < 8; y++) {
            for (int x = 0; x < 8; x++) {
                bi.getRaster().setSample(x, y, 0, (x + y) % 4);
            }
        }
        return LosslessFactory.createFromImage(doc, bi);
    }

    static BufferedImage gradient(int w, int h, int seed) {
        BufferedImage bi = new BufferedImage(w, h, BufferedImage.TYPE_INT_RGB);
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                int r = (x * 13 + seed) & 0xFF;
                int g = (y * 17 + seed) & 0xFF;
                int b = (x * y + seed) & 0xFF;
                bi.setRGB(x, y, new Color(r, g, b).getRGB());
            }
        }
        return bi;
    }

    private ExtractImagesToolFuzzProbe() {}
}
