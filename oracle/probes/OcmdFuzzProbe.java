import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentMembershipDictionary;

/**
 * Differential fuzz probe for the optional-content membership dictionary
 * (OCMD), Apache PDFBox 3.0.7 (wave 1530, agent E).
 *
 * Goes deeper than {@link OptionalContentFuzzProbe} on the OCMD-specific
 * surface: the {@code /OCGs} membership list (single OCG dict vs array vs
 * non-dict members vs non-dict/non-array /OCGs), the {@code /P} visibility
 * policy (default {@code AnyOn}; unknown name returned verbatim; non-name
 * value falling back to default), and the {@code /VE} visibility expression
 * (nested {@code [/And ...]} / {@code [/Or ...]} / {@code [/Not ...]} tree,
 * malformed operator, non-array scalar). Also covers the {@code /Type} not
 * {@code /OCMD} case (routes through {@code PDPropertyList.create}, so the
 * wrapper class is what diverges).
 *
 * File-driven: the pypdfbox sibling
 * (tests/pdmodel/graphics/optionalcontent/oracle/test_ocmd_fuzz_wave1530.py)
 * writes a deterministic corpus into a directory plus a {@code manifest.txt}
 * (one case name per line, in order). Each {@code <name>.pdf} carries the
 * fuzzed OCMD as the first page's resource {@code /Properties /MC1}. Both
 * sides read the exact same bytes on disk.
 *
 * Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; cls=&lt;simpleClass|null|ERR&gt; ocgs=&lt;count|n/a|ERR&gt; names=&lt;|-joined|n/a|ERR&gt; policy=&lt;name|n/a|ERR&gt; ve=&lt;op|absent|scalar|n/a|ERR&gt;
 * </pre>
 *
 * "names" is the "|"-joined list of each OCG's getName() (or the wrapper's
 * simple class name when it is not a PDOptionalContentGroup), in /OCGs order.
 * "ve" reports the operator name (first element) of the /VE array when /VE is
 * a COSArray with a leading COSName, "scalar" when /VE is present but not a
 * COSArray, "absent" when /VE is missing, and "empty" for an empty array.
 */
public final class OcmdFuzzProbe {

    static PrintStream out;

    static String ocgEntry(PDPropertyList g) {
        try {
            if (g instanceof PDOptionalContentGroup) {
                String n = ((PDOptionalContentGroup) g).getName();
                return n == null ? "" : n;
            }
            return g.getClass().getSimpleName();
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static String veShape(PDOptionalContentMembershipDictionary ocmd) {
        COSBase ve = ocmd.getCOSObject()
                .getDictionaryObject(COSName.getPDFName("VE"));
        if (ve == null) {
            return "absent";
        }
        if (!(ve instanceof COSArray)) {
            return "scalar";
        }
        COSArray arr = (COSArray) ve;
        if (arr.size() == 0) {
            return "empty";
        }
        COSBase head = arr.getObject(0);
        if (head instanceof COSName) {
            return ((COSName) head).getName();
        }
        return "noop";
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            PDPropertyList prop =
                    res == null ? null
                            : res.getProperties(COSName.getPDFName("MC1"));
            if (prop == null) {
                sb.append("cls=null ocgs=n/a names=n/a policy=n/a ve=n/a");
                out.println(sb.toString());
                return;
            }
            if (!(prop instanceof PDOptionalContentMembershipDictionary)) {
                sb.append("cls=").append(prop.getClass().getSimpleName());
                sb.append(" ocgs=n/a names=n/a policy=n/a ve=n/a");
                out.println(sb.toString());
                return;
            }
            PDOptionalContentMembershipDictionary ocmd =
                    (PDOptionalContentMembershipDictionary) prop;
            String ocgs;
            String names;
            try {
                List<PDPropertyList> list = ocmd.getOCGs();
                ocgs = Integer.toString(list.size());
                List<String> ns = new ArrayList<>();
                for (PDPropertyList g : list) {
                    ns.add(ocgEntry(g));
                }
                names = ns.isEmpty() ? "" : String.join("|", ns);
            } catch (Exception e) {
                ocgs = "ERR:" + e.getClass().getSimpleName();
                names = "ERR:" + e.getClass().getSimpleName();
            }
            String policy;
            try {
                COSName p = ocmd.getVisibilityPolicy();
                policy = p == null ? "null" : p.getName();
            } catch (Exception e) {
                policy = "ERR:" + e.getClass().getSimpleName();
            }
            String ve;
            try {
                ve = veShape(ocmd);
            } catch (Exception e) {
                ve = "ERR:" + e.getClass().getSimpleName();
            }
            sb.append("cls=").append(ocmd.getClass().getSimpleName());
            sb.append(" ocgs=").append(ocgs);
            sb.append(" names=").append(names);
            sb.append(" policy=").append(policy);
            sb.append(" ve=").append(ve);
        } catch (Exception e) {
            sb.append("cls=ERR:").append(e.getClass().getSimpleName());
            sb.append(" ocgs=ERR names=ERR policy=ERR ve=ERR");
        }
        out.println(sb.toString());
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
