import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import org.apache.fontbox.afm.CharMetric;
import org.apache.fontbox.afm.FontMetrics;
import org.apache.fontbox.afm.KernPair;
import org.apache.fontbox.util.BoundingBox;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;

/**
 * Live oracle probe: emit the AFM-parsed {@code org.apache.fontbox.afm.FontMetrics}
 * for each of the 5 distinct Adobe Core-14 AFM faces, in a canonical
 * line-oriented format that pypdfbox mirrors.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> AfmFontMetricsProbe
 *
 * Drives {@code Standard14Fonts.getAFM(name)} (which lazily runs the bundled
 * {@code AFMParser}) and dumps the parsed metrics straight from the FontBox
 * AFM object — NOT the PDFont advance-width path. Output (UTF-8, stdout), one
 * block per font:
 *   FONT\t<getFontName>
 *   HDR\t<afmVersion>\t<fullName>\t<familyName>\t<weight>\t<encodingScheme>\t<characterSet>
 *   VM\t<capHeight>\t<xHeight>\t<ascender>\t<descender>\t<italicAngle>\t<stdHW>\t<stdVW>\t<ulPos>\t<ulThick>
 *   BBOX\t<x0>\t<y0>\t<x1>\t<y1>     (font bounding box, or NULL)
 *   NCHAR\t<charMetricCount>
 *   NKERN\t<kernPairCount>
 *   CM\t<name>\t<code>\t<wx>\t<bx0>\t<by0>\t<bx1>\t<by1>   (every CharMetric, sorted by name)
 *   KP\t<first>\t<second>\t<x>\t<y>                       (every KernPair, sorted by first,second)
 * Floats normalized to 4 decimal places. Char metrics + kern pairs are sorted
 * so pypdfbox can assert the full set independent of list iteration order.
 */
public final class AfmFontMetricsProbe {

    // The 5 distinct AFM faces (the other 9 Standard-14 fonts are bold/oblique
    // variants whose AFMs are independent files; one representative per family
    // plus Symbol + ZapfDingbats covers the metric/kern/bbox surface).
    private static final String[] NAMES = {
        "Helvetica",
        "Times-Roman",
        "Courier",
        "Symbol",
        "ZapfDingbats",
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        for (String name : NAMES) {
            emit(out, Standard14Fonts.getAFM(name));
        }
    }

    private static void emit(PrintStream out, FontMetrics fm) {
        out.printf("FONT\t%s%n", fm.getFontName());
        out.printf("HDR\t%s\t%s\t%s\t%s\t%s\t%s%n",
                fmt(fm.getAFMVersion()),
                nz(fm.getFullName()), nz(fm.getFamilyName()), nz(fm.getWeight()),
                nz(fm.getEncodingScheme()), nz(fm.getCharacterSet()));
        out.printf("VM\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s%n",
                fmt(fm.getCapHeight()), fmt(fm.getXHeight()),
                fmt(fm.getAscender()), fmt(fm.getDescender()),
                fmt(fm.getItalicAngle()),
                fmt(fm.getStandardHorizontalWidth()),
                fmt(fm.getStandardVerticalWidth()),
                fmt(fm.getUnderlinePosition()), fmt(fm.getUnderlineThickness()));
        BoundingBox bbox = fm.getFontBBox();
        if (bbox == null) {
            out.printf("BBOX\tNULL%n");
        } else {
            out.printf("BBOX\t%s\t%s\t%s\t%s%n",
                    fmt(bbox.getLowerLeftX()), fmt(bbox.getLowerLeftY()),
                    fmt(bbox.getUpperRightX()), fmt(bbox.getUpperRightY()));
        }

        List<CharMetric> metrics = new ArrayList<>(fm.getCharMetrics());
        List<KernPair> kerns = new ArrayList<>(fm.getKernPairs());
        out.printf("NCHAR\t%d%n", metrics.size());
        out.printf("NKERN\t%d%n", kerns.size());

        metrics.sort(Comparator.comparing(AfmFontMetricsProbe::cmKey));
        for (CharMetric cm : metrics) {
            BoundingBox b = cm.getBoundingBox();
            String bs = (b == null)
                    ? "NULL\tNULL\tNULL\tNULL"
                    : fmt(b.getLowerLeftX()) + "\t" + fmt(b.getLowerLeftY())
                            + "\t" + fmt(b.getUpperRightX()) + "\t" + fmt(b.getUpperRightY());
            out.printf("CM\t%s\t%d\t%s\t%s%n",
                    nz(cm.getName()), cm.getCharacterCode(), fmt(cm.getWx()), bs);
        }

        kerns.sort(Comparator
                .comparing((KernPair k) -> nz(k.getFirstKernCharacter()))
                .thenComparing(k -> nz(k.getSecondKernCharacter())));
        for (KernPair kp : kerns) {
            out.printf("KP\t%s\t%s\t%s\t%s%n",
                    nz(kp.getFirstKernCharacter()), nz(kp.getSecondKernCharacter()),
                    fmt(kp.getX()), fmt(kp.getY()));
        }
    }

    private static String cmKey(CharMetric cm) {
        return nz(cm.getName());
    }

    private static String nz(String s) {
        return s == null ? "" : s;
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f; // collapse -0.0 to 0.0
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
