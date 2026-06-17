import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSBoolean;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.filespecification.PDFileSpecification;
import org.apache.pdfbox.pdmodel.interactive.action.OpenMode;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionEmbeddedGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionLaunch;
import org.apache.pdfbox.pdmodel.interactive.action.PDActionRemoteGoTo;
import org.apache.pdfbox.pdmodel.interactive.action.PDTargetDirectory;
import org.apache.pdfbox.pdmodel.interactive.action.PDWindowsLaunchParams;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationLink;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;

/**
 * Live oracle probe: emit a CANONICAL, deterministic dump of every
 * remote / embedded GoTo and Launch action found in a PDF, as Apache
 * PDFBox parses it. Complements ActionProbe (which dumps the basic
 * action surface + /Next chain); this probe focuses on the type-specific
 * detail of GoToR / GoToE / Launch.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> RemoteGotoProbe input.pdf
 *
 * Output (UTF-8, LF-terminated): one line per link-annotation action, in a
 * stable document order independent of object-number layout:
 *
 *   page<p>.link<i>\t<subtype>\t<detail>
 *
 * subtype = the action's /S name ("GoToR", "GoToE", "Launch", ...) or
 *           "null" when absent.
 *
 * detail by subtype (semicolon-joined key=value):
 *   - GoToR : "file=" + /F file-spec text (getFile().getFile())
 *           + ";d=" + canonical /D COS form (see canonD)
 *           + ";newwindow=" + OpenMode (getOpenInNewWindow()).
 *   - GoToE : "file=" + /F file-spec text
 *           + ";d=" + resolved /D destination (named:<name> / page<idx> / none)
 *           + ";newwindow=" + OpenMode
 *           + ";target=" + canonical /T target-directory chain (see canonTarget).
 *   - Launch: "file=" + /F file-spec text
 *           + ";newwindow=" + OpenMode
 *           + ";win=" + canonical /Win params (see canonWin).
 *   - other : "" .
 *
 * canonD canonicalises the raw /D COSBase of a GoToR (PDFBox keeps it raw
 * via getD() since the remote document is not opened): "int:<n>" for an
 * integer page index, "str:<s>" for a named-destination byte string,
 * "arr[<n>]:<elem0>,<elem1>,..." for an explicit destination array (each
 * element canonicalised: i<n> / n<name> / s<str> / ?), "name:<n>" for a
 * bare name, or "none" when absent.
 *
 * canonTarget walks the /T -> /T chain, emitting each hop as
 * "R<rel>|N<filename>|P<page-or-named>|A<annot>" joined by ">". A page in
 * /P is "p<int>" (getPageNumber, -1 when absent) and a named destination is
 * "d<name>" (getNamedDestination()). Annotation index is getAnnotationIndex
 * (-1 absent) or the /NM name via getAnnotationName.
 *
 * canonWin emits the /Win sub-dict as
 * "f=<F>|d=<D>|o=<O>|p=<P>" (filename / directory / operation / param).
 *
 * All free-text fields are escaped (backslash, newline, CR, tab) so each
 * record stays single-line.
 */
public final class RemoteGotoProbe {
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
          .append(escape(detail(action))).append('\n');
    }

    private static String detail(PDAction action) throws Exception {
        if (action instanceof PDActionRemoteGoTo) {
            PDActionRemoteGoTo a = (PDActionRemoteGoTo) action;
            return "file=" + nullToEmpty(fileText(a.getFile()))
                    + ";d=" + canonD(a.getD())
                    + ";newwindow=" + a.getOpenInNewWindow();
        }
        if (action instanceof PDActionEmbeddedGoTo) {
            PDActionEmbeddedGoTo a = (PDActionEmbeddedGoTo) action;
            return "file=" + nullToEmpty(fileText(a.getFile()))
                    + ";d=" + resolveDest(a.getDestination())
                    + ";newwindow=" + a.getOpenInNewWindow()
                    + ";target=" + canonTarget(a.getTargetDirectory());
        }
        if (action instanceof PDActionLaunch) {
            PDActionLaunch a = (PDActionLaunch) action;
            return "file=" + nullToEmpty(fileText(a.getFile()))
                    + ";newwindow=" + a.getOpenInNewWindow()
                    + ";win=" + canonWin(a.getWinLaunchParams());
        }
        return "";
    }

    /** Canonical form of a raw /D COSBase (GoToR keeps it unresolved). */
    private static String canonD(COSBase d) {
        if (d == null) {
            return "none";
        }
        if (d instanceof COSInteger) {
            return "int:" + ((COSInteger) d).intValue();
        }
        if (d instanceof COSString) {
            return "str:" + ((COSString) d).getString();
        }
        if (d instanceof COSName) {
            return "name:" + ((COSName) d).getName();
        }
        if (d instanceof COSArray) {
            COSArray arr = (COSArray) d;
            StringBuilder sb = new StringBuilder("arr[").append(arr.size()).append("]:");
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(canonElem(arr.getObject(i)));
            }
            return sb.toString();
        }
        return "?";
    }

    private static String canonElem(COSBase e) {
        if (e == null) {
            return "null";
        }
        if (e instanceof COSInteger) {
            return "i" + ((COSInteger) e).intValue();
        }
        if (e instanceof COSName) {
            return "n" + ((COSName) e).getName();
        }
        if (e instanceof COSString) {
            return "s" + ((COSString) e).getString();
        }
        return "?";
    }

    /** Resolve a destination to a canonical string (mirrors ActionProbe). */
    private static String resolveDest(PDDestination dest) {
        if (dest == null) {
            return "none";
        }
        if (dest instanceof PDNamedDestination) {
            String n = ((PDNamedDestination) dest).getNamedDestination();
            return "named:" + (n == null ? "" : n);
        }
        // Explicit page destination for an embedded GoTo carries an integer
        // page index in the array (not a page object), which PDPageDestination
        // exposes via getPageNumber() -- avoid retrievePageNumber() which would
        // try to resolve a page object in the (different) embedded document.
        if (dest instanceof
                org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination) {
            int idx = ((org.apache.pdfbox.pdmodel.interactive.documentnavigation
                    .destination.PDPageDestination) dest).getPageNumber();
            return "page" + idx;
        }
        return "none";
    }

    /** Canonical /T target-directory chain: hop>hop>... */
    private static String canonTarget(PDTargetDirectory target) {
        if (target == null) {
            return "none";
        }
        StringBuilder sb = new StringBuilder();
        int hop = 0;
        // Identity-cycle guard via a bounded walk.
        while (target != null && hop < 64) {
            if (hop > 0) {
                sb.append('>');
            }
            COSName rel = target.getRelationship();
            sb.append('R').append(rel == null ? "" : rel.getName());
            sb.append("|N").append(nullToEmpty(target.getFilename()));
            // /P -- page index (int) or named destination (string).
            PDNamedDestination nd = target.getNamedDestination();
            int pageNum = target.getPageNumber();
            if (nd != null) {
                String n = nd.getNamedDestination();
                sb.append("|Pd").append(n == null ? "" : n);
            } else {
                sb.append("|Pp").append(pageNum);
            }
            // /A -- annotation index (int) or /NM name (string).
            String annotName = target.getAnnotationName();
            int annotIdx = target.getAnnotationIndex();
            if (annotName != null) {
                sb.append("|Aa").append(annotName);
            } else {
                sb.append("|Ai").append(annotIdx);
            }
            target = target.getTargetDirectory();
            hop++;
        }
        return sb.toString();
    }

    /** Canonical /Win launch params: f=<F>|d=<D>|o=<O>|p=<P>. */
    private static String canonWin(PDWindowsLaunchParams win) {
        if (win == null) {
            return "none";
        }
        return "f=" + nullToEmpty(win.getFilename())
                + "|d=" + nullToEmpty(win.getDirectory())
                + "|o=" + nullToEmpty(win.getOperation())
                + "|p=" + nullToEmpty(win.getExecuteParam());
    }

    private static String fileText(PDFileSpecification fs) throws Exception {
        return fs == null ? null : fs.getFile();
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
