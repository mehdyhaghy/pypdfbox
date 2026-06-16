import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDAnnotationAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDDocumentCatalogAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDFormFieldAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDPageAdditionalActions;

/**
 * Live oracle probe for the ADDITIONAL-ACTIONS (/AA) trigger-getter surface in
 * Apache PDFBox 3.0.7 (wave 1548, agent D).
 *
 * <p>Distinct from the existing /AA probes:
 * <ul>
 *   <li>{@code AdditionalActionsProbe} enumerates triggers PRESENT in a real
 *       document (subtype + JS/URI salient field) — happy-path only.</li>
 *   <li>{@code AaTriggerJsonProbe} round-trips an authored page+catalog /AA via
 *       PDFBox setters, then reads back two well-formed triggers.</li>
 *   <li>{@code ActionAccessorProbe} drives the page /O,/C secondary accessors.</li>
 * </ul>
 * This probe fuzzes the four PD*AdditionalActions getter dispatch paths
 * ({@code getCOSDictionary} + {@code PDActionFactory.createAction}) over a
 * malformed corpus: each trigger key present with a well-typed action dict
 * (known / unknown / missing /S, and the six "extended" subtypes PDFBox's
 * createAction does NOT map), a wrong-typed value (name / int / array), null,
 * or absent. The projection is the RESOLVED PDAction class simple-name (the
 * createAction dispatch result) or "null", and whether the getter raised.
 *
 * <p>Driven file-based exactly like {@code ActionSubtypeFuzzProbe}: the pypdfbox
 * sibling test builds {@code corpus.pdf} whose catalog carries a {@code /FuzzAA}
 * COSArray, one entry per case — a dict with {@code /CLS} (page|annot|catalog|
 * field), {@code /TRIG} (the one-/two-letter trigger key) and {@code /AA} (the
 * additional-actions dictionary to wrap) — plus a {@code manifest.txt} (one case
 * name per line, in array order). Both libraries read the identical bytes.
 *
 * <p>Output grammar (one line per case, manifest order):
 *   {@code CASE <name> <class>|ERR:<exc>}
 */
public final class AdditionalActionsFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    /** Resolve the trigger getter for one (cls, trig) over its /AA dict. */
    static PDAction resolve(String cls, String trig, COSDictionary aa) {
        if ("page".equals(cls)) {
            PDPageAdditionalActions a = new PDPageAdditionalActions(aa);
            switch (trig) {
                case "O": return a.getO();
                case "C": return a.getC();
                default: throw new IllegalArgumentException("trig " + trig);
            }
        }
        if ("annot".equals(cls)) {
            PDAnnotationAdditionalActions a = new PDAnnotationAdditionalActions(aa);
            switch (trig) {
                case "E":  return a.getE();
                case "X":  return a.getX();
                case "D":  return a.getD();
                case "U":  return a.getU();
                case "Fo": return a.getFo();
                case "Bl": return a.getBl();
                case "PO": return a.getPO();
                case "PC": return a.getPC();
                case "PV": return a.getPV();
                case "PI": return a.getPI();
                default: throw new IllegalArgumentException("trig " + trig);
            }
        }
        if ("catalog".equals(cls)) {
            PDDocumentCatalogAdditionalActions a =
                    new PDDocumentCatalogAdditionalActions(aa);
            switch (trig) {
                case "WC": return a.getWC();
                case "WS": return a.getWS();
                case "DS": return a.getDS();
                case "WP": return a.getWP();
                case "DP": return a.getDP();
                default: throw new IllegalArgumentException("trig " + trig);
            }
        }
        if ("field".equals(cls)) {
            PDFormFieldAdditionalActions a = new PDFormFieldAdditionalActions(aa);
            switch (trig) {
                case "K": return a.getK();
                case "F": return a.getF();
                case "V": return a.getV();
                case "C": return a.getC();
                default: throw new IllegalArgumentException("trig " + trig);
            }
        }
        throw new IllegalArgumentException("cls " + cls);
    }

    static String project(COSDictionary entry) {
        String cls = entry.getNameAsString(n("CLS"));
        String trig = entry.getNameAsString(n("TRIG"));
        COSBase aaBase = entry.getDictionaryObject(n("AA"));
        COSDictionary aa =
                aaBase instanceof COSDictionary ? (COSDictionary) aaBase : new COSDictionary();
        PDAction action = resolve(cls, trig, aa);
        return action == null ? "null" : action.getClass().getSimpleName();
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        java.nio.file.Path dir = java.nio.file.Paths.get(args[0]);
        java.util.List<String> order =
                java.nio.file.Files.readAllLines(
                        dir.resolve("manifest.txt"), StandardCharsets.UTF_8);

        try (PDDocument doc = Loader.loadPDF(dir.resolve("corpus.pdf").toFile())) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSArray arr = (COSArray) catalog.getDictionaryObject(n("FuzzAA"));
            int i = 0;
            for (String name : order) {
                if (name.isEmpty()) {
                    continue;
                }
                COSBase entry = arr.getObject(i++);
                String proj;
                try {
                    proj = project((COSDictionary) entry);
                } catch (Exception ex) {
                    proj = "ERR:" + ex.getClass().getSimpleName();
                }
                out.println("CASE " + name + " " + proj);
            }
        }
    }
}
