import java.io.PrintStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDStream;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDMarkedContent;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;
import org.apache.pdfbox.text.PDFMarkedContentExtractor;

/**
 * Live oracle probe for the marked-content content-stream OPERATOR PROCESSORS
 * (BMC / BDC / EMC / MP / DP) driven end-to-end through the stream engine via
 * PDFMarkedContentExtractor.processPage.
 *
 * Where MarkedContentProbe tokenizes an existing page, this probe SYNTHESIZES a
 * one-page document whose content stream is a named fuzz case, attaches a
 * /Properties resource (so the /Name -> resource-lookup branch of BDC/DP can be
 * exercised), runs the extractor, and projects:
 *
 *   - the resulting marked-content tree (depth / tag / mcid / children), the
 *     observable effect of the marked-content STACK (begin pushes, end pops,
 *     EMC underflow is a no-op, unbalanced BMC leaves residue);
 *   - whether the engine threw, and which exception class, vs. logged + skipped.
 *
 * Usage:  java -cp ... MarkedContentOpFuzzProbe <caseName>
 *
 * Output (stdout, deterministic, sorted/canonical):
 *
 *   err=<none|ClassSimpleName>
 *   roots=<n>
 *   MC depth=<d> tag=<tag> mcid=<n> children=<n>      (one per node, DFS)
 */
public final class MarkedContentOpFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String name = args.length > 0 ? args[0] : "balanced";
        byte[] content = caseBytes(name);

        StringBuilder sb = new StringBuilder();
        String err = "<none>";
        java.util.List<PDMarkedContent> roots = java.util.Collections.emptyList();

        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage();
            doc.addPage(page);

            // Attach a /Properties resource list with one entry "P0" so the
            // named-property-list lookup branch of BDC/DP can resolve.
            PDResources resources = new PDResources();
            COSDictionary mc0 = new COSDictionary();
            mc0.setInt(COSName.MCID, 7);
            mc0.setString(COSName.getPDFName("Lang"), "en-US");
            resources.put(COSName.getPDFName("P0"),
                    PDPropertyList.create(mc0));
            page.setResources(resources);

            // Inject the raw content stream bytes verbatim.
            PDStream stream = new PDStream(doc);
            try (java.io.OutputStream os = stream.createOutputStream()) {
                os.write(content);
            }
            page.setContents(stream);

            PDFMarkedContentExtractor extractor = new PDFMarkedContentExtractor();
            try {
                extractor.processPage(page);
            } catch (Throwable t) {
                err = t.getClass().getSimpleName();
            }
            roots = extractor.getMarkedContents();
            sb.append("err=").append(err).append('\n');
            sb.append("roots=").append(roots.size()).append('\n');
            for (PDMarkedContent mc : roots) {
                emitTree(sb, mc, 0);
            }
        }
        out.print(sb);
    }

    private static void emitTree(StringBuilder sb, PDMarkedContent mc, int depth) {
        String tag = mc.getTag();
        sb.append("MC depth=").append(depth)
                .append(" tag=").append(tag == null ? "<null>" : tag)
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

    /** Named fuzz cases — content-stream bytes. */
    private static byte[] caseBytes(String name) {
        String s;
        switch (name) {
            case "balanced":
                s = "/Span BMC EMC";
                break;
            case "nested":
                s = "/Span BMC /Quote BMC EMC EMC";
                break;
            case "bmc_no_operand":
                // BMC with no tag operand at all.
                s = "BMC EMC";
                break;
            case "bmc_non_name_tag":
                // BMC with a non-name (integer) operand.
                s = "42 BMC EMC";
                break;
            case "bmc_trailing_name":
                // BMC where the last operand (used as tag upstream) is a
                // name but is preceded by junk operands.
                s = "1 (x) /Span BMC EMC";
                break;
            case "bdc_inline_dict":
                s = "/Span << /MCID 3 >> BDC EMC";
                break;
            case "bdc_named_props":
                // BDC with /Name resolving against /Properties (P0 -> MCID 7).
                s = "/Span /P0 BDC EMC";
                break;
            case "bdc_unknown_name":
                // Named property list that is not in /Properties.
                s = "/Span /NoSuch BDC EMC";
                break;
            case "bdc_missing_props":
                // BDC with only one operand (no property operand): underflow.
                s = "/Span BDC EMC";
                break;
            case "bdc_no_operands":
                // BDC with no operands at all.
                s = "BDC EMC";
                break;
            case "bdc_wrong_props_type":
                // Property operand is a string, not name/dict.
                s = "/Span (props) BDC EMC";
                break;
            case "bdc_non_name_tag":
                // First operand is an integer (cast to COSName upstream).
                s = "5 << /MCID 1 >> BDC EMC";
                break;
            case "emc_underflow":
                // EMC with no open sequence.
                s = "EMC";
                break;
            case "emc_double_underflow":
                s = "/Span BMC EMC EMC";
                break;
            case "unbalanced_bmc":
                // BMC never closed: residue on the stack at end of stream.
                s = "/Span BMC";
                break;
            case "unbalanced_two_bmc":
                s = "/A BMC /B BMC EMC";
                break;
            case "mp_point":
                s = "/Span MP";
                break;
            case "mp_no_operand":
                s = "MP";
                break;
            case "dp_inline_dict":
                s = "/Span << /MCID 9 >> DP";
                break;
            case "dp_named_props":
                s = "/Span /P0 DP";
                break;
            case "dp_missing_props":
                s = "/Span DP";
                break;
            case "dp_no_operands":
                s = "DP";
                break;
            case "dp_wrong_props_type":
                s = "/Span (props) DP";
                break;
            default:
                s = "/Span BMC EMC";
                break;
        }
        return s.getBytes(java.nio.charset.StandardCharsets.ISO_8859_1);
    }
}
