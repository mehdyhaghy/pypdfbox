import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
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
 * Differential fuzz probe for optional-content CONFIGURATION metadata, Apache
 * PDFBox 3.0.7 (wave 1559, agent E).
 *
 * Complements the well-formed OcConfigProbe (clean read-back) and the
 * malformed-parse-leniency OptionalContentFuzzProbe (wave 1514, which projected
 * groups / baseState / per-group enabled). Neither exercises the
 * CONFIGURATION-dict edge subset this probe targets:
 *
 * <ul>
 *   <li>{@code /D} default config: missing / non-dict; {@code /Order} nested
 *       arrays, label strings, non-OCG refs; {@code /RBGroups} malformed /
 *       nested; {@code /Locked}; {@code /BaseState} ON/OFF/Unchanged/unknown;
 *       {@code /ListMode}.</li>
 *   <li>{@code /Configs} alternate configurations: present / absent /
 *       non-array; per-entry {@code /Name} listing.</li>
 *   <li>OCG {@code /Usage} {@code /View} {@code /Print} {@code /Export}
 *       sub-dicts present / absent / wrong-type; {@code getRenderState} for
 *       VIEW / PRINT / EXPORT including the Export fallback.</li>
 *   <li>{@code getGroupNames} ordering (incl. addGroup append + name
 *       collisions).</li>
 * </ul>
 *
 * Driven file-based: the pypdfbox sibling
 * (tests/pdmodel/graphics/optionalcontent/oracle/test_oc_config_fuzz_wave1559.py)
 * writes the deterministic corpus into a directory plus a {@code manifest.txt}
 * (one case name per line, in order). Each {@code <name>.pdf} carries the
 * fuzzed {@code /OCProperties} on its catalog. Both sides read identical bytes.
 *
 * Line grammar (one per case, manifest order):
 * <pre>
 *   CASE &lt;name&gt; names=&lt;a|b|...|0|ERR&gt; base=&lt;ON|OFF|UNCHANGED|ERR&gt; order=&lt;tokens|none|ERR&gt; rb=&lt;g|g;...|none|ERR&gt; locked=&lt;n,...|none|ERR&gt; listmode=&lt;v|absent&gt; configs=&lt;n,...|none&gt; render=&lt;name:V/P/E|none|ERR&gt;
 * </pre>
 *
 * "names" is the "|"-joined getGroupNames() array ("0" when empty). "render"
 * picks the FIRST OCG (array order) and emits its getRenderState for VIEW,
 * PRINT, EXPORT joined by "/" ("none" per slot when null), or "none" when
 * there are no groups. "order" flattens /Order to canonical tokens
 * (LABEL:&lt;t&gt;, [ nested ], OCG /Name). "rb" lists each radio-button group
 * (members sorted, "|"-joined; groups ";"-joined). "configs" lists each
 * /Configs entry /Name (sorted). "listmode" reads /D /ListMode raw (no public
 * getter in PDFBox 3.0). Any accessor throwing is reported "ERR:&lt;Exc&gt;".
 */
public final class OcConfigFuzzProbe {

    static PrintStream out;

    private static COSDictionary asDict(COSBase base) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        return (base instanceof COSDictionary) ? (COSDictionary) base : null;
    }

    private static COSArray asArray(COSBase base) {
        if (base instanceof COSObject) {
            base = ((COSObject) base).getObject();
        }
        return (base instanceof COSArray) ? (COSArray) base : null;
    }

    private static String ocgName(COSBase entry) {
        COSDictionary d = asDict(entry);
        if (d == null) {
            return "?";
        }
        String n = d.getString(COSName.NAME);
        return n == null ? "" : n;
    }

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

    private static String renderSlot(PDOptionalContentGroup g, RenderDestination dest) {
        PDOptionalContentGroup.RenderState rs = g.getRenderState(dest);
        return rs == null ? "none" : rs.name();
    }

    static void runCase(File dir, String name) {
        File pdf = new File(dir, name + ".pdf");
        StringBuilder sb = new StringBuilder();
        sb.append("CASE ").append(name).append(' ');
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            PDDocumentCatalog catalog = doc.getDocumentCatalog();
            PDOptionalContentProperties ocp = catalog.getOCProperties();
            if (ocp == null) {
                out.println(sb.append("names=null base=null order=null rb=null "
                        + "locked=null listmode=null configs=null render=null"));
                return;
            }

            String names;
            List<PDOptionalContentGroup> groups = null;
            try {
                String[] arr = ocp.getGroupNames();
                names = (arr.length == 0) ? "0" : String.join("|", arr);
            } catch (Exception e) {
                names = "ERR:" + e.getClass().getSimpleName();
            }
            try {
                groups = new ArrayList<>(ocp.getOptionalContentGroups());
            } catch (Exception e) {
                groups = null;
            }

            String base;
            try {
                base = ocp.getBaseState().name();
            } catch (Exception e) {
                base = "ERR:" + e.getClass().getSimpleName();
            }

            COSDictionary d = ocp.getCOSObject()
                    .getCOSDictionary(COSName.getPDFName("D"));

            String order;
            try {
                COSArray oa = (d == null) ? null
                        : d.getCOSArray(COSName.getPDFName("Order"));
                if (oa == null) {
                    order = "none";
                } else {
                    List<String> t = new ArrayList<>();
                    flattenOrder(oa, t);
                    order = t.isEmpty() ? "empty" : String.join(" ", t);
                }
            } catch (Exception e) {
                order = "ERR:" + e.getClass().getSimpleName();
            }

            String rb;
            try {
                COSArray ra = (d == null) ? null
                        : d.getCOSArray(COSName.getPDFName("RBGroups"));
                if (ra == null) {
                    rb = "none";
                } else {
                    List<String> rbg = new ArrayList<>();
                    for (int i = 0; i < ra.size(); i++) {
                        COSArray grp = asArray(ra.getObject(i));
                        if (grp == null) {
                            continue;
                        }
                        List<String> m = new ArrayList<>();
                        for (int j = 0; j < grp.size(); j++) {
                            m.add(ocgName(grp.getObject(j)));
                        }
                        Collections.sort(m);
                        rbg.add(String.join("|", m));
                    }
                    Collections.sort(rbg);
                    rb = rbg.isEmpty() ? "none" : String.join(";", rbg);
                }
            } catch (Exception e) {
                rb = "ERR:" + e.getClass().getSimpleName();
            }

            String locked;
            try {
                COSArray la = (d == null) ? null
                        : d.getCOSArray(COSName.getPDFName("Locked"));
                if (la == null) {
                    locked = "none";
                } else {
                    List<String> m = new ArrayList<>();
                    for (int i = 0; i < la.size(); i++) {
                        m.add(ocgName(la.getObject(i)));
                    }
                    Collections.sort(m);
                    locked = m.isEmpty() ? "none" : String.join(",", m);
                }
            } catch (Exception e) {
                locked = "ERR:" + e.getClass().getSimpleName();
            }

            String listmode;
            COSName lm = (d == null) ? null
                    : d.getCOSName(COSName.getPDFName("ListMode"));
            listmode = (lm == null) ? "absent" : lm.getName();

            String configs;
            COSArray ca = ocp.getCOSObject()
                    .getCOSArray(COSName.getPDFName("Configs"));
            if (ca == null) {
                configs = "none";
            } else {
                List<String> cn = new ArrayList<>();
                for (int i = 0; i < ca.size(); i++) {
                    COSDictionary cd = asDict(ca.getObject(i));
                    if (cd == null) {
                        continue;
                    }
                    String n = cd.getString(COSName.NAME);
                    if (n != null) {
                        cn.add(n);
                    }
                }
                Collections.sort(cn);
                configs = cn.isEmpty() ? "0" : String.join(",", cn);
            }

            String render;
            try {
                if (groups == null || groups.isEmpty()) {
                    render = "none";
                } else {
                    PDOptionalContentGroup g0 = groups.get(0);
                    String gn = g0.getName();
                    render = (gn == null ? "" : gn) + ":"
                            + renderSlot(g0, RenderDestination.VIEW) + "/"
                            + renderSlot(g0, RenderDestination.PRINT) + "/"
                            + renderSlot(g0, RenderDestination.EXPORT);
                }
            } catch (Exception e) {
                render = "ERR:" + e.getClass().getSimpleName();
            }

            sb.append("names=").append(names);
            sb.append(" base=").append(base);
            sb.append(" order=").append(order);
            sb.append(" rb=").append(rb);
            sb.append(" locked=").append(locked);
            sb.append(" listmode=").append(listmode);
            sb.append(" configs=").append(configs);
            sb.append(" render=").append(render);
            out.println(sb.toString());
        } catch (Exception e) {
            out.println(sb.append("names=ERR:").append(e.getClass().getSimpleName())
                    .append(" base=ERR order=ERR rb=ERR locked=ERR "
                            + "listmode=ERR configs=ERR render=ERR"));
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
