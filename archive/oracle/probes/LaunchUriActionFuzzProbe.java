import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionLaunch;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionURI;
import org.apache.pdfbox.pdmodel.interactive.action.PDURIDictionary;
import org.apache.pdfbox.pdmodel.interactive.action.PDWindowsLaunchParams;

/**
 * Differential fuzz probe for the ACCESSOR surface of Launch / URI actions and
 * the document-level URI dictionary, Apache PDFBox 3.0.7 (wave 1530, agent C).
 *
 * Complements ActionFactoryFuzzProbe (which works purely at the raw-COS shape
 * level) and RemoteGotoProbe (which canonicalises GoToR/GoToE/Launch detail
 * from real link annotations). Neither drives the typed accessors of
 * PDActionLaunch (getFile/getF/getD/getO/getP, getWinLaunchParams →
 * PDWindowsLaunchParams getFilename/getDirectory/getOperation/getExecuteParam,
 * getOpenInNewWindow OpenMode tri-state), PDActionURI (getURI text-decode,
 * shouldTrackMousePosition), or PDURIDictionary (getBase) over MALFORMED
 * dictionaries (missing entries, wrong COS types, name-vs-string, non-dict
 * /Win, tri-state /NewWindow true/false/absent).
 *
 * Driven file-based exactly like ActionFactoryFuzzProbe: the pypdfbox sibling
 * (tests/.../oracle/test_launch_uri_action_fuzz_wave1530.py) builds a
 * deterministic /FuzzActions COSArray hung off the catalog, plus a parallel
 * /FuzzUriDicts COSArray of bare URI dictionaries, saves ONE corpus.pdf and a
 * manifest.txt (one case name per line — Launch/URI cases first, then the
 * URI-dict cases, in array order, with a blank-separating "@@URIDICTS" marker).
 * This probe loads the same bytes, walks both arrays, and projects a stable
 * line per case through the typed accessors.
 *
 * Output grammar (one line per case, manifest order):
 *   CASE &lt;name&gt; &lt;projection|ERR:&lt;Exc&gt;&gt;
 *
 * Launch projection (kind=launch):
 *   kind=launch file=&lt;getFile().getFile()|null&gt; f=&lt;getF()|null&gt;
 *   d=&lt;getD()|null&gt; o=&lt;getO()|null&gt; p=&lt;getP()|null&gt;
 *   newwin=&lt;OpenMode&gt; win=&lt;winProj&gt;
 * winProj = "none" when getWinLaunchParams() is null, else
 *   "f=&lt;getFilename()&gt;|d=&lt;getDirectory()&gt;|o=&lt;getOperation()&gt;|p=&lt;getExecuteParam()&gt;".
 *
 * URI projection (kind=uri):
 *   kind=uri uri=&lt;getURI()|null&gt; ismap=&lt;shouldTrackMousePosition()&gt;
 *
 * URI-dictionary projection (kind=uridict):
 *   kind=uridict base=&lt;getBase()|null&gt;
 *
 * Setter round-trip projection (kind=setop): exercises the upstream
 * PDWindowsLaunchParams.setOperation contract (which writes /D, not /O):
 *   kind=setop afterset_o=&lt;getOperation()&gt; raw_O=&lt;O shape&gt; raw_D=&lt;D shape&gt;
 *
 * All free-text fields are escaped (backslash, newline, CR, tab) to keep each
 * record single-line.
 */
public final class LaunchUriActionFuzzProbe {

    static PrintStream out;

    static String esc(String s) {
        if (s == null) {
            return "null";
        }
        return s.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }

    static String shape(COSBase b) {
        if (b == null) {
            return "null";
        }
        if (b instanceof org.apache.pdfbox.cos.COSStream) {
            return "stream";
        }
        if (b instanceof COSDictionary) {
            return "dict";
        }
        if (b instanceof COSArray) {
            return "arr";
        }
        if (b instanceof COSName) {
            return "name";
        }
        if (b instanceof org.apache.pdfbox.cos.COSString) {
            return "str";
        }
        if (b instanceof org.apache.pdfbox.cos.COSInteger) {
            return "int";
        }
        if (b instanceof org.apache.pdfbox.cos.COSFloat) {
            return "real";
        }
        if (b instanceof org.apache.pdfbox.cos.COSBoolean) {
            return "bool";
        }
        return "other";
    }

    static String winProj(PDWindowsLaunchParams win) {
        if (win == null) {
            return "none";
        }
        return "f=" + esc(win.getFilename())
                + "|d=" + esc(win.getDirectory())
                + "|o=" + esc(win.getOperation())
                + "|p=" + esc(win.getExecuteParam());
    }

    static String launchProj(COSDictionary d) throws Exception {
        PDActionLaunch a = new PDActionLaunch(d);
        PDFileSpecification fs = a.getFile();
        String file = fs == null ? null : fs.getFile();
        return "kind=launch file=" + esc(file)
                + " f=" + esc(a.getF())
                + " d=" + esc(a.getD())
                + " o=" + esc(a.getO())
                + " p=" + esc(a.getP())
                + " newwin=" + a.getOpenInNewWindow()
                + " win=" + winProj(a.getWinLaunchParams());
    }

    static String uriProj(COSDictionary d) {
        PDActionURI a = new PDActionURI(d);
        return "kind=uri uri=" + esc(a.getURI())
                + " ismap=" + a.shouldTrackMousePosition();
    }

    static String setOpProj(COSDictionary d) {
        // The /Win sub-dict; mutate it via the typed setter then read back.
        COSBase winBase = d.getDictionaryObject(COSName.WIN);
        COSDictionary winDict = winBase instanceof COSDictionary
                ? (COSDictionary) winBase
                : new COSDictionary();
        PDWindowsLaunchParams win = new PDWindowsLaunchParams(winDict);
        win.setOperation("print");
        return "kind=setop afterset_o=" + esc(win.getOperation())
                + " raw_O=" + shape(winDict.getDictionaryObject(COSName.O))
                + " raw_D=" + shape(winDict.getDictionaryObject(COSName.D));
    }

    static String uriDictProj(COSDictionary d) {
        PDURIDictionary u = new PDURIDictionary(d);
        return "kind=uridict base=" + esc(u.getBase());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");
        java.io.File dir = new java.io.File(args[0]);
        java.io.File pdf = new java.io.File(dir, "corpus.pdf");
        java.io.File manifest = new java.io.File(dir, "manifest.txt");
        String[] raw =
                new String(java.nio.file.Files.readAllBytes(manifest.toPath()),
                                java.nio.charset.StandardCharsets.UTF_8)
                        .split("\n");
        // Split the manifest into the action section and the uri-dict section.
        java.util.List<String> actNames = new java.util.ArrayList<>();
        java.util.List<String> dictNames = new java.util.ArrayList<>();
        boolean inDicts = false;
        for (String r : raw) {
            String t = r.trim();
            if (t.isEmpty()) {
                continue;
            }
            if (t.equals("@@URIDICTS")) {
                inDicts = true;
                continue;
            }
            if (inDicts) {
                dictNames.add(t);
            } else {
                actNames.add(t);
            }
        }
        try (PDDocument doc = Loader.loadPDF(pdf)) {
            COSDictionary catalog = doc.getDocumentCatalog().getCOSObject();
            COSArray acts = (COSArray)
                    catalog.getDictionaryObject(COSName.getPDFName("FuzzActions"));
            COSArray dicts = (COSArray)
                    catalog.getDictionaryObject(COSName.getPDFName("FuzzUriDicts"));
            for (int i = 0; i < actNames.size(); i++) {
                String name = actNames.get(i);
                COSBase entry = acts.getObject(i);
                COSDictionary d = entry instanceof COSDictionary
                        ? (COSDictionary) entry
                        : null;
                runActionCase(name, d);
            }
            for (int i = 0; i < dictNames.size(); i++) {
                String name = dictNames.get(i);
                COSBase entry = dicts.getObject(i);
                COSDictionary d = entry instanceof COSDictionary
                        ? (COSDictionary) entry
                        : null;
                runDictCase(name, d);
            }
        }
    }

    /** Canonical exception token; folds IOException ↔ OSError naming gap. */
    static String excToken(Exception e) {
        String n = e.getClass().getSimpleName();
        if (e instanceof java.io.IOException) {
            return "IOERR";
        }
        return n;
    }

    static void runActionCase(String name, COSDictionary d) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        try {
            if (d == null) {
                sb.append("kind=nondict");
            } else {
                String sub = d.getNameAsString(COSName.S);
                if ("Launch".equals(sub)) {
                    sb.append(launchProj(d));
                } else if ("URI".equals(sub)) {
                    sb.append(uriProj(d));
                } else if ("SetOp".equals(sub)) {
                    sb.append(setOpProj(d));
                } else {
                    sb.append("kind=unknown sub=").append(esc(sub));
                }
            }
        } catch (Exception e) {
            sb.append("ERR:").append(excToken(e));
        }
        out.println(sb.toString());
    }

    static void runDictCase(String name, COSDictionary d) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        try {
            if (d == null) {
                sb.append("kind=nondict");
            } else {
                sb.append(uriDictProj(d));
            }
        } catch (Exception e) {
            sb.append("ERR:").append(excToken(e));
        }
        out.println(sb.toString());
    }
}
