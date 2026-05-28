import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.common.PDDestinationOrAction;
import org.apache.pdfbox.pdmodel.interactive.action.PDAction;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDNamedDestination;
import org.apache.pdfbox.pdmodel.interactive.documentnavigation.destination.PDPageDestination;
import org.apache.pdfbox.pdmodel.interactive.viewerpreferences.PDViewerPreferences;

/**
 * Live oracle probe: emit Apache PDFBox's view of the catalog
 * /ViewerPreferences boundary fields plus /OpenAction kind + payload.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ViewerPrefsAndOpenActionProbe input.pdf
 *
 * Emits canonical, line-oriented output (UTF-8, stdout, no framing). Designed
 * to round out the {@link ViewerPrefsProbe} surface (which already covers the
 * six boolean flags and the four enum-string getters) with PDFBox 3.0.7's
 * boundary getters and the catalog open-action dispatch:
 *
 *   viewArea=<enum-string>     getViewArea()  (defaults to "CropBox" when absent)
 *   viewClip=<enum-string>     getViewClip()
 *   printArea=<enum-string>    getPrintArea()
 *   printClip=<enum-string>    getPrintClip()
 *   pickTrayByPDFSize=<bool>   raw /PickTrayByPDFSize boolean (no upstream getter)
 *   numCopies=<int-or-NULL>    raw /NumCopies integer
 *   printPageRange=<csv-or-NULL>  raw /PrintPageRange flat ints
 *   enforce=<csv-or-NULL>      raw /Enforce name array
 *   openAction.kind=<DESTINATION|ACTION|NULL>
 *   openAction.subType=<name-or-NULL>  (destination /D type token or action /S)
 *
 * Why two probes: ViewerPrefsProbe already exists and covers the boolean
 * flags + the four upstream-typed enum getters (NonFullScreenPageMode /
 * ReadingDirection / PrintScaling / Duplex). This probe focuses on the four
 * boundary getters and the open-action dispatch — orthogonal surfaces that
 * extend the parity envelope without duplicating existing lines.
 *
 * The boundary getters all bake the spec default "CropBox" straight into
 * upstream PDViewerPreferences (PDF 32000-1 §12.2 Table 150). The Java probe
 * relies on that for byte-for-byte parity against pypdfbox's matching
 * getters.
 *
 * /PickTrayByPDFSize, /NumCopies, /PrintPageRange, and /Enforce have no
 * upstream getter in PDFBox 3.0.7, so the probe reads them straight off the
 * raw /ViewerPreferences COS dictionary — exactly as the pypdfbox-side
 * reproducer does.
 */
public final class ViewerPrefsAndOpenActionProbe {

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String dumpFlatInts(COSArray arr) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < arr.size(); i++) {
            COSBase el = arr.getObject(i);
            if (i > 0) {
                sb.append(",");
            }
            if (el instanceof COSNumber) {
                sb.append(((COSNumber) el).intValue());
            } else {
                sb.append("?");
            }
        }
        return sb.toString();
    }

    private static String dumpNameArr(COSArray arr) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < arr.size(); i++) {
            COSBase el = arr.getObject(i);
            if (i > 0) {
                sb.append(",");
            }
            if (el instanceof COSName) {
                sb.append(((COSName) el).getName());
            } else {
                sb.append("?");
            }
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();
            PDViewerPreferences vp = cat.getViewerPreferences();

            if (vp != null) {
                out.println("viewArea=" + nz(vp.getViewArea()));
                out.println("viewClip=" + nz(vp.getViewClip()));
                out.println("printArea=" + nz(vp.getPrintArea()));
                out.println("printClip=" + nz(vp.getPrintClip()));

                COSDictionary vpDict = vp.getCOSObject();
                out.println(
                    "pickTrayByPDFSize="
                        + b(vpDict.getBoolean(COSName.getPDFName("PickTrayByPDFSize"), false))
                );

                COSBase numCopies = vpDict.getDictionaryObject(COSName.getPDFName("NumCopies"));
                if (numCopies instanceof COSNumber) {
                    out.println("numCopies=" + ((COSNumber) numCopies).intValue());
                } else {
                    out.println("numCopies=NULL");
                }

                COSBase ppr = vpDict.getDictionaryObject(COSName.getPDFName("PrintPageRange"));
                if (ppr instanceof COSArray) {
                    out.println("printPageRange=" + dumpFlatInts((COSArray) ppr));
                } else {
                    out.println("printPageRange=NULL");
                }

                COSBase enf = vpDict.getDictionaryObject(COSName.getPDFName("Enforce"));
                if (enf instanceof COSArray) {
                    out.println("enforce=" + dumpNameArr((COSArray) enf));
                } else {
                    out.println("enforce=NULL");
                }
            } else {
                // Spec defaults that bleed through PDFBox's getViewArea() etc
                // are baked into the getter — but only when a PDViewerPreferences
                // wrapper exists. With no /ViewerPreferences entry at all, no
                // wrapper exists, so we just emit "NULL" sentinels.
                out.println("viewArea=NULL");
                out.println("viewClip=NULL");
                out.println("printArea=NULL");
                out.println("printClip=NULL");
                out.println("pickTrayByPDFSize=false");
                out.println("numCopies=NULL");
                out.println("printPageRange=NULL");
                out.println("enforce=NULL");
            }

            // /OpenAction: PDFBox dispatches per the disassembly of
            // PDDocumentCatalog.getOpenAction(): a COSDictionary goes to
            // PDActionFactory.createAction (so the subtype is the /S name, or
            // null when /S is absent); a COSArray goes to PDDestination.create
            // (so the subtype is the destination type name at array index 1);
            // anything else yields null.
            PDDestinationOrAction oa = cat.getOpenAction();
            if (oa == null) {
                out.println("openAction.kind=NULL");
                out.println("openAction.subType=NULL");
            } else if (oa instanceof PDAction) {
                out.println("openAction.kind=ACTION");
                out.println("openAction.subType=" + nz(((PDAction) oa).getSubType()));
            } else if (oa instanceof PDPageDestination) {
                out.println("openAction.kind=DESTINATION");
                PDPageDestination pd = (PDPageDestination) oa;
                COSArray arr = pd.getCOSObject();
                if (arr.size() >= 2 && arr.getObject(1) instanceof COSName) {
                    out.println(
                        "openAction.subType=" + ((COSName) arr.getObject(1)).getName()
                    );
                } else {
                    out.println("openAction.subType=NULL");
                }
            } else if (oa instanceof PDNamedDestination) {
                // PDFBox's getOpenAction() doesn't actually take this path
                // (it only dispatches COSArray to PDDestination.create) — keep
                // the arm here so a future upstream change that broadens that
                // dispatch doesn't silently diverge from this probe.
                out.println("openAction.kind=DESTINATION");
                out.println("openAction.subType=Named");
            } else if (oa instanceof PDDestination) {
                out.println("openAction.kind=DESTINATION");
                out.println("openAction.subType=NULL");
            } else {
                out.println("openAction.kind=NULL");
                out.println("openAction.subType=NULL");
            }
        }
    }
}
