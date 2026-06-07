import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.documentinterchange.markedcontent.PDPropertyList;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentMembershipDictionary;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;

/**
 * Differential fuzz probe for optional-content parsing leniency, Apache PDFBox
 * 3.0.7 (wave 1514, agent C).
 *
 * Complements the well-formed OCG/OCMD oracle suites (round-trip authoring,
 * inverted PDFBox-authored read-back) — none of which exercise the MALFORMED
 * dictionary subset this probe targets:
 *
 * <ul>
 *   <li>{@code /OCProperties} with {@code /OCGs} array missing / empty /
 *       non-array / non-dict members; {@code /D} default config missing /
 *       wrong-type; {@code /D} {@code /ON} {@code /OFF} arrays (membership,
 *       unknown refs, wrong types); {@code /D} {@code /BaseState}
 *       ({@code /ON}/{@code /OFF}/unknown); OCG {@code /Name} missing /
 *       wrong-type; {@code /Intent} name-vs-array-vs-missing.</li>
 *   <li>{@code /OCMD} {@code /OCGs} single-vs-array-vs-missing; {@code /P}
 *       visibility policy ({@code /AnyOn}/{@code /AllOn}/{@code /AnyOff}/
 *       {@code /AllOff}/unknown/missing); {@code /VE} visibility expression
 *       (nested array, malformed).</li>
 * </ul>
 *
 * Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/graphics/optionalcontent/oracle/test_optional_content_fuzz_wave1514.py)
 * writes the deterministic corpus into a directory plus a {@code manifest.txt}
 * (one case name per line, in order). Each {@code ocp_<name>.pdf} carries the
 * fuzzed {@code /OCProperties} on its catalog; each {@code ocmd_<name>.pdf}
 * carries the fuzzed OCMD as the first page's resource
 * {@code /Properties /MC1}. Both sides read the exact same bytes on disk.
 *
 * Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; groups=&lt;count|names|ERR&gt; baseState=&lt;ON|OFF|UNCHANGED|ERR&gt; ocgState=&lt;n/a|states|ERR&gt;
 *   CASE &lt;name&gt; ocmd=&lt;class|null|ERR&gt; ocgs=&lt;count|ERR&gt; policy=&lt;name|ERR&gt; ve=&lt;present|absent|ERR&gt;
 * </pre>
 *
 * "groups" is either an int OCG count or a "|"-joined list of group names
 * (each group's getName(), "" when null) in array order. "ocgState" is the
 * "|"-joined isGroupEnabled(group) flags ("1"/"0") for each group in array
 * order, "n/a" when there are no groups. Any accessor throwing is reported as
 * "ERR:&lt;ExcSimpleName&gt;".
 */
public final class OptionalContentFuzzProbe {

    static PrintStream out;

    static String ocgName(PDOptionalContentGroup g) {
        try {
            String n = g.getName();
            return n == null ? "" : n;
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static void runOcpCase(File dir, String fullName) {
        File pdf = new File(dir, fullName + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(fullName).append(' ');
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDOptionalContentProperties ocp = catalog.getOCProperties();
            if (ocp == null) {
                sb.append("groups=null baseState=null ocgState=null");
                out.println(sb.toString());
                return;
            }
            String groups;
            List<PDOptionalContentGroup> list = null;
            try {
                list = new ArrayList<>();
                for (PDOptionalContentGroup g : ocp.getOptionalContentGroups()) {
                    list.add(g);
                }
                List<String> names = new ArrayList<>();
                for (PDOptionalContentGroup g : list) {
                    names.add(ocgName(g));
                }
                groups = names.isEmpty() ? "0" : String.join("|", names);
            } catch (Exception e) {
                groups = "ERR:" + e.getClass().getSimpleName();
            }
            String baseState;
            try {
                baseState = ocp.getBaseState().name();
            } catch (Exception e) {
                baseState = "ERR:" + e.getClass().getSimpleName();
            }
            String ocgState;
            try {
                if (list == null || list.isEmpty()) {
                    ocgState = "n/a";
                } else {
                    List<String> states = new ArrayList<>();
                    for (PDOptionalContentGroup g : list) {
                        states.add(ocp.isGroupEnabled(g) ? "1" : "0");
                    }
                    ocgState = String.join("|", states);
                }
            } catch (Exception e) {
                ocgState = "ERR:" + e.getClass().getSimpleName();
            }
            sb.append("groups=").append(groups);
            sb.append(" baseState=").append(baseState);
            sb.append(" ocgState=").append(ocgState);
        } catch (Exception e) {
            sb.append("groups=ERR:").append(e.getClass().getSimpleName());
            sb.append(" baseState=ERR ocgState=ERR");
        }
        out.println(sb.toString());
    }

    static void runOcmdCase(File dir, String fullName) {
        File pdf = new File(dir, fullName + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(fullName).append(' ');
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            PDPropertyList prop = res.getProperties(COSName.getPDFName("MC1"));
            if (prop == null) {
                sb.append("ocmd=null ocgs=null policy=null ve=null");
                out.println(sb.toString());
                return;
            }
            if (!(prop instanceof PDOptionalContentMembershipDictionary)) {
                sb.append("ocmd=").append(prop.getClass().getSimpleName());
                sb.append(" ocgs=n/a policy=n/a ve=n/a");
                out.println(sb.toString());
                return;
            }
            PDOptionalContentMembershipDictionary ocmd =
                    (PDOptionalContentMembershipDictionary) prop;
            String ocgs;
            try {
                ocgs = Integer.toString(ocmd.getOCGs().size());
            } catch (Exception e) {
                ocgs = "ERR:" + e.getClass().getSimpleName();
            }
            String policy;
            try {
                COSName p = ocmd.getVisibilityPolicy();
                policy = p == null ? "null" : p.getName();
            } catch (Exception e) {
                policy = "ERR:" + e.getClass().getSimpleName();
            }
            // PDFBox 3.0.7 has no typed /VE accessor on the OCMD wrapper, so
            // read the raw COS entry: "present" only when /VE resolves to a
            // COSArray (pypdfbox's get_visibility_expression() has the same
            // is-a-COSArray contract).
            String ve;
            try {
                org.apache.pdfbox.cos.COSBase veBase =
                        ocmd.getCOSObject()
                                .getDictionaryObject(COSName.getPDFName("VE"));
                ve = (veBase instanceof org.apache.pdfbox.cos.COSArray)
                        ? "present" : "absent";
            } catch (Exception e) {
                ve = "ERR:" + e.getClass().getSimpleName();
            }
            sb.append("ocmd=").append(ocmd.getClass().getSimpleName());
            sb.append(" ocgs=").append(ocgs);
            sb.append(" policy=").append(policy);
            sb.append(" ve=").append(ve);
        } catch (Exception e) {
            sb.append("ocmd=ERR:").append(e.getClass().getSimpleName());
            sb.append(" ocgs=ERR policy=ERR ve=ERR");
        }
        out.println(sb.toString());
    }

    static void runCase(File dir, String name) {
        if (name.startsWith("ocmd_")) {
            runOcmdCase(dir, name);
        } else if (name.startsWith("ocp_")) {
            runOcpCase(dir, name);
        }
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
