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

/** Differential malformed page-label number-tree probe (wave 1518). */
public final class PageLabelTreeFuzzProbe {
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

    private static void run(PDDocument doc, String name, COSDictionary tree) {
        try {
            PDPageLabels labels = new PDPageLabels(doc, tree);
            String indices = labels.getPageIndices().stream()
                    .map(String::valueOf).collect(Collectors.joining(","));
            String rendered = Arrays.stream(labels.getLabelsByPageIndices())
                    .map(s -> s == null ? "null" : s.replace("\0", "<NUL>"))
                    .collect(Collectors.joining("|"));
            System.out.println("CASE " + name + " count=" + labels.getPageRangeCount()
                    + " indices=" + indices + " labels=" + rendered);
        } catch (Exception e) {
            System.out.println("CASE " + name + " ERR:" + e.getClass().getSimpleName());
        }
    }

    public static void main(String[] args) throws Exception {
        try (PDDocument doc = new PDDocument()) {
            for (int i = 0; i < 6; i++) doc.addPage(new PDPage());
            COSDictionary decimal = range(COSName.D, null, null);
            run(doc, "empty", new COSDictionary());
            run(doc, "flat", nums(COSInteger.get(0), decimal,
                    COSInteger.get(3), range(COSName.getPDFName("r"), new COSString("A-"), COSInteger.get(2))));
            run(doc, "odd_nums", nums(COSInteger.get(0), decimal, COSInteger.get(3)));
            run(doc, "bad_key", nums(new COSString("0"), decimal));
            run(doc, "negative_key", nums(COSInteger.get(-1), decimal));
            run(doc, "bad_value", nums(COSInteger.get(0), COSInteger.get(7)));
            run(doc, "duplicate", nums(COSInteger.get(0), decimal,
                    COSInteger.get(0), range(COSName.getPDFName("A"), null, null)));
            run(doc, "unknown_style", nums(COSInteger.get(0),
                    range(COSName.getPDFName("Bogus"), new COSString("P"), null)));
            run(doc, "prefix_nul", nums(COSInteger.get(0),
                    range(COSName.D, new COSString(new byte[] {'A', 0, 'B'}), null)));
            run(doc, "start_zero", nums(COSInteger.get(0),
                    range(COSName.D, null, COSInteger.get(0))));
            run(doc, "start_negative", nums(COSInteger.get(0),
                    range(COSName.D, null, COSInteger.get(-2))));
            run(doc, "start_float", nums(COSInteger.get(0),
                    range(COSName.D, null, new COSFloat(2.9f))));

            COSDictionary child = nums(COSInteger.get(2),
                    range(COSName.getPDFName("a"), null, null));
            COSDictionary kids = new COSDictionary();
            kids.setItem(COSName.KIDS, array(child));
            run(doc, "kids", kids);

            COSDictionary both = nums(COSInteger.get(0), decimal);
            both.setItem(COSName.KIDS, array(child));
            run(doc, "kids_and_nums", both);
        }
    }
}
