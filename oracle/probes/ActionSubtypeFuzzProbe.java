import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionEmbeddedGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionImportData;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionJavaScript;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionLaunch;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionNamed;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionRemoteGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionResetForm;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionSubmitForm;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionURI;

/**
 * Live oracle probe for the TYPED ACCESSOR surface of the file-/URI-/script-
 * carrying PDAction subtypes in Apache PDFBox 3.0.7 (wave 1541, agent A).
 *
 * <p>Distinct from the three existing action fuzz probes:
 * <ul>
 *   <li>{@code ActionFactoryFuzzProbe} projects the raw-COS SHAPE after
 *       {@code PDActionFactory.createAction} dispatch (getDictionaryObject
 *       semantics), never the accessor methods.</li>
 *   <li>{@code ActionSubtypesFuzzProbe} drives the accessors of Hide / Thread /
 *       Sound only.</li>
 *   <li>{@code LaunchUriActionFuzzProbe} targets a narrower Launch/URI slice.</li>
 * </ul>
 * This probe drives the public typed getters that decode / dispatch a payload
 * (rather than reporting its COS shape) for the remaining subtypes:
 * <ul>
 *   <li>JavaScript: {@code getAction()} — string vs stream-body decode, null
 *       on a name / missing payload.</li>
 *   <li>URI: {@code getURI()} (upstream {@code getString}) +
 *       {@code shouldTrackMousePosition()} ({@code /IsMap} default).</li>
 *   <li>Named: {@code getN()} ({@code getNameAsString} tolerance — name vs
 *       string vs missing).</li>
 *   <li>Launch: {@code getFile()} ({@code PDFileSpecification.createFS}
 *       dispatch + IOException on a bad type), {@code getF/getD/getO/getP},
 *       {@code getWinLaunchParams()} presence, {@code getOpenInNewWindow()}
 *       (OpenMode tri-state).</li>
 *   <li>GoToR: {@code getFile()} (createFS), {@code getD()} shape,
 *       {@code getOpenInNewWindow()}.</li>
 *   <li>GoToE: {@code getFile()} (createFS), {@code getOpenInNewWindow()}.</li>
 *   <li>ImportData: {@code getFile()} (createFS).</li>
 *   <li>SubmitForm: {@code getFile()} (createFS), {@code getFields()} (raw
 *       COSArray), {@code getFlags()}.</li>
 *   <li>ResetForm: {@code getFields()}, {@code getFlags()}.</li>
 * </ul>
 *
 * <p>{@code getFile()} can throw IOException for a wrong-typed {@code /F}
 * (COSName / COSInteger); that case is projected as {@code ERR} (the
 * normalisation lets pypdfbox's {@code OSError} compare equal to upstream's
 * {@code IOException} — both libraries raising on the same input is the
 * contract, not the exception class name).
 *
 * <p>Driven file-based exactly like {@code ActionFactoryFuzzProbe}: the
 * pypdfbox sibling test builds a {@code corpus.pdf} whose catalog carries a
 * {@code /FuzzActions} COSArray, plus a {@code manifest.txt} (one case name per
 * line, in array order). Both libraries read the identical on-disk bytes.
 *
 * <p>Output grammar (one line per case, manifest order):
 *   {@code CASE <name> <projection>}
 * where projection is a per-subtype comma-joined "key=value" frame.
 */
public final class ActionSubtypeFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    /** Stable COS-shape token (mirrors the sibling probes' vocabulary). */
    static String shape(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof COSStream) {
            return "stream";
        }
        if (b instanceof COSDictionary) {
            return "dict";
        }
        if (b instanceof COSArray) {
            return "arr" + ((COSArray) b).size();
        }
        if (b instanceof COSName) {
            return "name";
        }
        if (b instanceof COSString) {
            return "str";
        }
        if (b instanceof COSBoolean) {
            return "bool";
        }
        if (b instanceof COSInteger) {
            return "int";
        }
        if (b instanceof COSFloat) {
            return "real";
        }
        return "other";
    }

    static String str(String s) {
        return s == null ? "null" : s;
    }

    /** {@code PDFileSpecification.createFS} class name, "null", or "ERR". */
    static String fileClass(COSDictionary d, COSName key) {
        try {
            PDFileSpecification fs = PDFileSpecification.createFS(d.getDictionaryObject(key));
            return fs == null ? "null" : fs.getClass().getSimpleName();
        } catch (Exception ex) {
            return "ERR";
        }
    }

    static String jsLine(COSDictionary d) {
        PDActionJavaScript a = new PDActionJavaScript(d);
        return "js=" + str(a.getAction());
    }

    static String uriLine(COSDictionary d) {
        PDActionURI a = new PDActionURI(d);
        return "uri=" + str(a.getURI()) + ",map=" + a.shouldTrackMousePosition();
    }

    static String namedLine(COSDictionary d) {
        PDActionNamed a = new PDActionNamed(d);
        return "n=" + str(a.getN());
    }

    static String launchLine(COSDictionary d) {
        PDActionLaunch a = new PDActionLaunch(d);
        return "file=" + fileClass(d, COSName.F)
                + ",f=" + str(a.getF())
                + ",d=" + str(a.getD())
                + ",o=" + str(a.getO())
                + ",p=" + str(a.getP())
                + ",win=" + (a.getWinLaunchParams() != null)
                + ",nw=" + a.getOpenInNewWindow().name();
    }

    static String gotorLine(COSDictionary d) {
        PDActionRemoteGoTo a = new PDActionRemoteGoTo(d);
        return "file=" + fileClass(d, COSName.F)
                + ",d=" + shape(a.getD())
                + ",nw=" + a.getOpenInNewWindow().name();
    }

    static String gotoeLine(COSDictionary d) {
        PDActionEmbeddedGoTo a = new PDActionEmbeddedGoTo(d);
        return "file=" + fileClass(d, COSName.F)
                + ",nw=" + a.getOpenInNewWindow().name();
    }

    static String importLine(COSDictionary d) {
        PDActionImportData a = new PDActionImportData(d);
        // getFile() does the same createFS dispatch as fileClass(); use it
        // directly so the accessor (not just the static) is exercised.
        try {
            PDFileSpecification fs = a.getFile();
            return "file=" + (fs == null ? "null" : fs.getClass().getSimpleName());
        } catch (Exception ex) {
            return "file=ERR";
        }
    }

    static String submitLine(COSDictionary d) {
        PDActionSubmitForm a = new PDActionSubmitForm(d);
        COSArray fields = a.getFields();
        String fieldsTok = fields == null ? "null" : "arr" + fields.size();
        return "file=" + fileClass(d, COSName.F)
                + ",fields=" + fieldsTok
                + ",flags=" + a.getFlags();
    }

    static String resetLine(COSDictionary d) {
        PDActionResetForm a = new PDActionResetForm(d);
        COSArray fields = a.getFields();
        String fieldsTok = fields == null ? "null" : "arr" + fields.size();
        return "fields=" + fieldsTok + ",flags=" + a.getFlags();
    }

    static String project(String name, COSDictionary d) {
        if (d == null) {
            return "NODICT";
        }
        if (name.startsWith("js_")) {
            return jsLine(d);
        }
        if (name.startsWith("uri_")) {
            return uriLine(d);
        }
        if (name.startsWith("named_")) {
            return namedLine(d);
        }
        if (name.startsWith("launch_")) {
            return launchLine(d);
        }
        if (name.startsWith("gotor_")) {
            return gotorLine(d);
        }
        if (name.startsWith("gotoe_")) {
            return gotoeLine(d);
        }
        if (name.startsWith("import_")) {
            return importLine(d);
        }
        if (name.startsWith("submit_")) {
            return submitLine(d);
        }
        if (name.startsWith("reset_")) {
            return resetLine(d);
        }
        return "UNKNOWN";
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, StandardCharsets.UTF_8);
        java.nio.file.Path dir = java.nio.file.Paths.get(args[0]);
        java.util.List<String> order =
                java.nio.file.Files.readAllLines(
                        dir.resolve("manifest.txt"), StandardCharsets.UTF_8);

        try (PDDocument doc = Loader.loadPDF(dir.resolve("corpus.pdf").toFile())) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSArray arr = (COSArray) catalog.getDictionaryObject(n("FuzzActions"));
            int i = 0;
            for (String name : order) {
                if (name.isEmpty()) {
                    continue;
                }
                COSBase entry = arr.getObject(i++);
                COSDictionary d = entry instanceof COSDictionary ? (COSDictionary) entry : null;
                String proj;
                try {
                    proj = project(name, d);
                } catch (Exception ex) {
                    proj = "ERR:" + ex.getClass().getSimpleName();
                }
                out.println("CASE " + name + " " + proj);
            }
        }
    }
}
