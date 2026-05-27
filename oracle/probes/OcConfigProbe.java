import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentGroup;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;
import org.apache.pdfbox.rendering.RenderDestination;

/**
 * Live oracle probe: emit Apache PDFBox's view of a PDF's optional-content
 * default-configuration METADATA (the /OCProperties /D config dict): OCG
 * names + resolved ON/OFF state + per-OCG /Usage View/Print render state,
 * the /Order UI tree (flattened with nesting + label markers), /RBGroups
 * radio-button membership, /Locked groups, and /BaseState.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> OcConfigProbe input.pdf
 * Output (UTF-8, one fact per line, canonical order):
 *   BASESTATE=<ON|OFF|UNCHANGED>
 *   OCG name=<n> enabled=<true|false> view=<ON|OFF|none> print=<ON|OFF|none>
 *      (one per OCG, sorted by name)
 *   ORDER <flattened tokens>   (one ORDER line; tokens space-joined)
 *   RBGROUP <name>|<name>|...  (one per radio-button group, sorted)
 *   LOCKED <name>              (one per locked OCG, sorted)
 * When the catalog has no /OCProperties: the single line NO_OCPROPERTIES.
 *
 * PDFBox 3.0 exposes no public getter for /Order, /RBGroups, /Locked, so the
 * probe reads those straight off the /D COSDictionary (mirroring pypdfbox's
 * PDOptionalContentConfiguration typed accessors). BaseState + isGroupEnabled
 * + getRenderState use the public PDFBox API.
 */
public final class OcConfigProbe {

    private static COSDictionary asDict(COSBase base) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        if (base instanceof COSDictionary) {
            return (COSDictionary) base;
        }
        return null;
    }

    private static COSArray asArray(COSBase base) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        if (base instanceof COSArray) {
            return (COSArray) base;
        }
        return null;
    }

    /** OCG /Name for a referenced dictionary, or "?" when not an OCG dict. */
    private static String ocgName(COSBase entry) {
        COSDictionary d = asDict(entry);
        if (d == null) {
            return "?";
        }
        String n = d.getString(COSName.NAME);
        return n == null ? "" : n;
    }

    /**
     * Flatten an /Order array into canonical tokens: a label string becomes
     * LABEL:&lt;text&gt;, a nested sub-array is wrapped in [ ... ], and an OCG
     * reference becomes its /Name. Mirrors the spec /Order grouping shape
     * (PDF 32000-1 Table 101).
     */
    private static void flattenOrder(COSArray order, List<String> tokens) {
        for (int i = 0; i < order.size(); i++) {
            COSBase raw = order.getObject(i);
            if (raw instanceof COSString) {
                tokens.add("LABEL:" + ((COSString) raw).getString());
                continue;
            }
            COSArray sub = asArray(raw);
            if (sub != null) {
                tokens.add("[");
                flattenOrder(sub, tokens);
                tokens.add("]");
                continue;
            }
            tokens.add(ocgName(raw));
        }
    }

    private static String renderName(PDOptionalContentGroup g, RenderDestination dest) {
        PDOptionalContentGroup.RenderState rs = g.getRenderState(dest);
        return rs == null ? "none" : rs.name();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDOptionalContentProperties ocp = catalog.getOCProperties();
            if (ocp == null) {
                out.println("NO_OCPROPERTIES");
                return;
            }

            out.println("BASESTATE=" + ocp.getBaseState().name());

            List<String> ocgLines = new ArrayList<>();
            for (PDOptionalContentGroup g : ocp.getOptionalContentGroups()) {
                String name = g.getName();
                boolean enabled = ocp.isGroupEnabled(g);
                ocgLines.add("OCG name=" + (name == null ? "" : name)
                        + " enabled=" + enabled
                        + " view=" + renderName(g, RenderDestination.VIEW)
                        + " print=" + renderName(g, RenderDestination.PRINT));
            }
            Collections.sort(ocgLines);
            for (String line : ocgLines) {
                out.println(line);
            }

            COSDictionary d = ocp.getCOSObject().getCOSDictionary(COSName.getPDFName("D"));
            if (d != null) {
                COSArray order = d.getCOSArray(COSName.getPDFName("Order"));
                List<String> orderTokens = new ArrayList<>();
                if (order != null) {
                    flattenOrder(order, orderTokens);
                }
                out.println("ORDER " + String.join(" ", orderTokens));

                List<String> rbLines = new ArrayList<>();
                COSArray rb = d.getCOSArray(COSName.getPDFName("RBGroups"));
                if (rb != null) {
                    for (int i = 0; i < rb.size(); i++) {
                        COSArray group = asArray(rb.getObject(i));
                        if (group == null) {
                            continue;
                        }
                        List<String> members = new ArrayList<>();
                        for (int j = 0; j < group.size(); j++) {
                            members.add(ocgName(group.getObject(j)));
                        }
                        Collections.sort(members);
                        rbLines.add("RBGROUP " + String.join("|", members));
                    }
                }
                Collections.sort(rbLines);
                for (String line : rbLines) {
                    out.println(line);
                }

                List<String> lockLines = new ArrayList<>();
                COSArray locked = d.getCOSArray(COSName.getPDFName("Locked"));
                if (locked != null) {
                    for (int i = 0; i < locked.size(); i++) {
                        lockLines.add("LOCKED " + ocgName(locked.getObject(i)));
                    }
                }
                Collections.sort(lockLines);
                for (String line : lockLines) {
                    out.println(line);
                }
            }
        }
    }
}
