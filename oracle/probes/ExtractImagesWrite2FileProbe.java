import java.awt.Color;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.PrintStream;
import java.security.MessageDigest;
import java.util.Map;
import java.util.TreeMap;
import javax.imageio.ImageIO;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.tools.ExtractImages;
import org.apache.pdfbox.util.Matrix;
import picocli.CommandLine;

/**
 * Live oracle probe for the {@code ExtractImages.write2file} dispatch: runs the
 * <em>real</em> {@code org.apache.pdfbox.tools.ExtractImages} CLI over a built
 * fixture PDF and reports, for each file the tool produced:
 *
 * <ul>
 *   <li>the output filename (so the {@code prefix-N.suffix} naming + extension
 *       dispatch can be pinned),</li>
 *   <li>{@code rawsha} — sha256 of the raw on-disk bytes (byte parity is
 *       achievable for the DCT JPEG passthrough path),</li>
 *   <li>{@code dim} + {@code pixsha} — width/height and a sha256 of the decoded
 *       RGB(A) pixel bytes (a reproducible digest that survives PNG-encoder
 *       differences between Java ImageIO and Pillow).</li>
 * </ul>
 *
 * <p>The fixture has four images so every {@code write2file} branch is hit:
 * <ol>
 *   <li>a plain DCT JPEG, RGB (passthrough -&gt; .jpg, byte parity),</li>
 *   <li>a flate-encoded lossless RGB image (-&gt; .png, pixel-digest parity),</li>
 *   <li>image #1 drawn a second time on page 2 (de-dup -&gt; no extra file),</li>
 *   <li>an /SMask'd JPEG (hasMasks -&gt; no passthrough -&gt; .png path).</li>
 * </ol>
 *
 * <p>Usage: {@code java -cp <pdfbox-app.jar>:<build> ExtractImagesWrite2FileProbe <fixture.pdf> <outdir>}
 * The fixture PDF and the output prefix dir are created by this probe.
 */
public final class ExtractImagesWrite2FileProbe {

    static PrintStream out;

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File pdf = new File(args[0]);
        File outDir = new File(args[1]);
        outDir.mkdirs();
        build(pdf);

        String prefix = new File(outDir, "img").getAbsolutePath();
        // Run the real tool via picocli (does NOT call System.exit, unlike
        // ExtractImages.main). Silence its "Writing image:" stdout chatter so
        // only the probe's parity lines reach our captured stdout.
        PrintStream realOut = System.out;
        System.setOut(new PrintStream(new ByteArrayOutputStream()));
        try {
            new CommandLine(new ExtractImages())
                    .execute("-i", pdf.getAbsolutePath(), "-prefix", prefix);
        } finally {
            System.setOut(realOut);
        }

        // Collect the files the tool produced, sorted by name for stability.
        File[] produced = outDir.listFiles();
        if (produced == null) {
            produced = new File[0];
        }
        TreeMap<String, File> byName = new TreeMap<>();
        for (File f : produced) {
            byName.put(f.getName(), f);
        }

        out.println("count " + byName.size());
        for (Map.Entry<String, File> e : byName.entrySet()) {
            File f = e.getValue();
            String rawSha = sha256(readAll(f));
            String line = "file " + e.getKey() + " rawsha " + rawSha;
            int[] dim = new int[2];
            String pixSha = pixelDigest(f, dim);
            if (pixSha != null) {
                line += " dim " + dim[0] + "x" + dim[1] + " pixsha " + pixSha;
            }
            out.println(line);
        }
    }

    static void build(File pdf) throws IOException {
        try (PDDocument doc = new PDDocument()) {
            // (1) plain DCT JPEG, RGB
            PDImageXObject jpeg = JPEGFactory.createFromImage(doc, gradient(16, 12, 7));
            // (2) flate lossless RGB
            PDImageXObject flate = LosslessFactory.createFromImage(doc, gradient(8, 6, 3));
            // (4) /SMask'd JPEG: JPEG base + a soft mask
            BufferedImage argb = new BufferedImage(10, 10, BufferedImage.TYPE_INT_ARGB);
            for (int y = 0; y < 10; y++) {
                for (int x = 0; x < 10; x++) {
                    int a = (x * 25) & 0xFF;
                    argb.setRGB(x, y, (a << 24) | (0x3366CC));
                }
            }
            PDImageXObject masked = JPEGFactory.createFromImage(doc, argb);

            PDPage page0 = new PDPage(new PDRectangle(0, 0, 400, 400));
            doc.addPage(page0);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page0)) {
                cs.drawImage(jpeg, new Matrix(160, 0, 0, 120, 10, 10));
                cs.drawImage(flate, new Matrix(80, 0, 0, 60, 10, 200));
                cs.drawImage(masked, new Matrix(100, 0, 0, 100, 200, 200));
            }

            // (3) page 1 redraws the SAME jpeg XObject: de-dup, no extra file.
            PDPage page1 = new PDPage(new PDRectangle(0, 0, 400, 400));
            doc.addPage(page1);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page1)) {
                cs.drawImage(jpeg, new Matrix(160, 0, 0, 120, 10, 10));
            }
            doc.save(pdf);
        }
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

    static byte[] readAll(File f) throws IOException {
        try (InputStream in = new FileInputStream(f)) {
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                bos.write(buf, 0, n);
            }
            return bos.toByteArray();
        }
    }

    /** Decode the image file and digest its RGB(A) pixel bytes, row-major. */
    static String pixelDigest(File f, int[] dimOut) {
        try {
            BufferedImage bi = ImageIO.read(f);
            if (bi == null) {
                return null;
            }
            int w = bi.getWidth();
            int h = bi.getHeight();
            dimOut[0] = w;
            dimOut[1] = h;
            boolean alpha = bi.getColorModel().hasAlpha();
            ByteArrayOutputStream bos = new ByteArrayOutputStream();
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int argb = bi.getRGB(x, y);
                    bos.write((argb >> 16) & 0xFF);
                    bos.write((argb >> 8) & 0xFF);
                    bos.write(argb & 0xFF);
                    if (alpha) {
                        bos.write((argb >> 24) & 0xFF);
                    }
                }
            }
            return sha256(bos.toByteArray());
        } catch (IOException ex) {
            return null;
        }
    }

    static String sha256(byte[] data) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] d = md.digest(data);
            StringBuilder sb = new StringBuilder();
            for (byte b : d) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception ex) {
            return "ERR";
        }
    }

    private ExtractImagesWrite2FileProbe() {}
}
