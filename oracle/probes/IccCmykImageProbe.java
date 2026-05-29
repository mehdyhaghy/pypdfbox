import java.awt.image.BufferedImage;
import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDICCBased;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe for the {@code ICCBased N=4 CMYK image} surface
 * (PDF 32000-1 §8.6.5.5).
 *
 * <p>Builds an image XObject whose {@code /ColorSpace} is
 * {@code [/ICCBased <stream /N 4 /Alternate /DeviceCMYK>]} carrying a VALID
 * CMYK ICC profile (with an {@code A2B0} LUT, so AWT's CMM can build a real
 * CMYK to sRGB transform — distinct from the LUT-less profile in
 * {@code test_icc_image_render_oracle.py} that forces the {@code /Alternate}
 * fallback). The raw 8-bpc CMYK raster bytes and the ICC profile bytes are
 * read from files written by the Python side, so both CMMs (Java AWT and
 * Pillow/LittleCMS2) consume byte-identical inputs.
 *
 * <p>The probe exercises three surfaces of the resolved {@link PDICCBased} via
 * {@link PDImageXObject#getImage()}:
 * <ol>
 *   <li>{@code getColorSpace().getNumberOfComponents()} — must be 4.</li>
 *   <li>{@code getColorSpace().getInitialColor()} — the all-zero CMYK init
 *       colour (4 components, each 0.0).</li>
 *   <li>{@code getImage()} — drives {@code PDICCBased.toRGBImage(raster)}, the
 *       CMYK to sRGB conversion through the embedded profile.</li>
 * </ol>
 *
 * <p>Output is a single JSON object on one line (UTF-8):
 * <pre>
 *   {"n":4,"initial":[0.0,0.0,0.0,0.0],"alt":"DeviceCMYK",
 *    "width":W,"height":H,"grid":[r,g,b, r,g,b, ...]}
 * </pre>
 * where {@code grid} is a {@code GRID x GRID} row-major downsampled RGB grid
 * (average of each cell's pixels, 0..255 ints). The Python side runs the same
 * profile + raster through {@code PDImageXObject.get_image()} and gates the
 * grid with the tolerant MAD/MAXDIFF fingerprint (CMYK to RGB CMM output
 * differs slightly between Java's CMM and LittleCMS2).
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; IccCmykImageProbe
 *   profile.icc raster.cmyk width height grid
 */
public final class IccCmykImageProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] profile = Files.readAllBytes(Paths.get(args[0]));
        byte[] raster = Files.readAllBytes(Paths.get(args[1]));
        int width = Integer.parseInt(args[2]);
        int height = Integer.parseInt(args[3]);
        int grid = Integer.parseInt(args[4]);

        // Build [/ICCBased <stream /N 4 /Alternate /DeviceCMYK>].
        COSStream iccStream = new COSStream();
        iccStream.setInt(COSName.N, 4);
        iccStream.setItem(COSName.ALTERNATE, COSName.DEVICECMYK);
        OutputStream pos = iccStream.createOutputStream();
        pos.write(profile);
        pos.close();
        COSArray csArray = new COSArray();
        csArray.add(COSName.getPDFName("ICCBased"));
        csArray.add(iccStream);

        // Build the image XObject stream over the raw CMYK raster.
        COSStream imgStream = new COSStream();
        OutputStream ios = imgStream.createRawOutputStream();
        ios.write(raster);
        ios.close();
        imgStream.setItem(COSName.TYPE, COSName.XOBJECT);
        imgStream.setItem(COSName.SUBTYPE, COSName.IMAGE);
        imgStream.setInt(COSName.WIDTH, width);
        imgStream.setInt(COSName.HEIGHT, height);
        imgStream.setInt(COSName.BITS_PER_COMPONENT, 8);
        imgStream.setItem(COSName.COLORSPACE, csArray);

        PDImageXObject image = new PDImageXObject(new PDStream(imgStream), null);

        PDColorSpace cs = image.getColorSpace();
        int n = cs.getNumberOfComponents();
        float[] initial = cs.getInitialColor().getComponents();
        String alt = "none";
        if (cs instanceof PDICCBased) {
            PDColorSpace a = ((PDICCBased) cs).getAlternateColorSpace();
            if (a != null) {
                alt = a.getName();
            }
        }

        BufferedImage img = image.getImage();
        int w = img.getWidth();
        int h = img.getHeight();

        StringBuilder sb = new StringBuilder();
        sb.append('{');
        sb.append("\"n\":").append(n).append(',');
        sb.append("\"initial\":[");
        for (int i = 0; i < initial.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(fmt(initial[i]));
        }
        sb.append("],");
        sb.append("\"alt\":\"").append(alt).append("\",");
        sb.append("\"width\":").append(w).append(',');
        sb.append("\"height\":").append(h).append(',');
        sb.append("\"grid\":[").append(grid(img, w, h, grid)).append(']');
        sb.append('}');
        out.println(sb.toString());
    }

    /** {@code GRID x GRID} row-major downsampled RGB grid (cell averages). */
    private static String grid(BufferedImage img, int w, int h, int g) {
        long[] rs = new long[g * g];
        long[] gs = new long[g * g];
        long[] bs = new long[g * g];
        long[] cnt = new long[g * g];
        for (int y = 0; y < h; y++) {
            int cy = (int) ((long) y * g / h);
            if (cy >= g) {
                cy = g - 1;
            }
            for (int x = 0; x < w; x++) {
                int cx = (int) ((long) x * g / w);
                if (cx >= g) {
                    cx = g - 1;
                }
                int rgb = img.getRGB(x, y);
                int idx = cy * g + cx;
                rs[idx] += (rgb >> 16) & 0xFF;
                gs[idx] += (rgb >> 8) & 0xFF;
                bs[idx] += rgb & 0xFF;
                cnt[idx] += 1;
            }
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < g * g; i++) {
            if (i > 0) {
                sb.append(',');
            }
            long c = cnt[i] > 0 ? cnt[i] : 1;
            sb.append(Math.round((double) rs[i] / c)).append(',');
            sb.append(Math.round((double) gs[i] / c)).append(',');
            sb.append(Math.round((double) bs[i] / c));
        }
        return sb.toString();
    }

    private static String fmt(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Integer.toString((int) v) + ".0";
        }
        return Float.toString(v);
    }
}
