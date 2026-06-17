import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;

/**
 * Differential fuzz probe for the optional-content MEMBERSHIP / VISIBILITY
 * resolution surface, Apache PDFBox 3.0.7 (wave 1539, agent B).
 *
 * Goes beyond {@link OptionalContentFuzzProbe} (wave 1514, which projects a
 * single {@code isGroupEnabled(group)} flag per group over simple
 * {@code /ON}/{@code /OFF}/{@code /BaseState} states) and beyond
 * {@link OcmdFuzzProbe} (wave 1530, which projects the static OCMD shape:
 * {@code /OCGs} count, {@code /P} policy name, {@code /VE} shape). Neither
 * touches the RESOLUTION-PRECEDENCE corners of
 * {@code PDOptionalContentProperties.isGroupEnabled} that this probe targets:
 *
 * <ul>
 *   <li>an OCG that appears in BOTH {@code /D /ON} and {@code /D /OFF} (which
 *       array wins — array order vs. /ON-first vs. /OFF-first);</li>
 *   <li>the name-based overload {@code isGroupEnabled(String)} resolving over
 *       multiple OCGs that SHARE a {@code /Name} but have split /ON//OFF
 *       membership (the overload short-circuits on the first ENABLED match);
 *       </li>
 *   <li>{@code /BaseState} {@code OFF} with selective {@code /ON} re-enable,
 *       and {@code Unchanged} resolution;</li>
 *   <li>{@code /ON} / {@code /OFF} arrays carrying non-dict members, an OCG
 *       not present in {@code /OCGs}, or duplicate references;</li>
 *   <li>an unknown {@code /BaseState} name (verbatim resolution / fall-back).
 *       </li>
 * </ul>
 *
 * The probe projects, per OCG (in /OCGs array order), both the group-object
 * result and the name-overload result, so a precedence divergence between the
 * two pypdfbox code paths surfaces against Apache PDFBox ground truth.
 *
 * File-driven: the pypdfbox sibling
 * (tests/pdmodel/graphics/optionalcontent/oracle/test_ocmd_fuzz_wave1539.py)
 * writes a deterministic corpus into a directory plus a {@code manifest.txt}
 * (one case name per line, in order). Each {@code <name>.pdf} carries the
 * fuzzed {@code /OCProperties} on its catalog. Both sides read the exact same
 * bytes on disk.
 *
 * Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; base=&lt;ON|OFF|UNCHANGED|ERR&gt; names=&lt;|-joined&gt; byGroup=&lt;|-joined 1/0&gt; byName=&lt;|-joined 1/0&gt;
 * </pre>
 *
 * "names" is the "|"-joined {@code getName()} of each group (in /OCGs order;
 * "" when null). "byGroup" is the "|"-joined {@code isGroupEnabled(group)}
 * flag ("1"/"0") for each group, and "byName" the
 * {@code isGroupEnabled(getName())} flag — both in the same order. Any
 * accessor throwing is reported as {@code ERR:<ExcSimpleName>}; missing
 * /OCProperties yields {@code base=null names= byGroup= byName=}.
 */
public final class OcmdMembershipFuzzProbe {

    static PrintStream out;

    static String safeName(PDOptionalContentGroup g) {
        try {
            String n = g.getName();
            return n == null ? "" : n;
        } catch (Exception e) {
            return "ERR:" + e.getClass().getSimpleName();
        }
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDOptionalContentProperties ocp = catalog.getOCProperties();
            if (ocp == null) {
                sb.append("base=null names= byGroup= byName=");
                out.println(sb.toString());
                return;
            }
            String base;
            try {
                base = ocp.getBaseState().name();
            } catch (Exception e) {
                base = "ERR:" + e.getClass().getSimpleName();
            }
            List<PDOptionalContentGroup> groups = new ArrayList<>();
            List<String> names = new ArrayList<>();
            try {
                for (PDOptionalContentGroup g
                        : ocp.getOptionalContentGroups()) {
                    groups.add(g);
                    names.add(safeName(g));
                }
            } catch (Exception e) {
                sb.append("base=").append(base);
                sb.append(" names=ERR:").append(e.getClass().getSimpleName());
                sb.append(" byGroup=ERR byName=ERR");
                out.println(sb.toString());
                return;
            }
            List<String> byGroup = new ArrayList<>();
            for (PDOptionalContentGroup g : groups) {
                try {
                    byGroup.add(ocp.isGroupEnabled(g) ? "1" : "0");
                } catch (Exception e) {
                    byGroup.add("ERR:" + e.getClass().getSimpleName());
                }
            }
            List<String> byName = new ArrayList<>();
            for (String nm : names) {
                try {
                    byName.add(ocp.isGroupEnabled(nm) ? "1" : "0");
                } catch (Exception e) {
                    byName.add("ERR:" + e.getClass().getSimpleName());
                }
            }
            sb.append("base=").append(base);
            sb.append(" names=").append(String.join("|", names));
            sb.append(" byGroup=").append(String.join("|", byGroup));
            sb.append(" byName=").append(String.join("|", byName));
        } catch (Exception e) {
            sb.append("base=ERR:").append(e.getClass().getSimpleName());
            sb.append(" names=ERR byGroup=ERR byName=ERR");
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
