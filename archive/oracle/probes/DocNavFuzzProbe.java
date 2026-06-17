import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDPageLabels;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.outline.PDOutlineItem;

/**
 * Differential leniency fuzz probe for the document-navigation parsing surface,
 * Apache PDFBox 3.0.7 (wave 1511, agent E). Complements the existing
 * destination / outline / page-label oracle probes (which pin happy-path types,
 * coordinates and label strings) by driving the MALFORMED-INPUT leniency edges:
 *
 *   create:<...>    PDDestination.create dispatch for unusual COS shapes —
 *                   string / name named-dests, nested arrays, COSNull page
 *                   slots, integer (remote) page slots, wrong arity, type-name
 *                   case / whitespace variants, non-name type element.
 *   outline:<...>   PDOutlineItem.getDestination contract for a malformed /Dest
 *                   (does it throw or fall closed?) plus the /Dest+/A precedence
 *                   question (getDestination reads /Dest only, ignoring /A).
 *   labels:<...>    PDPageLabels construction over malformed /Nums number trees
 *                   (odd size, non-integer key, non-dictionary value, negative
 *                   key, unknown /S style, /St 0, missing /Nums, ranges beyond
 *                   page count, overlapping starts) — does construction throw or
 *                   tolerate, and what labels does a tolerated tree render?
 *
 * Output (UTF-8, LF-terminated), one line per case:
 *   <label>\t<result>
 * where <result> is a compact deterministic token: a created-class simple name,
 * a named-destination payload, a rendered-label list, or "EXC:<ExceptionType>".
 *
 * Deterministic and seed-free: the corpus is a fixed inline list (no PDF I/O
 * for the destination / outline cases; the page-label cases build a tiny
 * in-memory five-page document).
 */
public final class DocNavFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();

        emitCreateCases(sb);
        emitOutlineCases(sb);
        emitLabelCases(sb);

        out.print(sb);
        out.flush();
    }

    // ---------------- PDDestination.create dispatch ----------------

    private static void emitCreateCases(StringBuilder sb) {
        line(sb, "create:named_string", createToken(new COSString("Chapter1")));
        line(sb, "create:named_name", createToken(COSName.getPDFName("Chapter2")));
        line(sb, "create:null", createToken(null));
        line(sb, "create:bare_int", createToken(COSInteger.get(7)));
        line(sb, "create:bare_dict", createToken(new COSDictionary()));
        line(sb, "create:bare_null_obj", createToken(COSNull.NULL));

        // Well-formed arrays.
        line(sb, "create:xyz_int_page", createToken(arr(COSInteger.get(0), name("XYZ"))));
        line(sb, "create:xyz_null_page", createToken(arr(COSNull.NULL, name("XYZ"))));
        line(sb, "create:xyz_dict_page", createToken(arr(new COSDictionary(), name("XYZ"))));
        line(sb, "create:fit", createToken(arr(COSInteger.get(0), name("Fit"))));
        line(sb, "create:fitb", createToken(arr(COSInteger.get(0), name("FitB"))));
        line(sb, "create:fith", createToken(arr(COSInteger.get(0), name("FitH"))));
        line(sb, "create:fitbh", createToken(arr(COSInteger.get(0), name("FitBH"))));
        line(sb, "create:fitv", createToken(arr(COSInteger.get(0), name("FitV"))));
        line(sb, "create:fitbv", createToken(arr(COSInteger.get(0), name("FitBV"))));
        line(sb, "create:fitr", createToken(arr(COSInteger.get(0), name("FitR"))));

        // Wrong arity (extra / missing coordinate slots still construct: create
        // only checks size() > 1 and item[1] is a name).
        line(sb, "create:xyz_only2", createToken(arr(COSInteger.get(0), name("XYZ"))));
        line(sb, "create:xyz_5slot", createToken(arr(COSInteger.get(0), name("XYZ"),
                COSInteger.get(1), COSInteger.get(2), new COSFloat(3.5f))));
        line(sb, "create:xyz_extra", createToken(arr(COSInteger.get(0), name("XYZ"),
                COSInteger.get(1), COSInteger.get(2), COSInteger.get(3), COSInteger.get(99))));

        // Type-name case / whitespace variants — case-sensitive, no trimming.
        line(sb, "create:xyz_lower", createToken(arr(COSInteger.get(0), name("xyz"))));
        line(sb, "create:xyz_trailspace", createToken(arr(COSInteger.get(0), name("XYZ "))));
        line(sb, "create:fit_lower", createToken(arr(COSInteger.get(0), name("fit"))));
        line(sb, "create:unknown_tag", createToken(arr(COSInteger.get(0), name("Foo"))));

        // Malformed arrays falling through to "can't convert".
        line(sb, "create:empty_array", createToken(new COSArray()));
        line(sb, "create:size1_array", createToken(arr(COSInteger.get(0))));
        line(sb, "create:nonname_int1", createToken(arr(COSInteger.get(0), COSInteger.get(5))));
        line(sb, "create:nonname_str1", createToken(arr(COSInteger.get(0), new COSString("XYZ"))));
        line(sb, "create:nested_array1", createToken(arr(COSInteger.get(0), arr(name("XYZ")))));
        line(sb, "create:null_at_1", createToken(arr(COSInteger.get(0), COSNull.NULL)));

        // Negative / integer remote page slots — these still construct; we read
        // the page number back to prove the slot semantics.
        line(sb, "create:neg_page", pageNumberToken(arr(COSInteger.get(-3), name("Fit"))));
        line(sb, "create:int_page", pageNumberToken(arr(COSInteger.get(4), name("Fit"))));
        line(sb, "create:null_page_num", pageNumberToken(arr(COSNull.NULL, name("Fit"))));
        line(sb, "create:dict_page_num", pageNumberToken(arr(new COSDictionary(), name("Fit"))));
    }

    private static String createToken(COSBase base) {
        try {
            PDDestination d = PDDestination.create(base);
            if (d == null) {
                return "null";
            }
            String cls = d.getClass().getSimpleName();
            if (d instanceof PDNamedDestination) {
                return cls + ":" + ((PDNamedDestination) d).getNamedDestination();
            }
            return cls;
        } catch (Exception e) {
            return "EXC:" + e.getClass().getSimpleName();
        }
    }

    private static String pageNumberToken(COSBase base) {
        try {
            PDDestination d = PDDestination.create(base);
            if (!(d instanceof PDPageDestination)) {
                return "notpage";
            }
            return "page=" + ((PDPageDestination) d).getPageNumber();
        } catch (Exception e) {
            return "EXC:" + e.getClass().getSimpleName();
        }
    }

    // ---------------- PDOutlineItem.getDestination ----------------

    private static void emitOutlineCases(StringBuilder sb) {
        // String /Dest -> named destination.
        line(sb, "outline:dest_string", outlineDestToken(new COSString("Bk"), null));
        // Name /Dest -> named destination.
        line(sb, "outline:dest_name", outlineDestToken(COSName.getPDFName("Bk"), null));
        // Array /Dest -> page destination.
        line(sb, "outline:dest_array", outlineDestToken(arr(COSInteger.get(1), name("Fit")), null));
        // Malformed /Dest (size-1 array) -> create throws; does getDestination
        // propagate or swallow?
        line(sb, "outline:dest_bad_array", outlineDestToken(arr(COSInteger.get(1)), null));
        // Malformed /Dest (bare integer) -> create throws.
        line(sb, "outline:dest_bad_int", outlineDestToken(COSInteger.get(9), null));
        // Malformed /Dest (bare dict) -> create throws.
        line(sb, "outline:dest_bad_dict", outlineDestToken(new COSDictionary(), null));
        // /Dest absent entirely.
        line(sb, "outline:dest_absent", outlineDestToken(null, null));
        // /Dest + /A both present: getDestination reads /Dest only (ignores /A).
        line(sb, "outline:dest_and_action", outlineDestToken(
                arr(COSInteger.get(2), name("Fit")), gotoAction()));
        // Only /A present, /Dest absent: getDestination is null (it never looks
        // at /A — that is getAction's job).
        line(sb, "outline:action_only", outlineDestToken(null, gotoAction()));
    }

    private static COSDictionary gotoAction() {
        COSDictionary a = new COSDictionary();
        a.setItem(COSName.getPDFName("S"), COSName.getPDFName("GoTo"));
        a.setItem(COSName.getPDFName("D"), new COSString("OtherTarget"));
        return a;
    }

    private static String outlineDestToken(COSBase dest, COSDictionary action) {
        PDOutlineItem item = new PDOutlineItem();
        if (dest != null) {
            item.getCOSObject().setItem(COSName.DEST, dest);
        }
        if (action != null) {
            item.getCOSObject().setItem(COSName.A, action);
        }
        try {
            PDDestination d = item.getDestination();
            if (d == null) {
                return "null";
            }
            String cls = d.getClass().getSimpleName();
            if (d instanceof PDNamedDestination) {
                return cls + ":" + ((PDNamedDestination) d).getNamedDestination();
            }
            return cls;
        } catch (Exception e) {
            return "EXC:" + e.getClass().getSimpleName();
        }
    }

    // ---------------- PDPageLabels malformed /Nums ----------------

    private static void emitLabelCases(StringBuilder sb) {
        // Well-formed baseline: one decimal range at page 0.
        line(sb, "labels:baseline", labelToken(numsTree(
                kv(0, range("D", null, null)))));

        // Odd-size /Nums array (trailing key with no value).
        COSArray odd = new COSArray();
        odd.add(COSInteger.get(0));
        odd.add(range("D", null, null));
        odd.add(COSInteger.get(2));
        line(sb, "labels:odd_size", labelToken(wrapNums(odd)));

        // Non-integer key (string) followed by a dict value.
        COSArray nonint = new COSArray();
        nonint.add(new COSString("zero"));
        nonint.add(range("D", null, null));
        line(sb, "labels:nonint_key", labelToken(wrapNums(nonint)));

        // Non-dictionary value (integer where a range dict is expected).
        COSArray nondict = new COSArray();
        nondict.add(COSInteger.get(0));
        nondict.add(COSInteger.get(42));
        line(sb, "labels:nondict_value", labelToken(wrapNums(nondict)));

        // Negative key -> skipped; only the implicit default remains.
        COSArray negkey = new COSArray();
        negkey.add(COSInteger.get(-1));
        negkey.add(range("R", null, null));
        line(sb, "labels:negative_key", labelToken(wrapNums(negkey)));

        // Unknown /S style on an otherwise valid range -> generator falls back
        // to decimal.
        line(sb, "labels:unknown_style", labelToken(numsTree(
                kv(0, range("Q", null, null)))));

        // /St 0 (start = 0) -> labels begin at 0 for decimal.
        line(sb, "labels:st_zero", labelToken(numsTree(
                kv(0, range("D", null, 0)))));

        // /St negative.
        line(sb, "labels:st_negative", labelToken(numsTree(
                kv(0, range("D", null, -2)))));

        // Missing /Nums entirely (empty number-tree dict) -> default labels.
        line(sb, "labels:missing_nums", labelToken(new COSDictionary()));

        // Empty /Nums array.
        line(sb, "labels:empty_nums", labelToken(wrapNums(new COSArray())));

        // Range starting beyond the (5-page) document.
        line(sb, "labels:start_beyond", labelToken(numsTree(
                kv(0, range("D", null, null)),
                kv(99, range("R", null, null)))));

        // Two ranges with the same start key (later wins on read order).
        COSArray dup = new COSArray();
        dup.add(COSInteger.get(0));
        dup.add(range("D", null, null));
        dup.add(COSInteger.get(0));
        dup.add(range("R", null, null));
        line(sb, "labels:duplicate_start", labelToken(wrapNums(dup)));

        // Multi-range: decimal 0.., roman from page 2.
        line(sb, "labels:multi_range", labelToken(numsTree(
                kv(0, range("D", null, null)),
                kv(2, range("r", null, 1)))));

        // /Kids with a non-dictionary child mixed with a /Nums sibling.
        COSDictionary kidsDict = new COSDictionary();
        COSArray kids = new COSArray();
        kids.add(COSInteger.get(123));
        kidsDict.setItem(COSName.getPDFName("Kids"), kids);
        COSArray nums = new COSArray();
        nums.add(COSInteger.get(0));
        nums.add(range("R", null, null));
        kidsDict.setItem(COSName.getPDFName("Nums"), nums);
        line(sb, "labels:kids_nonchild_with_nums", labelToken(kidsDict));
    }

    private static String labelToken(COSDictionary numberTree) {
        PDDocument doc = new PDDocument();
        try {
            for (int i = 0; i < 5; i++) {
                doc.addPage(new PDPage());
            }
            PDPageLabels labels = new PDPageLabels(doc, numberTree);
            String[] arr = labels.getLabelsByPageIndices();
            StringBuilder b = new StringBuilder("[");
            for (int i = 0; i < arr.length; i++) {
                if (i > 0) {
                    b.append(",");
                }
                b.append(arr[i] == null ? "" : arr[i]);
            }
            b.append("]");
            return b.toString();
        } catch (Exception e) {
            return "EXC:" + e.getClass().getSimpleName();
        } finally {
            try {
                doc.close();
            } catch (Exception ignore) {
                // closing a probe document never matters for the result.
            }
        }
    }

    // ---------------- helpers ----------------

    private static COSName name(String s) {
        return COSName.getPDFName(s);
    }

    private static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    private static COSDictionary range(String style, String prefix, Integer start) {
        COSDictionary d = new COSDictionary();
        if (style != null) {
            d.setItem(COSName.getPDFName("S"), COSName.getPDFName(style));
        }
        if (prefix != null) {
            d.setItem(COSName.getPDFName("P"), new COSString(prefix));
        }
        if (start != null) {
            d.setItem(COSName.getPDFName("St"), COSInteger.get(start));
        }
        return d;
    }

    private static COSBase[] kv(int key, COSDictionary value) {
        return new COSBase[] {COSInteger.get(key), value};
    }

    private static COSDictionary numsTree(COSBase[]... entries) {
        COSArray nums = new COSArray();
        for (COSBase[] e : entries) {
            nums.add(e[0]);
            nums.add(e[1]);
        }
        return wrapNums(nums);
    }

    private static COSDictionary wrapNums(COSArray nums) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.getPDFName("Nums"), nums);
        return d;
    }

    private static void line(StringBuilder sb, String label, String result) {
        sb.append(label).append('\t').append(result).append('\n');
    }
}
