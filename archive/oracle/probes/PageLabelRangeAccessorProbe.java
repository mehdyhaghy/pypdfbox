import java.io.PrintStream;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.common.PDPageLabelRange;

/**
 * Live oracle probe: pin the accessor / validation behaviour of
 * {@link PDPageLabelRange} in isolation (no document required).
 *
 *   - getStart() default when /St absent
 *   - getStyle() / getPrefix() null when absent
 *   - setStart(0) and setStart(-3) -> IllegalArgumentException
 *   - setPrefix(null) removes /P; setStyle(null) removes /S
 *   - setStart(1) explicitly writes /St (so getStart still 1 but key present)
 *
 * Output: UTF-8, tagged lines for a python test to parse.
 */
public final class PageLabelRangeAccessorProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        PDPageLabelRange r = new PDPageLabelRange();
        out.println("default.start=" + r.getStart());
        out.println("default.style=" + (r.getStyle() == null ? "null" : r.getStyle()));
        out.println("default.prefix=" + (r.getPrefix() == null ? "null" : r.getPrefix()));
        out.println("default.hasSt=" + r.getCOSObject().containsKey(COSName.ST));

        try {
            r.setStart(0);
            out.println("setStart0=NOEXC");
        } catch (IllegalArgumentException e) {
            out.println("setStart0=IAE:" + e.getMessage());
        }
        try {
            r.setStart(-3);
            out.println("setStartNeg=NOEXC");
        } catch (IllegalArgumentException e) {
            out.println("setStartNeg=IAE:" + e.getMessage());
        }

        // setStart(1) explicitly -> key present even though value equals default.
        r.setStart(1);
        out.println("afterSetStart1.hasSt=" + r.getCOSObject().containsKey(COSName.ST));
        out.println("afterSetStart1.start=" + r.getStart());

        // prefix set then cleared with null.
        r.setPrefix("X-");
        out.println("afterSetPrefix.hasP=" + r.getCOSObject().containsKey(COSName.P));
        r.setPrefix(null);
        out.println("afterClearPrefix.hasP=" + r.getCOSObject().containsKey(COSName.P));
        out.println("afterClearPrefix.prefix=" + (r.getPrefix() == null ? "null" : r.getPrefix()));

        // style set then cleared with null.
        r.setStyle(PDPageLabelRange.STYLE_ROMAN_UPPER);
        out.println("afterSetStyle.hasS=" + r.getCOSObject().containsKey(COSName.S));
        r.setStyle(null);
        out.println("afterClearStyle.hasS=" + r.getCOSObject().containsKey(COSName.S));
        out.println("afterClearStyle.style=" + (r.getStyle() == null ? "null" : r.getStyle()));

        // setStyle with an arbitrary (non STYLE_*) string: upstream does NOT validate.
        r.setStyle("Q");
        out.println("arbitraryStyle=" + (r.getStyle() == null ? "null" : r.getStyle()));
    }
}
