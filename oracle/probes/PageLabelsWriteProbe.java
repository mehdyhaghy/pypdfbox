import java.io.PrintStream;
import java.util.Map;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;
import org.apache.pdfbox.pdmodel.common.PDPageLabelRange;

/**
 * Live oracle probe: exercise the WRITE side of {@link PDPageLabels} /
 * {@link PDPageLabelRange}. Builds a number tree programmatically, then dumps:
 *
 *   1. the serialized /Nums array (key/dict-shape order) of getCOSObject(),
 *   2. the per-page computed label list (getLabelsByPageIndices),
 *   3. the inverse label->index map (getPageIndicesByLabels) -- duplicate
 *      label resolution (highest page index wins),
 *   4. selected accessor values (getStart default, getStyle null, etc).
 *
 * The scenario is selected by args[0]:
 *
 *   nums_order        out-of-order setLabelItem inserts, replace existing key
 *   prefix_only       a range with /P but no /S (prefix-only labels)
 *   gap_before        first explicit range at key 2 (default decimal at 0..1)
 *   dup_labels        two ranges yielding the same label strings
 *   start_default     accessor defaults: getStart()==1, getStyle()==null
 *   roman_big         /St=4000 roman (m-per-thousand quirk)
 *   letters_big       /St beyond ZZ
 *
 * Output: UTF-8, line oriented. Lines are tagged so a python test can parse.
 */
public final class PageLabelsWriteProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String scenario = args.length > 0 ? args[0] : "nums_order";
        int pageCount = args.length > 1 ? Integer.parseInt(args[1]) : 8;

        try (PDDocument doc = new PDDocument()) {
            for (int i = 0; i < pageCount; i++) {
                doc.addPage(new PDPage());
            }
            PDPageLabels labels = new PDPageLabels(doc);

            switch (scenario) {
                case "nums_order": {
                    // Insert out of order, then replace an existing start key.
                    PDPageLabelRange r5 = new PDPageLabelRange();
                    r5.setStyle(PDPageLabelRange.STYLE_ROMAN_LOWER);
                    labels.setLabelItem(5, r5);
                    PDPageLabelRange r2 = new PDPageLabelRange();
                    r2.setStyle(PDPageLabelRange.STYLE_LETTERS_UPPER);
                    labels.setLabelItem(2, r2);
                    // Replace the default range at key 0.
                    PDPageLabelRange r0 = new PDPageLabelRange();
                    r0.setStyle(PDPageLabelRange.STYLE_DECIMAL);
                    r0.setStart(100);
                    labels.setLabelItem(0, r0);
                    break;
                }
                case "prefix_only": {
                    PDPageLabelRange r0 = new PDPageLabelRange();
                    r0.setStyle(PDPageLabelRange.STYLE_DECIMAL);
                    labels.setLabelItem(0, r0);
                    PDPageLabelRange r3 = new PDPageLabelRange();
                    r3.setPrefix("Appendix-");
                    // No setStyle -> /S absent -> prefix-only labels.
                    labels.setLabelItem(3, r3);
                    break;
                }
                case "gap_before": {
                    // Leave default decimal at 0; first explicit range at 2.
                    PDPageLabelRange r2 = new PDPageLabelRange();
                    r2.setStyle(PDPageLabelRange.STYLE_ROMAN_UPPER);
                    labels.setLabelItem(2, r2);
                    break;
                }
                case "dup_labels": {
                    // Two ranges that both render "1","2",... decimal.
                    PDPageLabelRange r0 = new PDPageLabelRange();
                    r0.setStyle(PDPageLabelRange.STYLE_DECIMAL);
                    labels.setLabelItem(0, r0);
                    PDPageLabelRange r4 = new PDPageLabelRange();
                    r4.setStyle(PDPageLabelRange.STYLE_DECIMAL);
                    labels.setLabelItem(4, r4);
                    break;
                }
                case "start_default": {
                    // Just the default range; probe accessors below.
                    break;
                }
                case "roman_big": {
                    PDPageLabelRange r0 = new PDPageLabelRange();
                    r0.setStyle(PDPageLabelRange.STYLE_ROMAN_LOWER);
                    r0.setStart(4000);
                    labels.setLabelItem(0, r0);
                    break;
                }
                case "letters_big": {
                    PDPageLabelRange r0 = new PDPageLabelRange();
                    r0.setStyle(PDPageLabelRange.STYLE_LETTERS_UPPER);
                    r0.setStart(700);
                    labels.setLabelItem(0, r0);
                    break;
                }
                default:
                    break;
            }

            // 1. /Nums serialization order.
            COSDictionary cos = (COSDictionary) labels.getCOSObject();
            COSArray nums = (COSArray) cos.getDictionaryObject(COSName.NUMS);
            StringBuilder numsLine = new StringBuilder("nums");
            for (int i = 0; i + 1 < nums.size(); i += 2) {
                COSBase key = nums.getObject(i);
                COSDictionary rd = (COSDictionary) nums.getObject(i + 1);
                numsLine.append(' ').append(((org.apache.pdfbox.cos.COSInteger) key).intValue());
                numsLine.append('[');
                String s = rd.getNameAsString(COSName.S);
                String p = rd.getString(COSName.P);
                COSBase st = rd.getDictionaryObject(COSName.ST);
                numsLine.append("S=").append(s == null ? "null" : s);
                numsLine.append(",P=").append(p == null ? "null" : p);
                numsLine.append(",St=").append(st == null ? "null" :
                        ((org.apache.pdfbox.cos.COSInteger) st).intValue());
                numsLine.append(']');
            }
            out.println(numsLine);

            // 2. per-page labels
            String[] arr = labels.getLabelsByPageIndices();
            out.println("count=" + arr.length);
            for (int i = 0; i < arr.length; i++) {
                out.println("label " + i + "\t" + (arr[i] == null ? "" : arr[i]));
            }

            // 3. inverse map (sorted by label for determinism)
            Map<String, Integer> inv = labels.getPageIndicesByLabels();
            java.util.TreeMap<String, Integer> sorted = new java.util.TreeMap<>(inv);
            out.println("invsize=" + sorted.size());
            for (Map.Entry<String, Integer> e : sorted.entrySet()) {
                out.println("inv " + e.getKey() + "\t" + e.getValue());
            }

            // 4. accessor defaults on the range at key 0.
            PDPageLabelRange r0 = labels.getPageLabelRange(0);
            if (r0 != null) {
                out.println("r0.start=" + r0.getStart());
                out.println("r0.style=" + (r0.getStyle() == null ? "null" : r0.getStyle()));
                out.println("r0.prefix=" + (r0.getPrefix() == null ? "null" : r0.getPrefix()));
            }
            out.println("rangeCount=" + labels.getPageRangeCount());
        }
    }
}
