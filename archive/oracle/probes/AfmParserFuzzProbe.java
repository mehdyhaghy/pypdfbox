import java.io.ByteArrayInputStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import org.apache.fontbox.afm.CharMetric;
import org.apache.fontbox.afm.Composite;
import org.apache.fontbox.afm.FontMetrics;
import org.apache.fontbox.afm.KernPair;
import org.apache.fontbox.afm.AFMParser;
import org.apache.fontbox.util.BoundingBox;

/**
 * Live oracle probe for the lenient/strict AFM parse contract under malformed
 * input (wave 1522 differential font-parser fuzz; sibling of CffParserFuzzProbe
 * and AfmFontMetricsProbe).
 *
 * Reads raw (possibly corrupt) AFM bytes from a file, feeds them to FontBox's
 * {@link AFMParser} via the {@code AFMParser(InputStream)} constructor, calls
 * {@code parse(reducedDataset)} (arg[1] = "0" full / "1" reduced), and prints a
 * stable projection of the OUTCOME rather than the raw object graph:
 *
 *   ok=true
 *   ver=&lt;afmVersion 4dp&gt;
 *   name=&lt;FontName or NULL&gt;
 *   full=&lt;FullName or NULL&gt;
 *   bbox=&lt;x0,y0,x1,y1 or NULL&gt;
 *   nchar=&lt;CharMetric count&gt;
 *   nkern=&lt;KernPair count (all three lists)&gt;
 *   ncomp=&lt;Composite count&gt;
 *   cm0=&lt;name,code,wx,bbox of first CharMetric or NULL&gt;
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from {@code AFMParser.parse}. The pypdfbox side reproduces this
 * fingerprint exactly so the parity assertion is a single string compare.
 *
 * Usage:
 *   java -cp ... AfmParserFuzzProbe font.afm [0|1]
 */
public final class AfmParserFuzzProbe {

    public static void main(String[] args) throws Exception {
        byte[] bytes = java.nio.file.Files.readAllBytes(
                new java.io.File(args[0]).toPath());
        boolean reduced = args.length > 1 && "1".equals(args[1]);

        StringBuilder sb = new StringBuilder();
        try {
            AFMParser parser = new AFMParser(new ByteArrayInputStream(bytes));
            FontMetrics fm = parser.parse(reduced);
            sb.append("ok=true\n");
            sb.append("ver=").append(fmt(fm.getAFMVersion())).append('\n');
            sb.append("name=").append(nz(fm.getFontName())).append('\n');
            sb.append("full=").append(nz(fm.getFullName())).append('\n');
            sb.append("bbox=").append(bboxStr(fm.getFontBBox())).append('\n');
            List<CharMetric> metrics = new ArrayList<>(fm.getCharMetrics());
            int nkern = fm.getKernPairs().size()
                    + fm.getKernPairs0().size()
                    + fm.getKernPairs1().size();
            List<Composite> comps = new ArrayList<>(fm.getComposites());
            sb.append("nchar=").append(metrics.size()).append('\n');
            sb.append("nkern=").append(nkern).append('\n');
            sb.append("ncomp=").append(comps.size()).append('\n');
            sb.append("cm0=").append(cm0(metrics)).append('\n');
        } catch (Throwable t) {
            System.out.print("ok=false\n");
            return;
        }
        System.out.print(sb);
    }

    private static String cm0(List<CharMetric> metrics) {
        if (metrics.isEmpty()) {
            return "NULL";
        }
        metrics.sort(Comparator.comparing(m -> nz(m.getName())));
        CharMetric cm = metrics.get(0);
        return nz(cm.getName()) + "," + cm.getCharacterCode() + ","
                + fmt(cm.getWx()) + "," + bboxStr(cm.getBoundingBox());
    }

    private static String bboxStr(BoundingBox b) {
        if (b == null) {
            return "NULL";
        }
        return fmt(b.getLowerLeftX()) + "," + fmt(b.getLowerLeftY()) + ","
                + fmt(b.getUpperRightX()) + "," + fmt(b.getUpperRightY());
    }

    private static String nz(String s) {
        return s == null ? "NULL" : s;
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
