import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Differential fuzz probe for the RENDER-TIME axial (type 2) / radial (type 3)
 * shading paint, Apache PDFBox 3.0.7 (wave 1560, agent A).
 *
 * <p>Distinct angle from the per-pixel sample probes already in this tree
 * ({@code ShadingPixelProbe} drives explicit (x,y) RGB lookups for the domain
 * remap / background / degenerate-cone cases of waves 1484/1488): this probe
 * projects COARSE whole-page facts about the painted gradient so a wrong
 * gradient <em>direction</em>, a dropped {@code /Extend} region, or a degenerate
 * shading that should-or-should-not paint surfaces structurally rather than at a
 * single hand-picked pixel. It also exercises angles those tests do not: a
 * diagonal (non-axis-aligned) axial axis, an eccentric (offset-centre) nested
 * radial gradient, a type-3 stitching-function gradient, and a zero-length axis
 * / zero-radius degenerate shading.
 *
 * <p>The pypdfbox sibling
 * (tests/rendering/oracle/test_shading_paint_fuzz_wave1560.py) writes one
 * 100x100 PDF per case (a single {@code /Sh0 sh} clipped to the page) plus a
 * {@code manifest.txt} (one case name per line, in order) into a tmp directory.
 * Both sides render the same bytes at 72 DPI (1:1 device pixels) and project the
 * same facts.
 *
 * <p>Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; dims=&lt;w&gt;x&lt;h&gt; bbox=&lt;x0,y0,x1,y1|none&gt; painted=&lt;n&gt; colors=&lt;bucket&gt; p=&lt;r,g,b&gt;;&lt;r,g,b&gt;;...
 * </pre>
 * where {@code bbox} is the bounding box of all non-white pixels (or
 * {@code none} when nothing was painted), {@code painted} is the count of
 * non-white pixels bucketed to the nearest 200 (coarse — rasteriser AA differs),
 * {@code colors} buckets the distinct-colour count (1, few=2..8, many=9+) so a
 * flat fill vs a real gradient is distinguishable without pinning exact AA, and
 * {@code p=} lists the RGB at the case's probe points (passed by the sibling as
 * extra args after the dir, as flat x y x y ... but the SAME for every case via
 * a shared point set written into the manifest line — see below).
 *
 * <p>To keep the probe self-describing each manifest line is just the case
 * name; the probe samples a FIXED diagonal point set (centre, the four
 * mid-edges, the four corners) so the sibling can compare the same nine RGB
 * triples without per-case argument plumbing.
 */
public final class ShadingPaintFuzzProbe {

    static PrintStream out;

    // Fixed sample points on a 100x100 render: centre, mid-edges, corners.
    static final int[][] POINTS = {
        {50, 50}, {50, 5}, {50, 95}, {5, 50}, {95, 50},
        {5, 5}, {95, 5}, {5, 95}, {95, 95},
    };

    static boolean isWhite(int rgb) {
        int r = (rgb >> 16) & 0xFF;
        int g = (rgb >> 8) & 0xFF;
        int b = rgb & 0xFF;
        // Treat the unpainted page (and AA fringe to white) as white.
        return r >= 250 && g >= 250 && b >= 250;
    }

    static String colorBucket(int distinct) {
        if (distinct <= 1) {
            return "1";
        }
        if (distinct <= 8) {
            return "few";
        }
        return "many";
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        PDDocument doc = null;
        try {
            doc = Loader.loadPDF(pdf);
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(0, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            sb.append("dims=").append(w).append('x').append(h).append(' ');

            int minX = w;
            int minY = h;
            int maxX = -1;
            int maxY = -1;
            int painted = 0;
            Set<Integer> distinct = new HashSet<>();
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int rgb = img.getRGB(x, y);
                    if (!isWhite(rgb)) {
                        painted++;
                        if (x < minX) {
                            minX = x;
                        }
                        if (x > maxX) {
                            maxX = x;
                        }
                        if (y < minY) {
                            minY = y;
                        }
                        if (y > maxY) {
                            maxY = y;
                        }
                        // Quantise to a 16-level cube so AA dithering does not
                        // explode the distinct count; a flat fill stays 1.
                        int r = ((rgb >> 16) & 0xFF) >> 4;
                        int g = ((rgb >> 8) & 0xFF) >> 4;
                        int b = (rgb & 0xFF) >> 4;
                        distinct.add((r << 8) | (g << 4) | b);
                    }
                }
            }
            if (maxX < 0) {
                sb.append("bbox=none ");
            } else {
                sb.append("bbox=").append(minX).append(',').append(minY)
                        .append(',').append(maxX).append(',').append(maxY)
                        .append(' ');
            }
            int paintedBucket = ((painted + 100) / 200) * 200;
            sb.append("painted=").append(paintedBucket).append(' ');
            sb.append("colors=").append(colorBucket(distinct.size())).append(' ');

            sb.append("p=");
            for (int i = 0; i < POINTS.length; i++) {
                int cx = Math.max(0, Math.min(w - 1, POINTS[i][0]));
                int cy = Math.max(0, Math.min(h - 1, POINTS[i][1]));
                int rgb = img.getRGB(cx, cy);
                int r = (rgb >> 16) & 0xFF;
                int g = (rgb >> 8) & 0xFF;
                int b = rgb & 0xFF;
                if (i > 0) {
                    sb.append(';');
                }
                sb.append(r).append(',').append(g).append(',').append(b);
            }
        } catch (Exception e) {
            sb.append("dims=ERR bbox=ERR painted=ERR colors=ERR p=ERR:")
                    .append(e.getClass().getSimpleName());
        } finally {
            close(doc);
        }
        out.println(sb.toString());
    }

    static void close(PDDocument doc) {
        if (doc != null) {
            try {
                doc.close();
            } catch (Exception ignored) {
                // best-effort close
            }
        }
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        File dir = new File(args[0]);
        File manifest = new File(dir, "manifest.txt");
        String[] names =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        Arrays.stream(names)
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .forEach(name -> runCase(dir, name));
    }
}
