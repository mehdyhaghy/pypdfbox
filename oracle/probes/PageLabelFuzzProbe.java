import java.util.Arrays;
import java.util.stream.Collectors;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;

/**
 * Differential page-label fuzz probe (wave 1542).
 *
 * Complements PageLabelTreeFuzzProbe (wave 1518, which fuzzed the number-tree
 * STRUCTURE) by fuzzing the LABEL-STRING rendering: every valid /S style plus
 * unknown/missing/wrong-type styles, /St boundary values (0/neg/huge/float),
 * /P prefix forms (string/name/null/empty), roman subtractive boundaries
 * (4/9/40/90/400/900/3999/4000+), alphabetic doubling past 26 (AA, ZZ, AAA),
 * and label computation for page indices below first range, between ranges, and
 * past the last range (via an explicit large page count).
 *
 * Two output sections:
 *   TREE cases  -> build a /PageLabels number tree over N pages, dump per-page
 *                  label list + page indices + range count.
 *   RANGE cases -> drive PDPageLabelRange directly: render compute label at
 *                  several offsets to pin number formatting at boundaries.
 *
 * Output: UTF-8, line-oriented, NUL -> <NUL>.
 */
public final class PageLabelFuzzProbe {

    private static COSArray array(COSBase... values) {
        COSArray out = new COSArray();
        for (COSBase value : values) {
            out.add(value);
        }
        return out;
    }

    private static COSDictionary range(COSBase style, COSBase prefix, COSBase start) {
        COSDictionary out = new COSDictionary();
        if (style != null) out.setItem(COSName.S, style);
        if (prefix != null) out.setItem(COSName.P, prefix);
        if (start != null) out.setItem(COSName.ST, start);
        return out;
    }

    private static COSDictionary nums(COSBase... values) {
        COSDictionary out = new COSDictionary();
        out.setItem(COSName.NUMS, array(values));
        return out;
    }

    private static void runTree(int pages, String name, COSDictionary tree) {
        try (PDDocument doc = new PDDocument()) {
            for (int i = 0; i < pages; i++) doc.addPage(new PDPage());
            PDPageLabels labels = new PDPageLabels(doc, tree);
            String indices = labels.getPageIndices().stream()
                    .map(String::valueOf).collect(Collectors.joining(","));
            String rendered = Arrays.stream(labels.getLabelsByPageIndices())
                    .map(s -> s == null ? "null" : s.replace("\0", "<NUL>"))
                    .collect(Collectors.joining("|"));
            System.out.println("TREE " + name + " count=" + labels.getPageRangeCount()
                    + " indices=" + indices + " labels=" + rendered);
        } catch (Exception e) {
            System.out.println("TREE " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    private static void runStyleStarts(String name, String style, int[] starts) {
        org.apache.pdfbox.pdmodel.common.PDPageLabelRange r =
                new org.apache.pdfbox.pdmodel.common.PDPageLabelRange();
        if (style != null) r.setStyle(style);
        StringBuilder sb = new StringBuilder("RANGE " + name + " ");
        for (int i = 0; i < starts.length; i++) {
            r.getCOSObject().setItem(COSName.ST, COSInteger.get(starts[i]));
            // PDPageLabelRange has no public per-offset render; use a one-page
            // PDPageLabels to render the single label at the range start.
            String label = renderSingle(style, starts[i]);
            if (i > 0) sb.append("|");
            sb.append(starts[i]).append("=").append(label);
        }
        System.out.println(sb.toString());
    }

    private static String renderSingle(String style, int start) {
        try (PDDocument doc = new PDDocument()) {
            doc.addPage(new PDPage());
            COSBase styleObj = style == null ? null : COSName.getPDFName(style);
            PDPageLabels labels = new PDPageLabels(doc,
                    nums(COSInteger.get(0), range(styleObj, null, COSInteger.get(start))));
            String[] arr = labels.getLabelsByPageIndices();
            return arr.length == 0 || arr[0] == null ? "null" : arr[0].replace("\0", "<NUL>");
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    public static void main(String[] args) throws Exception {
        COSName D = COSName.D;
        COSName r = COSName.getPDFName("r");
        COSName R = COSName.getPDFName("R");
        COSName a = COSName.getPDFName("a");
        COSName A = COSName.getPDFName("A");

        // --- TREE cases: page-index resolution below/between/past ranges ---
        // 8 pages, first range starts at index 2 (pages 0,1 below first range).
        runTree(8, "below_first", nums(
                COSInteger.get(2), range(D, null, null),
                COSInteger.get(5), range(r, new COSString("R-"), null)));
        // gap then second range; pages between resolve to the earlier range.
        runTree(10, "between_ranges", nums(
                COSInteger.get(0), range(D, null, null),
                COSInteger.get(4), range(A, new COSString("App-"), null),
                COSInteger.get(8), range(r, null, COSInteger.get(1))));
        // last range short of page count -> labels continue past last start.
        runTree(6, "past_last", nums(
                COSInteger.get(0), range(R, null, null)));
        // out-of-order keys in /Nums (PDFBox builds a TreeMap-style order).
        runTree(6, "out_of_order", nums(
                COSInteger.get(3), range(a, null, null),
                COSInteger.get(0), range(D, null, null)));
        // missing index-0 range entirely; first range at index 1.
        runTree(4, "no_index0", nums(
                COSInteger.get(1), range(D, new COSString("P-"), null)));

        // --- TREE cases: style variants in a single range ---
        runTree(3, "style_D", nums(COSInteger.get(0), range(D, null, null)));
        runTree(3, "style_r", nums(COSInteger.get(0), range(r, null, null)));
        runTree(3, "style_R", nums(COSInteger.get(0), range(R, null, null)));
        runTree(3, "style_a", nums(COSInteger.get(0), range(a, null, null)));
        runTree(3, "style_A", nums(COSInteger.get(0), range(A, null, null)));
        runTree(3, "style_unknown",
                nums(COSInteger.get(0), range(COSName.getPDFName("Q"), null, null)));
        runTree(3, "style_missing",
                nums(COSInteger.get(0), range(null, new COSString("only-"), null)));
        // wrong-type /S (a COSString, not a COSName).
        COSDictionary styleWrong = range(null, null, null);
        styleWrong.setItem(COSName.S, new COSString("D"));
        runTree(3, "style_wrongtype", nums(COSInteger.get(0), styleWrong));

        // --- TREE cases: /P prefix forms ---
        runTree(2, "prefix_string", nums(COSInteger.get(0), range(D, new COSString("X-"), null)));
        runTree(2, "prefix_empty", nums(COSInteger.get(0), range(D, new COSString(""), null)));
        // /P as a name rather than a string (wrong type), with decimal /S.
        COSDictionary prefixName = range(null, null, null);
        prefixName.setItem(COSName.S, COSName.D);
        prefixName.setItem(COSName.P, COSName.getPDFName("Nm"));
        runTree(2, "prefix_name", nums(COSInteger.get(0), prefixName));

        // --- TREE cases: /St boundaries ---
        runTree(2, "st_zero", nums(COSInteger.get(0), range(D, null, COSInteger.get(0))));
        runTree(2, "st_negative", nums(COSInteger.get(0), range(D, null, COSInteger.get(-5))));
        runTree(2, "st_float", nums(COSInteger.get(0), range(D, null, new COSFloat(3.9f))));

        // --- RANGE cases: numeric formatting at boundaries ---
        int[] romanBounds = {1, 3, 4, 8, 9, 40, 49, 90, 99, 400, 900, 3999, 4000, 4999};
        runStyleStarts("roman_lower", "r", romanBounds);
        runStyleStarts("roman_upper", "R", romanBounds);
        int[] letterBounds = {1, 26, 27, 28, 52, 53, 702, 703};
        runStyleStarts("letters_lower", "a", letterBounds);
        runStyleStarts("letters_upper", "A", letterBounds);
        int[] decimalBounds = {1, 10, 100, 1000};
        runStyleStarts("decimal", "D", decimalBounds);
        // no style -> prefix-only (here prefix absent, so empty string).
        runStyleStarts("nostyle", null, new int[] {1, 5});
    }
}
