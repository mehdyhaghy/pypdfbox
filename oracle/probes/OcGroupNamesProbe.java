import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;

/**
 * Live oracle probe: emit Apache PDFBox's view of the /OCProperties name-keyed
 * accessor surface — the part of PDOptionalContentProperties that addresses
 * groups by their /Name string rather than by iterating
 * getOptionalContentGroups().
 *
 * Where OcgProbe / OcConfigProbe dump the OCG list and the /D config metadata,
 * this probe exercises the String-overloaded accessors:
 *   getGroupNames()             — the ordered /OCGs name array (insertion
 *                                 order, NOT sorted; "" for non-dict entries),
 *   hasGroup(name)              — name membership (present + absent names),
 *   isGroupEnabled(name)        — the String overload (resolves by /Name
 *                                 through /OCGs, "at least one enabled"),
 *   getGroup(name).getName()    — the name-keyed lookup round-trip.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OcGroupNamesProbe input.pdf
 * Output (UTF-8, one fact per line, canonical order — NAMES preserves the
 * /OCGs array order, the HAS/ENABLED/LOOKUP probe lines follow in that same
 * order, then explicit absent-name probes):
 *   NAMES=<n0>|<n1>|...                 (pipe-joined, /OCGs array order)
 *   HAS name=<n> present=<true|false>   (one per /OCGs name, array order)
 *   ENABLED name=<n> enabled=<true|false>
 *   LOOKUP name=<n> found=<true|false> roundtrip=<getGroup(n).getName()|null>
 *   ABSENT name=<missing> present=false enabled=false found=false
 * When the catalog has no /OCProperties: the single line NO_OCPROPERTIES.
 *
 * A synthetic absent name ("__no_such_layer__") probes the not-found path of
 * every name-keyed accessor in one shot.
 */
public final class OcGroupNamesProbe {

    private static final String ABSENT = "__no_such_layer__";

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDOptionalContentProperties ocp = catalog.getOCProperties();
            if (ocp == null) {
                out.println("NO_OCPROPERTIES");
                return;
            }

            String[] names = ocp.getGroupNames();
            StringBuilder joined = new StringBuilder();
            for (int i = 0; i < names.length; i++) {
                if (i > 0) {
                    joined.append("|");
                }
                joined.append(names[i] == null ? "" : names[i]);
            }
            out.println("NAMES=" + joined);

            for (String name : names) {
                out.println("HAS name=" + (name == null ? "" : name)
                        + " present=" + ocp.hasGroup(name));
            }
            for (String name : names) {
                out.println("ENABLED name=" + (name == null ? "" : name)
                        + " enabled=" + ocp.isGroupEnabled(name));
            }
            for (String name : names) {
                PDOptionalContentGroup g = ocp.getGroup(name);
                String roundtrip = "null";
                if (g != null) {
                    String n = g.getName();
                    roundtrip = n == null ? "" : n;
                }
                out.println("LOOKUP name=" + (name == null ? "" : name)
                        + " found=" + (g != null)
                        + " roundtrip=" + roundtrip);
            }

            out.println("ABSENT name=" + ABSENT
                    + " present=" + ocp.hasGroup(ABSENT)
                    + " enabled=" + ocp.isGroupEnabled(ABSENT)
                    + " found=" + (ocp.getGroup(ABSENT) != null));
        }
    }
}
