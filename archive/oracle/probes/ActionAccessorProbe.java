import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionLaunch;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionRemoteGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionURI;
import org.apache.pdfbox.pdmodel.interactive.action.PDPageAdditionalActions;
import org.apache.pdfbox.pdmodel.interactive.action.PDWindowsLaunchParams;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;

/**
 * Live oracle probe: dump the SECONDARY accessor surface of interactive
 * actions that {@code ActionProbe} deliberately omits (it covers the salient
 * target + /Next chain only). This probe drives the per-subtype boolean /
 * sub-dictionary / tri-state accessors so a silent dispatch or accessor
 * regression in those branches is caught at the field level:
 *
 *   - the action's Java CLASS simple-name (the PDActionFactory dispatch result);
 *   - URI    : shouldTrackMousePosition() (the /IsMap boolean);
 *   - GoToR  : getOpenInNewWindow() — the OpenMode tri-state over /NewWindow;
 *   - Launch : getOpenInNewWindow() (OpenMode) + the /Win sub-dict params
 *              (getFilename / getDirectory / getOperation / getExecuteParam);
 *   - /AA placement: page additional-actions /O (open) and /C (close) actions
 *              are dispatched and dumped exactly like a link /A action, proving
 *              the same factory path serves both annotation /A and dict /AA.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ActionAccessorProbe input.pdf
 *
 * Output (UTF-8, LF-terminated): one line per action, stable document order:
 *
 *   <location>\t<class>\t<accessors>
 *
 * Locations, in fixed order:
 *   - "page<p>.link<i>"   : /A on the i-th link annotation of page p.
 *   - "page<p>.aa.O" / ".aa.C" : the page's /AA open / close additional action.
 *
 * <class> is the Java simple class-name the factory produced (e.g.
 * "PDActionURI"); pypdfbox's type(action).__name__ must equal it.
 *
 * <accessors> is a ";"-joined key=value list, per class:
 *   URI    : ismap=<true|false>
 *   GoToR  : newwindow=<OpenMode name>
 *   Launch : newwindow=<OpenMode name>;win.file=<..>;win.dir=<..>;
 *            win.op=<..>;win.param=<..>
 *   other  : "" (no secondary surface exercised here)
 *
 * All free-text fields are escaped (backslash, newline, CR, tab) so each
 * record stays single-line. null sub-values render as the literal "null".
 */
public final class ActionAccessorProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            StringBuilder sb = new StringBuilder();
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
                PDPageAdditionalActions aa = page.getActions();
                if (aa != null) {
                    PDAction o = aa.getO();
                    if (o != null) {
                        emit(sb, "page" + p + ".aa.O", o);
                    }
                    PDAction c = aa.getC();
                    if (c != null) {
                        emit(sb, "page" + p + ".aa.C", c);
                    }
                }
                p++;
            }
            out.print(sb);
        }
    }

    private static void emit(StringBuilder sb, String location, PDAction action)
            throws Exception {
        sb.append(location).append('\t')
          .append(escape(action.getClass().getSimpleName())).append('\t')
          .append(escape(accessors(action))).append('\n');
    }

    private static String accessors(PDAction action) throws Exception {
        if (action instanceof PDActionURI) {
            return "ismap=" + ((PDActionURI) action).shouldTrackMousePosition();
        }
        if (action instanceof PDActionRemoteGoTo) {
            return "newwindow="
                    + ((PDActionRemoteGoTo) action).getOpenInNewWindow().name();
        }
        if (action instanceof PDActionLaunch) {
            PDActionLaunch a = (PDActionLaunch) action;
            StringBuilder s = new StringBuilder();
            s.append("newwindow=").append(a.getOpenInNewWindow().name());
            PDWindowsLaunchParams win = a.getWinLaunchParams();
            s.append(";win.file=").append(winText(win == null ? null : win.getFilename()));
            s.append(";win.dir=").append(winText(win == null ? null : win.getDirectory()));
            s.append(";win.op=").append(winText(win == null ? null : win.getOperation()));
            s.append(";win.param=")
             .append(winText(win == null ? null : win.getExecuteParam()));
            return s.toString();
        }
        return "";
    }

    private static String winText(String s) {
        return s == null ? "null" : s;
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
