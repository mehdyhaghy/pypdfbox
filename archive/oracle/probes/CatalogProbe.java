import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.PageLayout;
import org.apache.pdfbox.pdmodel.PageMode;
import org.apache.pdfbox.pdmodel.documentinterchange.logicalstructure.PDMarkInfo;
import org.apache.pdfbox.pdmodel.interactive.viewerpreferences.PDViewerPreferences;

/**
 * Live oracle probe: emit Apache PDFBox's document-catalog property view of a PDF.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CatalogProbe input.pdf
 *
 * Emits canonical, line-oriented output (UTF-8, stdout, no framing). One line
 * per catalog property the pypdfbox PDDocumentCatalog surface exposes:
 *
 *   version=<name-or-NULL>            (/Version override on the catalog)
 *   pageLayout=<enum-or-NULL>         (PDDocumentCatalog.getPageLayout())
 *   pageMode=<enum-or-NULL>           (PDDocumentCatalog.getPageMode())
 *   lang=<string-or-NULL>             (/Lang)
 *   openAction=<DICTIONARY|ARRAY|NULL> (kind of /OpenAction)
 *   markInfo.present=<bool>
 *   markInfo.marked=<bool>
 *   markInfo.userProperties=<bool>
 *   markInfo.suspects=<bool>
 *   viewerPrefs.present=<bool>
 *   viewerPrefs.hideToolbar=<bool>    (and the other sub-flags)
 *   ...
 *   outputIntents=<count>
 *   hasPageLabels=<bool>
 *   hasAcroForm=<bool>
 *   hasStructTreeRoot=<bool>
 *
 * Boolean values render as the lowercase literals "true" / "false" to match
 * pypdfbox's Python booleans formatted by the test reproducer. A missing
 * name/string field renders as the literal "NULL".
 */
public final class CatalogProbe {

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String b(boolean v) {
        return v ? "true" : "false";
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDDocumentCatalog cat = doc.getDocumentCatalog();

            out.println("version=" + nz(cat.getVersion()));

            PageLayout layout = cat.getPageLayout();
            out.println("pageLayout=" + (layout == null ? "NULL" : layout.stringValue()));

            PageMode mode = cat.getPageMode();
            out.println("pageMode=" + (mode == null ? "NULL" : mode.stringValue()));

            out.println("lang=" + nz(cat.getLanguage()));

            // /OpenAction: report kind (action dictionary vs destination array).
            COSDictionary catDict = cat.getCOSObject();
            COSBase openAction = catDict.getDictionaryObject(COSName.OPEN_ACTION);
            String oaKind;
            if (openAction instanceof COSDictionary) {
                oaKind = "DICTIONARY";
            } else if (openAction instanceof COSArray) {
                oaKind = "ARRAY";
            } else {
                oaKind = "NULL";
            }
            out.println("openAction=" + oaKind);

            // /MarkInfo
            PDMarkInfo markInfo = cat.getMarkInfo();
            out.println("markInfo.present=" + b(markInfo != null));
            if (markInfo != null) {
                out.println("markInfo.marked=" + b(markInfo.isMarked()));
                out.println("markInfo.userProperties=" + b(markInfo.usesUserProperties()));
                out.println("markInfo.suspects=" + b(markInfo.isSuspect()));
            } else {
                out.println("markInfo.marked=false");
                out.println("markInfo.userProperties=false");
                out.println("markInfo.suspects=false");
            }
            // PDF 32000-1 §14.8.1 tagged = /MarkInfo /Marked == true.
            out.println("isTagged=" + b(markInfo != null && markInfo.isMarked()));

            // /ViewerPreferences sub-flags
            PDViewerPreferences vp = cat.getViewerPreferences();
            out.println("viewerPrefs.present=" + b(vp != null));
            if (vp != null) {
                out.println("viewerPrefs.hideToolbar=" + b(vp.hideToolbar()));
                out.println("viewerPrefs.hideMenubar=" + b(vp.hideMenubar()));
                out.println("viewerPrefs.hideWindowUI=" + b(vp.hideWindowUI()));
                out.println("viewerPrefs.fitWindow=" + b(vp.fitWindow()));
                out.println("viewerPrefs.centerWindow=" + b(vp.centerWindow()));
                out.println("viewerPrefs.displayDocTitle=" + b(vp.displayDocTitle()));
                out.println("viewerPrefs.nonFullScreenPageMode=" + nz(vp.getNonFullScreenPageMode()));
                out.println("viewerPrefs.direction=" + nz(vp.getReadingDirection()));
            } else {
                out.println("viewerPrefs.hideToolbar=false");
                out.println("viewerPrefs.hideMenubar=false");
                out.println("viewerPrefs.hideWindowUI=false");
                out.println("viewerPrefs.fitWindow=false");
                out.println("viewerPrefs.centerWindow=false");
                out.println("viewerPrefs.displayDocTitle=false");
                out.println("viewerPrefs.nonFullScreenPageMode=NULL");
                out.println("viewerPrefs.direction=NULL");
            }

            out.println("outputIntents=" + cat.getOutputIntents().size());
            out.println("hasPageLabels=" + b(cat.getPageLabels() != null));
            out.println("hasAcroForm=" + b(cat.getAcroForm() != null));
            out.println("hasStructTreeRoot=" + b(cat.getStructureTreeRoot() != null));
        }
    }
}
