import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDDestinationOrAction;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionJavaScript;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionLaunch;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionNamed;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionRemoteGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionResetForm;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionSubmitForm;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionURI;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;

/**
 * Live oracle probe: emit a CANONICAL, deterministic dump of every action
 * found in a PDF, as Apache PDFBox parses it.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ActionProbe input.pdf
 *
 * Output (UTF-8, LF-terminated lines): one line per action, in a stable
 * document order so the listing is independent of object-number layout:
 *
 *   <location>\t<subtype>\t<salient>
 *
 * Locations are emitted in this fixed order:
 *   - "openaction"          : the catalog /OpenAction (only when it is an
 *                             action, not a bare destination array).
 *   - "page<p>.link<i>"     : the /A action on the i-th link annotation of
 *                             page p (0-based; links counted in /Annots order,
 *                             skipping non-link annotations).
 *
 * subtype = the action's /S name ("GoTo", "URI", "GoToR", "Launch", "Named",
 *           ...), or "null" when absent.
 *
 * salient = the field that identifies the action's target, by subtype:
 *   - URI    : "uri=" + the /URI string.
 *   - GoTo   : "dest=" + resolved destination (see resolveDest).
 *   - GoToR  : "file=" + /F text ; "dest=" + resolved destination.
 *   - Launch : "file=" + /F file-spec text ; "dest=" + /D launch command.
 *   - Named  : "name=" + the /N name.
 *   - JavaScript : "js=" + the /JS source (decoded from a string OR a stream).
 *   - SubmitForm : "url=" + /F text ; "flags=" + /Flags ; "fields=" + /Fields count.
 *   - ResetForm  : "flags=" + /Flags ; "fields=" + /Fields count.
 *   - other  : "" (subtype carries all the salient info).
 *
 * A trailing tab-separated column carries the /Next action chain:
 *   "next=" + chain-length + (":" + comma-joined subtypes when length > 0).
 * /Next may be a single action dict or an array (PDF 32000-1 Table 192);
 * PDAction.getNext() normalises both to a List, walked in order here.
 *
 * A destination resolves to "page<index>" for an explicit page target
 * (0-based, via retrievePageNumber), "named:<name>" for a named destination,
 * or "none" when /D is absent / unresolvable. All free-text fields are escaped
 * (backslash, newline, CR, tab) so each record stays single-line.
 */
public final class ActionProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            StringBuilder sb = new StringBuilder();
            PDDocumentCatalog catalog = doc.getDocumentCatalog();

            PDDestinationOrAction open = catalog.getOpenAction();
            if (open instanceof PDAction) {
                emit(sb, "openaction", (PDAction) open);
            }

            int p = 0;
            for (PDPage page : doc.getPages()) {
                int linkIndex = 0;
                for (PDAnnotation annot : page.getAnnotations()) {
                    if (!(annot instanceof PDAnnotationLink)) {
                        continue;
                    }
                    PDAction action = ((PDAnnotationLink) annot).getAction();
                    if (action != null) {
                        emit(sb, "page" + p + ".link" + linkIndex, action);
                    }
                    linkIndex++;
                }
                p++;
            }
            out.print(sb);
        }
    }

    private static void emit(StringBuilder sb, String location, PDAction action)
            throws Exception {
        String subtype = action.getSubType();
        sb.append(location).append('\t')
          .append(subtype == null ? "null" : escape(subtype)).append('\t')
          .append(escape(salient(action))).append('\t')
          .append(escape(nextChain(action))).append('\n');
    }

    /** Canonical "next=<len>[:<sub0>,<sub1>,...]" for the /Next chain. */
    private static String nextChain(PDAction action) {
        java.util.List<PDAction> next = action.getNext();
        if (next == null || next.isEmpty()) {
            return "next=0";
        }
        StringBuilder sub = new StringBuilder();
        for (int i = 0; i < next.size(); i++) {
            if (i > 0) {
                sub.append(',');
            }
            String s = next.get(i).getSubType();
            sub.append(s == null ? "null" : s);
        }
        return "next=" + next.size() + ":" + sub;
    }

    private static String salient(PDAction action) throws Exception {
        if (action instanceof PDActionURI) {
            String uri = ((PDActionURI) action).getURI();
            return "uri=" + (uri == null ? "" : uri);
        }
        if (action instanceof PDActionGoTo) {
            PDDestination dest = ((PDActionGoTo) action).getDestination();
            return "dest=" + resolveDest(dest);
        }
        if (action instanceof PDActionRemoteGoTo) {
            PDActionRemoteGoTo a = (PDActionRemoteGoTo) action;
            return "file=" + nullToEmpty(fileText(a.getFile())) + ";dest="
                    + resolveDest(PDDestination.create(a.getD()));
        }
        if (action instanceof PDActionLaunch) {
            PDActionLaunch a = (PDActionLaunch) action;
            return "file=" + nullToEmpty(fileText(a.getFile())) + ";dest="
                    + nullToEmpty(a.getD());
        }
        if (action instanceof PDActionNamed) {
            String n = ((PDActionNamed) action).getN();
            return "name=" + (n == null ? "" : n);
        }
        if (action instanceof PDActionJavaScript) {
            String js = ((PDActionJavaScript) action).getAction();
            return "js=" + (js == null ? "" : js);
        }
        if (action instanceof PDActionSubmitForm) {
            PDActionSubmitForm a = (PDActionSubmitForm) action;
            return "url=" + nullToEmpty(fileText(a.getFile()))
                    + ";flags=" + a.getFlags()
                    + ";fields=" + arraySize(a.getFields());
        }
        if (action instanceof PDActionResetForm) {
            PDActionResetForm a = (PDActionResetForm) action;
            return "flags=" + a.getFlags()
                    + ";fields=" + arraySize(a.getFields());
        }
        return "";
    }

    /** Element count of a COSArray, or -1 when the array is absent. */
    private static int arraySize(COSArray array) {
        return array == null ? -1 : array.size();
    }

    private static String fileText(PDFileSpecification fs) throws Exception {
        return fs == null ? null : fs.getFile();
    }

    /** Resolve a destination to a canonical string. */
    private static String resolveDest(PDDestination dest) {
        if (dest == null) {
            return "none";
        }
        if (dest instanceof PDNamedDestination) {
            String n = ((PDNamedDestination) dest).getNamedDestination();
            return "named:" + (n == null ? "" : n);
        }
        if (dest instanceof PDPageDestination) {
            int idx = ((PDPageDestination) dest).retrievePageNumber();
            return "page" + idx;
        }
        return "none";
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    private static String escape(String s) {
        if (s == null) {
            return "null";
        }
        return s.replace("\\", "\\\\")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");
    }
}
