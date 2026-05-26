import java.io.File;
import java.io.PrintStream;
import java.util.List;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDMarkedContent;
import org.apache.pdfbox.text.PDFMarkedContentExtractor;

/**
 * Live oracle probe: emit a page's marked-content operator sequence and the
 * PDFMarkedContentExtractor-built marked-content tree, in two canonical
 * sections so pypdfbox can be compared line-for-line.
 *
 * Usage:
 *   java -cp ... MarkedContentProbe input.pdf pageIndex     (tokenize a page)
 *   java -cp ... MarkedContentProbe stream.cs --raw         (tokenize raw bytes)
 *
 * Section 1 ("--- ops ---"): the marked-content operator subsequence of the
 * content stream as PDFStreamParser tokenizes it. Only BMC/BDC/EMC/MP/DP are
 * emitted, each with its tag and (for BDC/DP) the inline property dictionary or
 * resource /Properties name. Property dicts are rendered canonically with
 * sorted keys so the comparison is locale- and order-independent.
 *
 *   BMC /<tag>
 *   BDC /<tag> <propsValue>
 *   EMC
 *   MP /<tag>
 *   DP /<tag> <propsValue>
 *
 * where <propsValue> is either:
 *   /<name>            named property list (resource /Properties reference)
 *   { k=<v> ; k=<v> }  inline dictionary, keys sorted
 *
 * Section 2 ("--- tree ---"): the PDFMarkedContentExtractor marked-content tree
 * walked depth-first. One line per sequence, indented by nesting depth:
 *
 *   MC depth=<n> tag=<tag> mcid=<n> children=<n>
 *
 * The --raw form prints only section 1 (no document = no extractor walk).
 */
public final class MarkedContentProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        StringBuilder sb = new StringBuilder();
        if (args.length > 1 && "--raw".equals(args[1])) {
            byte[] bytes = java.nio.file.Files.readAllBytes(new File(args[0]).toPath());
            PDFStreamParser parser = new PDFStreamParser(bytes);
            sb.append("--- ops ---\n");
            emitOps(sb, parser.parse());
            out.print(sb);
            return;
        }
        int pageIndex = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(pageIndex);
            PDFStreamParser parser = new PDFStreamParser(page);
            sb.append("--- ops ---\n");
            emitOps(sb, parser.parse());

            sb.append("--- tree ---\n");
            PDFMarkedContentExtractor extractor = new PDFMarkedContentExtractor();
            extractor.processPage(page);
            for (PDMarkedContent mc : extractor.getMarkedContents()) {
                emitTree(sb, mc, 0);
            }
            out.print(sb);
        }
    }

    /**
     * Walk parsed tokens, accumulating operands, and emit only the
     * marked-content operators with their (canonical) operands.
     */
    private static void emitOps(StringBuilder sb, List<Object> tokens) {
        java.util.ArrayList<COSBase> operands = new java.util.ArrayList<>();
        for (Object tok : tokens) {
            if (tok instanceof Operator) {
                String name = ((Operator) tok).getName();
                switch (name) {
                    case "BMC":
                        sb.append("BMC ").append(tagOf(operands)).append('\n');
                        break;
                    case "BDC":
                        sb.append("BDC ").append(tagOf(operands)).append(' ')
                                .append(propsOf(operands)).append('\n');
                        break;
                    case "EMC":
                        sb.append("EMC\n");
                        break;
                    case "MP":
                        sb.append("MP ").append(tagOf(operands)).append('\n');
                        break;
                    case "DP":
                        sb.append("DP ").append(tagOf(operands)).append(' ')
                                .append(propsOf(operands)).append('\n');
                        break;
                    default:
                        break;
                }
                operands.clear();
            } else if (tok instanceof COSBase) {
                operands.add((COSBase) tok);
            }
        }
    }

    /** Tag: the first COSName operand rendered as /<name>, else "<none>". */
    private static String tagOf(List<COSBase> operands) {
        for (COSBase b : operands) {
            if (b instanceof COSName) {
                return "/" + ((COSName) b).getName();
            }
        }
        return "<none>";
    }

    /**
     * Property operand for BDC/DP: the second operand. A COSName is rendered
     * /<name> (resource reference); a COSDictionary is rendered canonically.
     */
    private static String propsOf(List<COSBase> operands) {
        if (operands.size() < 2) {
            return "<none>";
        }
        COSBase prop = operands.get(1);
        if (prop instanceof COSName) {
            return "/" + ((COSName) prop).getName();
        }
        if (prop instanceof COSDictionary) {
            return canonDict((COSDictionary) prop);
        }
        return "<bad>";
    }

    /** Canonical dictionary: { key=value ; ... } with keys sorted. */
    private static String canonDict(COSDictionary d) {
        TreeMap<String, COSBase> sorted = new TreeMap<>();
        for (COSName key : d.keySet()) {
            sorted.put(key.getName(), d.getDictionaryObject(key));
        }
        StringBuilder b = new StringBuilder("{ ");
        boolean first = true;
        for (java.util.Map.Entry<String, COSBase> e : sorted.entrySet()) {
            if (!first) {
                b.append(" ; ");
            }
            first = false;
            b.append(e.getKey()).append('=').append(canonValue(e.getValue()));
        }
        b.append(" }");
        return b.toString();
    }

    /** Canonical rendering of a COS value (the property-dict value space). */
    private static String canonValue(COSBase b) {
        if (b instanceof COSInteger) {
            return "INT:" + ((COSInteger) b).longValue();
        }
        if (b instanceof COSFloat) {
            return "REAL:" + canonFloat(((COSNumber) b).floatValue());
        }
        if (b instanceof COSName) {
            return "NAME:/" + ((COSName) b).getName();
        }
        if (b instanceof COSString) {
            return "STR:" + hex(((COSString) b).getBytes());
        }
        if (b instanceof COSBoolean) {
            return "BOOL:" + (((COSBoolean) b).getValue() ? "true" : "false");
        }
        if (b instanceof COSNull) {
            return "NULL";
        }
        if (b instanceof COSArray) {
            COSArray arr = (COSArray) b;
            StringBuilder s = new StringBuilder("[");
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    s.append(',');
                }
                s.append(canonValue(arr.get(i)));
            }
            return s.append(']').toString();
        }
        if (b instanceof COSDictionary) {
            return canonDict((COSDictionary) b);
        }
        if (b == null) {
            return "NULL";
        }
        return "COS:" + b.getClass().getSimpleName();
    }

    /** Marked-content tree node: depth-indented tag + MCID + child count. */
    private static void emitTree(StringBuilder sb, PDMarkedContent mc, int depth) {
        sb.append("MC depth=").append(depth)
                .append(" tag=").append(mc.getTag())
                .append(" mcid=").append(mc.getMCID());
        int children = 0;
        for (Object item : mc.getContents()) {
            if (item instanceof PDMarkedContent) {
                children++;
            }
        }
        sb.append(" children=").append(children).append('\n');
        for (Object item : mc.getContents()) {
            if (item instanceof PDMarkedContent) {
                emitTree(sb, (PDMarkedContent) item, depth + 1);
            }
        }
    }

    /**
     * Locale-independent canonical float rendering — identical to
     * TokenizeProbe.canonFloat so the two probes share a number grammar.
     */
    static String canonFloat(float f) {
        if (Float.isNaN(f)) {
            return "nan";
        }
        if (Float.isInfinite(f)) {
            return f > 0 ? "inf" : "-inf";
        }
        java.math.BigDecimal bd = new java.math.BigDecimal(Float.toString(f))
                .setScale(5, java.math.RoundingMode.HALF_EVEN)
                .stripTrailingZeros();
        String s = bd.toPlainString();
        if (s.equals("-0")) {
            s = "0";
        }
        return s;
    }

    private static String hex(byte[] data) {
        StringBuilder s = new StringBuilder(data.length * 2);
        for (byte v : data) {
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.toString();
    }
}
